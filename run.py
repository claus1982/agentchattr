"""Entry point — starts MCP server (port 8200) + web UI (port 8300)."""

import argparse
import asyncio
import secrets
import sys
import threading
import time
import logging
from pathlib import Path

# Ensure the project directory is on the import path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Start agentchattr (web UI + MCP server).",
        epilog="Flags override config.toml for this invocation. The same flags "
               "are also accepted by wrapper.py and wrapper_api.py so a launcher "
               "can isolate per-project instances by passing matching values to "
               "each process.",
    )
    parser.add_argument("--data-dir",      default=None, help="Override server.data_dir (path)")
    parser.add_argument("--port",          default=None, help="Override server.port (int)")
    parser.add_argument("--mcp-http-port", default=None, help="Override mcp.http_port (int)")
    parser.add_argument("--mcp-sse-port",  default=None, help="Override mcp.sse_port (int)")
    parser.add_argument("--upload-dir",    default=None, help="Override images.upload_dir (path)")
    parser.add_argument("--allow-network", action="store_true",
                        help="Allow binding to non-localhost hosts (with confirmation).")
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Parse flags for --help support; the actual env propagation happens via
    # the shared config_loader.apply_cli_overrides helper so run.py and the
    # wrappers use identical extraction logic.
    _parse_args()

    from config_loader import apply_cli_overrides, load_config
    apply_cli_overrides()

    config_path = ROOT / "config.toml"
    if not config_path.exists():
        print(f"Error: {config_path} not found")
        sys.exit(1)

    config = load_config(ROOT)

    # --- Security: generate a random session token (in-memory only) ---
    session_token = secrets.token_hex(32)

    # Configure the FastAPI app (creates shared store)
    from app import app, configure, set_event_loop, store as _store_ref
    configure(config, session_token=session_token)

    # Share stores with the MCP bridge
    from app import store, rules, summaries, jobs, room_settings, registry, router as app_router, agents as app_agents, session_engine, session_store
    import mcp_bridge
    mcp_bridge.store = store
    mcp_bridge.rules = rules
    mcp_bridge.summaries = summaries
    mcp_bridge.jobs = jobs
    mcp_bridge.room_settings = room_settings
    mcp_bridge.registry = registry
    mcp_bridge.config = config
    mcp_bridge.router = app_router
    mcp_bridge.agents = app_agents
    mcp_bridge.session_engine = session_engine
    mcp_bridge.session_store = session_store

    # Enable cursor and role persistence across restarts
    data_dir = ROOT / config.get("server", {}).get("data_dir", "./data")
    mcp_bridge._CURSORS_FILE = data_dir / "mcp_cursors.json"
    mcp_bridge._load_cursors()
    mcp_bridge._ROLES_FILE = data_dir / "roles.json"
    mcp_bridge._load_roles()

    # Start MCP servers in background threads
    http_port = config.get("mcp", {}).get("http_port", 8200)
    sse_port = config.get("mcp", {}).get("sse_port", 8201)
    mcp_bridge.mcp_http.settings.port = http_port
    mcp_bridge.mcp_sse.settings.port = sse_port

    threading.Thread(target=mcp_bridge.run_http_server, daemon=True).start()
    threading.Thread(target=mcp_bridge.run_sse_server, daemon=True).start()
    time.sleep(0.5)
    logging.getLogger(__name__).info("MCP streamable-http on port %d, SSE on port %d", http_port, sse_port)

    # Mount static files
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse

    static_dir = ROOT / "static"

    @app.get("/")
    async def index():
        # Read index.html fresh each request so changes take effect without restart.
        # Inject the session token into the HTML so the browser client can use it.
        # This is safe: same-origin policy prevents cross-origin pages from reading
        # the response body, so only the user's own browser tab gets the token.
        html = (static_dir / "index.html").read_text("utf-8")
        injected = html.replace(
            "</head>",
            f'<script>window.__SESSION_TOKEN__="{session_token}";</script>\n</head>',
        )
        return HTMLResponse(injected, headers={"Cache-Control": "no-store"})

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    watchdog_cfg = config.get("sessions", {})
    watchdog_idle_seconds = max(15.0, float(watchdog_cfg.get("waiting_retrigger_seconds", 45)))
    watchdog_poll_seconds = max(5.0, float(watchdog_cfg.get("watchdog_poll_seconds", 15)))
    planner_review_enabled = bool(watchdog_cfg.get("planner_review_enabled", True))
    planner_review_idle_seconds = max(30.0, float(watchdog_cfg.get("planner_review_idle_seconds", 180)))
    planner_review_repeat_seconds = max(
        planner_review_idle_seconds,
        float(watchdog_cfg.get("planner_review_repeat_seconds", 300)),
    )
    planner_autonomy_enabled = bool(watchdog_cfg.get("planner_autonomy_enabled", True))
    planner_autonomy_idle_seconds = max(60.0, float(watchdog_cfg.get("planner_autonomy_idle_seconds", 300)))
    planner_autonomy_repeat_seconds = max(
        planner_autonomy_idle_seconds,
        float(watchdog_cfg.get("planner_autonomy_repeat_seconds", 600)),
    )
    planner_autonomy_template_id = str(watchdog_cfg.get("planner_autonomy_template_id", "premium-ui-remediation")).strip() or "premium-ui-remediation"
    planner_autonomy_goal = str(
        watchdog_cfg.get(
            "planner_autonomy_goal",
            "Keep iterating until the current product work is genuinely excellent, then decide the next high-value evolution.",
        )
    ).strip()

    def _session_watchdog():
        while True:
            time.sleep(watchdog_poll_seconds)
            if not session_engine:
                continue
            try:
                recovered = session_engine.recover_stale_waits(max_idle_seconds=watchdog_idle_seconds)
                if recovered:
                    logging.getLogger(__name__).info(
                        "Session watchdog re-triggered %d stalled participant(s)",
                        recovered,
                    )
                if planner_review_enabled:
                    planner_reviews = session_engine.trigger_periodic_planner_reviews(
                        idle_seconds=planner_review_idle_seconds,
                        repeat_seconds=planner_review_repeat_seconds,
                    )
                    if planner_reviews:
                        logging.getLogger(__name__).info(
                            "Session watchdog woke planner %d time(s)",
                            planner_reviews,
                        )
                if planner_autonomy_enabled:
                    autonomy_channels = [
                        str(channel).strip()
                        for channel in room_settings.get("channels", ["general"])
                        if str(channel).strip()
                    ] or ["general"]
                    planner_autonomy = session_engine.trigger_autonomous_planner_cycles(
                        channels=autonomy_channels,
                        template_id=planner_autonomy_template_id,
                        idle_seconds=planner_autonomy_idle_seconds,
                        repeat_seconds=planner_autonomy_repeat_seconds,
                        default_goal=planner_autonomy_goal,
                    )
                    if planner_autonomy:
                        logging.getLogger(__name__).info(
                            "Session watchdog started planner autonomy review %d time(s)",
                            planner_autonomy,
                        )
            except Exception:
                logging.getLogger(__name__).exception("Session watchdog failed")

    # Capture the event loop for the store→WebSocket bridge
    @app.on_event("startup")
    async def on_startup():
        set_event_loop(asyncio.get_running_loop())
        # Resume any sessions that were active before restart
        if session_engine:
            session_engine.resume_active_sessions()
            threading.Thread(target=_session_watchdog, daemon=True).start()

    # Run web server
    import uvicorn
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 8300)

    # --- Security: warn if binding to a non-localhost address ---
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"\n  !! SECURITY WARNING — binding to {host} !!")
        print("  This exposes agentchattr to your local network.")
        print()
        print("  Risks:")
        print("  - No TLS: traffic (including session token) is plaintext")
        print("  - Anyone on your network can sniff the token and gain full access")
        print("  - With the token, anyone can @mention agents and trigger tool execution")
        print("  - If agents run with auto-approve, this means remote code execution")
        print()
        print("  Only use this on a trusted home network. Never on public/shared WiFi.")
        if "--allow-network" not in sys.argv:
            print("  Pass --allow-network to start anyway, or set host to 127.0.0.1.\n")
            sys.exit(1)
        else:
            print()
            try:
                confirm = input("  Type YES to accept these risks and start: ").strip()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm != "YES":
                print("  Aborted.\n")
                sys.exit(1)

    print(f"\n  agentchattr")
    print(f"  Web UI:  http://{host}:{port}")
    print(f"  MCP HTTP: http://{host}:{http_port}/mcp  (Claude, Codex)")
    print(f"  MCP SSE:  http://{host}:{sse_port}/sse   (Gemini)")
    print(f"  Data:    {data_dir}")
    print(f"  Agents auto-trigger on @mention")
    print(f"\n  Session token: {session_token}\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

