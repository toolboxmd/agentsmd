#!/usr/bin/env python3
"""Evaluate Repository Reconciliation through its public workflow/result seam."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


PREFLIGHT_MAX_AGE_SECONDS = 60
TARGET_FIELDS = {
    "id",
    "exact-target",
    "branch",
    "head",
    "issue",
    "pull-request",
    "expected-states",
}
APPROVAL_FIELDS = {
    "target",
    "action",
    "force",
    "branch-deletion",
    "operation-sha256",
}
APPROVAL_RECORD_FIELDS = {"schema", "record-id", "operation"}
WORKFLOW_REQUIRED_FIELDS = {
    "id",
    "target",
    "preflight",
    "mutation",
    "request",
    "recovery",
}
REQUEST_FIELDS = {
    "target",
    "action",
    "force",
    "branch-deletion",
    "approval-sha256",
}
MUTATION_FIELDS = {
    "state",
    "action",
    "force",
    "branch-deletion",
    "approval-sha256",
    "timestamp",
    "target",
}
RECOVERY_FIELDS = {
    "target",
    "action",
    "force",
    "branch-deletion",
    "approval-sha256",
    "interval",
    "authoritative-history-available",
    "preconditions-held-continuously",
    "exact-targets-match",
    "refs-recoverable",
    "authority-sufficient",
    "violated-precondition",
    "safe-restoration",
    "user-data-risk",
    "user-owned-decision",
    "ambiguous",
}
RESTORATION_FIELDS = {
    "state",
    "target",
    "action",
    "force",
    "branch-deletion",
    "approval-sha256",
    "conflict",
    "data-loss",
    "timestamp",
}
RECOVERY_PROOF_FIELDS = (
    "authoritative-history-available",
    "preconditions-held-continuously",
    "exact-targets-match",
    "refs-recoverable",
    "authority-sufficient",
    "violated-precondition",
)


def _escalate(
    reason: str,
    *,
    evidence_status: str = "incomplete",
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "decision": "escalate",
        "reason": reason,
        "mutation-action": "none",
        "human-gate": True,
        "user-notification": True,
        "evidence-status": evidence_status,
        "evidence": evidence or [],
    }


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_target(target: dict[str, Any]) -> bool:
    expected = target.get("expected-states")
    identity_fields = ("id", "exact-target", "branch", "head", "issue", "pull-request")
    return (
        set(target) == TARGET_FIELDS
        and all(_nonempty_string(target.get(field)) for field in identity_fields)
        and isinstance(expected, dict)
        and set(expected) == {"issue", "pull-request", "resource"}
        and all(_nonempty_string(value) for value in expected.values())
    )


def _operation_sha256(operation: dict[str, Any]) -> str:
    encoded = json.dumps(
        operation,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_approval(approval: dict[str, Any]) -> bool:
    if set(approval) != APPROVAL_FIELDS:
        return False
    operation = {
        field: approval[field]
        for field in ("target", "action", "force", "branch-deletion")
    }
    return (
        isinstance(approval.get("target"), dict)
        and _valid_target(approval["target"])
        and approval.get("action") == "remove-worktree"
        and approval.get("force") is False
        and approval.get("branch-deletion") is False
        and approval.get("operation-sha256") == _operation_sha256(operation)
    )


def _valid_approval_record(record: dict[str, Any]) -> bool:
    return (
        set(record) == APPROVAL_RECORD_FIELDS
        and type(record.get("schema")) is int
        and record["schema"] == 1
        and _nonempty_string(record.get("record-id"))
        and isinstance(record.get("operation"), dict)
        and _valid_approval(record["operation"])
    )


def _load_approval_record(
    path: Path, expected_sha256: str
) -> dict[str, Any] | None:
    try:
        raw_record = path.read_bytes()
        if hashlib.sha256(raw_record).hexdigest() != expected_sha256:
            return None
        record = json.loads(raw_record)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or not _valid_approval_record(record):
        return None
    return record


def _within_approval(
    target: dict[str, Any],
    approved_operation: dict[str, Any],
    request: dict[str, Any],
    mutation: dict[str, Any],
) -> bool:
    approved_target = approved_operation.get("target")
    requested_target = request.get("target")
    mutation_target = mutation.get("target")
    return (
        _valid_target(target)
        and _valid_approval(approved_operation)
        and set(request) == REQUEST_FIELDS
        and set(mutation) == MUTATION_FIELDS
        and isinstance(approved_target, dict)
        and isinstance(requested_target, dict)
        and isinstance(mutation_target, dict)
        and _valid_target(approved_target)
        and _valid_target(requested_target)
        and _valid_target(mutation_target)
        and target == approved_target == requested_target == mutation_target
        and request.get("action") == approved_operation.get("action")
        and request.get("force") is approved_operation.get("force")
        and request.get("branch-deletion")
        is approved_operation.get("branch-deletion")
        and request.get("approval-sha256")
        == approved_operation.get("operation-sha256")
        and mutation.get("state") in {"pending", "completed"}
        and mutation.get("action") == approved_operation.get("action")
        and mutation.get("force") is approved_operation.get("force")
        and mutation.get("branch-deletion")
        is approved_operation.get("branch-deletion")
        and mutation.get("approval-sha256")
        == approved_operation.get("operation-sha256")
        and _timestamp(mutation.get("timestamp")) is not None
    )


def _operation_record_matches(
    record: dict[str, Any], approved_operation: dict[str, Any]
) -> bool:
    record_target = record.get("target")
    return (
        _valid_approval(approved_operation)
        and isinstance(record_target, dict)
        and _valid_target(record_target)
        and record_target == approved_operation.get("target")
        and record.get("action") == approved_operation.get("action")
        and record.get("force") is approved_operation.get("force")
        and record.get("branch-deletion")
        is approved_operation.get("branch-deletion")
        and record.get("approval-sha256")
        == approved_operation.get("operation-sha256")
    )


def _missing_preflight_valid(preflight: dict[str, Any]) -> bool:
    return (
        set(preflight) == {"status", "observations"}
        and preflight.get("status") == "missing"
        and preflight.get("observations") == []
    )


def _structured_preflight(
    target: dict[str, Any],
    preflight: dict[str, Any],
    mutation: dict[str, Any],
) -> list[dict[str, Any]] | None:
    if not _valid_target(target) or set(preflight) != {"status", "observations"}:
        return None
    observations = preflight.get("observations")
    mutation_time = _timestamp(mutation.get("timestamp"))
    exact_targets = {
        "issue": target["issue"],
        "pull-request": target["pull-request"],
        "resource": target["exact-target"],
    }
    sources = {
        "issue": "live-api",
        "pull-request": "live-api",
        "resource": "live-system",
    }
    if (
        preflight.get("status") != "complete"
        or not isinstance(observations, list)
        or mutation_time is None
        or len(observations) != len(exact_targets)
    ):
        return None
    kinds: list[str] = []
    for observation in observations:
        if not isinstance(observation, dict):
            return None
        kind = observation.get("kind")
        observed_at = _timestamp(observation.get("timestamp"))
        if (
            set(observation)
            != {"kind", "exact-target", "state", "timestamp", "result", "source"}
            or not isinstance(kind, str)
            or kind not in exact_targets
            or observation.get("exact-target") != exact_targets[kind]
            or not _nonempty_string(observation.get("state"))
            or observed_at is None
            or observed_at > mutation_time
            or (mutation_time - observed_at).total_seconds()
            > PREFLIGHT_MAX_AGE_SECONDS
            or observation.get("result") not in {"pass", "fail"}
            or observation.get("source") != sources[kind]
        ):
            return None
        kinds.append(kind)
    if set(kinds) != set(exact_targets) or len(set(kinds)) != len(kinds):
        return None
    return observations


def _recovery_interval(
    recovery: dict[str, Any], mutation: dict[str, Any]
) -> dict[str, str] | None:
    interval = recovery.get("interval")
    if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
        return None
    start = _timestamp(interval.get("start"))
    end = _timestamp(interval.get("end"))
    mutation_time = _timestamp(mutation.get("timestamp"))
    if start is None or end is None or mutation_time is None:
        return None
    if not start <= mutation_time <= end:
        return None
    return {"start": interval["start"], "end": interval["end"]}


def _recovery_schema_valid(recovery: dict[str, Any]) -> bool:
    boolean_fields = RECOVERY_FIELDS - {
        "target",
        "action",
        "approval-sha256",
        "interval",
    }
    return set(recovery) == RECOVERY_FIELDS and all(
        isinstance(recovery.get(field), bool) for field in boolean_fields
    )


def _recovery_evidence(
    target: dict[str, Any],
    approved_operation: dict[str, Any],
    recovery: dict[str, Any],
    interval: dict[str, str],
) -> dict[str, Any]:
    return {
        "omission": "immediate-preflight-evidence-missing",
        "interval": interval,
        "contract-regression": "tests/test_repository_reconciliation_contract.py",
        "approval-sha256": approved_operation["operation-sha256"],
        "action": approved_operation["action"],
        "force": approved_operation["force"],
        "branch-deletion": approved_operation["branch-deletion"],
        "proof": {
            field: recovery[field] for field in RECOVERY_PROOF_FIELDS
        },
        "exact-target": target["exact-target"],
        "issue": target["issue"],
        "pull-request": target["pull-request"],
        "state": "preconditions-held-continuously",
        "timestamp": interval["end"],
        "result": "recovered",
    }


def _restoration_valid(
    restoration: dict[str, Any],
    approved_operation: dict[str, Any],
    interval: dict[str, str],
) -> bool:
    restored_at = _timestamp(restoration.get("timestamp"))
    interval_end = _timestamp(interval["end"])
    return (
        set(restoration) == RESTORATION_FIELDS
        and restoration.get("state") == "completed"
        and _operation_record_matches(restoration, approved_operation)
        and restoration.get("conflict") is False
        and restoration.get("data-loss") is False
        and restored_at is not None
        and interval_end is not None
        and restored_at >= interval_end
    )


def _restoration_evidence(
    target: dict[str, Any],
    approved_operation: dict[str, Any],
    recovery: dict[str, Any],
    restoration: dict[str, Any],
    interval: dict[str, str],
) -> dict[str, Any]:
    evidence = _recovery_evidence(
        target, approved_operation, recovery, interval
    )
    evidence["proof"]["safe-restoration"] = recovery["safe-restoration"]
    evidence.update(
        {
            "branch": restoration["target"]["branch"],
            "head": restoration["target"]["head"],
            "conflict": restoration["conflict"],
            "data-loss": restoration["data-loss"],
            "state": "restored-at-head",
            "timestamp": restoration["timestamp"],
            "result": "restored",
        }
    )
    return evidence


def evaluate(case: Any, approval_record: Any) -> dict[str, Any]:
    """Return the observable reconciliation result for one workflow input."""
    if not isinstance(case, dict) or not isinstance(approval_record, dict):
        return _escalate("invalid-or-unapproved-input")
    if not _valid_approval_record(approval_record):
        return _escalate("invalid-or-unapproved-input")
    workflow_fields = set(case)
    if workflow_fields not in (
        WORKFLOW_REQUIRED_FIELDS,
        WORKFLOW_REQUIRED_FIELDS | {"restoration"},
    ) or not _nonempty_string(case.get("id")):
        return _escalate("invalid-or-unapproved-input")
    approved_operation = approval_record["operation"]
    sections: dict[str, dict[str, Any]] = {}
    for name in (
        "target",
        "preflight",
        "mutation",
        "request",
        "recovery",
        "restoration",
    ):
        value = case.get(name, {})
        if not isinstance(value, dict):
            return _escalate("invalid-or-unapproved-input")
        sections[name] = value

    target = sections["target"]
    preflight = sections["preflight"]
    mutation = sections["mutation"]
    request = sections["request"]
    recovery = sections["recovery"]
    restoration = sections["restoration"]
    within_approval = _within_approval(
        target, approved_operation, request, mutation
    )

    if mutation.get("state") == "pending":
        if preflight.get("status") != "complete":
            return _escalate("invalid-preflight-evidence")
        if not within_approval:
            return _escalate("authority-expansion")
        observations = _structured_preflight(target, preflight, mutation)
        if observations is None:
            return _escalate("invalid-preflight-evidence")
        expected = target["expected-states"]
        passed = all(
            item["state"] == expected[item["kind"]]
            and item["result"] == "pass"
            for item in observations
        )
        if not passed:
            return {
                "decision": "preserve",
                "mutation-action": "none",
                "human-gate": False,
                "user-notification": False,
                "evidence-status": "preflight-failed",
                "evidence": observations,
            }
        return {
            "decision": "mutate",
            "mutation-action": "execute-approved-action",
            "human-gate": False,
            "user-notification": False,
            "evidence-status": "preflight-complete",
            "evidence": observations,
        }

    if mutation.get("state") == "completed":
        if not _missing_preflight_valid(preflight):
            return _escalate(
                "invalid-preflight-evidence", evidence_status="recovery-blocked"
            )
        if not within_approval:
            return _escalate("authority-expansion", evidence_status="recovery-blocked")
        if not _operation_record_matches(recovery, approved_operation):
            return _escalate(
                "authority-expansion", evidence_status="recovery-blocked"
            )
        interval = _recovery_interval(recovery, mutation)
        if not _recovery_schema_valid(recovery) or interval is None:
            return _escalate("proof-unavailable", evidence_status="recovery-blocked")
        if recovery["ambiguous"]:
            reason = "ambiguous-recovery"
        elif not recovery["authoritative-history-available"]:
            reason = "proof-unavailable"
        elif not recovery["exact-targets-match"]:
            reason = "target-mismatch"
        elif not recovery["authority-sufficient"]:
            reason = "authority-expansion"
        elif recovery["user-data-risk"]:
            reason = "user-data-risk"
        elif recovery["user-owned-decision"]:
            reason = "user-owned-decision"
        elif not recovery["refs-recoverable"]:
            reason = "unsafe-restoration"
        else:
            reason = ""

        if not reason and recovery["preconditions-held-continuously"]:
            if recovery["violated-precondition"]:
                reason = "ambiguous-recovery"
            else:
                evidence = _recovery_evidence(
                    target, approved_operation, recovery, interval
                )
                return {
                    "decision": "recovered",
                    "mutation-action": "none",
                    "human-gate": False,
                    "user-notification": False,
                    "evidence-status": "retrospective-complete",
                    "evidence": [evidence],
                }

        if not reason and recovery["violated-precondition"]:
            if recovery["safe-restoration"]:
                if not _operation_record_matches(
                    restoration, approved_operation
                ):
                    return _escalate(
                        "authority-expansion",
                        evidence_status="recovery-blocked",
                    )
                if _restoration_valid(
                    restoration, approved_operation, interval
                ):
                    evidence = _restoration_evidence(
                        target,
                        approved_operation,
                        recovery,
                        restoration,
                        interval,
                    )
                    return {
                        "decision": "restored",
                        "mutation-action": "restore-prior-worktree",
                        "human-gate": False,
                        "user-notification": False,
                        "evidence-status": "restoration-complete",
                        "evidence": [evidence],
                    }
            reason = "unsafe-restoration"
        if not reason:
            reason = "ambiguous-recovery"
        blocked_evidence = [
            {
                "exact-target": target["exact-target"],
                "state": "recovery-blocked",
                "timestamp": interval["end"],
                "result": reason,
            }
        ]
        return _escalate(
            reason,
            evidence_status="recovery-blocked",
            evidence=blocked_evidence,
        )

    return _escalate("invalid-or-unapproved-input")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate"])
    parser.add_argument("--approval-record", required=True, type=Path)
    parser.add_argument("--approval-record-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        workflow = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError):
        workflow = None
    approval_record = _load_approval_record(
        args.approval_record, args.approval_record_sha256
    )
    if approval_record is None:
        result = _escalate("invalid-or-unapproved-input")
    else:
        result = evaluate(workflow, approval_record)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
