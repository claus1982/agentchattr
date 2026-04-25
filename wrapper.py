"""Agent wrapper - runs the real interactive CLI with auto-trigger on @mentions.

Usage:
    python wrapper.py claude
    python wrapper.py codex
    python wrapper.py gemini
    python wrapper.py kimi
    python wrapper.py qwen

Cross-platform:
  - Windows: injects keystrokes via Win32 WriteConsoleInput (wrapper_windows.py)
  - Mac/Linux: injects keystrokes via tmux send-keys (wrapper_unix.py)

How it works:
  1. Starts the agent CLI in an interactive terminal.
  2. Watches the queue file in the background for @mentions from the chat room.
  3. When triggered, injects "use mcp to read #channel - you're mentioned, take appropriate action and respond".
  4. The agent picks up the prompt as if the user typed it.
"""

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SERVER_NAME = "agentchattr"


# ---------------------------------------------------------------------------
# Per-instance provider config
# ---------------------------------------------------------------------------

def _write_json_mcp_settings(config_file: Path, url: str, transport: str = "http",
                              *, token: str = "", http_key: str = "httpUrl") -> Path:
    """Write/merge a settings-style JSON file with nested mcpServers config.

    Preserves existing servers in the file — only updates the agentchattr entry.

    Gemini CLI 0.32+ expects:
      - "httpUrl" key (not "url") for streamable-http transport
      - "url" key for SSE transport
      - "trust": true to skip per-call approval prompts

    `http_key` controls which JSON key names the HTTP transport URL. Defaults
    to "httpUrl" (Gemini/Qwen). Providers like CodeBuddy that follow the
    standard MCP shape should set `mcp_http_key = "url"` in their config.
    Only affects settings_file / env injector modes (not the Claude flag
    writer or Kilo env_content writer).
    """
    config_file.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if config_file.exists():
        try:
            existing = json.loads(config_file.read_text("utf-8"))
        except Exception:
            pass
    servers = existing.get("mcpServers", {})
    # Default: Gemini-style "httpUrl" for HTTP. Override with http_key="url"
    # for providers that follow the standard MCP shape (e.g. CodeBuddy).
    if transport in ("http", "streamable-http"):
        entry: dict = {"type": "http", http_key: url, "trust": True}
    else:
        entry = {"type": transport, "url": url, "trust": True}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    servers[SERVER_NAME] = entry
    existing["mcpServers"] = servers

    # Enable folder trust so ~/.gemini/trustedFolders.json is respected
    security = existing.get("security", {})
    folder_trust = security.get("folderTrust", {})
    folder_trust["enabled"] = True
    security["folderTrust"] = folder_trust
    existing["security"] = security

    config_file.write_text(json.dumps(existing, indent=2) + "\n", "utf-8")
    return config_file


def _read_project_mcp_servers(project_dir: Path) -> dict:
    """Read existing MCP servers from the project's .mcp.json."""
    mcp_file = project_dir / ".mcp.json"
    if mcp_file.exists():
        try:
            data = json.loads(mcp_file.read_text("utf-8"))
            servers = data.get("mcpServers", {})
            # Remove agentchattr — we'll add our own authenticated version
            servers.pop(SERVER_NAME, None)
            return servers
        except Exception:
            pass
    return {}


def _write_claude_mcp_config(
    config_file: Path,
    url: str,
    *,
    token: str = "",
    project_servers: dict | None = None,
) -> Path:
    """Write a Claude Code --mcp-config file with bearer auth.

    Includes all project MCP servers (unity-mcp etc.) so --strict-mcp-config
    can be used without losing other servers."""
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Start with other project servers (e.g. unity-mcp)
    servers = dict(project_servers or {})

    # Add agentchattr with bearer token for direct server auth
    entry: dict = {"type": "http", "url": url}
    if token:
        entry["headers"] = {"Authorization": f"Bearer {token}"}
    servers[SERVER_NAME] = entry

    payload = {"mcpServers": servers}
    config_file.write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    return config_file


# ---------------------------------------------------------------------------
# Built-in provider defaults (applied when agent config has no mcp_inject)
# ---------------------------------------------------------------------------

_BUILTIN_DEFAULTS: dict[str, dict] = {
    "claude": {
        "mcp_inject": "flag",
        "mcp_flag": "--mcp-config",
        "mcp_transport": "http",
        "mcp_merge_project": True,  # include unity-mcp etc.
    },
    "gemini": {
        "mcp_inject": "env",
        "mcp_env_var": "GEMINI_CLI_SYSTEM_SETTINGS_PATH",
        "mcp_transport": "http",  # streamable-http; SSE has blocking issues in Gemini 0.32.x
        "mcp_merge_project": True,
    },
    "codex": {
        "mcp_inject": "proxy_flag",
        "mcp_proxy_flag_template": '-c mcp_servers.{server}.url="{url}"',
        # mcp_merge_project disabled — Codex reads .mcp.json natively,
        # and duplicate detection is name-based only (e.g. unityMCP vs unity-mcp)
    },
    "kimi": {
        "mcp_inject": "flag",
        "mcp_flag": "--mcp-config-file",
        "mcp_transport": "http",
        "mcp_merge_project": True,
    },
    "kilo": {
        "mcp_inject": "env_content",
        "mcp_env_var": "KILO_CONFIG_CONTENT",
        "mcp_transport": "http",
    },
}

_VALID_INJECT_MODES = {"settings_file", "env", "flag", "proxy_flag", "env_content"}


def _resolve_mcp_inject(agent: str, agent_cfg: dict) -> dict:
    """Resolve MCP injection config: explicit agent_cfg > built-in defaults > None."""
    inject_mode = agent_cfg.get("mcp_inject")
    if inject_mode:
        return dict(agent_cfg)
    if agent in _BUILTIN_DEFAULTS:
        merged = dict(_BUILTIN_DEFAULTS[agent])
        merged.update({k: v for k, v in agent_cfg.items() if k.startswith("mcp_")})
        return merged
    return {}


def _get_server_url(mcp_cfg: dict, transport: str) -> str:
    """Build the MCP server URL for the given transport."""
    if transport == "sse":
        port = mcp_cfg.get("sse_port", 8201)
        return f"http://127.0.0.1:{port}/sse"
    port = mcp_cfg.get("http_port", 8200)
    return f"http://127.0.0.1:{port}/mcp"


def _apply_mcp_inject(
    inject_cfg: dict,
    instance_name: str,
    data_dir: Path,
    proxy_url: str | None,
    *,
    token: str = "",
    mcp_cfg: dict | None = None,
    project_dir: Path | None = None,
) -> tuple[list[str], dict[str, str], Path | None]:
    """Apply MCP config injection based on the resolved inject config.

    Returns (extra_launch_args, inject_env, settings_path_or_None).
    settings_path is stored so re-registration can rewrite it.
    """
    mode = inject_cfg.get("mcp_inject")
    if not mode:
        return [], {}, None

    launch_args: list[str] = []
    inject_env: dict[str, str] = {}
    settings_path: Path | None = None
    config_dir = data_dir / "provider-config"
    transport = inject_cfg.get("mcp_transport", "http")
    server_url = _get_server_url(mcp_cfg or {}, transport)

    http_key = inject_cfg.get("mcp_http_key", "httpUrl")

    if mode == "settings_file":
        # Write a settings JSON file at a user-specified path (e.g. .qwen/settings.json,
        # or ~/.codebuddy/.mcp.json for user-scope configs).
        raw_path = inject_cfg.get("mcp_settings_path", "")
        if not raw_path:
            raise ValueError(f"mcp_inject = 'settings_file' requires mcp_settings_path")
        # Expand ~ to user home (e.g. ~/.codebuddy/.mcp.json), then resolve
        # relative paths against project_dir/CWD as before.
        target = Path(raw_path).expanduser()
        if not target.is_absolute():
            base = Path(project_dir) if project_dir else Path.cwd()
            target = base / target
        settings_path = _write_json_mcp_settings(target, server_url,
                                                  transport=transport, token=token,
                                                  http_key=http_key)
        # Optionally set an env var pointing to the settings file
        env_var = inject_cfg.get("mcp_env_var")
        if env_var:
            inject_env[env_var] = str(settings_path)

    elif mode == "env":
        # Write a settings file in provider-config dir, expose via env var
        env_var = inject_cfg.get("mcp_env_var")
        if not env_var:
            raise ValueError(f"mcp_inject = 'env' requires mcp_env_var")
        settings_path = _write_json_mcp_settings(
            config_dir / f"{instance_name}-settings.json",
            server_url, transport=transport, token=token, http_key=http_key,
        )
        # Merge project .mcp.json servers into the settings file
        merge_project = inject_cfg.get("mcp_merge_project", False)
        if merge_project and project_dir and settings_path:
            project_servers = _read_project_mcp_servers(project_dir)
            if project_servers:
                try:
                    data = json.loads(settings_path.read_text("utf-8"))
                    servers = data.get("mcpServers", {})
                    for name, cfg in project_servers.items():
                        if name not in servers:
                            # Normalize url key for providers that expect "httpUrl"
                            # (Gemini/Qwen). For standard-MCP providers with
                            # http_key="url", leave existing "url" entries as-is.
                            entry = dict(cfg)
                            srv_type = entry.get("type", "http")
                            if srv_type in ("http", "streamable-http") and http_key != "url":
                                if "url" in entry and http_key not in entry:
                                    entry[http_key] = entry.pop("url")
                            entry.setdefault("trust", True)
                            servers[name] = entry
                    data["mcpServers"] = servers
                    settings_path.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
                except Exception:
                    pass
        inject_env[env_var] = str(settings_path)

    elif mode == "flag":
        # Write a config file, pass it as a CLI flag
        flag = inject_cfg.get("mcp_flag", "--mcp-config")
        merge_project = inject_cfg.get("mcp_merge_project", False)
        project_servers = _read_project_mcp_servers(project_dir) if (merge_project and project_dir) else {}
        settings_path = _write_claude_mcp_config(
            config_dir / f"{instance_name}-mcp.json",
            server_url, token=token, project_servers=project_servers,
        )
        launch_args = [flag, str(settings_path)]

    elif mode == "env_content":
        # Build JSON config content and set it as an env var directly (no file written).
        # Used by Kilo CLI which reads KILO_CONFIG_CONTENT at startup.
        env_var = inject_cfg.get("mcp_env_var")
        if not env_var:
            raise ValueError("mcp_inject = 'env_content' requires mcp_env_var")
        entry: dict = {"type": "remote", "url": server_url, "enabled": True}
        if token:
            entry["headers"] = {"Authorization": f"Bearer {token}"}
        payload = {"mcp": {SERVER_NAME: entry}}
        inject_env[env_var] = json.dumps(payload)

    elif mode == "proxy_flag":
        # Pass the proxy URL as CLI flags (e.g. codex -c ...)
        template = inject_cfg.get("mcp_proxy_flag_template",
                                  '-c mcp_servers.{server}.url="{url}"')
        expanded = template.format(server=SERVER_NAME, url=proxy_url or "")
        launch_args = expanded.split()

    return launch_args, inject_env, settings_path


def _ensure_gemini_folder_trusted(project_dir: Path) -> None:
    """Add project_dir as TRUST_FOLDER in ~/.gemini/trustedFolders.json.

    Gemini CLI blocks ALL MCPs (including system-settings ones) for untrusted
    folders. A more-specific TRUST_FOLDER entry overrides any parent-level
    DO_NOT_TRUST rule, so we always write the exact cwd we're launching in.
    Respects GEMINI_CLI_TRUSTED_FOLDERS_PATH env override if set.
    """
    trusted_path_env = os.environ.get("GEMINI_CLI_TRUSTED_FOLDERS_PATH", "")
    if trusted_path_env:
        trusted_file = Path(trusted_path_env)
    else:
        trusted_file = Path.home() / ".gemini" / "trustedFolders.json"

    try:
        data: dict = {}
        if trusted_file.exists():
            try:
                data = json.loads(trusted_file.read_text("utf-8"))
            except Exception:
                data = {}

        folder_key = str(project_dir)
        if data.get(folder_key) == "TRUST_FOLDER":
            return  # already trusted — nothing to do

        data[folder_key] = "TRUST_FOLDER"
        trusted_file.parent.mkdir(parents=True, exist_ok=True)
        trusted_file.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
        print(f"  Trusted folder for Gemini MCPs: {folder_key}")
    except Exception as exc:
        print(f"  Warning: could not update Gemini trusted folders: {exc}")


def _build_provider_launch(
    agent: str,
    agent_cfg: dict,
    instance_name: str,
    data_dir: Path,
    proxy_url: str | None,
    extra_args: list[str],
    env: dict[str, str],
    *,
    token: str = "",
    mcp_cfg: dict | None = None,
    project_dir: Path | None = None,
) -> tuple[list[str], dict[str, str], dict[str, str], Path | None]:
    """Return provider-specific launch args/env/inject_env/settings_path.

    inject_env: env vars that must propagate INTO the agent process.  On
    Mac/Linux these are prefixed onto the tmux command via ``env VAR=val``
    because subprocess.run(env=...) only affects the tmux client binary.
    On Windows they are simply merged into the Popen env dict.
    """
    inject_cfg = _resolve_mcp_inject(agent, agent_cfg)
    mcp_args, inject_env, settings_path = _apply_mcp_inject(
        inject_cfg, instance_name, data_dir, proxy_url,
        token=token, mcp_cfg=mcp_cfg, project_dir=project_dir,
    )

    launch_args = [*mcp_args, *extra_args]

    # Codex wrappers are expected to run autonomously inside agentchattr.
    # If the interactive CLI stops for MCP approvals, the planner cannot
    # recover because the agent never reaches its session tools. Default to
    # non-interactive approvals and workspace-write sandbox unless the caller
    # already supplied an explicit policy.
    if agent == "codex":
        has_approval_override = any(
            arg in ("-a", "--ask-for-approval") or str(arg).startswith("--ask-for-approval=")
            for arg in launch_args
        )
        if not has_approval_override:
            approval_policy = str(agent_cfg.get("ask_for_approval", "never")).strip()
            if approval_policy:
                launch_args = ["-a", approval_policy, *launch_args]

        has_sandbox_override = any(
            arg in ("-s", "--sandbox", "--full-auto", "--dangerously-bypass-approvals-and-sandbox")
            or str(arg).startswith("--sandbox=")
            for arg in launch_args
        )
        if not has_sandbox_override:
            sandbox_mode = str(agent_cfg.get("sandbox", "workspace-write")).strip()
            if sandbox_mode:
                launch_args = ["-s", sandbox_mode, *launch_args]

    launch_env = dict(env)

    return launch_args, launch_env, inject_env, settings_path


def _register_instance(
    server_port: int,
    base: str,
    label: str | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    import urllib.request

    payload = {"base": base, "label": label}
    if provider:
        payload["provider"] = provider
    if model:
        payload["model"] = model

    reg_body = json.dumps(payload).encode()
    reg_req = urllib.request.Request(
        f"http://127.0.0.1:{server_port}/api/register",
        method="POST",
        data=reg_body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(reg_req, timeout=5) as reg_resp:
        return json.loads(reg_resp.read())


def _auth_headers(token: str, *, include_json: bool = False) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if include_json:
        headers["Content-Type"] = "application/json"
    return headers


def _extract_cli_model(extra_args: list[str]) -> str:
    for idx, arg in enumerate(extra_args):
        if arg == "--model" and idx + 1 < len(extra_args):
            return str(extra_args[idx + 1]).strip()
        if isinstance(arg, str) and arg.startswith("--model="):
            return arg.split("=", 1)[1].strip()
        if arg == "-m" and idx + 1 < len(extra_args):
            return str(extra_args[idx + 1]).strip()
    return ""


def _dismiss_codex_update(version_file: Path | None = None) -> str | None:
    """Best-effort: persist the current Codex release as dismissed.

    Codex stores update-check state in ~/.codex/version.json. When
    latest_version is newer than the installed CLI and dismissed_version is
    unset, the interactive launcher blocks on an update prompt. Wrappers need
    Codex to land directly in the composer, so mark the current latest version
    as dismissed before launching.
    """
    target = version_file or (Path.home() / ".codex" / "version.json")
    if not target.exists():
        return None

    try:
        data = json.loads(target.read_text("utf-8-sig"))
    except Exception:
        return None

    latest_version = str(data.get("latest_version", "")).strip()
    if not latest_version:
        return None

    dismissed_version = data.get("dismissed_version")
    if isinstance(dismissed_version, str) and dismissed_version.strip() == latest_version:
        return None

    data["dismissed_version"] = latest_version
    try:
        target.write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    except Exception:
        return None

    return latest_version


def _resolve_enter_backend(agent: str, agent_cfg: dict) -> str:
    configured = str(agent_cfg.get("enter_backend", "")).strip()
    if configured:
        return configured
    if sys.platform == "win32" and agent == "codex":
        return "wm_setfocus"
    return "console_input"


# ---------------------------------------------------------------------------
# Queue watcher
# ---------------------------------------------------------------------------

def _notify_recovery(data_dir: Path, agent_name: str):
    """Write a flag file that the server picks up and broadcasts as a system message."""
    try:
        flag = data_dir / f"{agent_name}_recovered"
        flag.write_text(agent_name, "utf-8")
    except Exception:
        pass


_IDENTITY_HINT = (
    " (If this is a multi-instance session, reclaim your previous identity from "
    "your context window, NOT from the chat history before responding. If you "
    "didn't have one, tell the user to give you a name by clicking your status "
    "pill at the top.)"
)


def _fetch_role(server_port: int, agent_name: str) -> str:
    """Fetch this agent's role from the server status endpoint."""
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{server_port}/api/roles")
        with urllib.request.urlopen(req, timeout=3) as resp:
            roles = json.loads(resp.read())
        return roles.get(agent_name, "")
    except Exception:
        return ""


def _fetch_active_rules(server_port: int, token: str = "") -> dict | None:
    """Fetch active rules from the server."""
    try:
        import urllib.request
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(f"http://127.0.0.1:{server_port}/api/rules/active", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _report_rule_sync(server_port: int, agent_name: str, epoch: int, token: str = ""):
    """Report that this agent has seen rules at the given epoch."""
    try:
        import urllib.request
        body = json.dumps({"epoch": epoch}).encode()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            f"http://127.0.0.1:{server_port}/api/rules/agent_sync/{agent_name}",
            method="POST",
            data=body,
            headers=headers,
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception:
        pass


def _ack_queue_prefix(queue_file: Path, consumed_text: str):
    """Remove only the queue prefix that was actually processed.

    This preserves entries appended while the current batch was being handled.
    If the file changed unexpectedly, leave it untouched so work is retried
    rather than dropped.
    """
    if not consumed_text:
        return

    try:
        current_text = queue_file.read_text("utf-8") if queue_file.exists() else ""
    except Exception:
        return

    if current_text.startswith(consumed_text):
        queue_file.write_text(current_text[len(consumed_text):], "utf-8")


def _process_queue_once(get_identity_fn, inject_fn, *, is_multi_instance: bool = False,
                        trigger_flag=None, server_port: int = 8300, agent_name: str = "",
                        get_token_fn=None, refresh_interval: int = 10) -> bool:
    """Process at most one queue batch and keep it pending until injection works."""
    _, queue_file = get_identity_fn()
    if not queue_file.exists() or queue_file.stat().st_size <= 0:
        return False

    queued_text = queue_file.read_text("utf-8")
    if not queued_text:
        return False

    lines = queued_text.splitlines()
    has_trigger = False
    channel = "general"
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        has_trigger = True
        if isinstance(data, dict) and "channel" in data:
            channel = data["channel"]

    if not has_trigger:
        _ack_queue_prefix(queue_file, queued_text)
        return False

    # Signal activity BEFORE injecting — covers the thinking phase
    if trigger_flag is not None:
        trigger_flag[0] = True
    time.sleep(0.5)

    job_id = None
    custom_prompt = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict) and "job_id" in data:
                job_id = data["job_id"]
            if isinstance(data, dict):
                raw_prompt = data.get("prompt", "")
                if isinstance(raw_prompt, str) and raw_prompt.strip():
                    custom_prompt = raw_prompt.strip()
        except json.JSONDecodeError:
            pass

    if custom_prompt:
        prompt = custom_prompt
    elif job_id:
        prompt = f"read job_id={job_id} via mcp. act if needed and reply concisely"
    else:
        prompt = f"read #{channel} via mcp. act if needed and reply concisely"

    # Use current identity (may have changed via rename)
    current_name, _ = get_identity_fn()
    # Append role if set — check both current name and base name
    role = _fetch_role(server_port, current_name)
    if not role and current_name != agent_name:
        role = _fetch_role(server_port, agent_name)
    if role:
        prompt += f"\n\nROLE: {role}"

    # Smart rules injection: first trigger, epoch change, or periodic refresh
    _token = get_token_fn() if get_token_fn else ""
    rules_data = _fetch_active_rules(server_port, _token)
    if trigger_flag is not None:
        trigger_count = trigger_flag[1] = trigger_flag[1] + 1 if len(trigger_flag) > 1 else 1
    else:
        trigger_count = 1
    if rules_data:
        # Use server-side refresh_interval (live from settings UI)
        ri = rules_data.get("refresh_interval", refresh_interval)
        last_rules_epoch = trigger_flag[2] if trigger_flag is not None and len(trigger_flag) > 2 else 0
        need_inject = (
            last_rules_epoch == 0
            or rules_data["epoch"] != last_rules_epoch
            or (ri > 0 and trigger_count % ri == 0)
        )
        if need_inject:
            if rules_data["rules"]:
                rules_text = "; ".join(rules_data["rules"])
                prompt += f"\n\nRULES:\n{rules_text}"
            if trigger_flag is not None:
                while len(trigger_flag) < 3:
                    trigger_flag.append(0)
                trigger_flag[2] = rules_data["epoch"]
            _report_rule_sync(server_port, current_name, rules_data["epoch"], _token)

    if is_multi_instance and (trigger_flag is None or len(trigger_flag) < 4 or trigger_flag[3]):
        prompt += _IDENTITY_HINT
        if trigger_flag is not None:
            while len(trigger_flag) < 4:
                trigger_flag.append(True)
            trigger_flag[3] = False

    try:
        # Flatten to single line — multi-line text triggers paste
        # detection in CLIs (Claude Code shows "[Pasted text +N]")
        # which can break injection of long session prompts.
        inject_fn(prompt.replace("\n", " "))
    except Exception as exc:
        print(f"  Queue inject failed for @{current_name}: {exc}")
        return False

    _ack_queue_prefix(queue_file, queued_text)
    return True


def _queue_watcher(get_identity_fn, inject_fn, *, is_multi_instance: bool = False, trigger_flag=None,
                   server_port: int = 8300, agent_name: str = "", get_token_fn=None,
                   refresh_interval: int = 10):
    """Poll queue file and inject an MCP read task when triggered."""
    watcher_state = trigger_flag if trigger_flag is not None else [False]
    while len(watcher_state) < 4:
        watcher_state.append(0 if len(watcher_state) < 3 else True)

    while True:
        try:
            _process_queue_once(
                get_identity_fn,
                inject_fn,
                is_multi_instance=is_multi_instance,
                trigger_flag=watcher_state,
                server_port=server_port,
                agent_name=agent_name,
                get_token_fn=get_token_fn,
                refresh_interval=refresh_interval,
            )
        except Exception:
            pass

        time.sleep(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    import urllib.error
    import urllib.request

    from config_loader import apply_cli_overrides, load_config

    # Apply AGENTCHATTR_* overrides (from CLI flags or env) BEFORE loading
    # config so the wrapper connects to the same data_dir/ports as a server
    # launched with matching flags.
    apply_cli_overrides()
    config = load_config(ROOT)

    agent_names = list(config.get("agents", {}).keys())

    parser = argparse.ArgumentParser(description="Agent wrapper with chat auto-trigger")
    parser.add_argument("agent", choices=agent_names, help=f"Agent to wrap ({', '.join(agent_names)})")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart on exit")
    parser.add_argument("--label", type=str, default=None, help="Custom display label")
    # Per-project isolation flags (must match the server's flags so wrappers
    # launched separately connect to the right instance). Values are consumed
    # by apply_cli_overrides() above; listing here so --help shows them.
    parser.add_argument("--data-dir",      default=None, help="Override server.data_dir (path)")
    parser.add_argument("--port",          default=None, help="Override server.port (int)")
    parser.add_argument("--mcp-http-port", default=None, help="Override mcp.http_port (int)")
    parser.add_argument("--mcp-sse-port",  default=None, help="Override mcp.sse_port (int)")
    parser.add_argument("--upload-dir",    default=None, help="Override images.upload_dir (path)")
    args, extra = parser.parse_known_args()

    agent = args.agent
    agent_cfg = config.get("agents", {}).get(agent, {})
    provider_name = str(agent_cfg.get("label", agent.capitalize())).strip()
    model_name = _extract_cli_model(extra)
    cwd = agent_cfg.get("cwd", ".")
    command = agent_cfg.get("command", agent)
    data_dir = ROOT / config.get("server", {}).get("data_dir", "./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    server_port = config.get("server", {}).get("port", 8300)
    mcp_cfg = config.get("mcp", {})

    try:
        registration = _register_instance(
            server_port,
            agent,
            args.label,
            provider=provider_name,
            model=model_name or None,
        )
    except Exception as exc:
        print(f"  Registration failed ({exc}).")
        print("  Wrapper cannot continue without a registered identity.")
        sys.exit(1)

    assigned_name = registration["name"]
    assigned_token = registration["token"]
    print(f"  Registered as: {assigned_name} (slot {registration.get('slot', '?')})")

    proxy = None
    proxy_url = None

    # Resolve MCP injection mode to determine if a proxy is needed.
    # Direct-connect modes (settings_file, env, flag) don't need a proxy.
    # proxy_flag mode needs a proxy. No mcp_inject = proxy fallback.
    inject_cfg = _resolve_mcp_inject(agent, agent_cfg)
    inject_mode = inject_cfg.get("mcp_inject", "")
    if inject_mode and inject_mode not in _VALID_INJECT_MODES:
        print(f"  Error: unknown mcp_inject mode '{inject_mode}' for agent '{agent}'.")
        print(f"  Valid modes: {', '.join(sorted(_VALID_INJECT_MODES))}")
        sys.exit(1)
    needs_proxy = inject_mode in ("proxy_flag", "") or not inject_mode

    if needs_proxy:
        from mcp_proxy import McpIdentityProxy

        transport = inject_cfg.get("mcp_transport", "http")
        if transport == "sse":
            upstream_base = f"http://127.0.0.1:{mcp_cfg.get('sse_port', 8201)}"
            proxy_path = "/sse"
        else:
            upstream_base = f"http://127.0.0.1:{mcp_cfg.get('http_port', 8200)}"
            proxy_path = "/mcp"

        proxy = McpIdentityProxy(
            upstream_base=upstream_base,
            upstream_path=proxy_path,
            agent_name=assigned_name,
            instance_token=assigned_token,
        )
        if proxy.start() is False:
            print("  Failed to start MCP proxy.")
            sys.exit(1)
        proxy_url = f"{proxy.url}{proxy_path}"

    _identity_lock = threading.Lock()
    _identity = {
        "name": assigned_name,
        "queue": data_dir / f"{assigned_name}_queue.jsonl",
        "token": assigned_token,
    }

    def get_identity():
        with _identity_lock:
            return _identity["name"], _identity["queue"]

    def get_token():
        with _identity_lock:
            return _identity["token"]

    # Rewrite MCP config when token/name changes (e.g. after 409 re-register).
    # Most CLIs won't re-read mid-session, but the file is correct for next restart.
    def _rewrite_mcp_config(instance_name: str, new_token: str):
        if not inject_mode or needs_proxy:
            return  # proxy-based agents don't have config files to rewrite
        try:
            _apply_mcp_inject(
                inject_cfg, instance_name, data_dir, proxy_url,
                token=new_token, mcp_cfg=mcp_cfg,
                project_dir=(ROOT / cwd).resolve(),
            )
        except Exception:
            pass

    def set_runtime_identity(new_name: str | None = None, new_token: str | None = None):
        with _identity_lock:
            old_name = _identity["name"]
            old_token = _identity["token"]
            changed = False
            if new_name and new_name != old_name:
                _identity["name"] = new_name
                _identity["queue"] = data_dir / f"{new_name}_queue.jsonl"
                changed = True
            if new_token and new_token != old_token:
                _identity["token"] = new_token
                changed = True
            current_name = _identity["name"]
            current_token = _identity["token"]

        if changed and proxy is not None:
            proxy.agent_name = current_name
            proxy.token = current_token
        if changed:
            if new_name and new_name != old_name:
                print(f"  Identity updated: {old_name} -> {new_name}")
            if new_token and new_token != old_token:
                print(f"  Session refreshed for @{current_name}")
            _rewrite_mcp_config(current_name, current_token)

        return changed

    queue_file = _identity["queue"]
    if queue_file.exists():
        queue_file.write_text("", "utf-8")

    strip_vars = {"CLAUDECODE"} | set(agent_cfg.get("strip_env", []))
    env = {k: v for k, v in os.environ.items() if k not in strip_vars}

    resolved = shutil.which(command)
    if not resolved:
        print(f"  Error: '{command}' not found on PATH.")
        print("  Install it first, then try again.")
        sys.exit(1)
    command = resolved

    if agent == "codex":
        dismissed_version = _dismiss_codex_update()
        if dismissed_version:
            print(f"  Dismissed Codex update prompt for {dismissed_version}.")

    project_dir = (ROOT / cwd).resolve()

    # Gemini: ensure the project directory is trusted so MCPs are allowed.
    # Gemini blocks ALL MCPs for untrusted folders — even system-settings ones.
    if agent == "gemini" or inject_cfg.get("mcp_inject") == "env":
        _ensure_gemini_folder_trusted(project_dir)

    launch_args, env, inject_env, mcp_settings_path = _build_provider_launch(
        agent=agent,
        agent_cfg=agent_cfg,
        instance_name=assigned_name,
        data_dir=data_dir,
        proxy_url=proxy_url,
        extra_args=extra,
        env=env,
        token=assigned_token,
        mcp_cfg=mcp_cfg,
        project_dir=project_dir,
    )

    print(f"  === {assigned_name.capitalize()} Chat Wrapper ===")
    if not needs_proxy:
        print(f"  MCP: direct connect ({inject_mode}) with bearer auth")
        if mcp_settings_path:
            print(f"  Config: {mcp_settings_path}")
    elif proxy_url:
        print(f"  Local MCP proxy: {proxy_url}")
    print(f"  @{assigned_name} mentions auto-inject MCP reads")
    print(f"  Starting {command} in {cwd}...\n")

    def _heartbeat():
        while True:
            current_name, _ = get_identity()
            current_token = get_token()
            url = f"http://127.0.0.1:{server_port}/api/heartbeat/{current_name}"
            try:
                req = urllib.request.Request(
                    url,
                    method="POST",
                    data=b"",
                    headers=_auth_headers(current_token),
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp_data = json.loads(resp.read())
                server_name = resp_data.get("name", current_name)
                if server_name != current_name:
                    set_runtime_identity(server_name)
            except urllib.error.HTTPError as exc:
                if exc.code == 409:
                    try:
                        replacement = _register_instance(
                            server_port,
                            agent,
                            args.label,
                            provider=provider_name,
                            model=model_name or None,
                        )
                        set_runtime_identity(replacement["name"], replacement["token"])
                        _notify_recovery(data_dir, replacement["name"])
                    except Exception:
                        pass
                time.sleep(5)
                continue
            except Exception:
                time.sleep(5)
                continue

            time.sleep(5)

    threading.Thread(target=_heartbeat, daemon=True).start()

    _watcher_inject_fn = None
    _watcher_thread = None
    _is_multi_instance = registration.get("slot", 1) > 1
    _trigger_flag = [False]  # shared: queue watcher sets True, activity checker reads
    _refresh_interval = 10  # default; overridden per-trigger by server settings

    def start_watcher(inject_fn):
        nonlocal _watcher_inject_fn, _watcher_thread
        _watcher_inject_fn = inject_fn
        _watcher_thread = threading.Thread(
            target=_queue_watcher,
            args=(get_identity, inject_fn),
            kwargs={"is_multi_instance": _is_multi_instance, "trigger_flag": _trigger_flag,
                    "server_port": server_port, "agent_name": assigned_name,
                    "get_token_fn": get_token, "refresh_interval": _refresh_interval},
            daemon=True,
        )
        _watcher_thread.start()

    def _watcher_monitor():
        nonlocal _watcher_thread
        while True:
            time.sleep(5)
            if _watcher_thread and not _watcher_thread.is_alive() and _watcher_inject_fn:
                _watcher_thread = threading.Thread(
                    target=_queue_watcher,
                    args=(get_identity, _watcher_inject_fn),
                    kwargs={"is_multi_instance": _is_multi_instance, "trigger_flag": _trigger_flag,
                            "server_port": server_port, "agent_name": assigned_name,
                            "get_token_fn": get_token, "refresh_interval": _refresh_interval},
                    daemon=True,
                )
                _watcher_thread.start()
                current_name, _ = get_identity()
                _notify_recovery(data_dir, current_name)

    threading.Thread(target=_watcher_monitor, daemon=True).start()

    _activity_checker = None

    def _set_activity_checker(checker):
        nonlocal _activity_checker
        _activity_checker = checker

    def _activity_monitor():
        last_active = None
        last_report_time = 0
        REPORT_INTERVAL = 3  # re-send state every 3s while active (keeps server lease fresh)
        while True:
            time.sleep(1)
            if not _activity_checker:
                continue
            try:
                active = _activity_checker()
                now = time.time()
                # Send on state change, periodically while active (refresh lease),
                # or periodically while idle (keep presence alive)
                IDLE_REPORT_INTERVAL = 8  # keep-alive while idle
                should_send = (
                    active != last_active
                    or (active and now - last_report_time >= REPORT_INTERVAL)
                    or (not active and now - last_report_time >= IDLE_REPORT_INTERVAL)
                )
                if should_send:
                    current_name, _ = get_identity()
                    current_token = get_token()
                    url = f"http://127.0.0.1:{server_port}/api/heartbeat/{current_name}"
                    body = json.dumps({"active": active}).encode()
                    req = urllib.request.Request(
                        url,
                        method="POST",
                        data=body,
                        headers=_auth_headers(current_token, include_json=True),
                    )
                    resp = urllib.request.urlopen(req, timeout=5)
                    resp_code = resp.getcode()
                    last_active = active
                    last_report_time = now
            except Exception:
                pass

    threading.Thread(target=_activity_monitor, daemon=True).start()

    _agent_pid = [None]

    if sys.platform == "win32":
        from wrapper_windows import get_activity_checker, run_agent

        _set_activity_checker(get_activity_checker(_agent_pid, agent_name=assigned_name, trigger_flag=_trigger_flag))
    else:
        from wrapper_unix import get_activity_checker, run_agent

        unix_session_name = f"agentchattr-{assigned_name}"
        _set_activity_checker(get_activity_checker(unix_session_name, trigger_flag=_trigger_flag))

    run_kwargs = dict(
        command=command,
        extra_args=launch_args,
        cwd=cwd,
        env=env,
        queue_file=queue_file,
        agent=agent,
        no_restart=args.no_restart,
        start_watcher=start_watcher,
        strip_env=list(strip_vars),
        pid_holder=_agent_pid,
        inject_env=inject_env,
        inject_delay=agent_cfg.get("inject_delay", 0.3),
        auto_allow_agentchattr_mcp=bool(
            agent_cfg.get("auto_allow_agentchattr_mcp", agent == "codex")
        ),
    )
    # Windows-only injection tuning (no-op on other platforms).
    if sys.platform == "win32":
        run_kwargs["enter_backend"] = _resolve_enter_backend(agent, agent_cfg)
    if sys.platform != "win32":
        run_kwargs["session_name"] = unix_session_name

    try:
        run_agent(**run_kwargs)
    finally:
        try:
            current_name, _ = get_identity()
            current_token = get_token()
            dereg_req = urllib.request.Request(
                f"http://127.0.0.1:{server_port}/api/deregister/{current_name}",
                method="POST",
                data=b"",
                headers=_auth_headers(current_token),
            )
            urllib.request.urlopen(dereg_req, timeout=5)
            print(f"  Deregistered {current_name}")
        except Exception:
            pass

        if proxy is not None:
            proxy.stop()

    print("  Wrapper stopped.")


if __name__ == "__main__":
    main()
