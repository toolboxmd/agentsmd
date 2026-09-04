#!/usr/bin/env python3
"""Public-seam proof for Repository Reconciliation execution and recovery."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tests/repository_reconciliation_validator.py"
FIXTURE = ROOT / "tests/fixtures/repository_reconciliation_cases.json"
APPROVAL_FIXTURE = (
    ROOT / "tests/fixtures/repository_reconciliation_approval.json"
)
APPROVAL_RECORD_SHA256 = (
    "368ca43b8f1c728bd9acaa3225389b21329e0715050b5988c2536cc844154c34"
)


def recorded_approval() -> dict[str, object]:
    return copy.deepcopy(
        json.loads(APPROVAL_FIXTURE.read_text())["operation"]
    )


def evaluate(
    case: dict[str, object],
    approval_record: Path = APPROVAL_FIXTURE,
    approval_record_sha256: str = APPROVAL_RECORD_SHA256,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "evaluate",
            "--approval-record",
            str(approval_record),
            "--approval-record-sha256",
            approval_record_sha256,
        ],
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


def approval_sha256(approval: dict[str, object]) -> str:
    operation = {
        field: approval[field]
        for field in ("target", "action", "force", "branch-deletion")
    }
    encoded = json.dumps(
        operation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class RepositoryReconciliationContractTests(unittest.TestCase):
    def test_fixture_publishes_every_execution_and_recovery_branch(self) -> None:
        payload = json.loads(FIXTURE.read_text())
        approval_record = json.loads(APPROVAL_FIXTURE.read_text())
        self.assertEqual(
            hashlib.sha256(APPROVAL_FIXTURE.read_bytes()).hexdigest(),
            APPROVAL_RECORD_SHA256,
        )
        self.assertEqual(
            set(approval_record), {"schema", "record-id", "operation"}
        )
        self.assertEqual(approval_record["schema"], 1)
        self.assertEqual(
            payload["contract"]["approval-record-input"],
            "out-of-band-path-and-sha256",
        )
        self.assertEqual(
            payload["contract"]["preflight-observation-fields"],
            ["kind", "exact-target", "state", "timestamp", "result", "source"],
        )
        self.assertEqual(payload["contract"]["preflight-max-age-seconds"], 60)
        self.assertEqual(
            payload["contract"]["approved-operation-fields"],
            [
                "target",
                "action",
                "force",
                "branch-deletion",
                "operation-sha256",
            ],
        )
        self.assertEqual(
            approval_record["operation"]["operation-sha256"],
            approval_sha256(approval_record["operation"]),
        )
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
            "approval record carries a canonical SHA-256 over that exact "
            "target, action, force=false, and branch-deletion=false",
            "Each request and pending or completed mutation must repeat and "
            "match the approved values and digest",
            "Load that recorded approval from its durable approval evidence "
            "separately from mutable execution, recovery, and restoration "
            "claims",
            "Select the durable approval record and its expected byte digest "
            "outside the mutable workflow input; the workflow cannot supply "
            "or replace either value",
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

    def test_recovery_rejects_synchronized_authority_substitution(self) -> None:
        for workflow_id in (
            "missed-immediate-evidence",
            "retrospective-safe-restoration",
        ):
            with self.subTest(workflow=workflow_id):
                case = workflow_case(workflow_id)
                for section in ("target",):
                    case[section]["exact-target"] = "/worktrees/unapproved/agentsmd"
                    case[section]["branch"] = "delete/unapproved"
                for section in ("request", "mutation", "recovery"):
                    case[section]["target"]["exact-target"] = (
                        "/worktrees/unapproved/agentsmd"
                    )
                    case[section]["target"]["branch"] = "delete/unapproved"
                if case.get("restoration"):
                    case["restoration"]["target"]["exact-target"] = (
                        "/worktrees/unapproved/agentsmd"
                    )
                    case["restoration"]["target"]["branch"] = (
                        "delete/unapproved"
                    )
                expanded_operation = {
                    "target": copy.deepcopy(case["target"]),
                    "action": "remove-worktree",
                    "force": False,
                    "branch-deletion": False,
                }
                expanded_sha = approval_sha256(expanded_operation)
                for section in ("request", "mutation", "recovery"):
                    case[section]["approval-sha256"] = expanded_sha
                if case.get("restoration"):
                    case["restoration"]["approval-sha256"] = expanded_sha

                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "authority-expansion")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])
                self.assertEqual(result["evidence-status"], "recovery-blocked")

                case["approved-operation"] = {
                    **expanded_operation,
                    "operation-sha256": expanded_sha,
                }
                result = evaluate(case)
                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(
                    result["reason"], "invalid-or-unapproved-input"
                )
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])

    def test_recorded_approval_is_strict_and_separate_from_workflow(self) -> None:
        base_case = workflow_case("missed-immediate-evidence")
        forged_case = copy.deepcopy(base_case)
        forged_case["approved-operation"] = recorded_approval()
        result = evaluate(forged_case)
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(result["reason"], "invalid-or-unapproved-input")

        result = evaluate(base_case, approval_record_sha256="0" * 64)
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(result["reason"], "invalid-or-unapproved-input")

        altered = json.loads(APPROVAL_FIXTURE.read_text())
        altered["operation"]["target"]["exact-target"] = (
            "/worktrees/newly-approved/agentsmd"
        )
        altered["operation"]["operation-sha256"] = approval_sha256(
            altered["operation"]
        )
        with tempfile.TemporaryDirectory() as directory:
            altered_path = Path(directory) / "approval.json"
            altered_path.write_text(json.dumps(altered))
            result = evaluate(base_case, approval_record=altered_path)
        self.assertEqual(result["decision"], "escalate")
        self.assertEqual(result["reason"], "invalid-or-unapproved-input")
        self.assertEqual(result["mutation-action"], "none")
        self.assertTrue(result["human-gate"])

        malformed_records = {
            "schema": {**json.loads(APPROVAL_FIXTURE.read_text()), "schema": 2},
            "boolean-schema": {
                **json.loads(APPROVAL_FIXTURE.read_text()),
                "schema": True,
            },
            "float-schema": {
                **json.loads(APPROVAL_FIXTURE.read_text()),
                "schema": 1.0,
            },
            "missing-operation": {"schema": 1, "record-id": "missing"},
            "unknown-field": {
                **json.loads(APPROVAL_FIXTURE.read_text()),
                "narrative": "approved earlier",
            },
        }
        for variant, record in malformed_records.items():
            with self.subTest(approval_record=variant):
                with tempfile.TemporaryDirectory() as directory:
                    malformed_path = Path(directory) / "approval.json"
                    malformed_path.write_text(json.dumps(record))
                    record_sha = hashlib.sha256(
                        malformed_path.read_bytes()
                    ).hexdigest()
                    result = evaluate(
                        base_case,
                        approval_record=malformed_path,
                        approval_record_sha256=record_sha,
                    )
                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(
                    result["reason"], "invalid-or-unapproved-input"
                )

    def test_operation_digest_is_utf8_canonical(self) -> None:
        approval = recorded_approval()
        approval["target"]["exact-target"] = "/worktrees/zażółć/agentsmd"
        self.assertEqual(
            approval_sha256(approval),
            "0c04da17cf870047305bfac0bebf7fed1b16b5e1b1406c226cd751644c0c338d",
        )

    def test_recovery_requires_exact_approved_and_executed_operation(self) -> None:
        variants = {
            "request-approval-sha-missing": (
                ("request", "approval-sha256"),
                None,
                True,
            ),
            "request-approval-sha-mismatch": (
                ("request", "approval-sha256"),
                "0" * 64,
                False,
            ),
            "mutation-force-missing": (("mutation", "force"), None, True),
            "mutation-branch-deletion-missing": (
                ("mutation", "branch-deletion"),
                None,
                True,
            ),
            "mutation-approval-sha-missing": (
                ("mutation", "approval-sha256"),
                None,
                True,
            ),
            "recovery-target": (
                ("recovery", "target", "exact-target"),
                "/worktrees/unapproved/agentsmd",
                False,
            ),
            "recovery-action": (
                ("recovery", "action"),
                "delete-branch",
                False,
            ),
            "recovery-force": (("recovery", "force"), True, False),
            "recovery-branch-deletion": (
                ("recovery", "branch-deletion"),
                True,
                False,
            ),
            "recovery-approval-sha": (
                ("recovery", "approval-sha256"),
                "0" * 64,
                False,
            ),
            "executed-force": (("mutation", "force"), True, False),
            "executed-branch-deletion": (
                ("mutation", "branch-deletion"),
                True,
                False,
            ),
        }
        for workflow_id in (
            "missed-immediate-evidence",
            "retrospective-safe-restoration",
        ):
            for variant, (path, value, delete) in variants.items():
                with self.subTest(workflow=workflow_id, variant=variant):
                    case = workflow_case(workflow_id)
                    if delete:
                        del case[path[0]][path[1]]
                    else:
                        set_case_value(case, path, value)
                    result = evaluate(case)

                    self.assertEqual(result["decision"], "escalate")
                    self.assertEqual(result["reason"], "authority-expansion")
                    self.assertEqual(result["mutation-action"], "none")
                    self.assertTrue(result["human-gate"])
                    self.assertEqual(result["evidence-status"], "recovery-blocked")

    def test_restoration_requires_exact_approved_operation(self) -> None:
        variants = {
            "target": (
                ("target", "exact-target"),
                "/worktrees/unapproved/agentsmd",
            ),
            "branch": (("target", "branch"), "delete/unapproved"),
            "action": (("action",), "delete-branch"),
            "force": (("force",), True),
            "branch-deletion": (("branch-deletion",), True),
            "approval-sha": (("approval-sha256",), "0" * 64),
        }
        for variant, (path, value) in variants.items():
            with self.subTest(variant=variant):
                case = workflow_case("retrospective-safe-restoration")
                set_case_value(case["restoration"], path, value)

                result = evaluate(case)

                self.assertEqual(result["decision"], "escalate")
                self.assertEqual(result["reason"], "authority-expansion")
                self.assertEqual(result["mutation-action"], "none")
                self.assertTrue(result["human-gate"])
                self.assertEqual(result["evidence-status"], "recovery-blocked")

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
        for section in ("target", "preflight", "request", "mutation"):
            case = workflow_case("live-preflight-success")
            case[section] = []
            cases.append((section, case))

        unhashable_kind = workflow_case("live-preflight-success")
        unhashable_kind["preflight"]["observations"][0]["kind"] = []
        cases.append(("unhashable-kind", unhashable_kind))

        empty_identity = workflow_case("live-preflight-success")
        empty_identity["target"]["issue"] = ""
        empty_identity["request"]["target"]["issue"] = ""
        empty_identity["mutation"]["target"]["issue"] = ""
        empty_identity["preflight"]["observations"][0]["exact-target"] = ""
        cases.append(("empty-identity", empty_identity))

        for kind, invalid_id in {
            "empty-workflow-id": "",
            "boolean-workflow-id": True,
            "number-workflow-id": 1,
            "list-workflow-id": [],
            "object-workflow-id": {},
        }.items():
            invalid_workflow_id = workflow_case("live-preflight-success")
            invalid_workflow_id["id"] = invalid_id
            cases.append((kind, invalid_workflow_id))

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
                    "approval-sha256": (
                        "f685daff0b69e400c4ba94a6c4b80eb7017b199be3bb8a2cb30d77cca500470e"
                    ),
                    "action": "remove-worktree",
                    "force": False,
                    "branch-deletion": False,
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
                    "approval-sha256": (
                        "f685daff0b69e400c4ba94a6c4b80eb7017b199be3bb8a2cb30d77cca500470e"
                    ),
                    "action": "remove-worktree",
                    "force": False,
                    "branch-deletion": False,
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
