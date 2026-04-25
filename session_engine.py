"""Session engine — orchestrates structured multi-agent sessions."""

import logging
import re
import threading
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Dissent mandate injected for review/critique roles
_DISSENT_LINE = "Provide your own independent analysis. Do not repeat or defer to other participants."
_MENTION_RE = re.compile(r"@([\w-]+)")
_NO_FILE_CHANGES_RE = re.compile(
    r"(?:files changed(?: in this pass)?\s*:\s*none\b|made no file changes\b)",
    re.IGNORECASE,
)
_NON_ACTIONABLE_REPLY_RE = re.compile(
    r"(?:\bno task\b|\bno actionable task\b|\bi(?: do)?n['’]t have a concrete task\b|\bi['’]m ready\b|\bwhat would you like me to do\b|\bsend the specific (?:change|bug|investigation)\b|\bsend the repository change\b)",
    re.IGNORECASE,
)
_NEXT_SLICE_TARGET_RE = re.compile(r"^next slice target\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_PROMPT_BREVITY_LINE = (
    "Be concise: prefer <=8 short lines, only new evidence/decisions/blockers, no recap."
)
_WATCHDOG_BREVITY_LINE = "Respond only if you have materially new direction. Keep it brief."

# Roles that get the dissent mandate
_DISSENT_ROLES = {"reviewer", "red_team", "critic", "challenger", "against"}


@dataclass(frozen=True)
class _LoopGuardSignal:
    signature: str
    target: str
    stagnant_role: str


class SessionEngine:
    """Orchestrates session turn flow on top of existing chat infrastructure.

    Listens to message store callbacks, advances session state, and triggers
    agents via the AgentTrigger system.
    """

    def __init__(self, session_store, message_store, agent_trigger, registry=None, session_options=None):
        self._store = session_store
        self._messages = message_store
        self._trigger = agent_trigger
        self._registry = registry
        self._lock = threading.Lock()
        self._planner_reviews: dict[int, dict] = {}
        self._planner_autonomy_reviews: dict[str, dict] = {}
        self._loop_guard: dict[int, dict] = {}
        self._session_options = dict(session_options or {})
        self._compact_prompts = bool(self._session_options.get("compact_prompts", True))
        self._non_productive_loop_enabled = bool(
            self._session_options.get("non_productive_loop_enabled", True)
        )
        self._non_productive_loop_limit = max(
            1,
            int(self._session_options.get("non_productive_loop_limit", 2) or 2),
        )

        # Hook into message stream
        self._messages.on_message(self._on_message)

    # --- Public API ---

    def start_session(self, template_id: str, channel: str, cast: dict,
                      started_by: str, goal: str = "") -> dict | None:
        """Start a new session. Returns the session dict or None on failure."""
        session = self._store.create(
            template_id=template_id,
            channel=channel,
            cast=cast,
            started_by=started_by,
            goal=goal,
        )
        if not session:
            return None

        log.info("Session %d started: %s in #%s", session["id"],
                 session["template_name"], channel)

        # Trigger the first participant
        self._trigger_current(session)
        return session

    def emit_current_phase_banner(self, session: dict):
        """Post the banner for the session's current phase."""
        tmpl = self._store.get_template(session.get("template_id", ""))
        if not tmpl:
            return

        phases = tmpl.get("phases", [])
        phase_idx = session.get("current_phase", 0)
        if phase_idx >= len(phases):
            return

        phase = phases[phase_idx]
        self._messages.add(
            sender="system",
            text=f"Phase: {phase['name']}",
            msg_type="session_phase",
            channel=session.get("channel", "general"),
            metadata={
                "session_id": session["id"],
                "phase": phase_idx,
                "phase_name": phase["name"],
            },
        )

    def end_session(self, session_id: int, reason: str = "ended by user") -> dict | None:
        """End a session early."""
        session = self._store.interrupt(session_id, reason)
        if session:
            log.info("Session %d interrupted: %s", session_id, reason)
        return session

    def get_active(self, channel: str) -> dict | None:
        """Get the active session for a channel, enriched with phase info."""
        session = self._store.get_active(channel)
        if not session:
            return None
        return self._enrich(session)

    def get_allowed_agent(self, channel: str) -> str | None:
        """If a session is active on this channel, return the agent whose turn it is.
        Returns None if no session is active (meaning all agents are allowed)."""
        session = self._store.get_active(channel)
        if not session or session.get("state") not in ("active", "waiting"):
            return None
        return self._get_expected_agent(session)

    def list_active(self) -> list[dict]:
        """List all active/waiting/paused sessions, enriched for the frontend."""
        active = []
        for session in self._store.list_all():
            if session.get("state") in ("active", "waiting", "paused"):
                active.append(self._enrich(session))
        return active

    def resume_active_sessions(self):
        """On server restart, resume any sessions that were in progress.

        Only re-trigger 'active' sessions. 'waiting' sessions already had
        their trigger sent before the restart — re-triggering would
        double-queue the same participant. A separate stale-wait watchdog
        is responsible for recovering sessions whose expected participant
        never posts back.
        """
        for session in self._store.list_all():
            if session.get("state") == "active":
                log.info("Resuming session %d (%s) from phase %d, turn %d",
                         session["id"], session.get("template_name", "?"),
                         session["current_phase"], session["current_turn"])
                self._trigger_current(session)

    def recover_stale_waits(self, *, max_idle_seconds: float = 45.0) -> int:
        """Re-trigger agent turns that have been waiting too long.

        The current engine is message-driven: once a participant is queued,
        progress only resumes when the expected message appears in chat.
        If a wrapper stays alive but the CLI silently stalls after consuming
        the queue entry, the session can remain in ``waiting`` forever.
        This watchdog nudges only stale, agent-owned waits and lets
        ``set_waiting`` refresh the timestamp so retries are rate-limited.
        """
        recovered = 0
        now = time.time()

        for session in self._store.list_all():
            if session.get("state") != "waiting":
                continue

            expected_agent = self._get_expected_agent(session)
            if not expected_agent or not self._is_agent(expected_agent):
                continue

            updated_at = float(session.get("updated_at") or 0)
            idle_for = now - updated_at
            if idle_for < max_idle_seconds:
                continue

            if self._agent_appears_busy(expected_agent):
                continue

            log.warning(
                "Session %d stalled waiting on %s for %.1fs — re-triggering",
                session["id"],
                expected_agent,
                idle_for,
            )
            self._trigger_current(session)
            recovered += 1

        return recovered

    def trigger_periodic_planner_reviews(
        self,
        *,
        idle_seconds: float = 180.0,
        repeat_seconds: float = 300.0,
    ) -> int:
        """Periodically wake the planner to supervise active work.

        The session template only gives the planner explicit turns during the
        initial planning phase and the next-slice loop. Between those turns the
        planner can stay idle even if the current work stalls, drifts, or needs
        a better follow-up slice. This watchdog nudges the planner out-of-band
        without changing the session turn owner.
        """
        triggered = 0
        now = time.time()
        active_session_ids: set[int] = set()

        for session in self._store.list_all():
            if session.get("state") not in ("active", "waiting"):
                continue

            session_id = int(session.get("id") or 0)
            if not session_id:
                continue
            active_session_ids.add(session_id)

            planner = self._resolve_current_agent(session, "planner")
            if not planner or not self._is_agent(planner):
                continue

            if self._get_expected_role(session) == "planner":
                self._remember_planner_review(session_id, self._planner_progress_key(session), last_wake_at=0.0)
                continue

            if self._agent_appears_busy(planner):
                continue

            progress_key = self._planner_progress_key(session)
            review_state = self._remember_planner_review(session_id, progress_key)

            idle_for = now - float(session.get("updated_at") or session.get("started_at") or now)
            if idle_for < idle_seconds:
                continue

            last_wake_at = float(review_state.get("last_wake_at") or 0.0)
            if last_wake_at and (now - last_wake_at) < repeat_seconds:
                continue

            tmpl = self._store.get_template(session.get("template_id", ""))
            prompt = self._assemble_planner_watchdog_prompt(session, tmpl)
            channel = session.get("channel", "general")

            log.info(
                "Session %d: waking planner %s after %.1fs without progress",
                session_id,
                planner,
                idle_for,
            )
            try:
                self._trigger.trigger_sync(planner, channel=channel, prompt=prompt)
            except Exception as exc:
                log.error("Session %d: failed to wake planner %s: %s", session_id, planner, exc)
                continue

            self._remember_planner_review(session_id, progress_key, last_wake_at=now)
            triggered += 1

        with self._lock:
            stale_session_ids = set(self._planner_reviews) - active_session_ids
            for stale_session_id in stale_session_ids:
                self._planner_reviews.pop(stale_session_id, None)

        return triggered

    def trigger_autonomous_planner_cycles(
        self,
        *,
        channels: list[str],
        template_id: str,
        idle_seconds: float = 300.0,
        repeat_seconds: float = 600.0,
        default_goal: str = "",
    ) -> int:
        """Wake the planner when no session is active so work can continue.

        This is intentionally separate from the normal session turn flow.
        When a channel has no active session, the planner becomes the agent that
        decides whether to restart corrective work, adapt the roadmap, or kick
        off the next feature cycle.
        """
        triggered = 0
        now = time.time()
        live_channels = set(channels)

        for channel in channels:
            session = self._store.get_active(channel)
            if session and session.get("state") in ("active", "waiting", "paused"):
                with self._lock:
                    self._planner_autonomy_reviews.pop(channel, None)
                continue

            planner = self._resolve_role_agent("planner")
            if not planner or not self._is_agent(planner):
                continue
            if self._agent_appears_busy(planner):
                continue

            last_session = self._get_last_session(channel)
            latest_messages = self._messages.get_recent(1, channel=channel)
            latest_message = latest_messages[-1] if latest_messages else None
            latest_message_id = latest_message.get("id", -1) if latest_message else -1
            observed_at = max(
                float(latest_message.get("timestamp") or 0.0) if latest_message else 0.0,
                float(last_session.get("updated_at") or 0.0) if last_session else 0.0,
            )
            progress_key = (
                latest_message_id,
                last_session.get("id") if last_session else None,
                last_session.get("state") if last_session else None,
                last_session.get("output_message_id") if last_session else None,
            )
            autonomy_state = self._remember_planner_autonomy_review(
                channel,
                progress_key,
                observed_at=observed_at or now,
            )

            idle_since = max(float(autonomy_state.get("observed_at") or 0.0), observed_at)
            if idle_since and (now - idle_since) < idle_seconds:
                continue

            last_wake_at = float(autonomy_state.get("last_wake_at") or 0.0)
            if last_wake_at and (now - last_wake_at) < repeat_seconds:
                continue

            prompt = self._assemble_planner_autonomy_prompt(
                channel=channel,
                template_id=template_id,
                default_goal=default_goal,
                last_session=last_session,
            )

            log.info(
                "Channel #%s: waking planner %s to continue autonomous work",
                channel,
                planner,
            )
            try:
                self._trigger.trigger_sync(planner, channel=channel, prompt=prompt)
            except Exception as exc:
                log.error("Channel #%s: failed to wake planner %s: %s", channel, planner, exc)
                continue

            self._remember_planner_autonomy_review(
                channel,
                progress_key,
                observed_at=observed_at or now,
                last_wake_at=now,
            )
            triggered += 1

        with self._lock:
            stale_channels = set(self._planner_autonomy_reviews) - live_channels
            for stale_channel in stale_channels:
                self._planner_autonomy_reviews.pop(stale_channel, None)

        return triggered

    def _is_agent(self, name: str) -> bool:
        """Check if name belongs to a registered agent (not a human)."""
        if self._registry:
            return self._registry.is_registered(name)
        return False

    def _message_targets_expected_turn(self, msg: dict, expected_agent: str, expected_role: str | None) -> bool:
        text = str(msg.get("text", "") or "")
        mentions = {name.lower() for name in _MENTION_RE.findall(text)}
        if not mentions:
            return False

        candidates = {expected_agent.lower()} if expected_agent else set()
        if expected_role:
            candidates.add(expected_role.lower())
        return bool(mentions & candidates)

    def _get_agent_display_name(self, agent_name: str | None, role: str | None = None) -> str | None:
        if agent_name and self._registry:
            try:
                inst = self._registry.get_instance(agent_name)
            except Exception:
                inst = None
            if inst:
                display_name = str(inst.get("display_name", "")).strip()
                if display_name:
                    return display_name
                label = str(inst.get("label", "")).strip()
                if label:
                    return label

        if role:
            return role.replace("_", " ").replace("-", " ").title()
        return agent_name

    def _agent_appears_busy(self, agent_name: str) -> bool:
        """Best-effort check to avoid re-queueing an agent mid-activity."""
        get_status = getattr(self._trigger, "get_status", None)
        if not callable(get_status):
            return False
        try:
            status = get_status() or {}
        except Exception:
            return False
        agent_status = status.get(agent_name, {})
        return bool(agent_status.get("busy"))

    def _resolve_role_agent(self, role: str) -> str | None:
        """Find a live runtime carrying the requested role label."""
        if self._is_agent(role):
            return role
        if not self._registry:
            return None

        role_key = role.strip().lower()
        for name, info in self._registry.get_all().items():
            label = str(info.get("label", "")).strip().lower()
            if label == role_key:
                return name

        return None

    def _planner_progress_key(self, session: dict) -> tuple:
        return (
            session.get("state"),
            session.get("current_phase"),
            session.get("current_turn"),
            session.get("last_message_id"),
            session.get("waiting_on"),
        )

    def _remember_planner_review(self, session_id: int, progress_key: tuple, *, last_wake_at: float | None = None) -> dict:
        with self._lock:
            state = self._planner_reviews.setdefault(
                session_id,
                {"progress_key": progress_key, "last_wake_at": 0.0},
            )
            if state.get("progress_key") != progress_key:
                state["progress_key"] = progress_key
                state["last_wake_at"] = 0.0
            if last_wake_at is not None:
                state["last_wake_at"] = last_wake_at
            return dict(state)

    def _remember_planner_autonomy_review(
        self,
        channel: str,
        progress_key: tuple,
        *,
        observed_at: float,
        last_wake_at: float | None = None,
    ) -> dict:
        with self._lock:
            state = self._planner_autonomy_reviews.setdefault(
                channel,
                {"progress_key": progress_key, "observed_at": observed_at, "last_wake_at": 0.0},
            )
            if state.get("progress_key") != progress_key:
                state["progress_key"] = progress_key
                state["observed_at"] = observed_at
                state["last_wake_at"] = 0.0
            else:
                state["observed_at"] = max(float(state.get("observed_at") or 0.0), observed_at)
            if last_wake_at is not None:
                state["last_wake_at"] = last_wake_at
            return dict(state)

    def _get_last_session(self, channel: str) -> dict | None:
        sessions = self._store.list_all(channel=channel)
        if not sessions:
            return None
        return max(sessions, key=lambda item: float(item.get("updated_at") or item.get("started_at") or 0.0))

    # --- Message callback ---

    def _on_message(self, msg: dict):
        """Called on every new chat message. Checks if it advances a session."""
        channel = msg.get("channel", "general")
        sender = msg.get("sender", "")

        # Ignore system-generated messages (banners, phase markers, etc.)
        if sender == "system" or msg.get("type", "chat") != "chat":
            return

        session = self._store.get_active(channel)
        if not session:
            return

        expected_agent = self._get_expected_agent(session)
        if not expected_agent:
            return

        expected_role = self._get_expected_role(session)
        allowed_senders = {expected_agent}
        if expected_role:
            allowed_senders.add(expected_role)

        cast_agents = set(session.get("cast", {}).values())
        cast_roles = set(session.get("cast", {}).keys())
        sender_is_agent = self._is_agent(sender) or sender in cast_agents or sender in cast_roles

        # Agent not in this session's cast — ignore
        if sender_is_agent and sender not in cast_agents and sender not in cast_roles:
            return

        if not sender_is_agent and self._is_agent(expected_agent):
            if self._message_targets_expected_turn(msg, expected_agent, expected_role):
                if session["state"] == "paused":
                    resumed = self._store.resume(session["id"])
                    if resumed:
                        session = resumed
                        self._trigger_current(session)
                log.info("Session %d kept active: human nudge for %s by %s",
                         session["id"], expected_agent, sender)
                return

            if sender not in allowed_senders:
                self._store.pause(session["id"])
                log.info("Session %d paused: human interruption by %s", session["id"], sender)
                return

        if sender in allowed_senders:
            # Auto-resume if paused
            if session["state"] == "paused":
                self._store.resume(session["id"])
            # Defer advance slightly so the triggering message broadcasts
            # before phase/completion banners are added
            threading.Timer(0.3, self._advance, args=(session, msg["id"])).start()
            return

        # Wrong agent spoke - ignore
        return

    # --- Engine core ---

    def _advance(self, session: dict, message_id: int):
        """Advance session after the expected agent has responded."""
        tmpl = self._store.get_template(session["template_id"])
        if not tmpl:
            self._store.interrupt(session["id"], "template not found")
            return

        phases = tmpl.get("phases", [])
        phase_idx = session["current_phase"]
        turn_idx = session["current_turn"]

        if phase_idx >= len(phases):
            self._store.complete(session["id"], message_id)
            return

        phase = phases[phase_idx]
        participants = phase.get("participants", [])

        next_turn = turn_idx + 1
        if next_turn < len(participants):
            # More turns in this phase
            session = self._store.advance_turn(session["id"], message_id)
            if session:
                self._trigger_current(session)
        else:
            # Phase complete
            if self._phase_is_complete(session, phase):
                self._store.complete(session["id"], message_id)
                log.info("Session %d complete via phase '%s' gate", session["id"], phase["name"])
                return

            next_phase = phase_idx + 1
            if next_phase < len(phases):
                # More phases
                session = self._store.advance_phase(session["id"], message_id)
                if session:
                    next_phase_obj = phases[next_phase]
                    self._messages.add(
                        sender="system",
                        text=f"Phase: {next_phase_obj['name']}",
                        msg_type="session_phase",
                        channel=session.get("channel", "general"),
                        metadata={"session_id": session["id"],
                                  "phase": next_phase, "phase_name": next_phase_obj["name"]},
                    )
                    self._trigger_current(session)
            else:
                loop_to_phase = phase.get("loop_to_phase")
                if isinstance(loop_to_phase, int) and 0 <= loop_to_phase < len(phases):
                    if self._maybe_pause_non_productive_loop(session, phases, phase_idx):
                        return
                    session = self._store.jump_to_phase(session["id"], loop_to_phase, message_id)
                    if session:
                        next_phase_obj = phases[loop_to_phase]
                        self._messages.add(
                            sender="system",
                            text=f"Phase: {next_phase_obj['name']}",
                            msg_type="session_phase",
                            channel=session.get("channel", "general"),
                            metadata={"session_id": session["id"],
                                      "phase": loop_to_phase,
                                      "phase_name": next_phase_obj["name"]},
                        )
                        self._trigger_current(session)
                    return

                # Session complete - check if this was the output phase
                is_output = phase.get("is_output", False)
                self._store.complete(session["id"],
                                     message_id if is_output else None)
                log.info("Session %d complete", session["id"])

    def _trigger_current(self, session: dict):
        """Trigger the agent whose turn it is."""
        tmpl = self._store.get_template(session["template_id"])
        if not tmpl:
            return

        phases = tmpl.get("phases", [])
        phase_idx = session["current_phase"]
        turn_idx = session["current_turn"]

        if phase_idx >= len(phases):
            return

        phase = phases[phase_idx]
        participants = phase.get("participants", [])

        if turn_idx >= len(participants):
            return

        role = participants[turn_idx]
        agent = self._resolve_current_agent(session, role)

        if not agent:
            log.warning("Session %d: no agent cast for role '%s'", session["id"], role)
            self._store.interrupt(session["id"], f"no agent for role '{role}'")
            return

        if not self._is_agent(agent):
            # Human's turn - just mark as waiting, don't trigger
            self._store.set_waiting(session["id"], agent)
            return

        # Mark waiting
        self._store.set_waiting(session["id"], agent)

        # Assemble the prompt
        prompt = self._assemble_prompt(session, tmpl, phase, role)

        # Trigger the agent
        channel = session.get("channel", "general")
        log.info("Session %d: triggering %s (%s) for phase '%s'",
                 session["id"], agent, role, phase["name"])

        try:
            self._trigger.trigger_sync(agent, channel=channel, prompt=prompt)
        except Exception as exc:
            log.error("Session %d: failed to trigger %s: %s",
                      session["id"], agent, exc)

    def _assemble_prompt(self, session: dict, tmpl: dict, phase: dict,
                         role: str) -> str:
        """Build the session-aware prompt for an agent."""
        phases = tmpl.get("phases", [])
        phase_idx = session["current_phase"]
        total_phases = len(phases)

        channel = session.get("channel", "general")
        lines = [f"SESSION: {tmpl.get('name', '?')}"]
        if session.get("goal"):
            lines.append(f"GOAL: {session['goal']}")
        lines.append(f"PHASE: {phase['name']} ({phase_idx + 1}/{total_phases})")
        lines.append(f"YOUR ROLE: {role}")
        lines.append(f"TASK: {phase.get('prompt', '')}")

        # Dissent mandate for review/critique roles
        if role.lower() in _DISSENT_ROLES:
            lines.append("Independent judgment only.")

        completion_marker = phase.get("complete_when_all_contain")
        if isinstance(completion_marker, str) and completion_marker.strip():
            lines.append(
                f"Write '{completion_marker}' only if the work is fully complete with no material gaps."
            )

        if isinstance(phase.get("loop_to_phase"), int):
            lines.append("After your message, the session auto-continues.")

        lines.append(f"Read recent #{channel} context, then reply via chat_send in #{channel}. No terminal-only response.")
        if self._compact_prompts:
            lines.append(_PROMPT_BREVITY_LINE)

        # Use double newlines to ensure separation in TUIs that might collapse single newlines
        return "\n\n".join(lines)

    def _assemble_planner_watchdog_prompt(self, session: dict, tmpl: dict | None) -> str:
        """Build a concise out-of-turn planner heartbeat prompt."""
        channel = session.get("channel", "general")
        phase_name = "unknown"
        current_role = self._get_expected_role(session) or "unknown"
        current_agent = self._get_expected_agent(session) or session.get("waiting_on") or "unknown"

        if tmpl:
            phases = tmpl.get("phases", [])
            phase_idx = int(session.get("current_phase") or 0)
            if 0 <= phase_idx < len(phases):
                phase_name = phases[phase_idx].get("name", phase_name)

        current_agent_display = self._get_agent_display_name(current_agent, current_role) or current_agent

        lines = [
            f"PLANNER HEARTBEAT: {tmpl.get('name', session.get('template_name', '?')) if tmpl else session.get('template_name', '?')}",
        ]
        if session.get("goal"):
            lines.append(f"GOAL: {session['goal']}")
        lines.extend([
            f"CURRENT PHASE: {phase_name}",
            f"CURRENT TURN OWNER: {current_role} ({current_agent_display})",
            "Out-of-turn supervision only.",
            "Inspect recent chat, repo state, and evidence.",
            "If work is stalled, drifting, or under-validated, post one concrete correction.",
            f"Use chat_read or chat_summary for #{channel}. If you have nothing materially new, stay silent.",
        ])
        if self._compact_prompts:
            lines.append(_WATCHDOG_BREVITY_LINE)
        return "\n\n".join(lines)

    def _assemble_planner_autonomy_prompt(
        self,
        *,
        channel: str,
        template_id: str,
        default_goal: str,
        last_session: dict | None,
    ) -> str:
        """Build the planner prompt used when no active session exists."""
        lines = [
            "PLANNER AUTONOMY HEARTBEAT",
            f"There is currently no active session in #{channel}.",
            "You own continuous product evolution for this channel.",
        ]

        if last_session:
            lines.extend([
                f"LAST SESSION TEMPLATE: {last_session.get('template_name', last_session.get('template_id', '?'))}",
                f"LAST SESSION STATE: {last_session.get('state', 'unknown')}",
            ])
            if last_session.get("goal"):
                lines.append(f"LAST SESSION GOAL: {last_session['goal']}")

        lines.extend([
            f"DEFAULT CONTINUATION TEMPLATE: {template_id}",
        ])
        if default_goal:
            lines.append(f"DEFAULT GOAL BASELINE: {default_goal}")

        lines.extend([
            "Inspect recent chat, current repo state, and the latest evidence before acting.",
            "If the previous work is still below bar, start the next corrective cycle immediately.",
            "If the current task is truly complete, decide the next meaningful evolution: corrections, adaptations, research, or a scoped new feature.",
            "Do not wait for a human unless there is a real blocker. Do not restart identical work blindly without naming the next concrete objective.",
            f"Use session_active(channel='{channel}') to inspect state. If a concrete next cycle is warranted, use session_start(sender='your_identity', template_id='{template_id}', channel='{channel}', goal='...') to launch it.",
            f"If you need to communicate strategic direction first, use chat_send in #{channel}. Otherwise start the session directly and keep momentum.",
        ])
        if self._compact_prompts:
            lines.append(_WATCHDOG_BREVITY_LINE)
        return "\n\n".join(lines)

    def _maybe_pause_non_productive_loop(self, session: dict, phases: list[dict], phase_idx: int) -> bool:
        """Pause sessions that are repeating the same no-progress loop."""
        if not self._non_productive_loop_enabled:
            return False

        signal = self._build_loop_guard_signal(session, phases, phase_idx)
        session_id = int(session.get("id") or 0)

        if not signal:
            with self._lock:
                self._loop_guard.pop(session_id, None)
            return False

        with self._lock:
            state = self._loop_guard.setdefault(session_id, {"signature": signal.signature, "count": 0})
            if state.get("signature") == signal.signature:
                state["count"] = int(state.get("count") or 0) + 1
            else:
                state["signature"] = signal.signature
                state["count"] = 1
            count = int(state["count"])

        if count < self._non_productive_loop_limit:
            return False

        paused = self._store.pause(session_id)
        if not paused:
            return False

        message = self._build_loop_guard_message(signal, count)
        self._messages.add(
            sender="system",
            text=message,
            msg_type="session_guard",
            channel=session.get("channel", "general"),
            metadata={"session_id": session_id, "guard": "non_productive_loop", "count": count},
        )
        log.warning(
            "Session %d paused by moderator guard after %d repeated stagnant cycles (%s)",
            session_id,
            count,
            signal.target,
        )
        return True

    def _build_loop_guard_signal(self, session: dict, phases: list[dict], phase_idx: int) -> _LoopGuardSignal | None:
        """Return a signature when the current loop has no material progress."""
        planner_role = self._get_expected_role(session) or "planner"
        implement_idx = self._find_phase_index(phases, "Implement")
        assess_idx = self._find_phase_index(phases, "Assess")
        if implement_idx is None or assess_idx is None:
            return None

        implement_messages = self._get_phase_messages_for_index(session, phases, implement_idx)
        assess_messages = self._get_phase_messages_for_index(session, phases, assess_idx)
        current_messages = self._get_phase_messages_for_index(session, phases, phase_idx)
        if not implement_messages or len(assess_messages) < 2 or not current_messages:
            return None

        implement_text = "\n".join(msg.get("text", "") for msg in implement_messages)
        no_file_changes = bool(_NO_FILE_CHANGES_RE.search(implement_text))
        non_actionable_reply = bool(_NON_ACTIONABLE_REPLY_RE.search(implement_text))
        if not no_file_changes and not non_actionable_reply:
            return None

        assess_texts = [msg.get("text", "") for msg in assess_messages]
        if not all("final_status: continue" in text.lower() for text in assess_texts):
            return None

        planner_text = "\n".join(msg.get("text", "") for msg in current_messages)
        target = self._extract_next_slice_target(planner_text) or "repeated no-progress next slice"
        signature = f"{planner_role.lower()}|{target}"
        return _LoopGuardSignal(signature=signature, target=target, stagnant_role="implementer")

    def _build_loop_guard_message(self, signal: _LoopGuardSignal, count: int) -> str:
        return (
            f"Moderator stop: pausing after {count} consecutive non-productive cycles. "
            f"Latest implementer turn reported no material output or only a non-actionable reply, Assess still returned CONTINUE, "
            f"and planner kept the same target: {signal.target}. "
            "Do not relaunch this loop until there is a new method, new evidence, or a final blocker decision."
        )

    def _find_phase_index(self, phases: list[dict], name: str) -> int | None:
        target = name.strip().lower()
        for idx, phase in enumerate(phases):
            if str(phase.get("name", "")).strip().lower() == target:
                return idx
        return None

    def _get_phase_messages_for_index(self, session: dict, phases: list[dict], phase_idx: int) -> list[dict]:
        if phase_idx < 0 or phase_idx >= len(phases):
            return []
        participants = phases[phase_idx].get("participants", [])
        if not participants:
            return []

        recent = self._messages.get_recent(400, channel=session.get("channel", "general"))
        start_idx = 0
        for idx in range(len(recent) - 1, -1, -1):
            msg = recent[idx]
            meta = msg.get("metadata", {})
            if (
                msg.get("type") == "session_phase"
                and meta.get("session_id") == session.get("id")
                and meta.get("phase") == phase_idx
            ):
                start_idx = idx + 1
                break

        phase_messages = recent[start_idx:]
        latest_by_sender = {}
        for msg in phase_messages:
            sender = msg.get("sender", "")
            if sender in participants and msg.get("type", "chat") == "chat":
                latest_by_sender[sender] = msg
        return [latest_by_sender[p] for p in participants if p in latest_by_sender]

    def _extract_next_slice_target(self, text: str) -> str:
        match = _NEXT_SLICE_TARGET_RE.search(text or "")
        if not match:
            return ""
        return re.sub(r"\s+", " ", match.group(1).strip().lower())

    def _get_expected_agent(self, session: dict) -> str | None:
        """Get the agent name expected to respond next."""
        tmpl = self._store.get_template(session["template_id"])
        if not tmpl:
            return None

        phases = tmpl.get("phases", [])
        phase_idx = session["current_phase"]
        turn_idx = session["current_turn"]

        if phase_idx >= len(phases):
            return None

        phase = phases[phase_idx]
        participants = phase.get("participants", [])

        if turn_idx >= len(participants):
            return None

        role = participants[turn_idx]
        return self._resolve_current_agent(session, role)

    def _get_expected_role(self, session: dict) -> str | None:
        """Get the role name expected to respond next."""
        tmpl = self._store.get_template(session["template_id"])
        if not tmpl:
            return None

        phases = tmpl.get("phases", [])
        phase_idx = session["current_phase"]
        turn_idx = session["current_turn"]

        if phase_idx >= len(phases):
            return None

        participants = phases[phase_idx].get("participants", [])
        if turn_idx >= len(participants):
            return None

        return participants[turn_idx]

    def _resolve_current_agent(self, session: dict, role: str) -> str | None:
        """Resolve the live runtime for a session role.

        Session casts persist the runtime name captured at session start, but
        wrappers can restart and come back with a new canonical instance name.
        Prefer the still-registered cast entry when available, else rebind the
        role to the currently registered runtime that carries the same role
        label or resolved rename target.
        """
        cast = session.get("cast", {})
        agent = cast.get(role)
        if not agent:
            return None

        def _persist(new_agent: str) -> str:
            if new_agent == agent:
                return new_agent
            updated = self._store.update_cast_agent(session["id"], role, new_agent)
            cast[role] = new_agent
            if updated:
                session.update(updated)
            return new_agent

        instances = self._registry.get_all() if self._registry else {}
        role_key = role.strip().lower()
        current_info = instances.get(agent)

        def _family_for(name: str, info: dict | None = None) -> str:
            if info and info.get("base"):
                return str(info.get("base"))
            if "-" in name:
                return name.split("-", 1)[0]
            return name

        current_family = _family_for(agent, current_info)

        role_match = None
        for name, info in instances.items():
            label = str(info.get("label", "")).strip().lower()
            if label == role_key and _family_for(name, info) == current_family:
                role_match = name
                break

        if self._is_agent(agent):
            current_label = str(current_info.get("label", "")).strip().lower() if current_info else ""
            if role_match and role_match != agent and current_label != role_key:
                return _persist(role_match)
            return agent

        if not self._registry:
            return agent

        if role_match:
            return _persist(role_match)

        try:
            resolved_name = self._registry.resolve_name(agent)
        except Exception:
            resolved_name = agent
        if resolved_name != agent and self._is_agent(resolved_name):
            return _persist(resolved_name)

        expected_base = None
        info = instances.get(agent)
        if info:
            expected_base = info.get("base")
        elif "-" in agent:
            expected_base = agent.split("-", 1)[0]

        if expected_base:
            family = [name for name, info in instances.items() if info.get("base") == expected_base]
            if len(family) == 1:
                return _persist(family[0])

        return agent

    def _phase_is_complete(self, session: dict, phase: dict) -> bool:
        """Return True when a phase explicitly signals session completion."""
        completion_marker = phase.get("complete_when_all_contain")
        if not isinstance(completion_marker, str) or not completion_marker.strip():
            return False

        participants = phase.get("participants", [])
        if not participants:
            return False

        phase_messages = self._get_phase_messages(session, participants)
        if len(phase_messages) != len(participants):
            return False

        marker = completion_marker.strip().lower()
        return all(marker in msg.get("text", "").lower() for msg in phase_messages)

    def _get_phase_messages(self, session: dict, participants: list[str]) -> list[dict]:
        """Get the latest response from each phase participant since the phase banner."""
        recent = self._messages.get_recent(200, channel=session.get("channel", "general"))
        phase_idx = session.get("current_phase", 0)
        start_idx = 0

        for idx in range(len(recent) - 1, -1, -1):
            msg = recent[idx]
            meta = msg.get("metadata", {})
            if (
                msg.get("type") == "session_phase"
                and meta.get("session_id") == session.get("id")
                and meta.get("phase") == phase_idx
            ):
                start_idx = idx + 1
                break

        phase_messages = recent[start_idx:]
        latest_by_sender = {}
        for msg in phase_messages:
            sender = msg.get("sender", "")
            if sender in participants and msg.get("type", "chat") == "chat":
                latest_by_sender[sender] = msg

        return [latest_by_sender[p] for p in participants if p in latest_by_sender]

    def _enrich(self, session: dict) -> dict:
        """Add computed fields to a session dict for the frontend."""
        tmpl = self._store.get_template(session["template_id"])
        current_role = None
        if tmpl:
            phases = tmpl.get("phases", [])
            session["total_phases"] = len(phases)
            phase_idx = session["current_phase"]
            if phase_idx < len(phases):
                phase = phases[phase_idx]
                session["phase_name"] = phase["name"]
                participants = phase.get("participants", [])
                turn_idx = session["current_turn"]
                if turn_idx < len(participants):
                    role = participants[turn_idx]
                    current_role = role
                    session["current_role"] = role
                    session["current_agent"] = self._resolve_current_agent(session, role)
                    session["current_agent_display"] = self._get_agent_display_name(
                        session.get("current_agent"),
                        role,
                    )
        waiting_on = session.get("waiting_on")
        if waiting_on:
            session["waiting_on_display"] = self._get_agent_display_name(waiting_on, current_role)
        return session
