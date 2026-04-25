"""Tests for wrapper.py MCP config writers.

Focused on the shape of the JSON written to provider settings files — Gemini
needs "httpUrl", CodeBuddy needs "url", legacy paths still work.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wrapper import (  # noqa: E402
    _build_provider_launch,
    _dismiss_codex_update,
    _extract_cli_model,
    _process_queue_once,
    _resolve_enter_backend,
    _write_json_mcp_settings,
)


class JsonMcpSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "settings.json"

    def _read(self):
        return json.loads(self.target.read_text("utf-8"))

    def test_default_http_uses_httpUrl_key(self):
        # Backward compat: no http_key override → "httpUrl" (Gemini-style)
        _write_json_mcp_settings(self.target, "http://127.0.0.1:8200/mcp",
                                 transport="http")
        data = self._read()
        entry = data["mcpServers"]["agentchattr"]
        self.assertEqual(entry["type"], "http")
        self.assertEqual(entry["httpUrl"], "http://127.0.0.1:8200/mcp")
        self.assertNotIn("url", entry)

    def test_http_key_override_writes_url_key(self):
        # CodeBuddy-style: http_key="url" → MCP-standard "url" key
        _write_json_mcp_settings(self.target, "http://127.0.0.1:8200/mcp",
                                 transport="http", http_key="url")
        data = self._read()
        entry = data["mcpServers"]["agentchattr"]
        self.assertEqual(entry["type"], "http")
        self.assertEqual(entry["url"], "http://127.0.0.1:8200/mcp")
        self.assertNotIn("httpUrl", entry)

    def test_sse_transport_always_uses_url(self):
        # SSE doesn't use httpUrl regardless of http_key setting
        _write_json_mcp_settings(self.target, "http://127.0.0.1:8201/sse",
                                 transport="sse")
        data = self._read()
        entry = data["mcpServers"]["agentchattr"]
        self.assertEqual(entry["type"], "sse")
        self.assertEqual(entry["url"], "http://127.0.0.1:8201/sse")

    def test_bearer_token_written_as_authorization_header(self):
        _write_json_mcp_settings(self.target, "http://127.0.0.1:8200/mcp",
                                 transport="http", token="secret-token-123",
                                 http_key="url")
        entry = self._read()["mcpServers"]["agentchattr"]
        self.assertEqual(entry["headers"]["Authorization"], "Bearer secret-token-123")

    def test_existing_servers_preserved(self):
        # Write a pre-existing settings file with an unrelated server
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(json.dumps({
            "mcpServers": {"some-other-server": {"type": "http", "url": "http://elsewhere"}}
        }))
        _write_json_mcp_settings(self.target, "http://127.0.0.1:8200/mcp",
                                 transport="http", http_key="url")
        data = self._read()
        self.assertIn("some-other-server", data["mcpServers"])
        self.assertIn("agentchattr", data["mcpServers"])


class ExpanduserPathTests(unittest.TestCase):
    """Verify the _build_provider_launch path expansion logic.

    Unit-testing _build_provider_launch directly would require too much
    scaffolding (registry, token, etc.). Instead we verify Path behavior
    matches our expectations — the wrapper code uses Path(...).expanduser()
    at a single well-defined spot.
    """

    def test_tilde_prefix_expands_to_home(self):
        raw = "~/.codebuddy/.mcp.json"
        expanded = Path(raw).expanduser()
        self.assertTrue(expanded.is_absolute())
        # Must no longer contain a literal ~
        self.assertNotIn("~", str(expanded))
        # Sanity: should land under the user's home dir
        self.assertTrue(str(expanded).startswith(str(Path.home())))

    def test_absolute_path_unchanged_by_expanduser(self):
        raw = str(Path("/tmp/literal-abs").resolve())
        expanded = Path(raw).expanduser()
        self.assertEqual(str(expanded), raw)

    def test_relative_path_stays_relative_after_expanduser(self):
        # Relative paths without ~ aren't made absolute by expanduser alone —
        # that's handled by the subsequent `base / target` join in wrapper.py.
        raw = ".qwen/settings.json"
        expanded = Path(raw).expanduser()
        self.assertFalse(expanded.is_absolute())


class QueueWatcherProcessingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue_file = Path(self.tmp.name) / "reviewer_queue.jsonl"

    def _identity(self):
        return "reviewer", self.queue_file

    def test_failed_injection_keeps_queue_for_retry(self):
        entry = json.dumps({
            "channel": "general",
            "prompt": "post your critique now",
        }) + "\n"
        self.queue_file.write_text(entry, "utf-8")
        injected = []

        def flaky_inject(prompt: str):
            injected.append(prompt)
            raise RuntimeError("terminal not ready")

        with mock.patch("wrapper.time.sleep", return_value=None), \
                mock.patch("wrapper._fetch_role", return_value=""), \
                mock.patch("wrapper._fetch_active_rules", return_value=None):
            processed = _process_queue_once(self._identity, flaky_inject)

        self.assertFalse(processed)
        self.assertEqual(injected, ["post your critique now"])
        self.assertEqual(self.queue_file.read_text("utf-8"), entry)

    def test_successful_injection_preserves_newly_appended_entries(self):
        first = json.dumps({"channel": "general", "prompt": "first prompt"}) + "\n"
        second = json.dumps({"channel": "general", "prompt": "second prompt"}) + "\n"
        self.queue_file.write_text(first, "utf-8")
        injected = []

        def inject_with_append(prompt: str):
            injected.append(prompt)
            with self.queue_file.open("a", encoding="utf-8") as handle:
                handle.write(second)

        with mock.patch("wrapper.time.sleep", return_value=None), \
                mock.patch("wrapper._fetch_role", return_value=""), \
                mock.patch("wrapper._fetch_active_rules", return_value=None):
            processed = _process_queue_once(self._identity, inject_with_append)

        self.assertTrue(processed)
        self.assertEqual(injected, ["first prompt"])
        self.assertEqual(self.queue_file.read_text("utf-8"), second)


class CliModelExtractionTests(unittest.TestCase):
    def test_extracts_model_from_split_flag(self):
        self.assertEqual(_extract_cli_model(["--label", "reviewer", "--model", "gpt-5.4"]), "gpt-5.4")

    def test_extracts_model_from_equals_flag(self):
        self.assertEqual(_extract_cli_model(["--model=gpt-5.4"]), "gpt-5.4")


class CodexLaunchDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = Path(self.tmp.name)
        self.project_dir = self.data_dir

    def test_codex_defaults_to_never_approval_and_workspace_write(self):
        launch_args, _env, _inject_env, _settings_path = _build_provider_launch(
            agent="codex",
            agent_cfg={},
            instance_name="codex-1",
            data_dir=self.data_dir,
            proxy_url="http://127.0.0.1:55274/mcp",
            extra_args=[],
            env={},
            token="",
            mcp_cfg={},
            project_dir=self.project_dir,
        )

        self.assertEqual(launch_args[:4], ["-s", "workspace-write", "-a", "never"])
        self.assertIn('mcp_servers.agentchattr.url="http://127.0.0.1:55274/mcp"', launch_args)

    def test_codex_respects_explicit_approval_and_sandbox_overrides(self):
        launch_args, _env, _inject_env, _settings_path = _build_provider_launch(
            agent="codex",
            agent_cfg={"ask_for_approval": "never", "sandbox": "workspace-write"},
            instance_name="codex-1",
            data_dir=self.data_dir,
            proxy_url="http://127.0.0.1:55274/mcp",
            extra_args=["-a", "on-request", "-s", "danger-full-access"],
            env={},
            token="",
            mcp_cfg={},
            project_dir=self.project_dir,
        )

        self.assertEqual(launch_args[:4], ["-c", 'mcp_servers.agentchattr.url="http://127.0.0.1:55274/mcp"', "-a", "on-request"])
        self.assertEqual(launch_args[-2:], ["-s", "danger-full-access"])
        self.assertEqual(launch_args.count("-a"), 1)
        self.assertEqual(launch_args.count("-s"), 1)


class CodexUpdateDismissalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.version_file = Path(self.tmp.name) / "version.json"

    def test_marks_latest_version_as_dismissed(self):
        self.version_file.write_text(json.dumps({
            "latest_version": "0.124.0",
            "dismissed_version": None,
        }), "utf-8")

        updated = _dismiss_codex_update(self.version_file)

        self.assertEqual(updated, "0.124.0")
        data = json.loads(self.version_file.read_text("utf-8"))
        self.assertEqual(data["dismissed_version"], "0.124.0")

    def test_skips_when_latest_version_already_dismissed(self):
        payload = {
            "latest_version": "0.124.0",
            "dismissed_version": "0.124.0",
        }
        self.version_file.write_text(json.dumps(payload), "utf-8")

        updated = _dismiss_codex_update(self.version_file)

        self.assertIsNone(updated)
        self.assertEqual(json.loads(self.version_file.read_text("utf-8")), payload)


class EnterBackendResolutionTests(unittest.TestCase):
    def test_prefers_explicit_enter_backend(self):
        self.assertEqual(
            _resolve_enter_backend("codex", {"enter_backend": "console_input"}),
            "console_input",
        )

    def test_defaults_codex_to_wm_setfocus_on_windows(self):
        with mock.patch("wrapper.sys.platform", "win32"):
            self.assertEqual(_resolve_enter_backend("codex", {}), "wm_setfocus")

    def test_defaults_other_agents_to_console_input(self):
        with mock.patch("wrapper.sys.platform", "win32"):
            self.assertEqual(_resolve_enter_backend("claude", {}), "console_input")


if __name__ == "__main__":
    unittest.main()
