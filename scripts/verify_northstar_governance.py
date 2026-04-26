from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from session_engine import SessionEngine
from session_store import SessionStore
from store import MessageStore


class ImmediateTimer:
    def __init__(self, interval: float, function, args=None, kwargs=None) -> None:
        self._function = function
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._function(*self._args, **self._kwargs)


EXPECTED_ROLES = [
    "delivery_lead",
    "product_manager",
    "technical_lead",
    "implementation_engineer",
    "qa_reviewer",
]
EXPECTED_PHASES = [
    "Intake",
    "Plan",
    "Technical Review",
    "Execute",
    "Assess",
    "Command",
]
EXPECTED_ROLE_SEQUENCE = [
    "delivery_lead",
    "product_manager",
    "technical_lead",
    "implementation_engineer",
    "qa_reviewer",
    "delivery_lead",
]
EXPECTED_HANDOFFS = [
    ("delivery_lead", "product_manager"),
    ("product_manager", "technical_lead"),
    ("technical_lead", "implementation_engineer"),
    ("implementation_engineer", "qa_reviewer"),
    ("qa_reviewer", "delivery_lead"),
]


class FakeTrigger:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def trigger_sync(self, agent: str, channel: str, prompt: str) -> None:
        self.calls.append({"agent": agent, "channel": channel, "prompt": prompt})

    def get_status(self) -> dict[str, Any]:
        return {}


class FakeRegistry:
    def __init__(self, names: set[str]) -> None:
        self._names = set(names)

    def is_registered(self, name: str) -> bool:
        return name in self._names

    def get_all(self) -> dict[str, dict[str, str]]:
        return {name: {"name": name, "label": name, "base": name} for name in self._names}

    def get_instance(self, name: str) -> dict[str, str] | None:
        if name not in self._names:
            return None
        return {"name": name, "label": name, "base": name}

    def resolve_name(self, name: str) -> str:
        return name


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def run_command(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)


def git_status_short(repo: Path) -> str:
    result = run_command(["git", "-C", str(repo), "status", "--short"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git status failed for {repo}")
    return result.stdout


def queue_snapshot(agentchattr_root: Path) -> dict[str, dict[str, Any]]:
    data_dir = agentchattr_root / "data"
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.glob("*_queue.jsonl")):
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        snapshot[path.name] = {
            "path": str(path),
            "size": path.stat().st_size if path.exists() else 0,
            "line_count": len(lines),
            "non_empty": bool(lines),
        }
    return snapshot


def parse_token_from_home(base_url: str) -> str:
    req = Request(f"{base_url}/")
    with urlopen(req, timeout=10) as response:
        html = response.read().decode("utf-8", errors="replace")
    match = re.search(r'window\.__SESSION_TOKEN__="([^"]+)"', html)
    if not match:
        raise RuntimeError("Could not discover session token from home page")
    return match.group(1)


def api_request(base_url: str, token: str, path: str, *, method: str = "GET", body: Any | None = None) -> Any:
    data = None
    headers = {"X-Session-Token": token}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{base_url}{path}", method=method, data=data, headers=headers)
    with urlopen(req, timeout=20) as response:
        text = response.read().decode("utf-8", errors="replace")
    return json.loads(text) if text else None


def static_contract_checks(agentchattr_root: Path) -> dict[str, Any]:
    template = json.loads((agentchattr_root / "session_templates" / "software-house-delivery.json").read_text(encoding="utf-8"))
    config_text = (agentchattr_root / "config.toml").read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        store = SessionStore(str(temp_root / "session_runs.json"), templates_dir=str(agentchattr_root / "session_templates"))
        messages = MessageStore(str(temp_root / "agentchattr_log.jsonl"))
        trigger = FakeTrigger()
        registry = FakeRegistry(set(EXPECTED_ROLES))
        with patch("session_engine.threading.Timer", ImmediateTimer):
            engine = SessionEngine(store, messages, trigger, registry=registry)
            session = engine.start_session(
                template_id="software-house-delivery",
                channel="general",
                cast={role: role for role in EXPECTED_ROLES},
                started_by="verify-script",
                goal="Verify Northstar prompt and transition contracts.",
            )
            if not session:
                raise RuntimeError("Failed to start static verification session")
            execute_prompt = trigger.calls[-1]["prompt"]
            messages.add(
                sender="implementation_engineer",
                text="Work performed: governance-only proof.\nValidation: prompt contract inspected.\nEvidence: handoff transition emitted.\nBlocker: none",
                channel="general",
            )
            handoffs = [msg for msg in messages.get_recent(20, channel="general") if msg.get("type") == "session_handoff"]
            latest_handoff = handoffs[-1] if handoffs else None

    return {
        "template_loaded": template.get("id") == "software-house-delivery",
        "roles_present": template.get("roles") == EXPECTED_ROLES,
        "states_present": [phase.get("name") for phase in template.get("phases", [])] == EXPECTED_PHASES,
        "default_autonomy_template": bool(re.search(r'planner_autonomy_template_id\s*=\s*"software-house-delivery"', config_text)),
        "client_escalation_role": template.get("governance", {}).get("client_escalation_role") == "delivery_lead",
        "quality_gate_role": template.get("governance", {}).get("quality_gate_role") == "qa_reviewer",
        "prompt_has_handoff_contract": all(
            token in execute_prompt
            for token in (
                "HANDOFF",
                "TO: @qa_reviewer",
                "ROLE: qa_reviewer",
                "ACTION: one concrete next action",
                "STATUS: what changed and what remains open",
            )
        ),
        "prompt_limits_client_escalation": "Only delivery_lead may escalate to the client" in execute_prompt,
        "prompt_limits_quality_gate": "Only qa_reviewer may reject quality at the gate" in execute_prompt,
        "transition_has_handoff_contract": bool(latest_handoff and latest_handoff.get("text", "").startswith("HANDOFF\n")),
        "transition_metadata_contract": bool(
            latest_handoff and (latest_handoff.get("metadata") or {}).get("handoff_contract") == "northstar-handoff-v1"
        ),
    }


def run_unit_tests(agentchattr_root: Path, output_path: Path) -> bool:
    result = run_command(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_session_template_validation",
            "tests.test_config_overrides",
            "tests.test_session_engine",
        ],
        cwd=agentchattr_root,
    )
    write_text(output_path, (result.stdout or "") + (result.stderr or ""))
    return result.returncode == 0


def wait_for_session_messages(base_url: str, token: str, channel: str, session_id: int, timeout_seconds: int) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    latest: list[dict[str, Any]] = []
    while time.time() < deadline:
        latest = api_request(base_url, token, f"/api/messages?{urlencode({'channel': channel, 'limit': 200})}")
        filtered = [msg for msg in latest if (msg.get("metadata") or {}).get("session_id") == session_id]
        role_messages = [msg for msg in filtered if (msg.get("metadata") or {}).get("session_role")]
        session_end = any(msg.get("type") == "session_end" for msg in filtered)
        if len(role_messages) >= len(EXPECTED_ROLE_SEQUENCE) and session_end:
            return filtered
        time.sleep(0.2)
    return [msg for msg in latest if (msg.get("metadata") or {}).get("session_id") == session_id]


def live_safe_mode_proof(base_url: str, token: str, artifacts_dir: Path, timeout_seconds: int) -> dict[str, Any]:
    channel = f"nsproof-{int(time.time()) % 1000000:06d}"
    cast = {
        "delivery_lead": "northstar-delivery",
        "product_manager": "northstar-product",
        "technical_lead": "northstar-technical",
        "implementation_engineer": "northstar-implementation",
        "qa_reviewer": "northstar-qa",
    }
    started = api_request(
        base_url,
        token,
        "/api/sessions/start",
        method="POST",
        body={
            "template_id": "software-house-delivery",
            "channel": channel,
            "cast": cast,
            "goal": "Northstar governance-only safe-mode proof. Do not modify files. Demonstrate delivery_lead -> product_manager -> technical_lead -> implementation_engineer -> qa_reviewer -> delivery_lead.",
            "started_by": "verify_northstar_governance",
            "safe_mode": True,
        },
    )
    session_id = int(started.get("id") or 0)
    if not session_id:
        raise RuntimeError(f"Could not start safe-mode proof session: {started}")

    transcript = wait_for_session_messages(base_url, token, channel, session_id, timeout_seconds)
    role_messages = [msg for msg in transcript if (msg.get("metadata") or {}).get("session_role")]
    handoffs = [msg for msg in transcript if msg.get("type") == "session_handoff"]
    active = api_request(base_url, token, f"/api/sessions/active?{urlencode({'channel': channel})}")

    write_json(artifacts_dir / "live-transcript.json", transcript)
    write_json(
        artifacts_dir / "live-summary.json",
        {
            "session_id": session_id,
            "channel": channel,
            "role_sequence": [msg.get("sender") for msg in role_messages],
            "handoffs": [
                {
                    "from_role": (msg.get("metadata") or {}).get("from_role"),
                    "to_role": (msg.get("metadata") or {}).get("to_role"),
                    "text": msg.get("text", ""),
                }
                for msg in handoffs
            ],
            "agentic_message_count": len(role_messages),
            "active_session_after": active,
        },
    )

    return {
        "session_id": session_id,
        "channel": channel,
        "transcript": transcript,
        "role_messages": role_messages,
        "handoffs": handoffs,
        "active_after": active,
        "cast": cast,
    }


def compare_online_agents(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return sorted(before.keys()) == sorted(after.keys())


def evaluate_checks(
    *,
    static_checks: dict[str, Any],
    unit_ok: bool,
    pre_routify_status: str,
    post_routify_status: str,
    pre_queue_snapshot: dict[str, Any],
    post_queue_snapshot: dict[str, Any],
    pre_status: dict[str, Any],
    post_status: dict[str, Any],
    live_result: dict[str, Any],
) -> list[dict[str, Any]]:
    role_messages = live_result["role_messages"]
    observed_role_sequence = [msg.get("sender") for msg in role_messages]
    observed_handoffs = [
        ((msg.get("metadata") or {}).get("from_role"), (msg.get("metadata") or {}).get("to_role"))
        for msg in live_result["handoffs"]
    ]
    agent_mapping_ok = [
        (msg.get("metadata") or {}).get("session_agent") == live_result["cast"].get(msg.get("sender"))
        for msg in role_messages
    ]
    copilot_clean = all(
        not pre_queue_snapshot.get(name, {}).get("non_empty") and not post_queue_snapshot.get(name, {}).get("non_empty")
        for name in ("copilot-1_queue.jsonl", "copilot-2_queue.jsonl")
    )

    return [
        {"name": "template software-house-delivery loaded", "ok": static_checks["template_loaded"]},
        {"name": "Northstar roles present", "ok": static_checks["roles_present"]},
        {"name": "Northstar states present", "ok": static_checks["states_present"]},
        {"name": "default autonomy template correct", "ok": static_checks["default_autonomy_template"]},
        {
            "name": "mandatory handoff format present in prompt and transition",
            "ok": static_checks["prompt_has_handoff_contract"] and static_checks["transition_has_handoff_contract"] and static_checks["transition_metadata_contract"],
        },
        {
            "name": "client escalation limited to delivery_lead",
            "ok": static_checks["client_escalation_role"] and static_checks["prompt_limits_client_escalation"],
        },
        {
            "name": "quality gate limited to qa_reviewer",
            "ok": static_checks["quality_gate_role"] and static_checks["prompt_limits_quality_gate"],
        },
        {"name": "expected Northstar cycle observed", "ok": observed_role_sequence == EXPECTED_ROLE_SEQUENCE},
        {"name": "expected handoffs observed", "ok": observed_handoffs == EXPECTED_HANDOFFS},
        {"name": "role to agent mapping verifiable", "ok": bool(role_messages) and all(agent_mapping_ok)},
        {"name": "Routify unchanged across live proof", "ok": pre_routify_status == post_routify_status},
        {"name": "copilot-1 and copilot-2 queues clean", "ok": copilot_clean},
        {"name": "no queue drift during safe-mode proof", "ok": pre_queue_snapshot == post_queue_snapshot},
        {"name": "no unexpected online identity drift", "ok": compare_online_agents(pre_status, post_status)},
        {"name": "no active proof session left behind", "ok": live_result["active_after"] is None},
        {"name": "unit validation passed", "ok": unit_ok},
        {"name": "transcript captured", "ok": bool(live_result["transcript"])},
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeatable Northstar governance verification")
    parser.add_argument("--agentchattr-root", default=str(ROOT))
    parser.add_argument("--routify-root", default=r"c:\Users\claud\Desktop\Routify")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8300")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    args = parser.parse_args()

    agentchattr_root = Path(args.agentchattr_root).resolve()
    routify_root = Path(args.routify_root).resolve()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    artifacts_dir = agentchattr_root / "artifacts" / "northstar-governance" / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    token = parse_token_from_home(args.api_base_url)

    pre_agentchattr_status = git_status_short(agentchattr_root)
    pre_routify_status = git_status_short(routify_root)
    pre_queue_snapshot = queue_snapshot(agentchattr_root)
    pre_status = api_request(args.api_base_url, token, "/api/status")
    pre_active_sessions = api_request(args.api_base_url, token, "/api/sessions/active-all")

    write_text(artifacts_dir / "pre-agentchattr-git-status.txt", pre_agentchattr_status)
    write_text(artifacts_dir / "pre-routify-git-status.txt", pre_routify_status)
    write_json(artifacts_dir / "pre-online-agents.json", pre_status)
    write_json(artifacts_dir / "pre-active-sessions.json", pre_active_sessions)
    write_json(artifacts_dir / "pre-queues.json", pre_queue_snapshot)

    static_checks = static_contract_checks(agentchattr_root)
    write_json(artifacts_dir / "static-contract-checks.json", static_checks)

    unit_ok = run_unit_tests(agentchattr_root, artifacts_dir / "unit-tests.txt")
    live_result = live_safe_mode_proof(args.api_base_url, token, artifacts_dir, args.timeout_seconds)

    post_agentchattr_status = git_status_short(agentchattr_root)
    post_routify_status = git_status_short(routify_root)
    post_queue_snapshot = queue_snapshot(agentchattr_root)
    post_status = api_request(args.api_base_url, token, "/api/status")
    post_active_sessions = api_request(args.api_base_url, token, "/api/sessions/active-all")

    write_text(artifacts_dir / "post-agentchattr-git-status.txt", post_agentchattr_status)
    write_text(artifacts_dir / "post-routify-git-status.txt", post_routify_status)
    write_json(artifacts_dir / "post-online-agents.json", post_status)
    write_json(artifacts_dir / "post-active-sessions.json", post_active_sessions)
    write_json(artifacts_dir / "post-queues.json", post_queue_snapshot)

    checks = evaluate_checks(
        static_checks=static_checks,
        unit_ok=unit_ok,
        pre_routify_status=pre_routify_status,
        post_routify_status=post_routify_status,
        pre_queue_snapshot=pre_queue_snapshot,
        post_queue_snapshot=post_queue_snapshot,
        pre_status=pre_status,
        post_status=post_status,
        live_result=live_result,
    )
    passed = all(item["ok"] for item in checks)

    summary = {
        "run_id": run_id,
        "artifacts_dir": str(artifacts_dir),
        "passed": passed,
        "checks": checks,
        "agentic_message_count": len(live_result["role_messages"]),
        "observed_handoffs": [
            {
                "from_role": pair[0],
                "to_role": pair[1],
            }
            for pair in [
                ((msg.get("metadata") or {}).get("from_role"), (msg.get("metadata") or {}).get("to_role"))
                for msg in live_result["handoffs"]
            ]
        ],
        "proof_channel": live_result["channel"],
        "proof_session_id": live_result["session_id"],
    }
    write_json(artifacts_dir / "summary.json", summary)

    print(f"Artifacts: {artifacts_dir}")
    for item in checks:
        marker = "PASS" if item["ok"] else "FAIL"
        print(f"[{marker}] {item['name']}")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, HTTPError, URLError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)