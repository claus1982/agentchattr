import sys
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from session_store import validate_session_template


class SessionTemplateValidationTests(unittest.TestCase):
    def test_accepts_governance_phase_kind_and_interrupt_fields(self):
        errors = validate_session_template(
            {
                "name": "Ops Loop",
                "roles": ["lead", "executor", "critic"],
                "governance": {
                    "lead_role": "lead",
                    "planning_role": "lead",
                    "client_escalation_role": "lead",
                    "quality_gate_role": "critic",
                    "executor_roles": ["executor"],
                    "review_roles": ["critic"],
                    "deterministic_phase_kinds": ["frame", "plan", "review", "decision"],
                    "autonomy_contract": "gfe",
                    "client_escalation_threshold": "hard-blocker-only",
                },
                "phases": [
                    {
                        "name": "Plan",
                        "participants": ["lead"],
                        "phase_kind": "plan",
                        "prompt": "Define the slice.",
                    },
                    {
                        "name": "Execute",
                        "participants": ["executor"],
                        "phase_kind": "execute",
                        "prompt": "Do the work.",
                    },
                    {
                        "name": "Assess",
                        "participants": ["critic"],
                        "phase_kind": "assess",
                        "prompt": "Judge the result.",
                        "is_output": True,
                        "interrupt_when_all_contain": "FINAL_STATUS: BLOCKED",
                        "interrupt_reason": "blocked externally",
                    },
                ],
            }
        )

        self.assertEqual(errors, [])

    def test_rejects_unknown_governance_roles_and_phase_kinds(self):
        errors = validate_session_template(
            {
                "name": "Broken Template",
                "roles": ["lead", "executor"],
                "governance": {
                    "lead_role": "ghost",
                    "client_escalation_role": "phantom",
                    "quality_gate_role": "ghost",
                    "executor_roles": ["executor", "ghost"],
                    "deterministic_phase_kinds": ["chaos"],
                    "autonomy_contract": "anything-goes",
                    "client_escalation_threshold": "ask-often",
                },
                "phases": [
                    {
                        "name": "Plan",
                        "participants": ["lead"],
                        "phase_kind": "chaos",
                        "prompt": "Define the slice.",
                        "is_output": True,
                    }
                ],
            }
        )

        self.assertTrue(any("governance.lead_role" in error for error in errors))
        self.assertTrue(any("governance.client_escalation_role" in error for error in errors))
        self.assertTrue(any("governance.quality_gate_role" in error for error in errors))
        self.assertTrue(any("governance.executor_roles" in error for error in errors))
        self.assertTrue(any("governance.deterministic_phase_kinds" in error for error in errors))
        self.assertTrue(any("governance.autonomy_contract" in error for error in errors))
        self.assertTrue(any("governance.client_escalation_threshold" in error for error in errors))
        self.assertTrue(any("phase_kind" in error for error in errors))

    def test_all_builtin_templates_validate(self):
        templates_dir = ROOT / "session_templates"
        failures = {}

        for file_path in templates_dir.glob("*.json"):
            template = json.loads(file_path.read_text("utf-8"))
            errors = validate_session_template(template)
            if errors:
                failures[file_path.name] = errors

        self.assertEqual(failures, {})


if __name__ == "__main__":
    unittest.main()
