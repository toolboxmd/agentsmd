from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("model_routing_v2_gates", ROOT / "gates.py")
assert SPEC and SPEC.loader
gates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gates)
DEFINITION = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
DEFINITION_SHA = "a" * 64
PACKAGE_SHA = "b" * 64


def review_artifact() -> dict:
    reviews = []
    for axis, reviewer in (
        ("standards", "root/reviewer-standards"),
        ("spec", "root/reviewer-spec"),
        ("security", "root/reviewer-security"),
    ):
        evidence = f"Independent {axis} review passed against the exact package."
        reviews.append(
            {
                "axis": axis,
                "reviewer_id": reviewer,
                "decision": "PASS",
                "evidence": evidence,
                "evidence_sha256": hashlib.sha256(evidence.encode()).hexdigest(),
            }
        )
    resolution = "The forged report path is permanently blocked by package design."
    return {
        "schema_version": 2,
        "decision": "ACCEPT",
        "definition_sha256": DEFINITION_SHA,
        "package_sha256": PACKAGE_SHA,
        "reviewed_at": "2026-08-31T12:00:00Z",
        "reviews": reviews,
        "findings": [
            {
                "id": "SEC-P1-001",
                "axis": "security",
                "priority": "P1",
                "status": "resolved",
                "summary": "A self-authored READY report used to pass validation.",
                "resolution": resolution,
                "resolution_evidence_sha256": hashlib.sha256(
                    resolution.encode()
                ).hexdigest(),
            }
        ],
        "summary": "All three independent axes passed and all P1/P2 findings are resolved.",
    }


def verifier_run(status: str, returncode: int, verifier_sha: str, workspace_sha: str) -> dict:
    return {
        "status": status,
        "returncode": returncode,
        "stdout_sha256": "c" * 64,
        "stderr_sha256": "d" * 64,
        "verifier_sha256": verifier_sha,
        "workspace_manifest_sha256": workspace_sha,
    }


def task_evidence() -> dict:
    base = "1" * 64
    known = "2" * 64
    public = "3" * 64
    hidden = "4" * 64
    return {
        "base_manifest_sha256": base,
        "known_good_manifest_sha256": known,
        "public_verifier_sha256": public,
        "hidden_verifier_sha256": hidden,
        "known_good_patch_sha256": "5" * 64,
        "runs": {
            "public_baseline": verifier_run("FAIL", 1, public, base),
            "public_known_good": verifier_run("PASS", 0, public, known),
            "hidden_baseline": verifier_run("FAIL", 1, hidden, base),
            "hidden_known_good": verifier_run("PASS", 0, hidden, known),
        },
    }


def source_evidence(task_id: str) -> dict:
    task = DEFINITION["tasks"][task_id]
    return {
        "repo": f"/controller/source/{task_id}",
        "base_commit": task["base_commit"],
        "base_tree": task["base_tree"],
        "base_ls_tree_sha256": "6" * 64,
        "historical_source_commit": task["historical_source_commit"],
        "historical_source_tree": task["historical_source_tree"],
        "historical_source_ls_tree_sha256": "7" * 64,
        "export_excludes": deepcopy(task["export_excludes"]),
        "base_archive_sha256": "8" * 64,
        "historical_source_archive_sha256": "9" * 64,
        "object_evidence_rechecked": True,
    }


def blocked_report() -> dict:
    blockers = gates.definition_blockers(DEFINITION) + [
        "independent_adversarial_review_required"
    ]
    report = {
        "schema_version": 3,
        "definition_id": DEFINITION["definition_id"],
        "definition_sha256": DEFINITION_SHA,
        "package_sha256": PACKAGE_SHA,
        "generated_at": "2026-08-31T12:00:00Z",
        "status": "BLOCKED",
        "paid_execution_authorized": False,
        "blockers": sorted(set(blockers)),
        "sources": {
            task_id: source_evidence(task_id)
            for task_id in ("use-grok", "karpathy-pointer")
        },
        "tasks": {
            "use-grok": task_evidence(),
            "karpathy-pointer": task_evidence(),
        },
        "security_tests": {
            "status": "PASS",
            "returncode": 0,
            "stdout_sha256": "e" * 64,
            "stderr_sha256": "f" * 64,
        },
        "adversarial_review": {
            "status": "MISSING",
            "artifact_sha256": None,
            "definition_sha256": None,
            "package_sha256": None,
            "unresolved_findings": [],
        },
        "external_boundary": deepcopy(DEFINITION["external_boundary"]),
        "quota_guard": deepcopy(DEFINITION["quota_guard"]),
        "offline_verifier_runtime": deepcopy(DEFINITION["offline_verifier_runtime"]),
        "payload_sha256": "0" * 64,
    }
    report["payload_sha256"] = gates.report_payload_sha256(report)
    return report


def validate(report: dict) -> None:
    gates.validate_readiness_report(
        report,
        definition=DEFINITION,
        definition_sha256=DEFINITION_SHA,
        package_sha256=PACKAGE_SHA,
        blockers=blocked_report()["blockers"],
    )


class DefinitionTests(unittest.TestCase):
    def test_current_definition_has_permanent_zero_spend_blockers(self) -> None:
        blockers = gates.definition_blockers(DEFINITION)
        self.assertIn("paid_execution_surface_absent", blockers)
        self.assertIn("trusted_external_boundary_verifier_absent", blockers)
        self.assertIn("exact_quota_ceiling_required", blockers)
        self.assertIn("external_boundary_unproven", blockers)

    def test_self_asserted_boundary_and_quota_cannot_clear_blockers(self) -> None:
        definition = deepcopy(DEFINITION)
        definition["quota_guard"]["max_used_basis_points"] = 9000
        definition["external_boundary"].update(
            {
                "status": "PROVEN",
                "accepted_adapter": "self-asserted",
                "trusted_issuer_public_key_sha256": "1" * 64,
                "receipt_sha256": "2" * 64,
            }
        )
        blockers = gates.definition_blockers(definition)
        self.assertIn("paid_execution_surface_absent", blockers)
        self.assertIn("trusted_external_boundary_verifier_absent", blockers)
        self.assertIn("quota_configuration_requires_successor_package", blockers)
        self.assertIn("external_boundary_claim_requires_successor_package", blockers)


class ReviewTests(unittest.TestCase):
    def test_strict_hash_bound_review_passes(self) -> None:
        gates.validate_adversarial_review(
            review_artifact(),
            definition_sha256=DEFINITION_SHA,
            package_sha256=PACKAGE_SHA,
        )

    def test_shallow_or_unresolved_review_fails(self) -> None:
        cases = []
        shallow = review_artifact()
        shallow["reviews"] = [{"axis": axis} for axis in gates.FROZEN_REVIEW_AXES]
        cases.append(shallow)
        timestamp = review_artifact()
        timestamp["reviewed_at"] = "not-a-dateZ"
        cases.append(timestamp)
        duplicate = review_artifact()
        duplicate["reviews"][1]["reviewer_id"] = duplicate["reviews"][0]["reviewer_id"]
        cases.append(duplicate)
        unresolved = review_artifact()
        unresolved["findings"][0]["status"] = "open"
        cases.append(unresolved)
        bad_hash = review_artifact()
        bad_hash["reviews"][0]["evidence_sha256"] = "0" * 64
        cases.append(bad_hash)
        for index, value in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(gates.GateError):
                gates.validate_adversarial_review(
                    value,
                    definition_sha256=DEFINITION_SHA,
                    package_sha256=PACKAGE_SHA,
                )


class ReadinessReportTests(unittest.TestCase):
    def test_complete_blocked_report_is_valid(self) -> None:
        validate(blocked_report())

    def test_complete_forged_ready_report_is_rejected(self) -> None:
        report = blocked_report()
        report["status"] = "READY"
        report["paid_execution_authorized"] = True
        report["blockers"] = []
        report["adversarial_review"] = {
            "status": "PASS",
            "artifact_sha256": "0" * 64,
            "definition_sha256": DEFINITION_SHA,
            "package_sha256": PACKAGE_SHA,
            "unresolved_findings": [],
        }
        report["payload_sha256"] = gates.report_payload_sha256(report)
        with self.assertRaises(gates.GateError):
            validate(report)

    def test_recomputed_self_hash_cannot_hide_evidence_mutations(self) -> None:
        mutations = {
            "stale package": lambda value: value.__setitem__("package_sha256", "0" * 64),
            "missing permanent blocker": lambda value: value["blockers"].remove(
                "paid_execution_surface_absent"
            ),
            "wrong source": lambda value: value["sources"]["use-grok"].__setitem__(
                "base_commit", "0" * 40
            ),
            "forged verifier": lambda value: value["tasks"]["use-grok"]["runs"][
                "public_known_good"
            ].__setitem__("verifier_sha256", "0" * 64),
            "runtime mutation": lambda value: value["offline_verifier_runtime"].__setitem__(
                "network", "host"
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = blocked_report()
                mutate(report)
                report["payload_sha256"] = gates.report_payload_sha256(report)
                with self.assertRaises(gates.GateError):
                    validate(report)

    def test_payload_mutation_without_rehash_is_rejected(self) -> None:
        report = blocked_report()
        report["generated_at"] = "2026-08-31T13:00:00Z"
        with self.assertRaises(gates.GateError):
            validate(report)


if __name__ == "__main__":
    unittest.main()
