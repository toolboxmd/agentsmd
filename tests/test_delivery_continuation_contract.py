#!/usr/bin/env python3
"""Deterministic proof for authorized delivery and continuation."""

from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from pathlib import Path

from tests.delivery_continuation_validator import load_cases, validate_case


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_HEADING = "## Authority and continuation"
FIXTURES = ROOT / "tests/fixtures/delivery_continuation_cases.json"
VALIDATOR = ROOT / "tests/delivery_continuation_validator.py"


def section(document: str, heading: str) -> str:
    return document.split(f"## {heading}", 1)[1].split("\n## ", 1)[0]


class DeliveryContinuationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = load_cases(FIXTURES)
        cls.contract = cls.payload["contract"]
        cls.cases = {case["id"]: case for case in cls.payload["cases"]}

    def test_global_contract_has_one_authoritative_location(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertEqual(agents.count(CONTRACT_HEADING), 1)
        contract = agents.split(CONTRACT_HEADING, 1)[1].split("\n## ", 1)[0]
        self.assertIn("Delivery Authority", contract)
        self.assertIn("fresh context", contract)
        self.assertIn("durable handoff", contract)
        self.assertIn("recover", contract)

    def test_work_delivery_human_gates_and_handoff_use_one_contract(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for heading in ("Work", "Delivery", "Human gates", "Handoff"):
            with self.subTest(heading=heading):
                self.assertIn(
                    "Authority and continuation", section(agents, heading)
                )
        self.assertEqual(agents.count("Delivery Authority is authorization"), 1)

    def test_glossary_and_to_tickets_point_to_the_global_contract(self) -> None:
        glossary = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
        marker = "**Delivery Authority**:"
        self.assertEqual(glossary.count(marker), 1)
        entry = glossary.split(marker, 1)[1].split("\n\n**", 1)[0]
        self.assertLessEqual(len(entry.strip().splitlines()), 5)
        self.assertIn("identified outcome or scope", entry)
        self.assertIn("Issues and", entry)
        self.assertIn("repositories", entry)

        tickets = (ROOT / "skills/to-tickets/SKILL.md").read_text(encoding="utf-8")
        boundary = section(tickets, "6. Continue at the implementation boundary")
        self.assertIn("Authority and continuation", boundary)
        self.assertIn("minimal durable context packet", boundary)
        self.assertNotIn("full current request into that handoff", boundary)

    def test_contract_is_host_neutral_and_does_not_create_an_orchestrator(
        self,
    ) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        contract = section(agents, "Authority and continuation")
        for host_control in ("codex_app", "create_thread", "Claude", "Codex"):
            self.assertNotIn(host_control, contract)
        self.assertIn("adapter choices", contract)
        self.assertIn("persistent orchestration service", contract)

    def test_behavioral_live_verification_remains_user_owned(self) -> None:
        override = (ROOT / "AGENTS.override.md").read_text(encoding="utf-8")
        normalized = " ".join(override.split())
        self.assertIn("User-owned behavioral Live Verification", normalized)
        self.assertIn("after release through normal work in real projects", normalized)

    def test_merge_experiment_evidence_and_supersession_are_truthful(self) -> None:
        evidence = self.payload["evidence"]["merge_authority_experiment"]
        self.assertEqual(evidence["issue"], "toolboxmd/agentsmd#29")
        self.assertEqual(evidence["released_version"], "5.0.0")
        self.assertEqual(evidence["fresh_session_observations"], 0)
        self.assertEqual(evidence["required_observations"], 3)
        self.assertFalse(evidence["stop_case_observed"])
        self.assertEqual(
            evidence["decision_lane_superseded_when"],
            "toolboxmd/agentsmd#46 merges",
        )
        self.assertEqual(evidence["historical_disposition"], "preserve")

    def test_authorized_implementation_continues_without_another_prompt(
        self,
    ) -> None:
        case = self.cases["authorized-continuation"]

        self.assertEqual(validate_case(case, self.contract), [])
        self.assertEqual(
            case["request"]["operations"],
            self.contract["implementation_operations"],
        )
        self.assertEqual(case["expected"]["decision"], "continue")
        self.assertEqual(case["expected"]["reauthorization_prompts"], 0)

    def test_structured_fixtures_cover_every_acceptance_branch(self) -> None:
        self.assertEqual(
            set(self.cases),
            {
                "authorized-continuation",
                "material-change-reauthorization",
                "explicit-stop",
                "unrelated-scope-isolation",
                "minimal-fresh-context",
                "concise-report-back",
                "next-issue-advancement",
                "blocked-next-issue",
                "interrupted-same-issue-resumption",
                "recovery",
                "completed-work-non-recreation",
                "missing-authority",
                "truthful-failure",
            },
        )
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    case["contract_location"],
                    self.contract["authoritative_location"],
                )
                self.assertEqual(validate_case(case, self.contract), [])

    def test_authority_boundaries_fail_closed(self) -> None:
        material = self.cases["material-change-reauthorization"]
        self.assertEqual(
            material["expected"]["decision"], "reauthorization-required"
        )
        self.assertEqual(material["expected"]["reauthorization_prompts"], 1)

        stopped = self.cases["explicit-stop"]
        self.assertEqual(stopped["expected"]["decision"], "stop-explicit")
        self.assertEqual(stopped["expected"]["reauthorization_prompts"], 0)

        unrelated = self.cases["unrelated-scope-isolation"]
        self.assertEqual(unrelated["expected"]["decision"], "authority-required")

        missing = self.cases["missing-authority"]
        self.assertEqual(missing["expected"]["decision"], "authority-required")

        self.assertEqual(
            set(self.contract["material_change_fields"]),
            {
                "outcome",
                "scope",
                "risk",
                "authority",
                "exact-candidate",
                "target",
                "protected-external-impact",
            },
        )
        self.assertEqual(
            self.contract["agent_owned_decisions"],
            ["routine-reversible-architecture"],
        )
        self.assertEqual(
            set(self.contract["human_owned_decisions"]),
            {
                "project-direction",
                "product-taste",
                "consequential-or-difficult-to-reverse-architecture",
                "credentials",
                "customer-data",
                "money",
                "destructive-production-change",
                "authority-never-granted",
            },
        )

        leaked = copy.deepcopy(self.cases["authorized-continuation"])
        leaked["request"]["repository"] = "toolboxmd/unrelated"
        self.assertTrue(validate_case(leaked, self.contract))

        empty_scope = copy.deepcopy(self.cases["authorized-continuation"])
        empty_scope["authority"] = {}
        empty_scope["request"] = {}
        empty_scope["expected"] = {
            "decision": "authority-required",
            "reauthorization_prompts": 1,
        }
        self.assertEqual(validate_case(empty_scope, self.contract), [])

        unknown_operation = copy.deepcopy(
            self.cases["authorized-continuation"]
        )
        unknown_operation["authority"]["operations"].append(
            "mystery-operation"
        )
        unknown_operation["request"]["operations"].append(
            "mystery-operation"
        )
        unknown_operation["expected"] = {
            "decision": "authority-required",
            "reauthorization_prompts": 1,
        }
        self.assertEqual(validate_case(unknown_operation, self.contract), [])

    def test_unknown_proof_states_and_events_fail_closed(self) -> None:
        unknown_proof = copy.deepcopy(
            self.cases["authorized-continuation"]
        )
        unknown_proof["proof_state"] = "probably-passed"
        self.assertTrue(validate_case(unknown_proof, self.contract))

        unknown_event = copy.deepcopy(
            self.cases["authorized-continuation"]
        )
        unknown_event["event"] = "mystery-transition"
        self.assertTrue(validate_case(unknown_event, self.contract))

    def test_each_external_operation_requires_exact_authority_and_target(
        self,
    ) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        contract_text = section(agents, "Authority and continuation")
        self.assertIn(
            "After the mutation, verify the resulting live state before "
            "reporting success.",
            " ".join(contract_text.split()),
        )

        for operation in self.contract["separately_authorized_operations"]:
            case = copy.deepcopy(self.cases["authorized-continuation"])
            case["request"]["operations"].append(operation)
            case["request"]["targets"][operation] = f"target://{operation}"
            with self.subTest(operation=operation, boundary="operation"):
                self.assertTrue(validate_case(case, self.contract))

            case["authority"]["operations"].append(operation)
            with self.subTest(operation=operation, boundary="target"):
                self.assertTrue(validate_case(case, self.contract))

            case["authority"]["targets"][operation] = f"target://{operation}"
            with self.subTest(operation=operation, boundary="authorized"):
                self.assertEqual(validate_case(case, self.contract), [])

            case["reported_delivery_states"] = {
                "implementation": "implemented",
                "proof": "passed",
                "commit": "committed",
                "push": "pushed",
                "pr": "opened",
                "merge": "not merged",
                "release": "not released",
                "publication": "not published",
                "distribution": "not distributed",
                "installation": "not installed",
                "deployment": "not deployed",
                "behavioral-live-verification": "pending",
            }
            case["reported_delivery_states"][operation] = self.contract[
                "successful_delivery_states"
            ][operation]
            with self.subTest(operation=operation, boundary="result-missing"):
                self.assertTrue(validate_case(case, self.contract))

            case["verified_external_results"] = {
                operation: {
                    "target": f"target://{operation}",
                    "state": self.contract["successful_delivery_states"][
                        operation
                    ],
                }
            }
            with self.subTest(operation=operation, boundary="result-verified"):
                self.assertEqual(validate_case(case, self.contract), [])

            case["verified_external_results"][operation]["target"] = (
                "target://wrong"
            )
            with self.subTest(operation=operation, boundary="result-mismatch"):
                self.assertTrue(validate_case(case, self.contract))

            case["verified_external_results"][operation] = {
                "target": f"target://{operation}",
                "state": "unknown-result",
            }
            with self.subTest(operation=operation, boundary="state-mismatch"):
                self.assertTrue(validate_case(case, self.contract))

    def test_fresh_context_is_minimal_and_coordinator_advances_independently(
        self,
    ) -> None:
        fresh = self.cases["minimal-fresh-context"]
        self.assertEqual(
            fresh["fresh_context_seed"],
            self.contract["fresh_context_fields"],
        )
        self.assertFalse(fresh["prior_transcript_included"])
        self.assertEqual(fresh["expected"]["context_mode"], "fresh")

        advanced = self.cases["next-issue-advancement"]
        self.assertTrue(advanced["coordinator_verified_git_and_github"])
        self.assertEqual(
            set(advanced["handoff"]), set(self.contract["handoff_fields"])
        )
        self.assertFalse(advanced["prior_transcript_included"])
        self.assertEqual(advanced["expected"]["decision"], "start-next-fresh")

        blocked = self.cases["blocked-next-issue"]
        self.assertFalse(blocked["blockers_clear"])
        self.assertEqual(blocked["expected"]["decision"], "blocked")
        self.assertNotIn("fresh_context_seed", blocked)

        transcript = copy.deepcopy(fresh)
        transcript["prior_transcript_included"] = True
        self.assertTrue(validate_case(transcript, self.contract))

    def test_handoff_recovery_and_interruption_preserve_exact_state(self) -> None:
        handoff = self.cases["concise-report-back"]
        self.assertEqual(
            set(handoff["handoff"]), set(self.contract["handoff_fields"])
        )
        self.assertEqual(handoff["handoff_channels"], ["issue", "pr"])

        recovery = self.cases["recovery"]
        self.assertEqual(
            set(recovery["recovered_state"]),
            set(self.contract["recovery_fields"]),
        )

        interrupted = self.cases["interrupted-same-issue-resumption"]
        self.assertEqual(interrupted["expected"]["context_mode"], "resume-same")

        incomplete = copy.deepcopy(handoff)
        del incomplete["handoff"]["proof-state"]
        self.assertTrue(validate_case(incomplete, self.contract))

    def test_event_specific_evidence_is_required(self) -> None:
        missing_handoff = copy.deepcopy(self.cases["concise-report-back"])
        del missing_handoff["handoff"]
        self.assertTrue(validate_case(missing_handoff, self.contract))

        missing_next_handoff = copy.deepcopy(
            self.cases["next-issue-advancement"]
        )
        del missing_next_handoff["handoff"]
        self.assertTrue(validate_case(missing_next_handoff, self.contract))

        missing_recovery = copy.deepcopy(self.cases["recovery"])
        del missing_recovery["recovered_state"]
        self.assertTrue(validate_case(missing_recovery, self.contract))

        missing_failure_report = copy.deepcopy(self.cases["truthful-failure"])
        del missing_failure_report["reported_delivery_states"]
        self.assertTrue(validate_case(missing_failure_report, self.contract))

    def test_completed_work_and_failures_remain_truthful(self) -> None:
        completed = self.cases["completed-work-non-recreation"]
        self.assertFalse(completed["expected"]["recreate_completed_work"])
        self.assertFalse(completed["expected"]["request_completed_approval"])

        failed = self.cases["truthful-failure"]
        self.assertEqual(failed["expected"]["decision"], "failed")
        self.assertEqual(
            set(failed["reported_delivery_states"]),
            set(self.contract["reported_delivery_states"]),
        )
        self.assertEqual(failed["reported_delivery_states"]["proof"], "failed")
        self.assertNotIn("delivered", failed["reported_delivery_states"].values())

        for false_label in ("delivered", "merged", "success", "released"):
            false_success = copy.deepcopy(failed)
            false_success["reported_delivery_states"]["merge"] = false_label
            with self.subTest(false_label=false_label):
                self.assertTrue(validate_case(false_success, self.contract))

        missing = self.cases["missing-authority"]
        self.assertNotIn("delivered", missing["reported_delivery_states"].values())

    def test_validator_cli_proves_every_fixture(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), "validate-cases", str(FIXTURES)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "13 cases valid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
