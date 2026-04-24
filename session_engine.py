"""Session engine — orchestrates structured multi-agent sessions."""

import logging
import threading
import time

log = logging.getLogger(__name__)

# Dissent mandate injected for review/critique roles
_DISSENT_LINE = "Provide your own independent analysis. Do not repeat or defer to other participants."

# Roles that get the dissent mandate
_DISSENT_ROLES = {"reviewer", "red_team", "critic", "challenger", "against"}


class SessionEngine:
    """Orchestrates session turn flow on top of existing chat infrastructure.

    Listens to message store callbacks, advances session state, and triggers
    agents via the AgentTrigger system.
    """

    def __init__(self, session_store, message_store, agent_trigger, registry=None):
        self._store = session_store
        self._messages = message_store
        self._trigger = agent_trigger
        self._registry = registry
        self._lock = threading.Lock()

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
        double-queue the same participant.
        """
        for session in self._store.list_all():
            if session.get("state") == "active":
                log.info("Resuming session %d (%s) from phase %d, turn %d",
                         session["id"], session.get("template_name", "?"),
                         session["current_phase"], session["current_turn"])
                self._trigger_current(session)

    def _is_agent(self, name: str) -> bool:
        """Check if name belongs to a registered agent (not a human)."""
        if self._registry:
            return self._registry.is_registered(name)
        return False

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

        cast_agents = set(session.get("cast", {}).values())
        sender_is_agent = self._is_agent(sender)

        # Agent not in this session's cast — ignore
        if sender_is_agent and sender not in cast_agents:
            return

        # Human spoke but it's not their turn — pause if an agent is expected
        if not sender_is_agent and sender != expected_agent and self._is_agent(expected_agent):
            self._store.pause(session["id"])
            log.info("Session %d paused: human interruption by %s", session["id"], sender)
            return

        if sender == expected_agent:
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
        cast = session.get("cast", {})
        agent = cast.get(role)

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
        lines = [
            f"SESSION: {tmpl.get('name', '?')}",
        ]
        if session.get("goal"):
            lines.append(f"GOAL: {session['goal']}")
        lines.append(f"PHASE: {phase['name']} ({phase_idx + 1}/{total_phases})")
        lines.append(f"YOUR ROLE: {role}")
        lines.append(f"INSTRUCTION: {phase.get('prompt', '')}")

        # Dissent mandate for review/critique roles
        if role.lower() in _DISSENT_ROLES:
            lines.append(f"\n{_DISSENT_LINE}")

        completion_marker = phase.get("complete_when_all_contain")
        if isinstance(completion_marker, str) and completion_marker.strip():
            lines.append(
                f"This phase decides whether the session ends. Include the exact line '{completion_marker}' only if the work is fully complete with no material gaps."
            )

        if isinstance(phase.get("loop_to_phase"), int):
            lines.append("After your message, the session will automatically continue into the next work cycle.")

        lines.append("")
        lines.append(f"IMPORTANT: You MUST respond using the 'chat_send' tool in the #{channel} channel. "
                      "The session flow is blocked until your message appears in the chat. "
                      "Do NOT respond only in your terminal.")
        lines.append("Read recent messages in the channel for context (use 'chat_read' or 'mcp read'), "
                      "then post your response. Stay focused on the session goal.")

        # Use double newlines to ensure separation in TUIs that might collapse single newlines
        return "\n\n".join(lines)

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
        cast = session.get("cast", {})
        return cast.get(role)

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
                    session["current_role"] = role
                    session["current_agent"] = session.get("cast", {}).get(role)
        return session
