#!/usr/bin/env python3
"""Fail-closed validators for the zero-spend benchmark readiness package."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,191}$")
PLACEHOLDERS = {"placeholder", "todo", "tbd", "n/a", "na", "unknown", "none"}
FROZEN_TASKS = ("use-grok", "karpathy-pointer")
FROZEN_REVIEW_AXES = ("standards", "spec", "security")
PERMANENT_BLOCKERS = {
    "paid_execution_surface_absent",
    "trusted_external_boundary_verifier_absent",
}


class GateError(ValueError):
    """Raised when a gate payload cannot be trusted."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _object(value: Any, name: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise GateError(f"{name} must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise GateError(f"{name} keys differ: missing={missing}, extra={extra}")
    return value


def _string(value: Any, name: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{name} must be a nonempty string")
    normalized = value.strip()
    if normalized.lower() in PLACEHOLDERS:
        raise GateError(f"{name} is a placeholder")
    if identifier and not IDENTIFIER_RE.fullmatch(normalized):
        raise GateError(f"{name} is not a valid identifier")
    return normalized


def _sha(value: Any, name: str) -> str:
    text = _string(value, name)
    if not SHA256_RE.fullmatch(text):
        raise GateError(f"{name} must be a lowercase SHA-256")
    return text


def _boolean(value: Any, name: str, expected: bool | None = None) -> bool:
    if not isinstance(value, bool):
        raise GateError(f"{name} must be a boolean")
    if expected is not None and value is not expected:
        raise GateError(f"{name} must be {str(expected).lower()}")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    text = _string(value, name)
    if not text.endswith("Z"):
        raise GateError(f"{name} must be UTC with a Z suffix")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise GateError(f"{name} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise GateError(f"{name} must use UTC")
    return parsed


def definition_blockers(definition: Mapping[str, Any]) -> list[str]:
    """Return blockers for this package, which can never authorize model spend."""
    blockers = set(PERMANENT_BLOCKERS)

    quota = definition.get("quota_guard")
    if not isinstance(quota, dict):
        blockers.add("quota_guard_invalid")
    else:
        ceiling = quota.get("max_used_basis_points")
        if ceiling is None:
            blockers.add("exact_quota_ceiling_required")
        else:
            blockers.add("quota_configuration_requires_successor_package")

    boundary = definition.get("external_boundary")
    if not isinstance(boundary, dict):
        blockers.add("external_boundary_invalid")
    else:
        if boundary.get("status") != "UNPROVEN":
            blockers.add("external_boundary_claim_requires_successor_package")
        blockers.add("external_boundary_unproven")
        if boundary.get("accepted_adapter") is None:
            blockers.add("external_boundary_adapter_required")
        else:
            blockers.add("external_boundary_claim_requires_successor_package")
        if boundary.get("trusted_issuer_public_key_sha256") is None:
            blockers.add("trusted_boundary_issuer_required")
        else:
            blockers.add("external_boundary_claim_requires_successor_package")
        if boundary.get("receipt_sha256") is None:
            blockers.add("boundary_receipt_required")
        else:
            blockers.add("external_boundary_claim_requires_successor_package")

    expected_surface = {
        "model_runner_in_this_package": False,
        "run_all_command": False,
        "paid_execution_authorized": False,
    }
    if definition.get("execution_surface") != expected_surface:
        blockers.add("readiness_execution_surface_mutated")
    return sorted(blockers)


def validate_adversarial_review(
    value: Any,
    *,
    definition_sha256: str,
    package_sha256: str,
) -> None:
    root = _object(
        value,
        "adversarial_review",
        {
            "schema_version",
            "decision",
            "definition_sha256",
            "package_sha256",
            "reviewed_at",
            "reviews",
            "findings",
            "summary",
        },
    )
    if root["schema_version"] != 2 or root["decision"] != "ACCEPT":
        raise GateError("adversarial review must be an accepted v2 decision")
    if _sha(root["definition_sha256"], "adversarial_review.definition_sha256") != definition_sha256:
        raise GateError("adversarial review binds a different definition")
    if _sha(root["package_sha256"], "adversarial_review.package_sha256") != package_sha256:
        raise GateError("adversarial review binds a different package")
    _timestamp(root["reviewed_at"], "adversarial_review.reviewed_at")
    _string(root["summary"], "adversarial_review.summary")

    reviews = root["reviews"]
    if not isinstance(reviews, list) or len(reviews) != len(FROZEN_REVIEW_AXES):
        raise GateError("adversarial review must contain exactly three axis reviews")
    observed_axes: list[str] = []
    reviewers: set[str] = set()
    for index, raw in enumerate(reviews):
        item = _object(
            raw,
            f"adversarial_review.reviews[{index}]",
            {"axis", "reviewer_id", "decision", "evidence", "evidence_sha256"},
        )
        axis = _string(item["axis"], f"adversarial_review.reviews[{index}].axis", identifier=True)
        reviewer = _string(
            item["reviewer_id"],
            f"adversarial_review.reviews[{index}].reviewer_id",
            identifier=True,
        )
        if reviewer in reviewers:
            raise GateError("adversarial review requires three distinct reviewers")
        reviewers.add(reviewer)
        observed_axes.append(axis)
        if item["decision"] != "PASS":
            raise GateError(f"adversarial review axis {axis} did not pass")
        evidence = _string(item["evidence"], f"adversarial_review.reviews[{index}].evidence")
        if _sha(
            item["evidence_sha256"],
            f"adversarial_review.reviews[{index}].evidence_sha256",
        ) != hashlib.sha256(evidence.encode("utf-8")).hexdigest():
            raise GateError(f"adversarial review axis {axis} evidence hash differs")
    if tuple(sorted(observed_axes)) != tuple(sorted(FROZEN_REVIEW_AXES)):
        raise GateError("adversarial review axes are not exact")

    findings = root["findings"]
    if not isinstance(findings, list):
        raise GateError("adversarial review findings must be an array")
    finding_ids: set[str] = set()
    for index, raw in enumerate(findings):
        item = _object(
            raw,
            f"adversarial_review.findings[{index}]",
            {
                "id",
                "axis",
                "priority",
                "status",
                "summary",
                "resolution",
                "resolution_evidence_sha256",
            },
        )
        finding_id = _string(item["id"], f"adversarial_review.findings[{index}].id", identifier=True)
        if finding_id in finding_ids:
            raise GateError("adversarial review finding IDs must be unique")
        finding_ids.add(finding_id)
        if item["axis"] not in FROZEN_REVIEW_AXES:
            raise GateError(f"adversarial review finding {finding_id} has an invalid axis")
        if item["priority"] not in {"P1", "P2", "P3"}:
            raise GateError(f"adversarial review finding {finding_id} has an invalid priority")
        if item["status"] not in {"resolved", "open"}:
            raise GateError(f"adversarial review finding {finding_id} has an invalid status")
        _string(item["summary"], f"adversarial_review.findings[{index}].summary")
        resolution = _string(
            item["resolution"], f"adversarial_review.findings[{index}].resolution"
        )
        if _sha(
            item["resolution_evidence_sha256"],
            f"adversarial_review.findings[{index}].resolution_evidence_sha256",
        ) != hashlib.sha256(resolution.encode("utf-8")).hexdigest():
            raise GateError(f"adversarial review finding {finding_id} resolution hash differs")
        if item["priority"] in {"P1", "P2"} and item["status"] != "resolved":
            raise GateError(f"adversarial review finding {finding_id} is unresolved")


def report_payload_sha256(report: Mapping[str, Any]) -> str:
    payload = dict(report)
    payload.pop("payload_sha256", None)
    return canonical_sha256(payload)


def _validate_verifier_run(
    run: Any,
    *,
    name: str,
    expected_status: str,
    expected_returncode: int,
    verifier_sha256: str,
    workspace_manifest_sha256: str,
) -> None:
    item = _object(
        run,
        name,
        {
            "status",
            "returncode",
            "stdout_sha256",
            "stderr_sha256",
            "verifier_sha256",
            "workspace_manifest_sha256",
        },
    )
    if item["status"] != expected_status or item["returncode"] != expected_returncode:
        raise GateError(f"{name} does not have the required terminal outcome")
    _sha(item["stdout_sha256"], f"{name}.stdout_sha256")
    _sha(item["stderr_sha256"], f"{name}.stderr_sha256")
    if _sha(item["verifier_sha256"], f"{name}.verifier_sha256") != verifier_sha256:
        raise GateError(f"{name} binds a different verifier")
    if _sha(
        item["workspace_manifest_sha256"], f"{name}.workspace_manifest_sha256"
    ) != workspace_manifest_sha256:
        raise GateError(f"{name} binds a different workspace")


def validate_readiness_report(
    report: Any,
    *,
    definition: Mapping[str, Any],
    definition_sha256: str,
    package_sha256: str,
    blockers: Sequence[str],
) -> None:
    """Validate a replay-bound BLOCKED report. READY is invalid by construction."""
    root = _object(
        report,
        "readiness",
        {
            "schema_version",
            "definition_id",
            "definition_sha256",
            "package_sha256",
            "generated_at",
            "status",
            "paid_execution_authorized",
            "blockers",
            "sources",
            "tasks",
            "security_tests",
            "adversarial_review",
            "external_boundary",
            "quota_guard",
            "offline_verifier_runtime",
            "payload_sha256",
        },
    )
    if root["schema_version"] != 3:
        raise GateError("readiness.schema_version must be 3")
    if root["definition_id"] != definition["definition_id"]:
        raise GateError("readiness definition ID differs")
    if _sha(root["definition_sha256"], "readiness.definition_sha256") != definition_sha256:
        raise GateError("readiness definition hash is stale")
    if _sha(root["package_sha256"], "readiness.package_sha256") != package_sha256:
        raise GateError("readiness package hash is stale")
    _timestamp(root["generated_at"], "readiness.generated_at")
    if root["status"] != "BLOCKED" or root["paid_execution_authorized"] is not False:
        raise GateError("this readiness-only package can emit only BLOCKED zero-spend reports")
    expected_blockers = sorted(set(blockers))
    if root["blockers"] != expected_blockers:
        raise GateError("readiness blockers differ from independently computed blockers")
    if not PERMANENT_BLOCKERS.issubset(root["blockers"]):
        raise GateError("readiness report is missing permanent zero-spend blockers")

    sources = root["sources"]
    if not isinstance(sources, dict) or set(sources) != set(FROZEN_TASKS):
        raise GateError("readiness sources must contain both frozen tasks")
    source_keys = {
        "repo",
        "base_commit",
        "base_tree",
        "base_ls_tree_sha256",
        "historical_source_commit",
        "historical_source_tree",
        "historical_source_ls_tree_sha256",
        "export_excludes",
        "base_archive_sha256",
        "historical_source_archive_sha256",
        "object_evidence_rechecked",
    }
    for task_id in FROZEN_TASKS:
        source = _object(sources[task_id], f"readiness.sources.{task_id}", source_keys)
        _string(source["repo"], f"readiness.sources.{task_id}.repo")
        for field in (
            "base_ls_tree_sha256",
            "historical_source_ls_tree_sha256",
            "base_archive_sha256",
            "historical_source_archive_sha256",
        ):
            _sha(source[field], f"readiness.sources.{task_id}.{field}")
        for label in ("base", "historical_source"):
            commit = source[f"{label}_commit"]
            tree = source[f"{label}_tree"]
            if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise GateError(f"readiness.sources.{task_id}.{label}_commit is invalid")
            if not isinstance(tree, str) or not re.fullmatch(r"[0-9a-f]{40}", tree):
                raise GateError(f"readiness.sources.{task_id}.{label}_tree is invalid")
            expected_task = definition["tasks"][task_id]
            if commit != expected_task[f"{label}_commit"] or tree != expected_task[f"{label}_tree"]:
                raise GateError(f"readiness source {task_id} {label} identity differs")
        if source["export_excludes"] != definition["tasks"][task_id]["export_excludes"]:
            raise GateError(f"readiness source {task_id} export exclusions differ")
        _boolean(
            source["object_evidence_rechecked"],
            f"readiness.sources.{task_id}.object_evidence_rechecked",
            True,
        )

    tasks = root["tasks"]
    if not isinstance(tasks, dict) or set(tasks) != set(FROZEN_TASKS):
        raise GateError("readiness tasks must contain both frozen tasks")
    for task_id in FROZEN_TASKS:
        item = _object(
            tasks[task_id],
            f"readiness.tasks.{task_id}",
            {
                "base_manifest_sha256",
                "known_good_manifest_sha256",
                "public_verifier_sha256",
                "hidden_verifier_sha256",
                "known_good_patch_sha256",
                "runs",
            },
        )
        base_manifest = _sha(
            item["base_manifest_sha256"],
            f"readiness.tasks.{task_id}.base_manifest_sha256",
        )
        known_manifest = _sha(
            item["known_good_manifest_sha256"],
            f"readiness.tasks.{task_id}.known_good_manifest_sha256",
        )
        public_sha = _sha(
            item["public_verifier_sha256"],
            f"readiness.tasks.{task_id}.public_verifier_sha256",
        )
        hidden_sha = _sha(
            item["hidden_verifier_sha256"],
            f"readiness.tasks.{task_id}.hidden_verifier_sha256",
        )
        _sha(
            item["known_good_patch_sha256"],
            f"readiness.tasks.{task_id}.known_good_patch_sha256",
        )
        runs = _object(
            item["runs"],
            f"readiness.tasks.{task_id}.runs",
            {
                "public_baseline",
                "public_known_good",
                "hidden_baseline",
                "hidden_known_good",
            },
        )
        _validate_verifier_run(
            runs["public_baseline"],
            name=f"readiness.tasks.{task_id}.runs.public_baseline",
            expected_status="FAIL",
            expected_returncode=1,
            verifier_sha256=public_sha,
            workspace_manifest_sha256=base_manifest,
        )
        _validate_verifier_run(
            runs["public_known_good"],
            name=f"readiness.tasks.{task_id}.runs.public_known_good",
            expected_status="PASS",
            expected_returncode=0,
            verifier_sha256=public_sha,
            workspace_manifest_sha256=known_manifest,
        )
        _validate_verifier_run(
            runs["hidden_baseline"],
            name=f"readiness.tasks.{task_id}.runs.hidden_baseline",
            expected_status="FAIL",
            expected_returncode=1,
            verifier_sha256=hidden_sha,
            workspace_manifest_sha256=base_manifest,
        )
        _validate_verifier_run(
            runs["hidden_known_good"],
            name=f"readiness.tasks.{task_id}.runs.hidden_known_good",
            expected_status="PASS",
            expected_returncode=0,
            verifier_sha256=hidden_sha,
            workspace_manifest_sha256=known_manifest,
        )

    security = _object(
        root["security_tests"],
        "readiness.security_tests",
        {"status", "returncode", "stdout_sha256", "stderr_sha256"},
    )
    if security["status"] != "PASS" or security["returncode"] != 0:
        raise GateError("readiness security tests did not pass")
    _sha(security["stdout_sha256"], "readiness.security_tests.stdout_sha256")
    _sha(security["stderr_sha256"], "readiness.security_tests.stderr_sha256")

    review = _object(
        root["adversarial_review"],
        "readiness.adversarial_review",
        {
            "status",
            "artifact_sha256",
            "definition_sha256",
            "package_sha256",
            "unresolved_findings",
        },
    )
    if review["status"] not in {"PASS", "MISSING", "FAIL"}:
        raise GateError("readiness adversarial-review status is invalid")
    if review["status"] == "PASS":
        _sha(review["artifact_sha256"], "readiness.adversarial_review.artifact_sha256")
        if review["definition_sha256"] != definition_sha256:
            raise GateError("readiness adversarial review definition differs")
        if review["package_sha256"] != package_sha256:
            raise GateError("readiness adversarial review package differs")
        if review["unresolved_findings"] != []:
            raise GateError("readiness adversarial review has unresolved findings")
    else:
        if any(review[field] is not None for field in ("artifact_sha256", "definition_sha256", "package_sha256")):
            raise GateError("non-passing adversarial review cannot claim bound hashes")
        if not isinstance(review["unresolved_findings"], list):
            raise GateError("readiness adversarial review findings must be an array")

    if root["external_boundary"] != definition["external_boundary"]:
        raise GateError("readiness external boundary differs from the frozen definition")
    if root["quota_guard"] != definition["quota_guard"]:
        raise GateError("readiness quota guard differs from the frozen definition")
    if root["offline_verifier_runtime"] != definition["offline_verifier_runtime"]:
        raise GateError("readiness offline verifier runtime differs from the frozen definition")
    expected_payload = report_payload_sha256(root)
    if _sha(root["payload_sha256"], "readiness.payload_sha256") != expected_payload:
        raise GateError("readiness payload hash does not match its evidence")
