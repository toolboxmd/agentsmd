#!/usr/bin/env python3
"""Public-seam proof for Repository Reconciliation execution and recovery."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tests/repository_reconciliation_validator.py"
FIXTURE = ROOT / "tests/fixtures/repository_reconciliation_cases.json"


def evaluate(case: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR), "evaluate"],
        cwd=ROOT,
        input=json.dumps(case),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


def merged_case(
    defaults: dict[str, object], overrides: dict[str, object]
) -> dict[str, object]:
    result = copy.deepcopy(defaults)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merged_case(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def workflow_case(case_id: str) -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text())
    fixture = next(
        case for case in payload["workflow-cases"] if case["id"] == case_id
    )
    return merged_case(payload["workflow-defaults"], fixture["input"])


def set_case_value(
    case: dict[str, object], path: tuple[str, ...], value: object
) -> None:
    current = case
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value


class RepositoryReconciliationContractTests(unittest.TestCase):
    def test_fixture_publishes_every_execution_and_recovery_branch(self) -> None:
        payload = json.loads(FIXTURE.read_text())
        self.assertEqual(
            payload["contract"]["preflight-observation-fields"],
            ["kind", "exact-target", "state", "timestamp", "result", "source"],
        )
        self.assertEqual(payload["contract"]["preflight-max-age-seconds"], 60)
        self.assertEqual(
            payload["contract"]["retrospective-recovery-proofs"],
            [
                "authoritative-history-available",
                "preconditions-held-continuously",
                "exact-targets-match",
                "refs-recoverable",
                "authority-sufficient",
            ],
        )
        self.assertEqual(
            set(payload["contract"]["escalation-reasons"]),
            {
                "ambiguous-recovery",
                "unsafe-restoration",
                "proof-unavailable",
                "target-mismatch",
                "authority-expansion",
                "user-data-risk",
                "user-owned-decision",
            },
        )
        cases = {case["id"]: case for case in payload["workflow-cases"]}
        self.assertEqual(
            set(cases),
            {
                "live-preflight-success",
                "live-preflight-failure",
                "missed-immediate-evidence",
                "retrospective-safe-restoration",
                "ambiguous-recovery",
                "unsafe-restoration",
            },
        )
        for case in cases.values():
            with self.subTest(case=case["id"]):
                workflow = merged_case(payload["workflow-defaults"], case["input"])
                result = evaluate(workflow)
                for key, expected in case["expected"].items():
                    self.assertEqual(result[key], expected)

    def test_agent_contract_requires_observed_preflight_and_self_healing(
        self,
    ) -> None:
        contract = " ".join((ROOT / "AGENTS.md").read_text().split())
        for required in (
            "query each approved target's live owning Issue, pull request, and "
            "exact resource state immediately before mutation",
            "exact target, observed state, timestamp, source, and result",
            "Narrative claims are not evidence",
            "no older than 60 seconds and never after the recorded mutation "
            "timestamp",
            "Bind one approved manifest identity across the request, mutation, "
            "recovery, and restoration",
            "candidate ID, exact target, branch, commit, owning Issue and pull "
            "request, expected states, action, force flag, and branch-deletion "
            "flag",
            "recover without notifying the user or requesting another approval",
            "authoritative event history proves every precondition held "
            "continuously",
            "restore the exact prior worktree from its preserved branch and "
            "commit without conflict or data loss",
            "Recovery reuses the approved target and action; it does not add "
            "cleanup targets, delete branches, use force, or broaden authority",
            "Escalate only when restoration is unsafe, proof is unavailable or "
            "ambiguous, target or authority expands, uncommitted or user data "
            "may be affected, or a user-owned decision remains",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

    def test_live_preflight_emits_exact_evidence_before_mutation(self) -> None:
        case = workflow_case("live-preflight-success")
        observations = case["preflight"]["observations"]
        result = evaluate(case)

        self.assertEqual(result["decision"], "mutate")
        self.assertEqual(result["mutation-action"], "execute-approved-action")
        self.assertFalse(result["human-gate"])
        self.assertFalse(result["user-notification"])
        self.assertEqual(result["evidence-status"], "preflight-complete")
        self.assertEqual(result["evidence"], observations)

    def test_failed_live_preflight_preserves_target_without_mutation(self) -> None:
        case = workflow_case("live-preflight-failure")
        observations = case["preflight"]["observations"]
        result = evaluate(case)

        self.assertEqual(result["decision"], "preserve")
        self.assertEqual(result["mutation-action"], "none")
        self.assertFalse(result["human-gate"])
        self.assertFalse(result["user-notification"])
        self.assertEqual(result["evidence-status"], "preflight-failed")
        self.assertEqual(result["evidence"], observations)

    def test_narrated_preflight_cannot_authorize_mutation(self) -> None:
        base_case = workflow_case("live-preflight-success")
        invalid_observations = {
            "narrative": [
                "Issue and pull request checked immediately before mutation"
            ],
            "duplicate": base_case["preflight"]["observations"]
            + [base_case["preflight"]["observations"][0]],
        }
        for evidence_kind, observations in invalid_observations.items():
            with self.subTest(evidence_kind=evidence_kind):
                case = copy.deepcopy(base_case)
                case["preflight"]["observations"] = observations
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "invalid-preflight-evidence")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])
                self.assertEqual(result["evidence-status"], "incomplete")
                self.assertEqual(result["evidence"], [])

    def test_execution_rejects_target_action_or_authority_expansion(self) -> None:
        base_case = workflow_case("live-preflight-success")
        variants = {
            "new-target": (("request", "target", "exact-target"), "/worktrees/another/agentsmd"),
            "different-action": (("request", "action"), "delete-branch"),
            "force": (("request", "force"), True),
            "branch-deletion": (("request", "branch-deletion"), True),
        }
        for expansion, (path, value) in variants.items():
            with self.subTest(expansion=expansion):
                case = copy.deepcopy(base_case)
                set_case_value(case, path, value)
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "authority-expansion")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])
                self.assertEqual(result["evidence-status"], "incomplete")

        case = copy.deepcopy(base_case)
        case["approval"]["action"] = "delete-branch"
        case["request"]["action"] = "delete-branch"
        result = evaluate(case)
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(result["reason"], "authority-expansion")
        self.assertEqual(result["mutation-action"], "none")

    def test_recovery_and_self_heal_reuse_exact_approval_and_authority(
        self,
    ) -> None:
        variants = {
            "new-target": (
                ("request", "target", "exact-target"),
                "/worktrees/other/agentsmd",
            ),
            "different-action": (("request", "action"), "delete-branch"),
            "force": (("request", "force"), True),
            "branch-deletion": (("request", "branch-deletion"), True),
            "unknown-request-field": (("request", "settings-mutation"), True),
            "mutation-action": (("mutation", "action"), "delete-branch"),
            "mutation-identity": (
                ("mutation", "target", "head"),
                "2222222222222222222222222222222222222222",
            ),
            "owner-issue": (("target", "issue"), "toolboxmd/agentsmd#14"),
            "owner-pull-request": (
                ("target", "pull-request"),
                "toolboxmd/agentsmd#42",
            ),
        }
        for workflow_id in (
            "missed-immediate-evidence",
            "retrospective-safe-restoration",
        ):
            for expansion, (path, value) in variants.items():
                with self.subTest(workflow=workflow_id, expansion=expansion):
                    case = workflow_case(workflow_id)
                    set_case_value(case, path, value)
                    result = evaluate(case)

                    self.assertEqual(result["decision"], "escalate")
                    self.assertEqual(result["reason"], "authority-expansion")
                    self.assertEqual(result["mutation-action"], "none")
                    self.assertTrue(result["human-gate"])

    def test_full_manifest_identity_is_bound_before_live_mutation(self) -> None:
        variants = {
            "id": (("target", "id"), "WT-OTHER"),
            "branch": (("target", "branch"), "fix/other"),
            "head": (
                ("target", "head"),
                "2222222222222222222222222222222222222222",
            ),
            "expected-issue-state": (
                ("target", "expected-states", "issue"),
                "open",
            ),
            "expected-pr-state": (
                ("target", "expected-states", "pull-request"),
                "closed",
            ),
            "expected-resource-state": (
                ("target", "expected-states", "resource"),
                "dirty",
            ),
            "mutation-identity": (
                ("mutation", "target", "head"),
                "2222222222222222222222222222222222222222",
            ),
        }
        observation_index = {"issue": 0, "pull-request": 1, "resource": 2}
        for drift, (path, value) in variants.items():
            with self.subTest(drift=drift):
                case = workflow_case("live-preflight-success")
                set_case_value(case, path, value)
                if path[:2] == ("target", "expected-states"):
                    case["preflight"]["observations"][observation_index[path[2]]][
                        "state"
                    ] = value
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "authority-expansion")
                self.assertEqual(result["mutation-action"], "none")

    def test_missing_preflight_shape_is_strict_and_fail_closed(self) -> None:
        variants = {
            "extra-field": {
                "status": "missing",
                "observations": [],
                "narrative": "checked earlier",
            },
            "unknown-status": {"status": "unknown", "observations": []},
            "string-observations": {"status": "missing", "observations": "none"},
            "object-observations": {"status": "missing", "observations": {}},
            "narrative-observation": {
                "status": "missing",
                "observations": ["Issue looked closed"],
            },
        }
        for malformed, preflight in variants.items():
            with self.subTest(malformed=malformed):
                case = workflow_case("missed-immediate-evidence")
                case["preflight"] = preflight
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "invalid-preflight-evidence")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])

    def test_preflight_timestamp_must_immediately_precede_mutation(self) -> None:
        variants = {
            "stale": "1970-01-01T00:00:00Z",
            "malformed": "yesterday",
            "future": "2026-09-03T10:27:00Z",
        }
        for evidence_kind, timestamp in variants.items():
            with self.subTest(evidence_kind=evidence_kind):
                case = workflow_case("live-preflight-success")
                case["preflight"]["observations"][0]["timestamp"] = timestamp
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "invalid-preflight-evidence")
                self.assertEqual(result["mutation-action"], "none")

    def test_malformed_inputs_return_structured_escalation(self) -> None:
        cases = []
        for section in ("target", "preflight", "approval", "request", "mutation"):
            case = workflow_case("live-preflight-success")
            case[section] = []
            cases.append((section, case))

        unhashable_kind = workflow_case("live-preflight-success")
        unhashable_kind["preflight"]["observations"][0]["kind"] = []
        cases.append(("unhashable-kind", unhashable_kind))

        empty_identity = workflow_case("live-preflight-success")
        empty_identity["target"]["issue"] = ""
        empty_identity["approval"]["target"]["issue"] = ""
        empty_identity["request"]["target"]["issue"] = ""
        empty_identity["mutation"]["target"]["issue"] = ""
        empty_identity["preflight"]["observations"][0]["exact-target"] = ""
        cases.append(("empty-identity", empty_identity))

        for malformed, case in cases:
            with self.subTest(malformed=malformed):
                result = evaluate(case)
                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])

    def test_missing_immediate_evidence_recovers_from_authoritative_history(
        self,
    ) -> None:
        result = evaluate(workflow_case("missed-immediate-evidence"))

        self.assertEqual(result["decision"], "recovered")
        self.assertEqual(result["mutation-action"], "none")
        self.assertFalse(result["human-gate"])
        self.assertFalse(result["user-notification"])
        self.assertEqual(result["evidence-status"], "retrospective-complete")
        self.assertEqual(
            result["evidence"],
            [
                {
                    "omission": "immediate-preflight-evidence-missing",
                    "interval": {
                        "start": "2026-09-03T10:26:00Z",
                        "end": "2026-09-03T10:27:32Z",
                    },
                    "contract-regression": (
                        "tests/test_repository_reconciliation_contract.py"
                    ),
                    "proof": {
                        "authoritative-history-available": True,
                        "preconditions-held-continuously": True,
                        "exact-targets-match": True,
                        "refs-recoverable": True,
                        "authority-sufficient": True,
                        "violated-precondition": False,
                    },
                    "exact-target": "/worktrees/9f8c/agentsmd",
                    "issue": "toolboxmd/agentsmd#39",
                    "pull-request": "toolboxmd/agentsmd#63",
                    "state": "preconditions-held-continuously",
                    "timestamp": "2026-09-03T10:27:32Z",
                    "result": "recovered",
                }
            ],
        )

    def test_violated_precondition_restores_exact_safe_worktree(self) -> None:
        result = evaluate(workflow_case("retrospective-safe-restoration"))

        self.assertEqual(result["decision"], "restored")
        self.assertEqual(result["mutation-action"], "restore-prior-worktree")
        self.assertFalse(result["human-gate"])
        self.assertFalse(result["user-notification"])
        self.assertEqual(result["evidence-status"], "restoration-complete")
        self.assertEqual(
            result["evidence"],
            [
                {
                    "omission": "immediate-preflight-evidence-missing",
                    "interval": {
                        "start": "2026-09-03T10:26:00Z",
                        "end": "2026-09-03T10:27:32Z",
                    },
                    "contract-regression": (
                        "tests/test_repository_reconciliation_contract.py"
                    ),
                    "proof": {
                        "authoritative-history-available": True,
                        "preconditions-held-continuously": False,
                        "exact-targets-match": True,
                        "refs-recoverable": True,
                        "authority-sufficient": True,
                        "violated-precondition": True,
                        "safe-restoration": True,
                    },
                    "exact-target": "/worktrees/9f8c/agentsmd",
                    "issue": "toolboxmd/agentsmd#39",
                    "pull-request": "toolboxmd/agentsmd#63",
                    "branch": "fix/39-specify-through-tickets",
                    "head": "c9ff447cefb53768f00de1b0ff26e7662be8669f",
                    "conflict": False,
                    "data-loss": False,
                    "state": "restored-at-head",
                    "timestamp": "2026-09-03T10:27:40Z",
                    "result": "restored",
                }
            ],
        )

    def test_recovery_requires_a_valid_interval(self) -> None:
        variants = {
            "null": None,
            "missing-end": {"start": "2026-09-03T10:26:00Z"},
            "malformed-end": {
                "start": "2026-09-03T10:26:00Z",
                "end": "yesterday",
            },
            "reversed": {
                "start": "2026-09-03T10:28:00Z",
                "end": "2026-09-03T10:27:32Z",
            },
            "does-not-cover-mutation": {
                "start": "2026-09-03T10:27:00Z",
                "end": "2026-09-03T10:27:32Z",
            },
        }
        for interval_kind, interval in variants.items():
            with self.subTest(interval_kind=interval_kind):
                case = workflow_case("missed-immediate-evidence")
                case["recovery"]["interval"] = interval
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "proof-unavailable")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])

    def test_ambiguous_or_unsafe_recovery_escalates_without_mutation(self) -> None:
        base_case = workflow_case("missed-immediate-evidence")
        variants = {
            "ambiguous-recovery": {"ambiguous": True},
            "unsafe-restoration": {
                "preconditions-held-continuously": False,
                "violated-precondition": True,
                "refs-recoverable": False,
            },
            "proof-unavailable": {"authoritative-history-available": False},
            "target-mismatch": {"exact-targets-match": False},
            "authority-expansion": {"authority-sufficient": False},
            "user-data-risk": {"user-data-risk": True},
            "user-owned-decision": {"user-owned-decision": True},
        }
        for expected_reason, changes in variants.items():
            with self.subTest(reason=expected_reason):
                case = copy.deepcopy(base_case)
                case["id"] = expected_reason
                case["recovery"].update(changes)
                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], expected_reason)
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])
                self.assertTrue(result["user-notification"])
                self.assertEqual(result["evidence-status"], "recovery-blocked")
                self.assertEqual(
                    result["evidence"],
                    [
                        {
                            "exact-target": "/worktrees/9f8c/agentsmd",
                            "state": "recovery-blocked",
                            "timestamp": "2026-09-03T10:27:32Z",
                            "result": expected_reason,
                        }
                    ],
                )


if __name__ == "__main__":
    unittest.main()
