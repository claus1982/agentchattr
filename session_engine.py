"""Session engine — orchestrates structured multi-agent sessions."""

import logging
import os
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
_BLOCKER_LINE_RE = re.compile(r"^blocker\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_BLOCKER_DETAIL_RE = re.compile(r"(?ms)^BLOCKER\s*$.*?^DETAIL:\s*(.+)$")
_GAPS_LINE_RE = re.compile(r"^gaps\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_BLOCKER_REPLY_RE = re.compile(
    r"(?:\bblock(?:ed|er)\b|\bmissing\b[^\n]{0,80}\b(?:png|proof|artifact|screenshot)s?\b|\bexternal(?:/manual)?\b[^\n]{0,80}\b(?:capture|proof|artifact|dependency)\b)",
    re.IGNORECASE,
)
_PROMPT_BREVITY_LINE = (
    "Be concise: prefer <=8 short lines, only new evidence/decisions/blockers, no recap."
)
_WATCHDOG_BREVITY_LINE = "Respond only if you have materially new direction. Keep it brief."
_SAFE_MODE_TRUE_VALUES = {"1", "true", "yes", "on"}

_SESSION_OUTPUT_CONTRACTS = {
    "intake": [
        "Return exactly these 4 lines:",
        "Client goal: ...",
        "Constraints/success bar: ...",
        "Missing inputs: none or ...",
        "Decision: Proceed to Plan. or Decision: BLOCKED because ...",
    ],
    "plan": [
        "Return exactly these 5 lines:",
        "Slice: ...",
        "Owner: ...",
        "Acceptance criteria: ...",
        "Required evidence: ...",
        "Dependencies/fallback: ...",
    ],
    "technical review": [
        "Return exactly these 4 lines:",
        "Feasibility: ...",
        "Hidden blockers: ...",
        "Execution contract: ...",
        "Decision: Proceed. or Decision: BLOCKED because ...",
    ],
    "execute": [
        "Return exactly these 4 lines:",
        "Work performed: ...",
        "Validation: ...",
        "Evidence: ...",
        "Blocker: none or ...",
    ],
    "assess": [
        "Return exactly these 4 lines:",
        "Assessment: ...",
        "Evidence check: ...",
        "Gaps: ...",
        "FINAL_STATUS: APPROVED or CONTINUE or BLOCKED",
    ],
    "command": [
        "Return exactly these 4 lines:",
        "Decision: ...",
        "Owner: ...",
        "Next command: ...",
        "Reason: ...",
    ],
}

_NON_ACTIONABLE_FALLBACKS = {
    "intake": lambda goal: [
        f"Client goal: {goal or 'Advance the current client request under the active product and UI contracts.'}",
        "Constraints/success bar: stay within the active contracts, keep ownership explicit, require evidence, and avoid speculative scope.",
        "Missing inputs: none blocking for initial planning; proceed using the current client brief and room context.",
        "Decision: Proceed to Plan.",
    ],
    "plan": lambda goal: [
        "Slice: Define and execute the first premium UI slice with visible user impact and low architectural risk.",
        "Owner: implementation_engineer",
        "Acceptance criteria: one concrete surface updated, premium states included, existing contracts respected, and mobile-first clarity preserved.",
        "Required evidence: touched files, focused validation, and at least one proof artifact or explicit blocker.",
        "Dependencies/fallback: if scope is still too broad, technical_review narrows it before execute.",
    ],
    "technical review": lambda goal: [
        "Feasibility: proceed with a presentation-first slice inside the current contracts and existing architecture.",
        "Hidden blockers: none proven yet beyond runtime autonomy limits; execution must surface concrete repo or tool blockers if they appear.",
        "Execution contract: implement one scoped slice, validate it narrowly, and report evidence or an exact blocker.",
        "Decision: Proceed.",
    ],
    "command": lambda goal: [
        "Decision: Continue with the next planned slice.",
        "Owner: product_manager",
        "Next command: convert the latest gaps into one concrete next slice and hand it to implementation_engineer.",
        "Reason: governance fallback kept the room moving after a non-actionable lead reply.",
    ],
}

# Roles that get the dissent mandate
_DISSENT_ROLES = {"reviewer", "red_team", "critic", "challenger", "against"}
_LEAD_ROLE_HINTS = ("planner", "moderator", "lead", "manager", "producer", "synthesiser", "proposer")
_PLANNING_ROLE_HINTS = ("planner", "producer", "proposer", "lead", "manager", "synthesiser")
_EXECUTION_ROLE_HINTS = ("implementer", "builder", "executor", "developer", "engineer")
_PHASE_KIND_ALIASES = {
    "frame": "frame",
    "discovery": "frame",
    "plan": "plan",
    "planning": "plan",
    "review": "review",
    "critique": "review",
    "execute": "execute",
    "execution": "execute",
    "implement": "execute",
    "assessment": "assess",
    "assess": "assess",
    "summary": "summary",
    "synthesis": "summary",
    "verdict": "decision",
    "decision": "decision",
    "other": "other",
}


@dataclass(frozen=True)
class _LoopGuardSignal:
    signature: str
    target: str
    stagnant_role: str
    reason: str


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
                      started_by: str, goal: str = "", session_options: dict | None = None) -> dict | None:
        """Start a new session. Returns the session dict or None on failure."""
        session = self._store.create(
            template_id=template_id,
            channel=channel,
            cast=cast,
            started_by=started_by,
            goal=goal,
            session_options=session_options,
        )
        if not session:
            return None

        log.info("Session %d started: %s in #%s", session["id"],
                 session["template_name"], channel)

        # Trigger the first participant
        self._trigger_current(session)
        latest = self._store.get(session["id"])
        return latest or session

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
        recent = self._messages.get_recent(8, channel=session.get("channel", "general"))
        for msg in reversed(recent):
            metadata = msg.get("metadata") or {}
            if (
                msg.get("type") == "session_phase"
                and metadata.get("session_id") == session.get("id")
                and metadata.get("phase") == phase_idx
                and metadata.get("phase_name") == phase.get("name")
            ):
                return

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

            tmpl = self._store.get_template(session.get("template_id", ""))
            lead_role, lead_agent = self._resolve_session_lead(session, tmpl)
            if not lead_role or not lead_agent or not self._is_agent(lead_agent):
                continue

            if self._roles_equal(self._get_expected_role(session), lead_role):
                self._remember_planner_review(session_id, self._planner_progress_key(session), last_wake_at=0.0)
                continue

            if self._agent_appears_busy(lead_agent):
                continue

            progress_key = self._planner_progress_key(session)
            review_state = self._remember_planner_review(session_id, progress_key)

            idle_for = now - float(session.get("updated_at") or session.get("started_at") or now)
            if idle_for < idle_seconds:
                continue

            last_wake_at = float(review_state.get("last_wake_at") or 0.0)
            if last_wake_at and (now - last_wake_at) < repeat_seconds:
                continue

            prompt = self._assemble_planner_watchdog_prompt(session, tmpl, lead_role)
            channel = session.get("channel", "general")

            log.info(
                "Session %d: waking session lead %s (%s) after %.1fs without progress",
                session_id,
                lead_agent,
                lead_role,
                idle_for,
            )
            try:
                self._trigger.trigger_sync(lead_agent, channel=channel, prompt=prompt)
            except Exception as exc:
                log.error("Session %d: failed to wake session lead %s: %s", session_id, lead_agent, exc)
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
        tmpl = self._store.get_template(template_id)
        governance = self._get_template_governance(tmpl)
        lead_role = governance.get("lead_role") or "planner"

        for channel in channels:
            session = self._store.get_active(channel)
            if session and session.get("state") in ("active", "waiting", "paused"):
                with self._lock:
                    self._planner_autonomy_reviews.pop(channel, None)
                continue

            lead_agent = self._resolve_role_agent(lead_role)
            if not lead_agent or not self._is_agent(lead_agent):
                continue
            if self._agent_appears_busy(lead_agent):
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
                tmpl=tmpl,
                lead_role=lead_role,
            )

            log.info(
                "Channel #%s: waking session lead %s (%s) to continue autonomous work",
                channel,
                lead_agent,
                lead_role,
            )
            try:
                self._trigger.trigger_sync(lead_agent, channel=channel, prompt=prompt)
            except Exception as exc:
                log.error("Channel #%s: failed to wake session lead %s: %s", channel, lead_agent, exc)
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

    def _annotate_session_message(
        self,
        msg: dict,
        session: dict,
        *,
        role: str | None,
        agent: str | None,
    ):
        """Stamp the triggering chat message with session role metadata."""
        if msg.get("id") is None:
            return

        metadata = dict(msg.get("metadata") or {})
        metadata["session_id"] = session.get("id")
        metadata["session_template_id"] = session.get("template_id")

        if role:
            metadata["session_role"] = role

        if agent:
            metadata["session_agent"] = agent

        tmpl = self._store.get_template(session.get("template_id", ""))
        if tmpl:
            phases = tmpl.get("phases", [])
            phase_idx = int(session.get("current_phase") or 0)
            if 0 <= phase_idx < len(phases):
                metadata["session_phase"] = phase_idx
                metadata["session_phase_name"] = phases[phase_idx].get("name")

        updated = self._messages.update_message(msg["id"], {"metadata": metadata})
        if updated:
            msg["metadata"] = metadata

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

    def _roles_equal(self, left: str | None, right: str | None) -> bool:
        return bool(left and right and left.strip().lower() == right.strip().lower())

    def _get_template_governance(self, tmpl: dict | None) -> dict:
        """Return normalized governance metadata with sensible fallbacks."""
        roles = tmpl.get("roles", []) if isinstance(tmpl, dict) else []
        canonical_roles = []
        role_lookup = {}
        for role in roles:
            if not isinstance(role, str):
                continue
            canonical = role.strip()
            if not canonical:
                continue
            canonical_roles.append(canonical)
            role_lookup[canonical.lower()] = canonical

        governance = tmpl.get("governance", {}) if isinstance(tmpl, dict) else {}
        if not isinstance(governance, dict):
            governance = {}

        def _match_role(value: str | None) -> str | None:
            if not isinstance(value, str):
                return None
            return role_lookup.get(value.strip().lower())

        def _match_role_list(values) -> list[str]:
            matched = []
            if not isinstance(values, list):
                return matched
            for item in values:
                role = _match_role(item)
                if role and role not in matched:
                    matched.append(role)
            return matched

        executor_roles = _match_role_list(governance.get("executor_roles"))
        review_roles = _match_role_list(governance.get("review_roles"))
        lead_role = _match_role(governance.get("lead_role"))
        planning_role = _match_role(governance.get("planning_role"))

        if not executor_roles:
            executor_roles = [role_lookup[hint] for hint in _EXECUTION_ROLE_HINTS if hint in role_lookup]

        if not review_roles:
            review_roles = [role_lookup[hint] for hint in _DISSENT_ROLES if hint in role_lookup]

        if not planning_role:
            for hint in _PLANNING_ROLE_HINTS:
                if hint in role_lookup:
                    planning_role = role_lookup[hint]
                    break

        if not lead_role:
            candidates = []
            if planning_role:
                candidates.append(planning_role)
            candidates.extend(role_lookup[hint] for hint in _LEAD_ROLE_HINTS if hint in role_lookup)
            for candidate in candidates:
                if candidate:
                    lead_role = candidate
                    break

        if not lead_role and canonical_roles:
            lead_role = canonical_roles[0]

        if not planning_role:
            planning_role = lead_role

        deterministic_phase_kinds = []
        raw_deterministic_phase_kinds = governance.get("deterministic_phase_kinds")
        if isinstance(raw_deterministic_phase_kinds, list):
            for item in raw_deterministic_phase_kinds:
                if not isinstance(item, str):
                    continue
                phase_kind = _PHASE_KIND_ALIASES.get(item.strip().lower(), item.strip().lower())
                if phase_kind in _PHASE_KIND_ALIASES.values() and phase_kind not in deterministic_phase_kinds:
                    deterministic_phase_kinds.append(phase_kind)

        autonomy_contract = str(governance.get("autonomy_contract") or "").strip().lower() or None
        client_escalation_threshold = (
            str(governance.get("client_escalation_threshold") or "").strip().lower() or "standard"
        )
        client_escalation_role = _match_role(governance.get("client_escalation_role"))
        quality_gate_role = _match_role(governance.get("quality_gate_role"))

        if not client_escalation_role:
            client_escalation_role = lead_role

        if not quality_gate_role:
            quality_gate_role = role_lookup.get("qa_reviewer")
        if not quality_gate_role and review_roles:
            quality_gate_role = review_roles[0]

        return {
            "lead_role": lead_role,
            "planning_role": planning_role,
            "executor_roles": executor_roles,
            "review_roles": review_roles,
            "deterministic_phase_kinds": deterministic_phase_kinds,
            "autonomy_contract": autonomy_contract,
            "client_escalation_threshold": client_escalation_threshold,
            "client_escalation_role": client_escalation_role,
            "quality_gate_role": quality_gate_role,
        }

    def _session_safe_mode(self, session: dict, tmpl: dict | None = None) -> bool:
        explicit = session.get("safe_mode")
        if explicit is not None:
            return bool(explicit)

        env_value = str(os.getenv("NORTHSTAR_SAFE_MODE", "") or "").strip().lower()
        if env_value in _SAFE_MODE_TRUE_VALUES:
            return True

        self._get_template_governance(tmpl or self._store.get_template(session.get("template_id", "")))
        return False

    def _handoff_contract_prompt_lines(self, *, mention_target: str, next_role: str | None) -> list[str]:
        return [
            "Use this exact HANDOFF block whenever work passes to the governed next owner:",
            "HANDOFF",
            f"TO: {mention_target}",
            f"ROLE: {next_role or 'next_owner'}",
            "ACTION: one concrete next action",
            "STATUS: what changed and what remains open",
        ]

    def _blocker_contract_prompt_lines(self, role: str) -> list[str]:
        return [
            "Use this exact BLOCKER block only for a true blocker:",
            "BLOCKER",
            f"OWNER: {role}",
            "TYPE: tool | permission | dependency | client",
            "DETAIL: exact blocker in one line",
            "ASK: the single unblock request or decision needed",
        ]

    def _recent_session_messages(self, session: dict, *, limit: int = 80) -> list[dict]:
        channel = session.get("channel", "general")
        session_id = session.get("id")
        recent = self._messages.get_recent(limit, channel=channel)
        return [
            msg
            for msg in recent
            if (msg.get("metadata") or {}).get("session_id") == session_id
        ]

    def _extract_latest_structured_line(self, messages: list[dict], pattern: re.Pattern[str]) -> str | None:
        for msg in reversed(messages):
            text = str(msg.get("text") or "")
            match = pattern.search(text)
            if match:
                value = match.group(1).strip()
                if value:
                    return value.rstrip(".")
        return None

    def _should_use_deterministic_turn(self, tmpl: dict, phase: dict) -> bool:
        governance = self._get_template_governance(tmpl)
        phase_kind = self._phase_kind(phase)
        deterministic_phase_kinds = set(governance.get("deterministic_phase_kinds") or [])
        return phase_kind in deterministic_phase_kinds

    def _build_deterministic_turn_output(self, session: dict, tmpl: dict, phase: dict, role: str) -> str | None:
        goal = str(session.get("goal") or "").strip()
        phase_name = str(phase.get("name") or "").strip().lower()
        session_messages = self._recent_session_messages(session)
        blocker = self._extract_blocker_signature(*[msg.get("text", "") for msg in session_messages])
        gaps = self._extract_latest_structured_line(session_messages, _GAPS_LINE_RE)
        safe_mode = self._session_safe_mode(session, tmpl)

        if phase_name == "intake":
            missing_inputs = "none blocking for initial planning" if goal else "exact client goal"
            decision = "Decision: Proceed to Plan." if goal else "Decision: BLOCKED because the client goal is missing."
            return "\n".join([
                f"Client goal: {goal or 'Advance the active client request under the current product, UI, and architecture contracts.'}",
                "Constraints/success bar: stay within active contracts, keep ownership explicit, require evidence, and avoid speculative scope.",
                f"Missing inputs: {missing_inputs}",
                decision,
            ])

        if phase_name == "plan":
            slice_line = (
                f"Resolve or prove the current blocker: {blocker}."
                if blocker
                else (gaps or "Define the highest-value premium UI slice that can be validated quickly.")
            )
            return "\n".join([
                f"Slice: {slice_line}",
                "Owner: implementation_engineer",
                "Acceptance criteria: one concrete visible slice lands, premium states are covered, and the result stays within the active contracts.",
                "Required evidence: touched files, focused validation, and at least one concrete proof artifact or an exact blocker.",
                "Dependencies/fallback: if scope is still too broad or blocked, technical_review must narrow it before execution continues.",
            ])

        if phase_name == "technical review":
            hidden_blockers = blocker or "none proven yet beyond what execution must verify"
            return "\n".join([
                "Feasibility: proceed with one scoped slice inside the current contracts and existing architecture.",
                f"Hidden blockers: {hidden_blockers}.",
                "Execution contract: implement the slice, run focused validation, and report concrete evidence or an exact blocker.",
                "Decision: Proceed.",
            ])

        if phase_name == "execute" and safe_mode:
            return "\n".join([
                "Work performed: Safe-mode governance execution only. No Routify files were modified and no builds/tests were run.",
                "Validation: Safe-mode guard active; execution remained text-only and queue-free.",
                "Evidence: transcript, handoff events, and pre/post snapshots will verify unchanged repos and queues.",
                "Blocker: none",
            ])

        if phase_name == "assess" and safe_mode:
            return "\n".join([
                "Assessment: the governance-only safe-mode proof is attributable and repeatable.",
                "Evidence check: distinct role messages, handoff events, and snapshot artifacts are available.",
                "Gaps: none blocking the governance proof; return to delivery_lead for final command closure.",
                "FINAL_STATUS: CONTINUE",
            ])

        if phase_name == "command":
            next_command = (
                f"convert the latest gap or blocker into one concrete proof-oriented slice: {gaps or blocker}"
                if gaps or blocker
                else (
                    "stop after recording the safe-mode proof transcript; no Routify execution is authorized in this pass"
                    if safe_mode
                    else "convert the latest assess feedback into one concrete next slice and hand it to implementation_engineer"
                )
            )
            return "\n".join([
                (
                    "Decision: Governance proof complete in safe mode."
                    if safe_mode
                    else "Decision: Continue with the next planned slice."
                ),
                ("Owner: delivery_lead" if safe_mode else "Owner: product_manager"),
                f"Next command: {next_command}.",
                (
                    "Reason: safe mode demonstrated the required chain without allowing file changes or Routify task execution."
                    if safe_mode
                    else "Reason: the session is not complete, no terminal blocker was proven, and governance should keep execution moving."
                ),
            ])

        fallback = _NON_ACTIONABLE_FALLBACKS.get(phase_name)
        if fallback:
            return "\n".join(fallback(goal))
        return None

    def _run_deterministic_turn(self, session: dict, tmpl: dict, phase: dict, role: str) -> bool:
        text = self._build_deterministic_turn_output(session, tmpl, phase, role)
        if not text:
            return False

        log.info(
            "Session %d: synthesizing deterministic %s turn for phase '%s'",
            session["id"],
            role,
            phase.get("name", "?"),
        )

        message = self._messages.add(
            sender=role,
            text=text,
            channel=session.get("channel", "general"),
            metadata={
                "session_id": session.get("id"),
                "session_template_id": session.get("template_id"),
                "session_phase": session.get("current_phase"),
                "session_phase_name": phase.get("name"),
                "session_role": role,
                "session_agent": self._resolve_current_agent(session, role),
                "session_synthetic_turn": True,
                "session_deterministic_turn": True,
                "session_safe_mode": self._session_safe_mode(session, tmpl),
            },
        )
        self._advance(session, message["id"])
        return True

    def _resolve_session_lead(self, session: dict, tmpl: dict | None = None) -> tuple[str | None, str | None]:
        governance = self._get_template_governance(tmpl or self._store.get_template(session.get("template_id", "")))
        lead_role = governance.get("lead_role")
        if not lead_role:
            return None, None
        lead_agent = self._resolve_current_agent(session, lead_role)
        if not lead_agent or not self._is_agent(lead_agent):
            lead_agent = self._resolve_role_agent(lead_role)
        return lead_role, lead_agent

    def _phase_kind(self, phase: dict) -> str:
        raw = str(phase.get("phase_kind", "") or "").strip().lower()
        if raw:
            return _PHASE_KIND_ALIASES.get(raw, raw)

        name = str(phase.get("name", "") or "").strip().lower()
        if "assess" in name:
            return "assess"
        if "implement" in name or "execute" in name or name == "respond":
            return "execute"
        if "review" in name or "critique" in name or "challenge" in name:
            return "review"
        if "plan" in name or "frame" in name or "next slice" in name:
            return "plan"
        if "summary" in name or "synthesis" in name:
            return "summary"
        if "verdict" in name or "decision" in name:
            return "decision"
        return "other"

    def _find_previous_phase_by_kind(self, phases: list[dict], *, before_idx: int, kinds: set[str]) -> int | None:
        for idx in range(before_idx - 1, -1, -1):
            if self._phase_kind(phases[idx]) in kinds:
                return idx
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
        metadata = msg.get("metadata") or {}

        # Ignore system-generated messages (banners, phase markers, etc.)
        if sender == "system" or msg.get("type", "chat") != "chat":
            return

        if metadata.get("session_synthetic_turn"):
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
            self._annotate_session_message(
                msg,
                session,
                role=expected_role,
                agent=expected_agent,
            )
            if sender_is_agent and _NON_ACTIONABLE_REPLY_RE.search(msg.get("text", "") or ""):
                tmpl = self._store.get_template(session.get("template_id", ""))
                governance = self._get_template_governance(tmpl)
                executor_roles = {
                    str(item).strip().lower() for item in governance.get("executor_roles", [])
                }
                role_key = str(expected_role or "").strip().lower()
                phase_name = ""
                phases = tmpl.get("phases", []) if isinstance(tmpl, dict) else []
                phase_idx = int(session.get("current_phase") or 0)
                if 0 <= phase_idx < len(phases):
                    phase_name = str(phases[phase_idx].get("name") or "")
                fallback_text = self._build_non_actionable_turn_fallback(session, expected_role)
                if fallback_text:
                    self._messages.add(
                        sender="system",
                        text=(
                            f"Session fallback: {expected_agent} replied non-actionably, so the moderator generated a structured {expected_role or 'governance'} handoff to keep delivery moving."
                        ),
                        msg_type="session_guard",
                        channel=channel,
                        metadata={
                            "session_id": session.get("id"),
                            "guard": "non_actionable_turn_fallback",
                            "agent": expected_agent,
                            "role": expected_role,
                        },
                    )
                    self._messages.add(
                        sender=expected_agent,
                        text=fallback_text,
                        msg_type="chat",
                        channel=channel,
                        metadata={
                            "session_id": session.get("id"),
                            "session_template_id": session.get("template_id"),
                            "session_role": expected_role,
                            "session_agent": expected_agent,
                            "session_phase": session.get("current_phase"),
                            "session_phase_name": phase_name,
                            "session_fallback_generated": True,
                        },
                    )
                    log.warning(
                        "Session %d used fallback for non-actionable reply from %s (%s)",
                        session["id"],
                        expected_agent,
                        expected_role,
                    )
                    return
                if role_key in executor_roles:
                    log.warning(
                        "Session %d accepted non-actionable executor reply from %s (%s) for downstream review/loop guard handling",
                        session["id"],
                        expected_agent,
                        expected_role,
                    )
                else:
                    reason = f"non-actionable turn reply from {expected_role or expected_agent}"
                    self._messages.add(
                        sender="system",
                        text=(
                            f"Session blocked: {expected_agent} replied without executing the assigned turn. "
                            "The session will not advance on a readiness/no-task reply."
                        ),
                        msg_type="session_guard",
                        channel=channel,
                        metadata={
                            "session_id": session.get("id"),
                            "guard": "non_actionable_turn",
                            "agent": expected_agent,
                            "role": expected_role,
                        },
                    )
                    self._store.interrupt(session["id"], reason)
                    log.warning(
                        "Session %d interrupted on non-actionable reply from %s (%s)",
                        session["id"],
                        expected_agent,
                        expected_role,
                    )
                    return
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

        previous_session = dict(session)

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
                self._emit_session_handoff(previous_session, session)
                self._trigger_current(session)
        else:
            # Phase complete
            interrupt_reason = self._phase_interrupt_reason(session, phase)
            if interrupt_reason:
                self._store.interrupt(session["id"], interrupt_reason)
                log.info(
                    "Session %d interrupted via phase '%s' blocker gate: %s",
                    session["id"],
                    phase["name"],
                    interrupt_reason,
                )
                return

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
                    self._emit_session_handoff(previous_session, session)
                    self._trigger_current(session)
            else:
                if self._session_safe_mode(session, tmpl) and self._phase_kind(phase) == "decision":
                    self._store.complete(session["id"], message_id)
                    log.info("Session %d complete via safe-mode decision gate", session["id"])
                    return

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
                        self._emit_session_handoff(previous_session, session)
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

        if self._session_safe_mode(session, tmpl):
            if self._run_deterministic_turn(session, tmpl, phase, role):
                return

        if self._should_use_deterministic_turn(tmpl, phase):
            if self._run_deterministic_turn(session, tmpl, phase, role):
                return

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
        lines.append(
            "Coordination, planning, review, assessment, and blocker-management turns are real tasks even when no repository edit is requested. Do not ask for a separate repo task when the turn itself is a governance turn."
        )
        lines.extend(self._autonomy_contract_lines(tmpl, phase, role))

        # Dissent mandate for review/critique roles
        if role.lower() in _DISSENT_ROLES:
            lines.append("Independent judgment only.")

        phase_name_key = str(phase.get("name", "") or "").strip().lower()
        output_contract = _SESSION_OUTPUT_CONTRACTS.get(phase_name_key)
        if output_contract:
            lines.extend(output_contract)

        completion_marker = phase.get("complete_when_all_contain")
        if isinstance(completion_marker, str) and completion_marker.strip():
            lines.append(
                f"Write '{completion_marker}' only if the work is fully complete with no material gaps."
            )

        if isinstance(phase.get("loop_to_phase"), int):
            lines.append("After your message, the session auto-continues.")

        lines.extend(self._role_guidance_lines(tmpl, phase, role))
        lines.extend(self._handoff_prompt_lines(session, tmpl, phase, role))

        lines.append(
            f"Read recent #{channel} context, then produce the turn output for #{channel}. If your runtime can send chat messages directly, reply via chat_send in #{channel}; otherwise return plain text only and the wrapper will post it."
        )
        if self._compact_prompts:
            lines.append(_PROMPT_BREVITY_LINE)

        # Use double newlines to ensure separation in TUIs that might collapse single newlines
        return "\n\n".join(lines)

    def _role_guidance_lines(self, tmpl: dict, phase: dict, role: str) -> list[str]:
        governance = self._get_template_governance(tmpl)
        role_key = role.strip().lower()
        phase_kind = self._phase_kind(phase)
        lead_role = str(governance.get("lead_role") or "").strip().lower()
        planning_role = str(governance.get("planning_role") or "").strip().lower()
        executor_roles = {str(item).strip().lower() for item in governance.get("executor_roles", [])}
        review_roles = {str(item).strip().lower() for item in governance.get("review_roles", [])}
        client_escalation_role = str(governance.get("client_escalation_role") or lead_role).strip().lower()
        quality_gate_role = str(governance.get("quality_gate_role") or "").strip().lower()

        lines = []
        if role_key == lead_role:
            lines.append(
                "You are the session lead. Own command authority, blocker disposition, and whether work should continue, pause, or stop."
            )

        if role_key == planning_role:
            lines.extend([
                "Turn the current goal and review findings into one concrete next slice with clear ownership and acceptance criteria.",
                "Do not relaunch the same blocked slice unless there is a materially new method or new evidence.",
            ])

        if role_key in executor_roles:
            lines.extend([
                "You own concrete execution, validation, and the evidence for your assigned slice.",
                "Do not delegate missing artifacts or blocker evidence upward; produce them yourself when tools allow.",
                "If blocked, add 'BLOCKER: ...' with the exact missing artifact, permission, dependency, or tool failure.",
            ])
            lines.extend(self._blocker_contract_prompt_lines(role))

        if role_key in review_roles or role_key in _DISSENT_ROLES:
            lines.append(
                "Judge independently and state whether a gap is executor-owned work or a true external blocker."
            )
            if phase_kind == "assess" or phase.get("interrupt_when_all_contain"):
                lines.append(
                    "Use 'FINAL_STATUS: BLOCKED' plus 'BLOCKER: ...' when the remaining gap cannot be resolved inside the current execution lane."
                )
            lines.extend(self._blocker_contract_prompt_lines(role))

        if role_key == client_escalation_role:
            lines.append(
                "Only you may emit 'CLIENT_ESCALATION: ...', and only after the internal chain is exhausted and a hard blocker still remains."
            )
        elif client_escalation_role:
            lines.append(
                f"Do not emit 'CLIENT_ESCALATION: ...'. Only {client_escalation_role} may escalate to the client."
            )

        if role_key == quality_gate_role:
            lines.append(
                "Only you may emit 'QUALITY_REJECTED: ...' when the slice misses the acceptance bar."
            )
        elif quality_gate_role:
            lines.append(
                f"Do not emit 'QUALITY_REJECTED: ...'. Only {quality_gate_role} may reject quality at the gate."
            )

        if role_key == lead_role and phase_kind in {"plan", "assess", "summary", "decision"}:
            lines.append(
                "When the room is repeating the same blocker, convert it into a blocker decision or a materially new method instead of another loop."
            )
            lines.extend(self._blocker_contract_prompt_lines(role))

        return lines

    def _autonomy_contract_lines(self, tmpl: dict, phase: dict, role: str) -> list[str]:
        governance = self._get_template_governance(tmpl)
        autonomy_contract = str(governance.get("autonomy_contract") or "").strip().lower()
        if autonomy_contract != "gfe":
            return []

        phase_kind = self._phase_kind(phase)
        role_key = role.strip().lower()
        review_roles = {str(item).strip().lower() for item in governance.get("review_roles", [])}
        lead_role = str(governance.get("lead_role") or "").strip().lower()
        lines = [
            "Follow the room's GFE autonomy contract: make the best forward progress you can from partial requirements instead of stopping for routine clarification.",
            "Return to the client only for a hard blocker, an irreversible product decision, or a direct conflict in requirements that the room cannot responsibly resolve.",
            "Communicate through explicit inter-agent handoffs: state what changed, what remains open, who owns the next move, and the exact blocker if one exists.",
        ]

        if phase_kind == "plan":
            lines.append(
                "Convert ambiguity into the safest high-value slice and the next owner; do not ask the client for details that execution or review can resolve internally."
            )

        if phase_kind == "execute":
            lines.append(
                "When requirements are partial, choose the highest-value safe implementation path, validate it, and surface concrete tradeoffs instead of waiting for perfect instructions."
            )

        if phase_kind == "assess" or role_key in review_roles:
            lines.append(
                "Mark work BLOCKED only when the remaining gap truly requires client input, external access, or a dependency outside the room's control."
            )

        if role_key == lead_role:
            lines.append(
                "Keep the room moving autonomously: synthesize partial inputs into direction, and only escalate outward when the blocker meets the GFE threshold."
            )

        return lines

    def _handoff_prompt_lines(self, session: dict, tmpl: dict, phase: dict, role: str) -> list[str]:
        next_target = self._predict_followup_target(session, tmpl)
        if not next_target:
            return []

        next_agent = next_target.get("agent")
        next_role = next_target.get("role")
        next_phase_name = str(next_target.get("phase_name") or "").strip() or "next phase"
        if not next_agent and not next_role:
            return []

        mention_target = f"@{next_agent}" if next_agent else f"@{next_role}"
        next_label = self._get_agent_display_name(next_agent, next_role) or next_role or next_agent or "next owner"
        current_phase_name = str(phase.get("name") or "current phase")
        transition_note = (
            f"The next governed owner is {mention_target} ({next_label}) in phase '{next_phase_name}'."
            if next_phase_name != current_phase_name
            else f"The next governed owner is {mention_target} ({next_label}) in this same phase."
        )
        return [
            transition_note,
            *self._handoff_contract_prompt_lines(mention_target=mention_target, next_role=next_role),
        ]

    def _predict_followup_target(self, session: dict, tmpl: dict | None = None) -> dict | None:
        tmpl = tmpl or self._store.get_template(session.get("template_id", ""))
        if not tmpl:
            return None

        phases = tmpl.get("phases", [])
        phase_idx = int(session.get("current_phase") or 0)
        turn_idx = int(session.get("current_turn") or 0)
        if phase_idx >= len(phases):
            return None

        phase = phases[phase_idx]
        participants = phase.get("participants", [])
        if turn_idx >= len(participants):
            return None

        if turn_idx + 1 < len(participants):
            next_phase_idx = phase_idx
            next_turn_idx = turn_idx + 1
        else:
            next_phase_idx = phase_idx + 1
            if next_phase_idx >= len(phases):
                loop_to_phase = phase.get("loop_to_phase")
                if not isinstance(loop_to_phase, int) or not (0 <= loop_to_phase < len(phases)):
                    return None
                next_phase_idx = loop_to_phase
            next_turn_idx = 0

        next_phase = phases[next_phase_idx]
        next_participants = next_phase.get("participants", [])
        if next_turn_idx >= len(next_participants):
            return None

        next_role = next_participants[next_turn_idx]
        next_agent = self._resolve_current_agent(session, next_role)
        return {
            "phase_index": next_phase_idx,
            "phase_name": next_phase.get("name"),
            "role": next_role,
            "agent": next_agent,
        }

    def _emit_session_handoff(self, previous_session: dict, next_session: dict):
        current_role = self._get_expected_role(previous_session)
        current_agent = self._get_expected_agent(previous_session)
        next_role = self._get_expected_role(next_session)
        next_agent = self._get_expected_agent(next_session)
        if not next_role and not next_agent:
            return

        prev_template = self._store.get_template(previous_session.get("template_id", ""))
        next_template = self._store.get_template(next_session.get("template_id", ""))
        prev_phase_name = None
        next_phase_name = None

        if prev_template:
            prev_phases = prev_template.get("phases", [])
            prev_idx = int(previous_session.get("current_phase") or 0)
            if 0 <= prev_idx < len(prev_phases):
                prev_phase_name = prev_phases[prev_idx].get("name")

        if next_template:
            next_phases = next_template.get("phases", [])
            next_idx = int(next_session.get("current_phase") or 0)
            if 0 <= next_idx < len(next_phases):
                next_phase_name = next_phases[next_idx].get("name")

        mention_target = f"@{next_agent}" if next_agent else f"@{next_role}"
        handoff_text = "\n".join([
            "HANDOFF",
            f"FROM_ROLE: {current_role or 'unknown'}",
            f"FROM_AGENT: {current_agent or 'unknown'}",
            f"TO_ROLE: {next_role or 'unknown'}",
            f"TO_AGENT: {mention_target}",
            f"NEXT_PHASE: {next_phase_name or prev_phase_name or 'current'}",
            "ACTION: continue the governed session with the next owned turn",
            (
                f"STATUS: transition from {prev_phase_name or 'current phase'} to {next_phase_name}."
                if next_phase_name and next_phase_name != prev_phase_name
                else "STATUS: next governed turn stays in the current phase."
            ),
        ])

        self._messages.add(
            sender="system",
            text=handoff_text,
            msg_type="session_handoff",
            channel=next_session.get("channel", "general"),
            metadata={
                "session_id": next_session.get("id"),
                "from_role": current_role,
                "from_agent": current_agent,
                "to_role": next_role,
                "to_agent": next_agent,
                "from_phase": prev_phase_name,
                "to_phase": next_phase_name,
                "handoff_contract": "northstar-handoff-v1",
            },
        )

    def _assemble_planner_watchdog_prompt(self, session: dict, tmpl: dict | None, lead_role: str | None = None) -> str:
        """Build a concise out-of-turn planner heartbeat prompt."""
        channel = session.get("channel", "general")
        phase_name = "unknown"
        current_role = self._get_expected_role(session) or "unknown"
        current_agent = self._get_expected_agent(session) or session.get("waiting_on") or "unknown"
        governance = self._get_template_governance(tmpl)
        lead_role = lead_role or governance.get("lead_role") or "planner"
        lead_title = "PLANNER HEARTBEAT" if lead_role.strip().lower() == "planner" else "SESSION LEAD HEARTBEAT"

        if tmpl:
            phases = tmpl.get("phases", [])
            phase_idx = int(session.get("current_phase") or 0)
            if 0 <= phase_idx < len(phases):
                phase_name = phases[phase_idx].get("name", phase_name)

        current_agent_display = self._get_agent_display_name(current_agent, current_role) or current_agent
        lead_display = self._get_agent_display_name(None, lead_role) or lead_role

        lines = [
            f"{lead_title}: {tmpl.get('name', session.get('template_name', '?')) if tmpl else session.get('template_name', '?')}",
        ]
        if session.get("goal"):
            lines.append(f"GOAL: {session['goal']}")
        lines.extend([
            f"COMMAND ROLE: {lead_display}",
            f"CURRENT PHASE: {phase_name}",
            f"CURRENT TURN OWNER: {current_role} ({current_agent_display})",
            "Out-of-turn supervision only.",
            "Inspect recent chat, repo state, and evidence.",
            "If work is stalled, drifting, or under-validated, post one concrete correction, ownership change, or blocker decision.",
            "If the same blocker keeps repeating, turn it into a blocker decision instead of another identical slice.",
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
        tmpl: dict | None,
        lead_role: str,
    ) -> str:
        """Build the planner prompt used when no active session exists."""
        lead_title = "PLANNER AUTONOMY HEARTBEAT" if lead_role.strip().lower() == "planner" else "SESSION LEAD AUTONOMY HEARTBEAT"
        lead_display = self._get_agent_display_name(None, lead_role) or lead_role
        lines = [
            lead_title,
            f"There is currently no active session in #{channel}.",
            f"{lead_display} owns continuous product evolution for this channel.",
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
        if tmpl:
            lines.append(f"COMMAND ROLE: {lead_display}")

        lines.extend([
            "Inspect recent chat, current repo state, and the latest evidence before acting.",
            "If the previous work is still below bar, start the next corrective cycle immediately.",
            "If the current task is truly complete, decide the next meaningful evolution: corrections, adaptations, research, or a scoped new feature.",
            "If the last cycle is blocked on the same external dependency, prefer a blocker decision or a materially new method over restarting the same loop.",
            "Do not wait for a human unless there is a real blocker. Do not restart identical work blindly without naming the next concrete objective and owner.",
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
        tmpl = self._store.get_template(session.get("template_id", ""))
        governance = self._get_template_governance(tmpl)
        planning_role = governance.get("planning_role") or self._get_expected_role(session) or "planner"
        implement_idx = self._find_previous_phase_by_kind(phases, before_idx=phase_idx, kinds={"execute"})
        assess_idx = self._find_previous_phase_by_kind(phases, before_idx=phase_idx, kinds={"assess"})
        if implement_idx is None:
            implement_idx = self._find_phase_index(phases, "Implement")
        if assess_idx is None:
            assess_idx = self._find_phase_index(phases, "Assess")
        if implement_idx is None or assess_idx is None:
            return None

        implement_participants = phases[implement_idx].get("participants", [])
        assess_participants = phases[assess_idx].get("participants", [])
        current_participants = phases[phase_idx].get("participants", [])

        implement_messages = self._get_phase_messages_for_index(session, phases, implement_idx)
        assess_messages = self._get_phase_messages_for_index(session, phases, assess_idx)
        current_messages = self._get_phase_messages_for_index(session, phases, phase_idx)
        if (
            len(implement_messages) < len(implement_participants)
            or len(assess_messages) < len(assess_participants)
            or len(current_messages) < len(current_participants)
        ):
            return None

        implement_text = "\n".join(msg.get("text", "") for msg in implement_messages)
        assess_texts = [msg.get("text", "") for msg in assess_messages]
        no_file_changes = bool(_NO_FILE_CHANGES_RE.search(implement_text))
        non_actionable_reply = bool(_NON_ACTIONABLE_REPLY_RE.search(implement_text))
        blocker_signature = self._extract_blocker_signature(implement_text, *assess_texts)
        blocker_reply = bool(blocker_signature) or bool(_BLOCKER_REPLY_RE.search(implement_text))
        if not no_file_changes and not non_actionable_reply and not blocker_reply:
            return None

        if not all("final_status: continue" in text.lower() for text in assess_texts):
            return None

        planner_text = "\n".join(msg.get("text", "") for msg in current_messages)
        target = (
            blocker_signature
            or self._extract_next_slice_target(planner_text)
            or "repeated no-progress next slice"
        )
        if non_actionable_reply:
            reason = "non-actionable reply"
        elif no_file_changes:
            reason = "no material output"
        elif blocker_reply:
            reason = "same blocker repeated"
        else:
            reason = "no material output"
        signature = f"{planning_role.lower()}|{reason}|{target}"
        return _LoopGuardSignal(
            signature=signature,
            target=target,
            stagnant_role=",".join(implement_participants) or "executor",
            reason=reason,
        )

    def _build_loop_guard_message(self, signal: _LoopGuardSignal, count: int) -> str:
        return (
            f"Moderator stop: pausing after {count} consecutive non-productive cycles. "
            f"Latest loop reason: {signal.reason}. Assess still returned CONTINUE, "
            f"and the repeated target/blocker was: {signal.target}. "
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

    def _extract_blocker_signature(self, *texts: str) -> str:
        for text in texts:
            detail_match = _BLOCKER_DETAIL_RE.search(text or "")
            if detail_match:
                blocker = re.sub(r"\s+", " ", detail_match.group(1).strip().lower())
                if blocker not in {"none", "n/a", "na", "no blocker", "no blockers"}:
                    return blocker
            match = _BLOCKER_LINE_RE.search(text or "")
            if match:
                blocker = re.sub(r"\s+", " ", match.group(1).strip().lower())
                if blocker in {"none", "n/a", "na", "no blocker", "no blockers"}:
                    continue
                return blocker
        return ""

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

    def _phase_interrupt_reason(self, session: dict, phase: dict) -> str | None:
        """Return an interrupt reason when a phase explicitly signals a blocker."""
        interrupt_marker = phase.get("interrupt_when_all_contain")
        if not isinstance(interrupt_marker, str) or not interrupt_marker.strip():
            return None

        participants = phase.get("participants", [])
        if not participants:
            return None

        phase_messages = self._get_phase_messages(session, participants)
        if len(phase_messages) != len(participants):
            return None

        marker = interrupt_marker.strip().lower()
        if not all(marker in msg.get("text", "").lower() for msg in phase_messages):
            return None

        blocker = self._extract_blocker_signature(*(msg.get("text", "") for msg in phase_messages))
        base_reason = str(phase.get("interrupt_reason", "")).strip()
        if blocker:
            return f"{base_reason}: {blocker}" if base_reason else f"blocked: {blocker}"
        return base_reason or interrupt_marker.strip()

    def _build_non_actionable_turn_fallback(self, session: dict, expected_role: str | None) -> str | None:
        """Generate a deterministic governance handoff when a provider gives a non-actionable reply."""
        tmpl = self._store.get_template(session["template_id"])
        if not tmpl:
            return None

        phases = tmpl.get("phases", [])
        phase_idx = session.get("current_phase", 0)
        if phase_idx >= len(phases):
            return None

        phase_name = str(phases[phase_idx].get("name", "") or "").strip().lower()
        builder = _NON_ACTIONABLE_FALLBACKS.get(phase_name)
        if not builder:
            return None

        goal = str(session.get("goal") or "").strip()
        lines = builder(goal)
        return "\n".join(line for line in lines if line)

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
