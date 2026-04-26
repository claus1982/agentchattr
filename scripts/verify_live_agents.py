from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import websockets


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


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


def parse_token_from_home(base_url: str) -> str:
    req = Request(f"{base_url}/")
    with urlopen(req, timeout=10) as response:
        html = response.read().decode("utf-8", errors="replace")
    marker = 'window.__SESSION_TOKEN__="'
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("Could not discover session token from home page")
    start += len(marker)
    end = html.find('"', start)
    if end < 0:
        raise RuntimeError("Could not parse session token from home page")
    return html[start:end]


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


def queue_snapshot(agentchattr_root: Path) -> dict[str, dict[str, Any]]:
    data_dir = agentchattr_root / "data"
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.glob("copilot*_queue.jsonl")):
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        snapshot[path.name] = {
            "path": str(path),
            "size": path.stat().st_size if path.exists() else 0,
            "line_count": len(lines),
            "non_empty": bool(lines),
        }
    return snapshot


def clear_runtime_files(agentchattr_root: Path) -> list[str]:
    data_dir = agentchattr_root / "data"
    removed: list[str] = []
    for path in sorted(data_dir.glob("copilot*_queue.jsonl")):
        try:
            path.unlink(missing_ok=True)
            removed.append(path.name)
        except OSError:
            pass
    for name in ("renames.json", "renames.tmp"):
        path = data_dir / name
        try:
            path.unlink(missing_ok=True)
            removed.append(path.name)
        except OSError:
            pass
    return removed


def server_is_running(base_url: str) -> bool:
    try:
        parse_token_from_home(base_url)
        return True
    except Exception:
        return False


def start_logged_process(args: list[str], *, cwd: Path, log_path: Path) -> tuple[subprocess.Popen[str], Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("w", encoding="utf-8")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        args,
        cwd=str(cwd),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creationflags,
    )
    return proc, handle


def stop_logged_process(proc: subprocess.Popen[str] | None, handle: Any | None) -> None:
    try:
        if proc and proc.poll() is None:
            try:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                proc.kill()
                proc.wait(timeout=5)
    finally:
        if handle:
            handle.flush()
            handle.close()


def wait_for_server(base_url: str, *, timeout_seconds: int) -> str:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        try:
            return parse_token_from_home(base_url)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready: {last_error or 'timeout'}")


def wait_for_agent_online(base_url: str, token: str, *, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = api_request(base_url, token, "/api/status")
        agent = status.get("copilot") if isinstance(status, dict) else None
        if isinstance(agent, dict) and agent.get("available"):
            return status
        time.sleep(0.5)
    raise RuntimeError("@copilot did not come online before timeout")


def latest_message_id(base_url: str, token: str, channel: str) -> int:
    messages = api_request(base_url, token, f"/api/messages?{urlencode({'channel': channel, 'limit': 200})}")
    return max((int(msg.get("id") or 0) for msg in messages), default=0)


async def send_user_message_ws(base_url: str, token: str, *, channel: str, text: str) -> None:
    ws_url = base_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
    ws_url = f"{ws_url}/ws?{urlencode({'token': token})}"
    async with websockets.connect(ws_url, max_size=2**20) as websocket:
        deadline = time.time() + 10
        while time.time() < deadline:
            event = json.loads(await asyncio.wait_for(websocket.recv(), timeout=5))
            if event.get("type") == "status":
                break
        await websocket.send(json.dumps({
            "type": "message",
            "sender": "user",
            "text": text,
            "channel": channel,
        }))
        await asyncio.sleep(0.2)


def wait_for_reply(base_url: str, token: str, *, channel: str, since_id: int, expected_sender: str, timeout_seconds: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    deadline = time.time() + timeout_seconds
    latest: list[dict[str, Any]] = []
    while time.time() < deadline:
        latest = api_request(base_url, token, f"/api/messages?{urlencode({'channel': channel, 'limit': 200})}")
        recent = [msg for msg in latest if int(msg.get("id") or 0) > since_id]
        for msg in recent:
            msg_id = int(msg.get("id") or 0)
            if msg_id <= since_id:
                continue
            if msg.get("sender") != expected_sender:
                continue
            if str(msg.get("type") or "chat") != "chat":
                continue
            return msg, recent
        time.sleep(0.5)
    return None, [msg for msg in latest if int(msg.get("id") or 0) > since_id]


def classify_duplicate_names(status: dict[str, Any]) -> list[str]:
    return sorted(
        name
        for name in status.keys()
        if name == "copilot" or name.startswith("copilot-")
    )


def run_cycle(
    *,
    cycle_index: int,
    agentchattr_root: Path,
    routify_root: Path,
    base_url: str,
    timeout_seconds: int,
    artifacts_dir: Path,
) -> dict[str, Any]:
    cycle_dir = artifacts_dir / f"cycle-{cycle_index}"
    cycle_dir.mkdir(parents=True, exist_ok=True)

    cleanup_before = clear_runtime_files(agentchattr_root)
    pre_queue = queue_snapshot(agentchattr_root)
    pre_agentchattr_status = git_status_short(agentchattr_root)
    pre_routify_status = git_status_short(routify_root)

    server_proc = None
    wrapper_proc = None
    server_handle = None
    wrapper_handle = None

    probe_text = "@copilot rispondi solo con LIVE_OK"
    channel = "general"
    response = None
    transcript: list[dict[str, Any]] = []
    online_status: dict[str, Any] = {}
    error = ""

    try:
        server_proc, server_handle = start_logged_process(
            [PYTHON, "-u", str(agentchattr_root / "run.py")],
            cwd=agentchattr_root,
            log_path=cycle_dir / "server.log",
        )
        token = wait_for_server(base_url, timeout_seconds=timeout_seconds)

        wrapper_proc, wrapper_handle = start_logged_process(
            [PYTHON, "-u", str(agentchattr_root / "wrapper_copilot.py"), "copilot"],
            cwd=agentchattr_root,
            log_path=cycle_dir / "wrapper.log",
        )

        online_status = wait_for_agent_online(base_url, token, timeout_seconds=timeout_seconds)
        duplicate_names = classify_duplicate_names(online_status)
        if duplicate_names != ["copilot"]:
            raise RuntimeError(f"Unexpected copilot identities online: {duplicate_names}")

        baseline_id = latest_message_id(base_url, token, channel)
        asyncio.run(send_user_message_ws(base_url, token, channel=channel, text=probe_text))
        response, transcript = wait_for_reply(
            base_url,
            token,
            channel=channel,
            since_id=baseline_id,
            expected_sender="copilot",
            timeout_seconds=timeout_seconds,
        )
        if not response:
            raise RuntimeError("No @copilot chat reply arrived after the LIVE_OK probe")
        if (response.get("text") or "").strip() != "LIVE_OK":
            raise RuntimeError(f"Expected exact LIVE_OK reply, got: {(response.get('text') or '').strip()!r}")

        post_status = api_request(base_url, token, "/api/status")
        duplicate_after = classify_duplicate_names(post_status)
        if duplicate_after != ["copilot"]:
            raise RuntimeError(f"Unexpected copilot identities after reply: {duplicate_after}")

    except Exception as exc:
        error = str(exc)
    finally:
        stop_logged_process(wrapper_proc, wrapper_handle)
        stop_logged_process(server_proc, server_handle)

    cleanup_after = clear_runtime_files(agentchattr_root)
    post_queue = queue_snapshot(agentchattr_root)
    post_agentchattr_status = git_status_short(agentchattr_root)
    post_routify_status = git_status_short(routify_root)

    cycle_result = {
        "cycle": cycle_index,
        "probe_text": probe_text,
        "cleanup_before": cleanup_before,
        "cleanup_after": cleanup_after,
        "pre_queue": pre_queue,
        "post_queue": post_queue,
        "pre_agentchattr_status": pre_agentchattr_status,
        "post_agentchattr_status": post_agentchattr_status,
        "pre_routify_status": pre_routify_status,
        "post_routify_status": post_routify_status,
        "online_status": online_status,
        "response": response,
        "transcript": transcript,
        "passed": not error
        and response is not None
        and (response.get("text") or "").strip() == "LIVE_OK"
        and pre_agentchattr_status == post_agentchattr_status
        and pre_routify_status == post_routify_status
        and all(not item.get("non_empty") for item in post_queue.values()),
        "error": error,
    }

    write_json(cycle_dir / "result.json", cycle_result)
    write_json(cycle_dir / "transcript.json", transcript)
    return cycle_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Repeatable live-agent verification for @copilot one-shot mode")
    parser.add_argument("--agentchattr-root", default=str(ROOT))
    parser.add_argument("--routify-root", default=r"c:\Users\claud\Desktop\Routify")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8300")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    agentchattr_root = Path(args.agentchattr_root).resolve()
    routify_root = Path(args.routify_root).resolve()
    run_id = time.strftime("%Y%m%d-%H%M%S")
    artifacts_dir = agentchattr_root / "data" / "live-agent-proof" / run_id
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if server_is_running(args.api_base_url):
        raise RuntimeError("A local agentchattr server is already running. Stop it or use verify_live_agents.ps1 for a clean run.")

    results = []
    for cycle_index in range(1, max(1, args.cycles) + 1):
        result = run_cycle(
            cycle_index=cycle_index,
            agentchattr_root=agentchattr_root,
            routify_root=routify_root,
            base_url=args.api_base_url,
            timeout_seconds=args.timeout_seconds,
            artifacts_dir=artifacts_dir,
        )
        results.append(result)
        if not result["passed"]:
            break

    passed = len(results) == max(1, args.cycles) and all(item["passed"] for item in results)
    summary = {
        "run_id": run_id,
        "artifacts_dir": str(artifacts_dir),
        "cycles_requested": max(1, args.cycles),
        "cycles_completed": len(results),
        "passed": passed,
        "default_design": "option-2-headless-one-shot",
        "results": results,
    }
    write_json(artifacts_dir / "summary.json", summary)

    print(f"Artifacts: {artifacts_dir}")
    for result in results:
        marker = "PASS" if result["passed"] else "FAIL"
        detail = "LIVE_OK" if result.get("response") else (result.get("error") or "no response")
        print(f"[{marker}] cycle {result['cycle']}: {detail}")
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, HTTPError, URLError, subprocess.SubprocessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)