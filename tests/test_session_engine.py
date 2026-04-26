import sys
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from session_engine import SessionEngine
from session_store import SessionStore
from store import MessageStore


class _ImmediateTimer:
    def __init__(self, interval, function, args=None, kwargs=None):
        self._function = function
        self._args = args or ()
        self._kwargs = kwargs or {}

    def start(self):
        self._function(*self._args, **self._kwargs)


class _FakeTrigger:
    def __init__(self):
        self.calls = []
        self.status = {}

    def trigger_sync(self, agent, channel, prompt):
        self.calls.append({"agent": agent, "channel": channel, "prompt": prompt})

    def get_status(self):
        return dict(self.status)


class _FakeRegistry:
    def __init__(self, names, *, instances=None, renames=None):
        self._names = set(names)
        self._instances = instances or {
            name: {"name": name, "label": name, "base": name.split("-", 1)[0]}
            for name in names
        }
        self._renames = renames or {}

    def is_registered(self, name):
        return name in self._names

    def get_all(self):
        return dict(self._instances)

    def get_instance(self, name):
        return self._instances.get(name)

    def resolve_name(self, name):
        return self._renames.get(name, name)


class PremiumUiRemediationSessionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp_root = Path(self._tmp.name)

        self.store = SessionStore(
            str(tmp_root / "session_runs.json"),
            templates_dir=str(ROOT / "session_templates"),
        )
        self.messages = MessageStore(str(tmp_root / "agentchattr_log.jsonl"))
        self.trigger = _FakeTrigger()
        self.registry = _FakeRegistry({
            "implementer", "planner", "reviewer", "challenger",
            "codex-1", "codex-2", "codex-3", "codex-4",
        })
        self.engine = SessionEngine(self.store, self.messages, self.trigger, registry=self.registry)
        self.cast = {
            "implementer": "implementer",
            "planner": "planner",
            "reviewer": "reviewer",
            "challenger": "challenger",
        }
        self.timer_patch = patch("session_engine.threading.Timer", _ImmediateTimer)
        self.timer_patch.start()
        self.addCleanup(self.timer_patch.stop)

    def _start_session(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast=self.cast,
            started_by="tester",
            goal="Match the mockups before stopping.",
        )
        self.assertIsNotNone(session)
        return session

    def _send(self, sender, text):
        return self.messages.add(sender=sender, text=text, channel="general")

    def _register_template(self, template_id: str, source_id: str, transform=None):
        template = self.store.get_template(source_id)
        self.assertIsNotNone(template)
        template = json.loads(json.dumps(template))
        template["id"] = template_id
        if transform:
            transform(template)
        self.store.register_runtime_template(template)
        return template

    def _drive_to_assess(self):
        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")
        self._send("planner", "Plan ready. Slice 1 targets route list premium polish.")
        self._send("reviewer", "Plan critique: watch flatness in card surfaces.")
        self._send("challenger", "Plan critique: avoid generic chips and weak CTA framing.")
        self._send("implementer", "Implementation ready. Playwright passed and mockup gaps are smaller.")

    def test_loops_back_to_critique_plan_when_assess_requires_more_work(self):
        session = self._start_session()

        self._drive_to_assess()
        self._send(
            "reviewer",
            "Still not mockup-level. FINAL_STATUS: CONTINUE\nRemaining gaps: card depth and CTA integration.",
        )
        self._send(
            "challenger",
            "Not ready to ship. FINAL_STATUS: CONTINUE\nRemaining gaps: hierarchy still too generic on mobile.",
        )

        waiting_on_planner = self.store.get_active("general")
        self.assertIsNotNone(waiting_on_planner)
        self.assertEqual(waiting_on_planner["current_phase"], 5)
        self.assertEqual(waiting_on_planner["waiting_on"], "planner")

        self._send(
            "planner",
            "Next slice: increase card depth, CTA integration, and mobile hierarchy before re-review.",
        )

        looped = self.store.get_active("general")
        self.assertIsNotNone(looped)
        self.assertEqual(looped["current_phase"], 2)
        self.assertEqual(looped["current_turn"], 0)
        self.assertEqual(looped["waiting_on"], "reviewer")
        self.assertEqual(looped["state"], "waiting")

    def test_completes_only_when_both_assessors_explicitly_approve(self):
        session = self._start_session()

        self._drive_to_assess()
        self._send(
            "reviewer",
            "This now matches the mockup quality bar. FINAL_STATUS: APPROVED",
        )
        final_message = self._send(
            "challenger",
            "Android presentation looks shippable and aligned. FINAL_STATUS: APPROVED",
        )

        self.assertIsNone(self.store.get_active("general"))
        completed = self.store.get(session["id"])
        self.assertIsNotNone(completed)
        self.assertEqual(completed["state"], "complete")
        self.assertEqual(completed["output_message_id"], final_message["id"])

    def test_role_alias_reply_advances_when_cast_uses_runtime_instance_name(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        self.assertEqual(self.trigger.calls[-1]["agent"], "codex-4")

        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 1)
        self.assertEqual(active["waiting_on"], "codex-3")

    def test_software_house_delivery_autoruns_governance_until_execute(self):
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Validate deterministic governance fallback on a non-actionable Intake reply.",
        )

        self.assertIsNotNone(session)

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 3)
        self.assertEqual(active["waiting_on"], "implementation_engineer")

        self.assertEqual(len(trigger.calls), 1)
        self.assertEqual(trigger.calls[-1]["agent"], "implementation_engineer")

        deterministic_messages = [
            msg for msg in messages.get_recent(10, channel="general")
            if (msg.get("metadata") or {}).get("session_deterministic_turn")
        ]
        self.assertEqual(
            [msg["sender"] for msg in deterministic_messages],
            ["delivery_lead", "product_manager", "technical_lead"],
        )
        self.assertEqual(
            [(msg.get("metadata") or {}).get("session_phase_name") for msg in deterministic_messages],
            ["Intake", "Plan", "Technical Review"],
        )

    def test_non_actionable_intake_reply_uses_governance_fallback_and_advances(self):
        self._register_template(
            "software-house-delivery-fallback",
            "software-house-delivery",
            lambda template: template.get("governance", {}).pop("deterministic_phase_kinds", None),
        )

        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-fallback-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery-fallback",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Validate deterministic governance fallback on a non-actionable Intake reply.",
        )

        self.assertIsNotNone(session)
        self.assertEqual(trigger.calls[-1]["agent"], "delivery_lead")

        messages.add(
            sender="delivery_lead",
            text="I'm ready, but there's no task yet.",
            channel="general",
        )

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 1)
        self.assertEqual(active["waiting_on"], "product_manager")

        recent = messages.get_recent(10, channel="general")
        guard = [msg for msg in recent if msg.get("type") == "session_guard"]
        self.assertTrue(guard)
        self.assertIn("Session fallback", guard[-1]["text"])

        fallback_messages = [
            msg for msg in recent if (msg.get("metadata") or {}).get("session_fallback_generated")
        ]
        self.assertTrue(fallback_messages)
        self.assertIn("Client goal:", fallback_messages[-1]["text"])
        self.assertEqual(
            (fallback_messages[-1].get("metadata") or {}).get("session_phase_name"),
            "Intake",
        )

    def test_software_house_delivery_execute_prompt_enforces_gfe_autonomy(self):
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-gfe-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Advance a partial premium UI requirement autonomously.",
        )

        self.assertIsNotNone(session)
        execute_prompt = trigger.calls[-1]["prompt"]
        self.assertIn("Follow the room's GFE autonomy contract", execute_prompt)
        self.assertIn("Return to the client only for a hard blocker", execute_prompt)
        self.assertIn("Communicate through explicit inter-agent handoffs", execute_prompt)
        self.assertIn("choose the highest-value safe implementation path", execute_prompt)
        self.assertIn("HANDOFF", execute_prompt)
        self.assertIn("TO: @qa_reviewer", execute_prompt)
        self.assertIn("Only delivery_lead may escalate to the client", execute_prompt)
        self.assertIn("Only qa_reviewer may reject quality at the gate", execute_prompt)

    def test_software_house_delivery_emits_visible_hierarchy_handoff_between_turns(self):
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-handoff-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Keep the room's hierarchy visible in chat.",
        )

        self.assertIsNotNone(session)
        messages.add(
            sender="implementation_engineer",
            text="Work performed: landed the slice.\nValidation: focused checks passed.\nEvidence: route detail preview updated.\nBlocker: none",
            channel="general",
        )

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 4)
        self.assertEqual(active["waiting_on"], "qa_reviewer")

        handoffs = [
            msg for msg in messages.get_recent(12, channel="general")
            if msg.get("type") == "session_handoff"
        ]
        self.assertTrue(handoffs)
        self.assertTrue(handoffs[-1]["text"].startswith("HANDOFF\n"))
        self.assertIn("TO_ROLE: qa_reviewer", handoffs[-1]["text"])
        self.assertIn("TO_AGENT: @qa_reviewer", handoffs[-1]["text"])
        self.assertEqual((handoffs[-1].get("metadata") or {}).get("to_role"), "qa_reviewer")
        self.assertEqual((handoffs[-1].get("metadata") or {}).get("handoff_contract"), "northstar-handoff-v1")

    def test_software_house_delivery_lead_prompt_uses_gfe_when_deterministic_start_is_disabled(self):
        self._register_template(
            "software-house-delivery-live-lead",
            "software-house-delivery",
            lambda template: template.get("governance", {}).pop("deterministic_phase_kinds", None),
        )
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-live-lead-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery-live-lead",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Advance a partial premium UI requirement autonomously.",
        )

        self.assertIsNotNone(session)
        lead_prompt = trigger.calls[-1]["prompt"]
        self.assertIn("Follow the room's GFE autonomy contract", lead_prompt)
        self.assertIn("Keep the room moving autonomously", lead_prompt)
        self.assertIn("Communicate through explicit inter-agent handoffs", lead_prompt)
        self.assertIn("Only you may emit 'CLIENT_ESCALATION: ...'", lead_prompt)

    def test_software_house_continue_command_replans_without_provider_turns(self):
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-continue-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Drive the software-house session through a CONTINUE loop.",
        )

        self.assertIsNotNone(session)
        self.assertEqual(trigger.calls[-1]["agent"], "implementation_engineer")

        messages.add(
            sender="implementation_engineer",
            text="Work performed: landed the slice.\nValidation: focused checks ran.\nEvidence: artifact pending review.\nBlocker: none",
            channel="general",
        )
        messages.add(
            sender="qa_reviewer",
            text="Assessment: not yet at bar.\nEvidence check: implementation exists.\nGaps: premium loading state is still missing.\nFINAL_STATUS: CONTINUE",
            channel="general",
        )

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 3)
        self.assertEqual(active["waiting_on"], "implementation_engineer")

        recent = messages.get_recent(12, channel="general")
        deterministic_messages = [
            msg for msg in recent if (msg.get("metadata") or {}).get("session_deterministic_turn")
        ]
        self.assertTrue(any(msg["sender"] == "delivery_lead" and "Next command:" in msg["text"] for msg in deterministic_messages))
        self.assertTrue(any(msg["sender"] == "product_manager" and "premium loading state is still missing" in msg["text"] for msg in deterministic_messages))

    def test_software_house_delivery_safe_mode_completes_with_verifiable_role_agent_cycle(self):
        registry = _FakeRegistry(set())
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-safe-mode-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        cast = {
            "delivery_lead": "northstar-delivery",
            "product_manager": "northstar-product",
            "technical_lead": "northstar-technical",
            "implementation_engineer": "northstar-implementation",
            "qa_reviewer": "northstar-qa",
        }

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast=cast,
            started_by="tester",
            goal="Run a governance-only proof with no file changes.",
            session_options={"safe_mode": True},
        )

        self.assertIsNotNone(session)
        self.assertEqual(session["state"], "complete")
        self.assertEqual(len(trigger.calls), 0)
        self.assertIsNone(self.store.get_active("general"))

        transcript = [
            msg for msg in messages.get_recent(40, channel="general")
            if (msg.get("metadata") or {}).get("session_id") == session["id"]
        ]
        role_messages = [msg for msg in transcript if (msg.get("metadata") or {}).get("session_role")]
        self.assertEqual(
            [msg["sender"] for msg in role_messages],
            [
                "delivery_lead",
                "product_manager",
                "technical_lead",
                "implementation_engineer",
                "qa_reviewer",
                "delivery_lead",
            ],
        )
        self.assertEqual(
            [(msg.get("metadata") or {}).get("session_agent") for msg in role_messages],
            [
                "northstar-delivery",
                "northstar-product",
                "northstar-technical",
                "northstar-implementation",
                "northstar-qa",
                "northstar-delivery",
            ],
        )
        self.assertTrue(all((msg.get("metadata") or {}).get("session_safe_mode") for msg in role_messages))

        handoffs = [msg for msg in transcript if msg.get("type") == "session_handoff"]
        self.assertEqual(
            [
                ((msg.get("metadata") or {}).get("from_role"), (msg.get("metadata") or {}).get("to_role"))
                for msg in handoffs
            ],
            [
                ("delivery_lead", "product_manager"),
                ("product_manager", "technical_lead"),
                ("technical_lead", "implementation_engineer"),
                ("implementation_engineer", "qa_reviewer"),
                ("qa_reviewer", "delivery_lead"),
            ],
        )

    def test_emit_current_phase_banner_skips_duplicate_after_deterministic_start(self):
        registry = _FakeRegistry({
            "delivery_lead",
            "product_manager",
            "technical_lead",
            "implementation_engineer",
            "qa_reviewer",
        })
        messages = MessageStore(str(Path(self._tmp.name) / "software-house-banner-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="software-house-delivery",
            channel="general",
            cast={
                "delivery_lead": "delivery_lead",
                "product_manager": "product_manager",
                "technical_lead": "technical_lead",
                "implementation_engineer": "implementation_engineer",
                "qa_reviewer": "qa_reviewer",
            },
            started_by="tester",
            goal="Avoid duplicate execute banner after deterministic start.",
        )

        self.assertIsNotNone(session)
        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 3)

        messages.add(
            sender="system",
            text="Session started: Northstar Software Delivery",
            msg_type="session_start",
            channel="general",
            metadata={"session_id": active["id"]},
        )
        engine.emit_current_phase_banner(active)

        execute_banners = [
            msg for msg in messages.get_recent(20, channel="general")
            if msg.get("type") == "session_phase"
            and (msg.get("metadata") or {}).get("session_id") == active["id"]
            and (msg.get("metadata") or {}).get("phase") == 3
            and msg.get("text") == "Phase: Execute"
        ]
        self.assertEqual(len(execute_banners), 1)

    def test_rebinds_stale_runtime_name_to_live_role_instance(self):
        self.registry = _FakeRegistry(
            {"codex", "codex-1", "codex-3", "codex-4"},
            instances={
                "codex": {"name": "codex", "label": "reviewer", "base": "codex"},
                "codex-1": {"name": "codex-1", "label": "challenger", "base": "codex"},
                "codex-3": {"name": "codex-3", "label": "planner", "base": "codex"},
                "codex-4": {"name": "codex-4", "label": "implementer", "base": "codex"},
            },
            renames={"codex-2": "codex"},
        )
        messages = MessageStore(str(Path(self._tmp.name) / "rebind-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=self.registry)

        session = engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        messages.add(sender="implementer", text="Baseline ready. Slice 1 should tighten visual hierarchy.", channel="general")
        messages.add(sender="planner", text="Plan ready. Critique the current slice before implementation.", channel="general")

        self.assertEqual(trigger.calls[-1]["agent"], "codex")
        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["waiting_on"], "codex")
        self.assertEqual(active["cast"]["reviewer"], "codex")

    def test_human_nudge_to_expected_agent_does_not_pause_session(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        self._drive_to_assess()

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["state"], "waiting")
        self.assertEqual(active["waiting_on"], "codex-2")

        self._send("Claudio", "@codex-2 prosegui")

        nudged = self.store.get_active("general")
        self.assertIsNotNone(nudged)
        self.assertEqual(nudged["state"], "waiting")
        self.assertEqual(nudged["waiting_on"], "codex-2")

    def test_human_nudge_resumes_paused_session_and_retriggers_expected_agent(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        self._drive_to_assess()
        paused = self.store.pause(session["id"])
        self.assertIsNotNone(paused)
        self.assertEqual(paused["state"], "paused")

        trigger_calls_before = len(self.trigger.calls)
        self._send("Claudio", "@codex-2 prosegui")

        nudged = self.store.get_active("general")
        self.assertIsNotNone(nudged)
        self.assertEqual(nudged["state"], "waiting")
        self.assertEqual(nudged["waiting_on"], "codex-2")
        self.assertGreater(len(self.trigger.calls), trigger_calls_before)
        self.assertEqual(self.trigger.calls[-1]["agent"], "codex-2")

    def test_periodic_planner_review_wakes_planner_when_work_stalls(self):
        session = self._start_session()

        with patch("session_engine.time.time", return_value=session["updated_at"] + 181):
            woke = self.engine.trigger_periodic_planner_reviews(
                idle_seconds=180,
                repeat_seconds=300,
            )

        self.assertEqual(woke, 1)
        self.assertEqual(self.trigger.calls[-1]["agent"], "planner")
        self.assertIn("PLANNER HEARTBEAT", self.trigger.calls[-1]["prompt"])
        self.assertIn("CURRENT TURN OWNER: implementer", self.trigger.calls[-1]["prompt"])

        trigger_calls_after_first_wake = len(self.trigger.calls)
        with patch("session_engine.time.time", return_value=session["updated_at"] + 250):
            woke_again = self.engine.trigger_periodic_planner_reviews(
                idle_seconds=180,
                repeat_seconds=300,
            )

        self.assertEqual(woke_again, 0)
        self.assertEqual(len(self.trigger.calls), trigger_calls_after_first_wake)

    def test_periodic_planner_review_skips_when_planner_is_current_turn(self):
        session = self._start_session()
        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["waiting_on"], "planner")

        trigger_calls_before = len(self.trigger.calls)
        with patch("session_engine.time.time", return_value=active["updated_at"] + 181):
            woke = self.engine.trigger_periodic_planner_reviews(
                idle_seconds=180,
                repeat_seconds=300,
            )

        self.assertEqual(woke, 0)
        self.assertEqual(len(self.trigger.calls), trigger_calls_before)

    def test_periodic_review_uses_template_lead_role_when_no_planner_exists(self):
        registry = _FakeRegistry({"proposer", "for", "against", "moderator"})
        messages = MessageStore(str(Path(self._tmp.name) / "debate-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        session = engine.start_session(
            template_id="debate",
            channel="general",
            cast={
                "proposer": "proposer",
                "for": "for",
                "against": "against",
                "moderator": "moderator",
            },
            started_by="tester",
            goal="Resolve a product decision.",
        )

        self.assertIsNotNone(session)
        self.assertEqual(trigger.calls[-1]["agent"], "proposer")

        with patch("session_engine.time.time", return_value=session["updated_at"] + 181):
            woke = engine.trigger_periodic_planner_reviews(
                idle_seconds=180,
                repeat_seconds=300,
            )

        self.assertEqual(woke, 1)
        self.assertEqual(trigger.calls[-1]["agent"], "moderator")
        self.assertIn("SESSION LEAD HEARTBEAT", trigger.calls[-1]["prompt"])
        self.assertIn("COMMAND ROLE: Moderator", trigger.calls[-1]["prompt"])

    def test_periodic_planner_review_skips_busy_planner(self):
        session = self._start_session()
        self.trigger.status = {"planner": {"busy": True}}

        trigger_calls_before = len(self.trigger.calls)
        with patch("session_engine.time.time", return_value=session["updated_at"] + 181):
            woke = self.engine.trigger_periodic_planner_reviews(
                idle_seconds=180,
                repeat_seconds=300,
            )

        self.assertEqual(woke, 0)
        self.assertEqual(len(self.trigger.calls), trigger_calls_before)

    def test_compact_prompt_requests_short_delta_only_output(self):
        session = self._start_session()

        prompt = self.trigger.calls[-1]["prompt"]
        self.assertIn("Be concise:", prompt)
        self.assertIn("reply via chat_send in #general", prompt)
        self.assertNotIn("IMPORTANT: You MUST respond", prompt)

    def test_prompts_assign_artifact_ownership_and_blocker_handoff(self):
        self._start_session()

        implementer_prompt = self.trigger.calls[-1]["prompt"]
        self.assertIn("You own concrete execution, validation, and the evidence", implementer_prompt)
        self.assertIn("Do not delegate missing artifacts or blocker evidence upward", implementer_prompt)

        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")
        planner_prompt = self.trigger.calls[-1]["prompt"]
        self.assertIn("Turn the current goal and review findings into one concrete next slice", planner_prompt)

        self._send("planner", "Plan ready. Slice 1 targets route list premium polish.")
        reviewer_prompt = self.trigger.calls[-1]["prompt"]
        self.assertIn("state whether a gap is executor-owned work or a true external blocker", reviewer_prompt)

    def test_assess_blocked_interrupts_session(self):
        session = self._start_session()

        self._drive_to_assess()
        self._send(
            "reviewer",
            "Cannot approve. FINAL_STATUS: BLOCKED\nBLOCKER: four android png screenshots are missing for mobile proof.",
        )
        self._send(
            "challenger",
            "This is externally blocked. FINAL_STATUS: BLOCKED\nBLOCKER: four android png screenshots are missing for mobile proof.",
        )

        self.assertIsNone(self.store.get_active("general"))
        blocked = self.store.get(session["id"])
        self.assertIsNotNone(blocked)
        self.assertEqual(blocked["state"], "interrupted")
        self.assertIn("blocked: external dependency or missing proof artifact", blocked["interrupt_reason"])
        self.assertIn("four android png screenshots are missing for mobile proof", blocked["interrupt_reason"])

    def test_pauses_after_repeated_non_productive_loop(self):
        self._start_session()

        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")
        self._send("planner", "Plan ready. Current slice targets hierarchy only.")
        self._send("reviewer", "Plan critique: keep it narrow.")
        self._send("challenger", "Plan critique: avoid generic polish.")
        self._send(
            "implementer",
            "Implementer update: Files changed in this pass: none. No new evidence was produced.",
        )
        self._send("reviewer", "FINAL_STATUS: CONTINUE")
        self._send("challenger", "FINAL_STATUS: CONTINUE")
        self._send("planner", "PLANNER_NEXT_SLICE:\n\nNext slice target: external/manual proof capture only.")

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 2)
        self.assertEqual(active["waiting_on"], "reviewer")

        self._send("reviewer", "Plan critique: still proof-first.")
        self._send("challenger", "Plan critique: no speculative UI edits.")
        self._send(
            "implementer",
            "Implementer update for current slice: files changed: none. Still blocked on the same proof path.",
        )
        self._send("reviewer", "FINAL_STATUS: CONTINUE")
        self._send("challenger", "FINAL_STATUS: CONTINUE")
        self._send("planner", "PLANNER_NEXT_SLICE:\n\nNext slice target: external/manual proof capture only.")

        paused = self.store.get_active("general")
        self.assertIsNotNone(paused)
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(paused["current_phase"], 5)

        recent = self.messages.get_recent(20, channel="general")
        guard_messages = [msg for msg in recent if msg.get("type") == "session_guard"]
        self.assertTrue(guard_messages)
        self.assertIn("Moderator stop", guard_messages[-1]["text"])

    def test_pauses_after_repeated_non_actionable_implementer_replies(self):
        self._start_session()

        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")
        self._send("planner", "Plan ready. Current slice targets hierarchy only.")
        self._send("reviewer", "Plan critique: keep it narrow.")
        self._send("challenger", "Plan critique: avoid generic polish.")
        self._send("implementer", "I'm ready, but there's no task yet.")
        self._send("reviewer", "FINAL_STATUS: CONTINUE")
        self._send("challenger", "FINAL_STATUS: CONTINUE")
        self._send("planner", "PLANNER_NEXT_SLICE:\n\nNext slice target: direct proof capture only.")

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 2)
        self.assertEqual(active["waiting_on"], "reviewer")

        self._send("reviewer", "Plan critique: still proof-first.")
        self._send("challenger", "Plan critique: no speculative UI edits.")
        self._send("implementer", "I don't have a concrete task to execute yet.")
        self._send("reviewer", "FINAL_STATUS: CONTINUE")
        self._send("challenger", "FINAL_STATUS: CONTINUE")
        self._send("planner", "PLANNER_NEXT_SLICE:\n\nNext slice target: direct proof capture only.")

        paused = self.store.get_active("general")
        self.assertIsNotNone(paused)
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(paused["current_phase"], 5)

        recent = self.messages.get_recent(20, channel="general")
        guard_messages = [msg for msg in recent if msg.get("type") == "session_guard"]
        self.assertTrue(guard_messages)
        self.assertIn("non-actionable reply", guard_messages[-1]["text"])

    def test_pauses_after_repeated_same_blocker_cycle(self):
        self._start_session()

        self._send("implementer", "Baseline ready. Slice 1 should tighten visual hierarchy.")
        self._send("planner", "Plan ready. Current slice targets proof completion.")
        self._send("reviewer", "Plan critique: evidence must be real.")
        self._send("challenger", "Plan critique: no speculative approval.")
        self._send(
            "implementer",
            "Implemented what is locally possible. BLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "reviewer",
            "FINAL_STATUS: CONTINUE\nBLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "challenger",
            "FINAL_STATUS: CONTINUE\nBLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "planner",
            "PLANNER_NEXT_SLICE:\n\nNext slice target: four android png screenshots are missing for routes and route detail mobile proof.",
        )

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 2)
        self.assertEqual(active["waiting_on"], "reviewer")

        self._send("reviewer", "Plan critique: still the same blocker.")
        self._send("challenger", "Plan critique: do not pretend this is different work.")
        self._send(
            "implementer",
            "Still blocked. BLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "reviewer",
            "FINAL_STATUS: CONTINUE\nBLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "challenger",
            "FINAL_STATUS: CONTINUE\nBLOCKER: four android png screenshots are missing for routes and route detail mobile proof.",
        )
        self._send(
            "planner",
            "PLANNER_NEXT_SLICE:\n\nNext slice target: four android png screenshots are missing for routes and route detail mobile proof.",
        )

        paused = self.store.get_active("general")
        self.assertIsNotNone(paused)
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(paused["current_phase"], 5)

        recent = self.messages.get_recent(20, channel="general")
        guard_messages = [msg for msg in recent if msg.get("type") == "session_guard"]
        self.assertTrue(guard_messages)
        self.assertIn("same blocker repeated", guard_messages[-1]["text"])

    def test_loop_guard_uses_phase_kinds_for_non_premium_templates(self):
        self.store._templates["ops-loop"] = {
            "id": "ops-loop",
            "name": "Ops Loop",
            "roles": ["lead", "executor", "critic"],
            "governance": {
                "lead_role": "lead",
                "planning_role": "lead",
                "executor_roles": ["executor"],
                "review_roles": ["critic"],
            },
            "phases": [
                {
                    "name": "Frame",
                    "participants": ["lead"],
                    "phase_kind": "plan",
                    "prompt": "Define the work.",
                },
                {
                    "name": "Do Work",
                    "participants": ["executor"],
                    "phase_kind": "execute",
                    "prompt": "Execute the task.",
                },
                {
                    "name": "Judge",
                    "participants": ["critic"],
                    "phase_kind": "assess",
                    "prompt": "Assess the result.",
                    "is_output": True,
                    "complete_when_all_contain": "FINAL_STATUS: APPROVED",
                },
                {
                    "name": "Replan",
                    "participants": ["lead"],
                    "phase_kind": "plan",
                    "prompt": "Choose the next slice.",
                    "loop_to_phase": 1,
                },
            ],
        }

        session = self.engine.start_session(
            template_id="ops-loop",
            channel="general",
            cast={"lead": "planner", "executor": "implementer", "critic": "reviewer"},
            started_by="tester",
            goal="Resolve an ops blocker.",
        )

        self.assertIsNotNone(session)
        self._send("lead", "Frame done. Start execution.")
        self._send("executor", "Files changed in this pass: none. Still blocked on the same dependency.")
        self._send("critic", "FINAL_STATUS: CONTINUE\nBLOCKER: external credential approval is still missing.")
        self._send("lead", "Next slice target: external credential approval is still missing.")

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_phase"], 1)
        self.assertEqual(active["waiting_on"], "implementer")

        self._send("executor", "Files changed in this pass: none. Still blocked on the same dependency.")
        self._send("critic", "FINAL_STATUS: CONTINUE\nBLOCKER: external credential approval is still missing.")
        self._send("lead", "Next slice target: external credential approval is still missing.")

        paused = self.store.get_active("general")
        self.assertIsNotNone(paused)
        self.assertEqual(paused["state"], "paused")
        self.assertEqual(paused["current_phase"], 3)


    def test_autonomous_planner_cycle_wakes_when_channel_has_no_active_session(self):
        self.messages.add(
            sender="system",
            text="Previous work loop ended.",
            channel="general",
            timestamp=100.0,
            time_str="00:01:40",
        )

        with patch("session_engine.time.time", return_value=401.0):
            woke = self.engine.trigger_autonomous_planner_cycles(
                channels=["general"],
                template_id="premium-ui-remediation",
                idle_seconds=180,
                repeat_seconds=300,
                default_goal="Keep going until the work is excellent.",
            )

        self.assertEqual(woke, 1)
        self.assertEqual(self.trigger.calls[-1]["agent"], "planner")
        self.assertIn("PLANNER AUTONOMY HEARTBEAT", self.trigger.calls[-1]["prompt"])
        self.assertIn("session_start", self.trigger.calls[-1]["prompt"])

    def test_autonomous_planner_cycle_skips_when_session_is_already_active(self):
        self._start_session()

        trigger_calls_before = len(self.trigger.calls)
        with patch("session_engine.time.time", return_value=401.0):
            woke = self.engine.trigger_autonomous_planner_cycles(
                channels=["general"],
                template_id="premium-ui-remediation",
                idle_seconds=180,
                repeat_seconds=300,
                default_goal="Keep going until the work is excellent.",
            )

        self.assertEqual(woke, 0)
        self.assertEqual(len(self.trigger.calls), trigger_calls_before)

    def test_autonomous_cycle_uses_template_lead_role(self):
        registry = _FakeRegistry({"proposer", "for", "against", "moderator"})
        messages = MessageStore(str(Path(self._tmp.name) / "debate-autonomy-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=registry)

        messages.add(
            sender="system",
            text="Previous debate ended.",
            channel="general",
            timestamp=100.0,
            time_str="00:01:40",
        )

        with patch("session_engine.time.time", return_value=401.0):
            woke = engine.trigger_autonomous_planner_cycles(
                channels=["general"],
                template_id="debate",
                idle_seconds=180,
                repeat_seconds=300,
                default_goal="Keep decisions moving.",
            )

        self.assertEqual(woke, 1)
        self.assertEqual(trigger.calls[-1]["agent"], "moderator")
        self.assertIn("SESSION LEAD AUTONOMY HEARTBEAT", trigger.calls[-1]["prompt"])
        self.assertIn("COMMAND ROLE: Moderator", trigger.calls[-1]["prompt"])

    def test_autonomous_planner_cycle_respects_repeat_interval_without_new_progress(self):
        self.messages.add(
            sender="system",
            text="Previous work loop ended.",
            channel="general",
            timestamp=100.0,
            time_str="00:01:40",
        )

        with patch("session_engine.time.time", return_value=401.0):
            first = self.engine.trigger_autonomous_planner_cycles(
                channels=["general"],
                template_id="premium-ui-remediation",
                idle_seconds=180,
                repeat_seconds=300,
                default_goal="Keep going until the work is excellent.",
            )
        with patch("session_engine.time.time", return_value=550.0):
            second = self.engine.trigger_autonomous_planner_cycles(
                channels=["general"],
                template_id="premium-ui-remediation",
                idle_seconds=180,
                repeat_seconds=300,
                default_goal="Keep going until the work is excellent.",
            )

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_enrich_exposes_human_readable_agent_display(self):
        self.registry = _FakeRegistry(
            {"codex-1", "codex-2", "codex-3", "codex-4"},
            instances={
                "codex-1": {"name": "codex-1", "label": "challenger", "base": "codex", "display_name": "Challenger (GPT-5.4)"},
                "codex-2": {"name": "codex-2", "label": "reviewer", "base": "codex", "display_name": "Reviewer (GPT-5.4)"},
                "codex-3": {"name": "codex-3", "label": "planner", "base": "codex", "display_name": "Planner (Codex)"},
                "codex-4": {"name": "codex-4", "label": "implementer", "base": "codex", "display_name": "Implementer (Codex)"},
            },
        )
        messages = MessageStore(str(Path(self._tmp.name) / "display-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=self.registry)

        session = engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        messages.add(sender="implementer", text="Baseline ready. Slice 1 should tighten visual hierarchy.", channel="general")
        messages.add(sender="planner", text="Plan ready. Critique the current slice before implementation.", channel="general")

        active = engine.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["current_agent"], "codex-2")
        self.assertEqual(active["current_agent_display"], "Reviewer (GPT-5.4)")
        self.assertEqual(active["waiting_on_display"], "Reviewer (GPT-5.4)")

    def test_tags_expected_turn_messages_with_session_role_metadata(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)

        first = self.messages.add(
            sender="codex-4",
            text="Baseline ready. Slice 1 should tighten visual hierarchy.",
            channel="general",
        )

        self.assertEqual(first.get("metadata", {}).get("session_id"), session["id"])
        self.assertEqual(first.get("metadata", {}).get("session_role"), "implementer")
        self.assertEqual(first.get("metadata", {}).get("session_phase_name"), "Baseline")

        second = self.messages.add(
            sender="codex-3",
            text="Plan ready. Critique the current slice before implementation.",
            channel="general",
        )

        self.assertEqual(second.get("metadata", {}).get("session_role"), "planner")
        self.assertEqual(second.get("metadata", {}).get("session_phase_name"), "Plan")

    def test_prefers_role_labeled_runtime_over_generic_rename_target(self):
        self.registry = _FakeRegistry(
            {"codex-1", "codex-2", "codex-3", "codex-4"},
            instances={
                "codex-1": {"name": "codex-1", "label": "Codex 1", "base": "codex", "display_name": "Codex 1 (Codex)"},
                "codex-2": {"name": "codex-2", "label": "reviewer", "base": "codex", "display_name": "Reviewer (Codex)"},
                "codex-3": {"name": "codex-3", "label": "planner", "base": "codex", "display_name": "Planner (Codex)"},
                "codex-4": {"name": "codex-4", "label": "implementer", "base": "codex", "display_name": "Implementer (Codex)"},
            },
            renames={"codex-6": "codex-1"},
        )
        messages = MessageStore(str(Path(self._tmp.name) / "role-match-agentchattr_log.jsonl"))
        trigger = _FakeTrigger()
        engine = SessionEngine(self.store, messages, trigger, registry=self.registry)

        session = engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-6",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        messages.add(sender="implementer", text="Baseline ready. Slice 1 should tighten visual hierarchy.", channel="general")
        messages.add(sender="planner", text="Plan ready. Critique the current slice before implementation.", channel="general")

        self.assertEqual(trigger.calls[-1]["agent"], "codex-2")
        active = engine.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["waiting_on"], "codex-2")
        self.assertEqual(active["cast"]["reviewer"], "codex-2")

    def test_rebind_drops_stale_derived_session_fields_from_persistence(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-2",
                "planner": "codex-3",
                "reviewer": "codex-4",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)

        active_views = self.engine.list_active()
        self.assertEqual(active_views[0]["current_agent"], "codex-2")

        persisted_before = json.loads((Path(self._tmp.name) / "session_runs.json").read_text("utf-8"))[0]
        self.assertNotIn("current_agent", persisted_before)

        self.store._sessions[0]["current_agent"] = "codex-2"
        self.store._sessions[0]["current_agent_display"] = "Implementer (Codex)"
        self.store._sessions[0]["waiting_on"] = "codex-2"
        self.store._save()

        self.store.update_cast_agent(session["id"], "implementer", "codex-3")

        persisted_after = json.loads((Path(self._tmp.name) / "session_runs.json").read_text("utf-8"))[0]
        self.assertEqual(persisted_after["cast"]["implementer"], "codex-3")
        self.assertEqual(persisted_after["waiting_on"], "codex-3")
        self.assertNotIn("current_agent", persisted_after)
        self.assertNotIn("current_agent_display", persisted_after)

    def test_retriggers_stale_waiting_agent_session(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        self._drive_to_assess()

        active = self.store.get_active("general")
        self.assertIsNotNone(active)
        self.assertEqual(active["state"], "waiting")
        self.assertEqual(active["waiting_on"], "codex-2")

        trigger_calls_before = len(self.trigger.calls)
        self.store._sessions[0]["updated_at"] = time.time() - 90
        recovered = self.engine.recover_stale_waits(max_idle_seconds=30)

        self.assertEqual(recovered, 1)
        self.assertGreater(len(self.trigger.calls), trigger_calls_before)
        self.assertEqual(self.trigger.calls[-1]["agent"], "codex-2")

    def test_does_not_retrigger_fresh_waiting_agent_session(self):
        session = self.engine.start_session(
            template_id="premium-ui-remediation",
            channel="general",
            cast={
                "implementer": "codex-4",
                "planner": "codex-3",
                "reviewer": "codex-2",
                "challenger": "codex-1",
            },
            started_by="tester",
            goal="Match the mockups before stopping.",
        )

        self.assertIsNotNone(session)
        self._drive_to_assess()

        trigger_calls_before = len(self.trigger.calls)
        recovered = self.engine.recover_stale_waits(max_idle_seconds=300)

        self.assertEqual(recovered, 0)
        self.assertEqual(len(self.trigger.calls), trigger_calls_before)


if __name__ == "__main__":
    unittest.main()