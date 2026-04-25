"""One-shot GitHub Copilot CLI wrapper for agentchattr.

Uses `copilot -p` for each @mention trigger instead of driving the
interactive terminal UI. This keeps the existing registration, MCP auth,
queue-file routing, and server API flow, but avoids fragile Windows focus
and Enter-injection behavior.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).parent
DEFAULT_TIMEOUT_SECONDS = 180
MAX_CONTEXT_LINE_CHARS = 700
MAX_CONTEXT_TOTAL_CHARS = 3500
MAX_RULES_CHARS = 600
MAX_PROMPT_CHARS = 6000


def _clip_text(text: str, limit: int) -> str:
    text = (text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 16:
        return text[:limit]
    return f"{text[:limit - 15].rstrip()} ...(truncated)"


def _trim_context_lines(lines: list[str], limit: int) -> list[str]:
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        line_len = len(line) + (1 if kept else 0)
        if kept and total + line_len > limit:
            break
        kept.append(line)
        total += line_len
    return list(reversed(kept))


def _build_role_task_instruction(role: str, *, in_job: bool) -> str:
    role_key = (role or "").strip().lower()
    if role_key == "planner":
        location = "job thread" if in_job else "channel"
        return (
            f"You were mentioned in this {location} as the coordinator. The latest direct assignment is your task, "
            "even when it is only coordination or monitoring work. In a single reply you must: "
            "1) state the current status or blocker, "
            "2) assign the next concrete slice to @implementer, "
            "3) ask @reviewer for one focused critique, "
            "4) ask @challenger for one focused critique, "
            "5) state when the next update will happen. "
            "Use direct instructions and explicit @mentions. Never answer with readiness, missing-task, or blocked-for-repo-task language."
        )
    if role_key == "reviewer":
        return (
            "You were mentioned as reviewer. Treat any visible slice, plan, status, or coordination brief as actionable. "
            "Reply with one focused critique of the current slice or one concrete missing validation step. "
            "Do not answer with readiness or missing-task language."
        )
    if role_key == "challenger":
        return (
            "You were mentioned as challenger. Treat any visible slice, plan, status, or coordination brief as actionable. "
            "Reply with the sharpest concrete risk, missing edge, or premium-feel gap in the current slice. "
            "Do not answer with readiness or missing-task language."
        )
    return (
        "You were mentioned. Respond to the latest relevant message that mentions you. "
        "If it assigns coordination, monitoring, planning, review, critique, or delegation work, perform that duty directly in chat with concrete next steps and @mentions. "
        "Do not reply with readiness or ask the user to restate the task."
    )


def _is_generic_mcp_read_prompt(prompt: str) -> bool:
    normalized = " ".join((prompt or "").strip().lower().split())
    return (
        normalized.startswith("use mcp to read ")
        and "you're mentioned" in normalized
        and "take appropriate action and respond" in normalized
    )


def _derive_task_instruction(role: str, *, custom_prompt: str, trigger_text: str, in_job: bool) -> str:
    prompt = (custom_prompt or "").strip()
    if prompt and not _is_generic_mcp_read_prompt(prompt):
        return prompt

    trigger_text = (trigger_text or "").strip()
    if trigger_text:
        return (
            "Respond to this exact chat assignment. Do not answer with readiness or ask for the task again.\n"
            f"{trigger_text}"
        )

    return _build_role_task_instruction(role, in_job=in_job)


def _run_prompt_command(command_args: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    if sys.platform == "win32" and Path(command_args[0]).suffix.lower() in {".cmd", ".bat"}:
        comspec = os.environ.get("ComSpec", "cmd.exe")
        command_args = [comspec, "/d", "/c", *command_args]

    return subprocess.run(
        command_args,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def main():
    from config_loader import apply_cli_overrides, load_config
    from wrapper import (
        _IDENTITY_HINT,
        _auth_headers,
        _extract_cli_model,
        _fetch_active_rules,
        _fetch_role,
        _register_instance,
        _report_rule_sync,
    )

    apply_cli_overrides()
    config = load_config(ROOT)

    if "copilot" not in config.get("agents", {}):
        print("  Error: [agents.copilot] is missing from config.toml")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="One-shot GitHub Copilot CLI wrapper")
    parser.add_argument("agent", choices=["copilot"], help="Agent to wrap (copilot)")
    parser.add_argument("--label", type=str, default=None, help="Custom display label")
    parser.add_argument("--data-dir", default=None, help="Override server.data_dir (path)")
    parser.add_argument("--port", default=None, help="Override server.port (int)")
    parser.add_argument("--mcp-http-port", default=None, help="Override mcp.http_port (int)")
    parser.add_argument("--mcp-sse-port", default=None, help="Override mcp.sse_port (int)")
    parser.add_argument("--upload-dir", default=None, help="Override images.upload_dir (path)")
    args, extra = parser.parse_known_args()

    agent = args.agent
    agent_cfg = config["agents"][agent]
    server_port = config.get("server", {}).get("port", 8300)
    mcp_cfg = config.get("mcp", {})
    data_dir = ROOT / config.get("server", {}).get("data_dir", "./data")
    data_dir.mkdir(parents=True, exist_ok=True)

    command = agent_cfg.get("command", agent)
    resolved_command = shutil.which(command)
    if not resolved_command:
        print(f"  Error: '{command}' not found on PATH.")
        sys.exit(1)

    cwd = agent_cfg.get("cwd", ".")
    project_dir = (ROOT / cwd).resolve()
    strip_vars = {"CLAUDECODE"} | set(agent_cfg.get("strip_env", []))
    base_env = {k: v for k, v in os.environ.items() if k not in strip_vars}
    timeout_seconds = int(agent_cfg.get("prompt_timeout", DEFAULT_TIMEOUT_SECONDS))
    context_messages = int(agent_cfg.get("context_messages", 20))
    provider_name = str(agent_cfg.get("label", agent.capitalize())).strip()
    model_name = _extract_cli_model(extra)
    oneshot_profiles_dir = data_dir / "copilot-oneshot-home"
    oneshot_profiles_dir.mkdir(parents=True, exist_ok=True)

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
        print("  Is the server running? Start it with: python run.py")
        sys.exit(1)

    assigned_name = registration["name"]
    assigned_token = registration["token"]
    print(f"  Registered as: {assigned_name} (slot {registration.get('slot', '?')})")

    state_lock = threading.Lock()
    state = {
        "name": assigned_name,
        "token": assigned_token,
        "working": False,
        "launch_args": [],
        "launch_env": dict(base_env),
    }

    def refresh_launch_state(instance_name: str, token: str):
        instance_profile_dir = oneshot_profiles_dir / instance_name
        instance_profile_dir.mkdir(parents=True, exist_ok=True)
        with state_lock:
            state["launch_args"] = list(extra)
            state["launch_env"] = {
                **base_env,
                "USERPROFILE": str(instance_profile_dir),
                "HOME": str(instance_profile_dir),
            }

    def get_name() -> str:
        with state_lock:
            return state["name"]

    def get_token() -> str:
        with state_lock:
            return state["token"]

    def set_working(value: bool):
        with state_lock:
            state["working"] = value

    def is_working() -> bool:
        with state_lock:
            return state["working"]

    def get_launch() -> tuple[list[str], dict[str, str]]:
        with state_lock:
            return list(state["launch_args"]), dict(state["launch_env"])

    def set_identity(new_name: str | None = None, new_token: str | None = None):
        refresh_needed = False
        current_name = None
        current_token = None
        with state_lock:
            if new_name and new_name != state["name"]:
                state["name"] = new_name
                refresh_needed = True
            if new_token and new_token != state["token"]:
                state["token"] = new_token
                refresh_needed = True
            current_name = state["name"]
            current_token = state["token"]

        if refresh_needed:
            refresh_launch_state(current_name, current_token)

    refresh_launch_state(assigned_name, assigned_token)

    def send_channel_message(text: str, channel: str):
        body = json.dumps({"text": text, "channel": channel}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{server_port}/api/send",
            method="POST",
            data=body,
            headers=_auth_headers(get_token(), include_json=True),
        )
        with urllib.request.urlopen(req, timeout=10):
            return

    def read_channel_messages(channel: str) -> list[dict]:
        params = f"limit={context_messages}&channel={channel}"
        req = urllib.request.Request(
            f"http://127.0.0.1:{server_port}/api/messages?{params}",
            headers=_auth_headers(get_token()),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def read_job_messages(job_id: int) -> list[dict]:
        req = urllib.request.Request(
            f"http://127.0.0.1:{server_port}/api/jobs/{job_id}/messages",
            headers=_auth_headers(get_token()),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def send_job_message(job_id: int, text: str):
        body = json.dumps({"text": text, "sender": get_name()}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{server_port}/api/jobs/{job_id}/messages",
            method="POST",
            data=body,
            headers={"Content-Type": "application/json", **_auth_headers(get_token())},
        )
        with urllib.request.urlopen(req, timeout=10):
            return

    def strip_self_prefix(text: str) -> str:
        current_name = get_name()
        for prefix in (f"{current_name}: ", f"{current_name}:"):
            if text.startswith(prefix):
                return text[len(prefix):].lstrip()
        return text

    def _format_context_line(msg: dict) -> str:
        sender = msg.get("sender", "user")
        text = (msg.get("text", "") or "").strip()
        timestamp = msg.get("time", "") or ""
        attachments = msg.get("attachments", []) or []
        prefix = f"[{timestamp}] " if timestamp else ""

        attachment_note = ""
        if attachments:
            attachment_names = []
            for attachment in attachments[:4]:
                if not isinstance(attachment, dict):
                    continue
                name = (attachment.get("name") or "").strip()
                if not name:
                    url = (attachment.get("url") or "").strip()
                    if url:
                        name = Path(url).name
                if not name:
                    name = attachment.get("type") or "attachment"
                attachment_names.append(name)
            if attachment_names:
                remainder = len(attachments) - len(attachment_names)
                suffix = f" (+{remainder} more)" if remainder > 0 else ""
                attachment_note = f" [attachments: {', '.join(attachment_names)}{suffix}]"
            else:
                attachment_note = f" [attachments: {len(attachments)}]"

        if text:
            return f"{prefix}{sender}: {text}{attachment_note}"
        return f"{prefix}{sender}:{attachment_note}"

    def build_prompt(*, channel: str, job_id: int | None, task_instruction: str, trigger_text: str, role: str, rules_text: str, include_identity_hint: bool) -> str:
        current_name = get_name()
        role_key = (role or "").strip().lower()
        if job_id is not None:
            conversation = read_job_messages(job_id)
            scope_line = f"Job thread: {job_id}"
        else:
            conversation = read_channel_messages(channel)
            scope_line = f"Channel: #{channel}"

        filtered_messages = [
            msg for msg in conversation
            if isinstance(msg, dict)
            and msg.get("sender") not in {"system", current_name}
            and ((msg.get("text", "") or "").strip() or (msg.get("attachments", []) or []))
        ]
        context_lines = [
            _clip_text(_format_context_line(msg), MAX_CONTEXT_LINE_CHARS)
            for msg in filtered_messages[-context_messages:]
        ]
        context_lines = _trim_context_lines(context_lines, MAX_CONTEXT_TOTAL_CHARS)
        recent_context = "\n".join(context_lines).strip() or "(no recent chat context available)"
        latest_message = context_lines[-1] if context_lines else "(no latest message available)"
        latest_message = _clip_text(latest_message, 1200)
        trigger_text = _clip_text((trigger_text or "").strip(), 1200)
        rules_text = _clip_text(rules_text, MAX_RULES_CHARS)

        parts = [
            "You are GitHub Copilot participating in an agentchattr room.",
            f"Your visible name in this room is {current_name}.",
            "Reply in plain text only and do not prefix your own name.",
            "Do not call MCP tools, do not use external tools, and do not try to read more context.",
            "All of the context you need for this reply is provided below.",
            "If the latest message directly assigns you a chat duty, that duty is the task.",
            "Treat coordination, planning, monitoring, review, critique, and delegation requests as actionable tasks; do not reply that there is no task when the user has assigned one in chat.",
            "If recent context references screenshots or attachments you cannot inspect directly, do not block on that limitation. Use the attachment hints in context, delegate visual inspection to the most appropriate teammate if needed, and keep the work moving.",
            "If your role is Planner, default to choosing the next concrete slice, assigning it by @mention, and monitoring progress in chat.",
            "If your role is Reviewer or Challenger, default to critiquing the current plan or progress and stating the next missing evidence, delta, or adjustment.",
            "Forbidden replies when the latest message gives you a direct duty: 'Ready.', 'Understood.', 'No actionable task was provided', 'I need the actual task'. Perform the duty instead.",
            scope_line,
        ]
        if role:
            parts.append(f"Role: {role}")
        if rules_text:
            parts.append(f"Rules: {rules_text}")
        if include_identity_hint:
            parts.append(_IDENTITY_HINT.strip())
        if role_key == "planner":
            parts.append(
                "Planner output contract: your reply must include these lines in plain text: "
                "'stato corrente:', '@implementer:', '@reviewer:', '@challenger:', 'prossimo update:'."
            )
        elif role_key in {"reviewer", "challenger"}:
            parts.append("Critique output contract: name one concrete issue or one concrete validation step for the current slice.")
        if trigger_text:
            parts.append(f"Primary trigger message: {trigger_text}")
        parts.append(f"Task: {task_instruction}")
        parts.append(f"The latest message you must answer is: {latest_message}")
        parts.append("Follow the latest message exactly when it contains a direct instruction.")
        parts.append("Recent conversation:")
        parts.append(recent_context)

        prompt = "\n\n".join(parts)
        if len(prompt) <= MAX_PROMPT_CHARS:
            return prompt

        shortened_context = _trim_context_lines(context_lines, max(1200, MAX_CONTEXT_TOTAL_CHARS // 2))
        prompt = "\n\n".join([
            *parts[:-1],
            "\n".join(shortened_context).strip() or "(recent context truncated)",
        ])
        return _clip_text(prompt, MAX_PROMPT_CHARS)

    def run_copilot_prompt(prompt: str) -> str:
        launch_args, launch_env = get_launch()
        command_args = [resolved_command, *launch_args, "-p", prompt]
        proc = _run_prompt_command(
            command_args,
            cwd=project_dir,
            env=launch_env,
            timeout=timeout_seconds,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()

        if proc.returncode != 0 and not stdout:
            detail = stderr.splitlines()[-1] if stderr else f"copilot exited with code {proc.returncode}"
            raise RuntimeError(detail)

        return strip_self_prefix(stdout)

    def handle_trigger(prompt: str, *, channel: str, job_id: int | None):
        set_working(True)
        try:
            response = run_copilot_prompt(prompt).strip()
            if not response:
                return
            if job_id is not None:
                send_job_message(job_id, response)
            else:
                send_channel_message(response, channel)
            print(f"  [{channel}] Responded ({len(response)} chars)")
        except Exception as exc:
            print(f"  Error handling trigger: {exc}")
        finally:
            set_working(False)

    def heartbeat():
        while True:
            try:
                current_name = get_name()
                current_token = get_token()
                body = json.dumps({"active": is_working()}).encode()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{server_port}/api/heartbeat/{current_name}",
                    method="POST",
                    data=body,
                    headers=_auth_headers(current_token, include_json=True),
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp_data = json.loads(resp.read())
                server_name = resp_data.get("name", current_name)
                if server_name != current_name:
                    print(f"  Identity updated: {current_name} -> {server_name}")
                    set_identity(new_name=server_name)
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
                        set_identity(replacement["name"], replacement["token"])
                        print(f"  Re-registered as: {replacement['name']}")
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=heartbeat, daemon=True).start()

    queue_file = data_dir / f"{assigned_name}_queue.jsonl"
    if queue_file.exists():
        queue_file.write_text("", "utf-8")

    print("\n  === Copilot One-Shot Wrapper ===")
    print(f"  Command: {resolved_command} -p <prompt>")
    print(f"  Working directory: {project_dir}")
    print(f"  @{assigned_name} mentions trigger one-shot Copilot calls")
    print("  Ctrl+C to stop\n")

    first_mention = True
    last_rules_epoch = 0
    trigger_count = 0
    is_multi_instance = registration.get("slot", 1) > 1

    try:
        while True:
            try:
                current_name = get_name()
                current_queue = data_dir / f"{current_name}_queue.jsonl"
                if current_queue.exists() and current_queue.stat().st_size > 0:
                    with open(current_queue, "r", encoding="utf-8") as handle:
                        lines = handle.readlines()
                    current_queue.write_text("", "utf-8")

                    has_trigger = False
                    channel = "general"
                    job_id = None
                    custom_prompt = ""
                    trigger_text = ""
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        has_trigger = True
                        if isinstance(data, dict):
                            channel = data.get("channel", channel)
                            if "job_id" in data:
                                job_id = data["job_id"]
                            raw_prompt = data.get("prompt", "")
                            if isinstance(raw_prompt, str) and raw_prompt.strip():
                                custom_prompt = raw_prompt.strip()
                            raw_text = data.get("text", "")
                            if isinstance(raw_text, str) and raw_text.strip():
                                trigger_text = raw_text.strip()

                    if has_trigger:
                        role = _fetch_role(server_port, current_name)
                        if not role and current_name != agent:
                            role = _fetch_role(server_port, agent)

                        task_instruction = _derive_task_instruction(
                            role,
                            custom_prompt=custom_prompt,
                            trigger_text=trigger_text,
                            in_job=job_id is not None,
                        )

                        current_token = get_token()
                        rules_data = _fetch_active_rules(server_port, current_token)
                        trigger_count += 1
                        rules_text = ""
                        if rules_data:
                            refresh_interval = rules_data.get("refresh_interval", 10)
                            need_inject = (
                                last_rules_epoch == 0
                                or rules_data["epoch"] != last_rules_epoch
                                or (refresh_interval > 0 and trigger_count % refresh_interval == 0)
                            )
                            if need_inject:
                                if rules_data["rules"]:
                                    rules_text = "; ".join(rules_data["rules"])
                                last_rules_epoch = rules_data["epoch"]
                                _report_rule_sync(server_port, current_name, rules_data["epoch"], current_token)

                        include_identity_hint = first_mention and is_multi_instance
                        if first_mention and is_multi_instance:
                            first_mention = False

                        prompt = build_prompt(
                            channel=channel,
                            job_id=job_id,
                            task_instruction=task_instruction,
                            trigger_text=trigger_text,
                            role=role,
                            rules_text=rules_text,
                            include_identity_hint=include_identity_hint,
                        )
                        handle_trigger(prompt, channel=channel, job_id=job_id)
            except Exception:
                pass

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  Shutting down...")
    finally:
        try:
            current_name = get_name()
            current_token = get_token()
            req = urllib.request.Request(
                f"http://127.0.0.1:{server_port}/api/deregister/{current_name}",
                method="POST",
                data=b"",
                headers=_auth_headers(current_token),
            )
            urllib.request.urlopen(req, timeout=5)
            print(f"  Deregistered {current_name}")
        except Exception:
            pass

    print("  Wrapper stopped.")


if __name__ == "__main__":
    main()