"""Session store — persists active session runs to JSON."""

import json
import time
import threading
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_ALLOWED_PHASE_KINDS = {
    "frame",
    "plan",
    "review",
    "execute",
    "assess",
    "summary",
    "decision",
    "other",
}

_ALLOWED_AUTONOMY_CONTRACTS = {"gfe"}

_ALLOWED_CLIENT_ESCALATION_THRESHOLDS = {"hard-blocker-only", "standard"}


_DERIVED_SESSION_KEYS = {
    "total_phases",
    "phase_name",
    "current_role",
    "current_agent",
    "current_agent_display",
    "waiting_on_display",
}


class SessionStore:
    def __init__(self, path: str, templates_dir: str | None = None):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._sessions: list[dict] = []
        self._next_id = 1
        self._lock = threading.Lock()
        self._callbacks: list = []
        self._templates: dict[str, dict] = {}
        self._template_sources: dict[str, str] = {}
        self._templates_dir = Path(templates_dir) if templates_dir else None
        self._custom_templates_path = self._path.parent / "custom_templates.json"
        self._templates_fingerprint: tuple | None = None
        self._load()

        # Warn about legacy file
        legacy = self._path.parent / "sessions.json"
        if legacy.exists() and legacy != self._path:
            log.info("Ignoring legacy sessions.json; Sessions uses %s", self._path.name)

        self.refresh_templates(force=True)

    # --- Persistence ---

    def _load(self):
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text("utf-8"))
            if isinstance(raw, list):
                self._sessions = [self._serialize_session(s) for s in raw if isinstance(s, dict)]
                if self._sessions:
                    self._next_id = max(s["id"] for s in self._sessions) + 1
        except (json.JSONDecodeError, KeyError):
            self._sessions = []

    def _save(self):
        self._path.write_text(
            json.dumps([self._serialize_session(s) for s in self._sessions], indent=2, ensure_ascii=False) + "\n",
            "utf-8",
        )

    def _serialize_session(self, session: dict) -> dict:
        data = dict(session)
        for key in _DERIVED_SESSION_KEYS:
            data.pop(key, None)
        return data

    # --- Templates ---

    def _template_fingerprint(self) -> tuple:
        builtin = []
        if self._templates_dir and self._templates_dir.exists():
            for file_path in sorted(self._templates_dir.glob("*.json")):
                try:
                    stat = file_path.stat()
                    builtin.append((file_path.name, stat.st_mtime_ns, stat.st_size))
                except OSError:
                    continue

        custom = None
        if self._custom_templates_path.exists():
            try:
                stat = self._custom_templates_path.stat()
                custom = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                custom = ("error",)

        return (tuple(builtin), custom)

    def _read_templates_from_dir(self, directory: Path | None) -> dict[str, dict]:
        templates: dict[str, dict] = {}
        if not directory:
            return templates
        if not directory.exists():
            log.warning("Session templates directory not found: %s", directory)
            return templates

        for file_path in sorted(directory.glob("*.json")):
            try:
                tmpl = json.loads(file_path.read_text("utf-8"))
                tid = tmpl.get("id", file_path.stem)
                tmpl["id"] = tid
                tmpl.setdefault("is_custom", False)
                templates[tid] = tmpl
            except (json.JSONDecodeError, KeyError) as exc:
                log.warning("Failed to load template %s: %s", file_path.name, exc)
        return templates

    def _read_custom_templates(self) -> dict[str, dict]:
        templates: dict[str, dict] = {}
        if not self._custom_templates_path.exists():
            return templates

        try:
            custom = json.loads(self._custom_templates_path.read_text("utf-8"))
            for tmpl in (custom if isinstance(custom, list) else []):
                tid = tmpl.get("id", "")
                if not tid:
                    continue
                saved = dict(tmpl)
                saved["is_custom"] = True
                templates[tid] = saved
        except (json.JSONDecodeError, KeyError) as exc:
            log.warning("Failed to load custom templates: %s", exc)
        return templates

    def refresh_templates(self, *, force: bool = False):
        fingerprint = self._template_fingerprint()
        with self._lock:
            if not force and fingerprint == self._templates_fingerprint:
                return

        builtin_templates = self._read_templates_from_dir(self._templates_dir)
        custom_templates = self._read_custom_templates()

        with self._lock:
            for template_id, source in list(self._template_sources.items()):
                if source in {"builtin", "custom"}:
                    self._template_sources.pop(template_id, None)
                    self._templates.pop(template_id, None)

            for template_id, template in builtin_templates.items():
                self._templates[template_id] = template
                self._template_sources[template_id] = "builtin"
                log.info("Loaded session template: %s", template_id)

            for template_id, template in custom_templates.items():
                self._templates[template_id] = template
                self._template_sources[template_id] = "custom"
                log.info("Loaded custom template: %s", template_id)

            self._templates_fingerprint = fingerprint

    def get_templates(self) -> list[dict]:
        self.refresh_templates()
        with self._lock:
            return [
                dict(template)
                for template_id, template in self._templates.items()
                if self._template_sources.get(template_id) != "runtime"
            ]

    def get_template(self, template_id: str) -> dict | None:
        self.refresh_templates()
        with self._lock:
            tmpl = self._templates.get(template_id)
            return dict(tmpl) if tmpl else None

    def register_runtime_template(self, tmpl: dict) -> dict:
        saved = dict(tmpl)
        template_id = str(saved.get("id", "")).strip()
        if not template_id:
            raise ValueError("runtime template id is required")
        saved["id"] = template_id
        saved.setdefault("is_custom", True)

        with self._lock:
            self._templates[template_id] = saved
            self._template_sources[template_id] = "runtime"
        return dict(saved)

    def save_custom_template(self, tmpl: dict) -> dict:
        custom_path = self._custom_templates_path
        custom = []
        if custom_path.exists():
            try:
                custom = json.loads(custom_path.read_text("utf-8"))
            except (json.JSONDecodeError, KeyError):
                custom = []

        saved = dict(tmpl)
        saved["is_custom"] = True
        custom = [t for t in custom if t.get("id") != saved.get("id")]
        custom.append(saved)
        custom_path.write_text(json.dumps(custom, indent=2, ensure_ascii=False) + "\n", "utf-8")
        self._templates[saved["id"]] = saved
        self._template_sources[saved["id"]] = "custom"
        self._templates_fingerprint = None
        return saved

    def delete_custom_template(self, template_id: str) -> bool:
        tmpl = self._templates.get(template_id)
        if not tmpl or self._template_sources.get(template_id) != "custom":
            return False

        custom_path = self._custom_templates_path
        custom = []
        if custom_path.exists():
            try:
                custom = json.loads(custom_path.read_text("utf-8"))
            except (json.JSONDecodeError, KeyError):
                custom = []

        new_custom = [t for t in custom if t.get("id") != template_id]
        if len(new_custom) != len(custom):
            custom_path.write_text(json.dumps(new_custom, indent=2, ensure_ascii=False) + "\n", "utf-8")

        self._templates.pop(template_id, None)
        self._template_sources.pop(template_id, None)
        self._templates_fingerprint = None
        return True

    # --- Callbacks ---

    def on_change(self, callback):
        """Register a callback(action, session) on any change.
        action: 'create', 'update', 'complete', 'interrupt'."""
        self._callbacks.append(callback)

    def _fire(self, action: str, session: dict):
        for cb in self._callbacks:
            try:
                cb(action, session)
            except Exception:
                pass

    # --- Session lifecycle ---

    def create(self, template_id: str, channel: str, cast: dict,
               started_by: str, goal: str = "", session_options: dict | None = None) -> dict | None:
        """Create and persist a new session run."""
        tmpl = self._templates.get(template_id)
        if not tmpl:
            return None

        options = dict(session_options or {})

        with self._lock:
            # One active session per channel
            for s in self._sessions:
                if s.get("channel") == channel and s.get("state") in ("active", "waiting", "paused"):
                    return None

            session = {
                "id": self._next_id,
                "template_id": template_id,
                "template_name": tmpl.get("name", template_id),
                "channel": channel,
                "cast": cast,
                "state": "active",
                "current_phase": 0,
                "current_turn": 0,
                "started_by": started_by,
                "started_at": time.time(),
                "updated_at": time.time(),
                "last_message_id": None,
                "output_message_id": None,
                "goal": goal.strip()[:500],
            }
            if "safe_mode" in options:
                session["safe_mode"] = bool(options.get("safe_mode"))
            self._next_id += 1
            self._sessions.append(session)
            self._save()

        self._fire("create", session)
        return session

    def get(self, session_id: int) -> dict | None:
        with self._lock:
            for s in self._sessions:
                if s["id"] == session_id:
                    return dict(s)
            return None

    def get_active(self, channel: str) -> dict | None:
        """Get the active/waiting/paused session for a channel."""
        with self._lock:
            for s in self._sessions:
                if s.get("channel") == channel and s.get("state") in ("active", "waiting", "paused"):
                    return dict(s)
            return None

    def list_all(self, channel: str | None = None) -> list[dict]:
        with self._lock:
            result = [dict(s) for s in self._sessions]
        if channel:
            result = [s for s in result if s.get("channel") == channel]
        return result

    def advance_turn(self, session_id: int, message_id: int | None = None) -> dict | None:
        """Advance to the next turn within the current phase."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] not in ("active", "waiting"):
                return None
            session["current_turn"] += 1
            session["state"] = "active"
            session["updated_at"] = time.time()
            if message_id is not None:
                session["last_message_id"] = message_id
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def advance_phase(self, session_id: int, message_id: int | None = None) -> dict | None:
        """Advance to the next phase, resetting turn to 0."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] not in ("active", "waiting"):
                return None
            session["current_phase"] += 1
            session["current_turn"] = 0
            session["state"] = "active"
            session["updated_at"] = time.time()
            if message_id is not None:
                session["last_message_id"] = message_id
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def jump_to_phase(self, session_id: int, phase_index: int,
                      message_id: int | None = None) -> dict | None:
        """Jump to an explicit phase, resetting turn to 0."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] not in ("active", "waiting"):
                return None
            session["current_phase"] = phase_index
            session["current_turn"] = 0
            session["state"] = "active"
            session["updated_at"] = time.time()
            if message_id is not None:
                session["last_message_id"] = message_id
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def set_waiting(self, session_id: int, agent: str) -> dict | None:
        """Mark session as waiting on a specific agent."""
        with self._lock:
            session = self._find(session_id)
            if not session:
                return None
            session["state"] = "waiting"
            session["waiting_on"] = agent
            session["updated_at"] = time.time()
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def update_cast_agent(self, session_id: int, role: str, agent: str) -> dict | None:
        """Update the persisted runtime bound to a session role.

        Used when an agent restarts and comes back with a new canonical runtime
        name while keeping the same logical role label.
        """
        with self._lock:
            session = self._find(session_id)
            if not session:
                return None

            cast = session.setdefault("cast", {})
            old_agent = cast.get(role)
            if old_agent == agent:
                return dict(session)

            cast[role] = agent
            if session.get("waiting_on") == old_agent:
                session["waiting_on"] = agent
            session["updated_at"] = time.time()
            self._save()
            result = dict(session)

        self._fire("update", result)
        return result

    def pause(self, session_id: int) -> dict | None:
        """Pause session (human interruption)."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] not in ("active", "waiting"):
                return None
            session["state"] = "paused"
            session["updated_at"] = time.time()
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def resume(self, session_id: int) -> dict | None:
        """Resume a paused session."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] != "paused":
                return None
            session["state"] = "active"
            session["updated_at"] = time.time()
            self._save()
            result = dict(session)
        self._fire("update", result)
        return result

    def complete(self, session_id: int, output_message_id: int | None = None) -> dict | None:
        """Mark session as complete."""
        with self._lock:
            session = self._find(session_id)
            if not session:
                return None
            session["state"] = "complete"
            session["updated_at"] = time.time()
            if output_message_id is not None:
                session["output_message_id"] = output_message_id
            self._save()
            result = dict(session)
        self._fire("complete", result)
        return result

    def interrupt(self, session_id: int, reason: str = "ended by user") -> dict | None:
        """End session early."""
        with self._lock:
            session = self._find(session_id)
            if not session or session["state"] in ("complete", "interrupted"):
                return None
            session["state"] = "interrupted"
            session["interrupt_reason"] = reason
            session["updated_at"] = time.time()
            self._save()
            result = dict(session)
        self._fire("interrupt", result)
        return result

    def _find(self, session_id: int) -> dict | None:
        """Find session by ID (caller must hold lock)."""
        for s in self._sessions:
            if s["id"] == session_id:
                return s
        return None


def validate_session_template(tmpl: dict) -> list[str]:
    """Validate a session template dict. Returns list of errors (empty = valid)."""
    errors = []

    if not isinstance(tmpl, dict):
        return ["Template must be a JSON object"]

    if not tmpl.get("name") or not isinstance(tmpl.get("name"), str):
        errors.append("Missing or invalid 'name' (string required)")

    roles = tmpl.get("roles", [])
    if not isinstance(roles, list) or len(roles) == 0:
        errors.append("'roles' must be a non-empty array")
    elif len(roles) > 6:
        errors.append(f"Too many roles ({len(roles)}, max 6)")

    phases = tmpl.get("phases", [])
    if not isinstance(phases, list) or len(phases) == 0:
        errors.append("'phases' must be a non-empty array")
    elif len(phases) > 6:
        errors.append(f"Too many phases ({len(phases)}, max 6)")

    roles_set = set(roles) if isinstance(roles, list) else set()
    output_count = 0

    governance = tmpl.get("governance")
    if governance is not None:
        if not isinstance(governance, dict):
            errors.append("'governance' must be an object when provided")
        else:
            for key in ("lead_role", "planning_role", "client_escalation_role", "quality_gate_role"):
                value = governance.get(key)
                if value is not None:
                    if not isinstance(value, str):
                        errors.append(f"'governance.{key}' must be a string")
                    elif value not in roles_set:
                        errors.append(f"'governance.{key}' role '{value}' not in roles list")
            for key in ("executor_roles", "review_roles"):
                value = governance.get(key)
                if value is not None:
                    if not isinstance(value, list):
                        errors.append(f"'governance.{key}' must be an array")
                    else:
                        for role in value:
                            if role not in roles_set:
                                errors.append(f"'governance.{key}' role '{role}' not in roles list")
            deterministic_phase_kinds = governance.get("deterministic_phase_kinds")
            if deterministic_phase_kinds is not None:
                if not isinstance(deterministic_phase_kinds, list):
                    errors.append("'governance.deterministic_phase_kinds' must be an array")
                else:
                    for phase_kind in deterministic_phase_kinds:
                        if not isinstance(phase_kind, str):
                            errors.append(
                                "'governance.deterministic_phase_kinds' entries must be strings"
                            )
                        elif phase_kind not in _ALLOWED_PHASE_KINDS:
                            errors.append(
                                "'governance.deterministic_phase_kinds' entries must be phase kinds"
                            )
            autonomy_contract = governance.get("autonomy_contract")
            if autonomy_contract is not None:
                if not isinstance(autonomy_contract, str):
                    errors.append("'governance.autonomy_contract' must be a string")
                elif autonomy_contract not in _ALLOWED_AUTONOMY_CONTRACTS:
                    errors.append(
                        "'governance.autonomy_contract' must be one of ['gfe']"
                    )
            client_escalation_threshold = governance.get("client_escalation_threshold")
            if client_escalation_threshold is not None:
                if not isinstance(client_escalation_threshold, str):
                    errors.append("'governance.client_escalation_threshold' must be a string")
                elif client_escalation_threshold not in _ALLOWED_CLIENT_ESCALATION_THRESHOLDS:
                    errors.append(
                        "'governance.client_escalation_threshold' must be one of ['hard-blocker-only', 'standard']"
                    )

    for i, phase in enumerate(phases if isinstance(phases, list) else []):
        if not isinstance(phase, dict):
            errors.append(f"Phase {i + 1}: must be an object")
            continue
        if not phase.get("name"):
            errors.append(f"Phase {i + 1}: missing 'name'")
        participants = phase.get("participants", [])
        if not isinstance(participants, list) or len(participants) == 0:
            errors.append(f"Phase {i + 1}: 'participants' must be a non-empty array")
        elif len(participants) > 4:
            errors.append(f"Phase {i + 1}: too many participants ({len(participants)}, max 4)")
        for p in (participants if isinstance(participants, list) else []):
            if p not in roles_set:
                errors.append(f"Phase {i + 1}: participant '{p}' not in roles list")
        prompt = phase.get("prompt", "")
        if isinstance(prompt, str) and len(prompt) > 200:
            errors.append(f"Phase {i + 1}: prompt too long ({len(prompt)} chars, max 200)")
        if phase.get("is_output"):
            output_count += 1
        phase_kind = phase.get("phase_kind")
        if phase_kind is not None:
            if not isinstance(phase_kind, str):
                errors.append(f"Phase {i + 1}: 'phase_kind' must be a string")
            elif phase_kind not in _ALLOWED_PHASE_KINDS:
                errors.append(
                    f"Phase {i + 1}: 'phase_kind' must be one of {sorted(_ALLOWED_PHASE_KINDS)}"
                )
        completion_marker = phase.get("complete_when_all_contain")
        if completion_marker is not None and not isinstance(completion_marker, str):
            errors.append(f"Phase {i + 1}: 'complete_when_all_contain' must be a string")
        interrupt_marker = phase.get("interrupt_when_all_contain")
        if interrupt_marker is not None and not isinstance(interrupt_marker, str):
            errors.append(f"Phase {i + 1}: 'interrupt_when_all_contain' must be a string")
        interrupt_reason = phase.get("interrupt_reason")
        if interrupt_reason is not None and not isinstance(interrupt_reason, str):
            errors.append(f"Phase {i + 1}: 'interrupt_reason' must be a string")
        loop_to_phase = phase.get("loop_to_phase")
        if loop_to_phase is not None:
            if not isinstance(loop_to_phase, int):
                errors.append(f"Phase {i + 1}: 'loop_to_phase' must be an integer")
            elif isinstance(phases, list) and not (0 <= loop_to_phase < len(phases)):
                errors.append(
                    f"Phase {i + 1}: 'loop_to_phase' must target an existing phase index"
                )

    if output_count == 0 and isinstance(phases, list) and len(phases) > 0:
        errors.append("No phase marked as 'is_output: true'")
    elif output_count > 1:
        errors.append(f"Multiple phases marked as output ({output_count}, expected 1)")

    return errors
