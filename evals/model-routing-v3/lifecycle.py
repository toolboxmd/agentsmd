"""Fail-closed lifecycle state for the model-routing v3 benchmark.

The trusted controller owns model execution.  This module owns only ordering,
deadline, evidence-binding, and persistence rules.  It deliberately exposes no
batch operation, arbitrary cell selector, retry, repair, or rereview path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = 1
HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
TERMINAL_STATUSES = {
    "ACCEPTED",
    "BOUNDARY_FAILURE",
    "CONTROLLER_ERROR",
    "IMPLEMENTATION_FAILED",
    "PROVIDER_UNAVAILABLE",
    "QUOTA_EXHAUSTED",
    "TELEMETRY_FAILURE",
    "TIMEOUT",
    "UNSAFE_SCOPE",
    "UNSAFE_TELEMETRY",
    "VERIFICATION_FAILED",
    "REVIEW_BLOCKED",
}
ACTIVE_FAILURE_STATUSES = {
    "BOUNDARY_FAILURE",
    "CONTROLLER_ERROR",
    "PROVIDER_UNAVAILABLE",
    "QUOTA_EXHAUSTED",
    "TELEMETRY_FAILURE",
}
SCORABLE_FAILURE_STATUSES = {
    "IMPLEMENTATION_FAILED",
    "PROVIDER_UNAVAILABLE",
    "QUOTA_EXHAUSTED",
    "REVIEW_BLOCKED",
    "TIMEOUT",
    "VERIFICATION_FAILED",
}
HARD_STOP_STATUSES = TERMINAL_STATUSES - SCORABLE_FAILURE_STATUSES - {"ACCEPTED"}


class LifecycleError(ValueError):
    """Raised when evidence or a requested transition violates the lifecycle."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_definition(path: Path) -> tuple[dict[str, Any], str]:
    """Read and validate one exact definition file and return its raw hash."""

    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid definition: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("definition must be an object")
    validate_definition(value)
    return value, sha256_bytes(raw)


def validate_package_review(
    review: Mapping[str, Any],
    *,
    definition_sha256: str,
    package_sha256: str,
) -> dict[str, Any]:
    """Validate the exact-hash, three-axis gate required before model spend."""

    value = dict(_mapping(review, "package review"))
    if set(value) != {
        "status",
        "definition_sha256",
        "package_sha256",
        "reviews",
        "summary",
    }:
        raise LifecycleError("package review has missing or unexpected fields")
    if value["status"] != "ACCEPT":
        raise LifecycleError("package review is not accepted")
    if value["definition_sha256"] != _hash(
        definition_sha256, "definition_sha256"
    ):
        raise LifecycleError("package review definition hash does not match")
    if value["package_sha256"] != _hash(package_sha256, "package_sha256"):
        raise LifecycleError("package review package hash does not match")
    reviews = value["reviews"]
    if not isinstance(reviews, list) or len(reviews) != 3:
        raise LifecycleError("package review requires exactly three axes")
    axes: set[str] = set()
    reviewers: set[str] = set()
    for item in reviews:
        record = _mapping(item, "package review axis")
        if set(record) != {"axis", "reviewer", "status", "findings", "summary"}:
            raise LifecycleError("package review axis has invalid fields")
        axis = record.get("axis")
        reviewer = _nonempty(record.get("reviewer"), "package reviewer")
        findings = record.get("findings")
        if axis not in {"standards", "spec", "security"}:
            raise LifecycleError("package review axis is invalid")
        if axis in axes or reviewer in reviewers:
            raise LifecycleError("package axes and reviewers must be unique")
        if record.get("status") != "PASS":
            raise LifecycleError("every package review axis must pass")
        if not isinstance(findings, list) or findings:
            raise LifecycleError("accepted package review cannot retain findings")
        _nonempty(record.get("summary"), "package review summary")
        axes.add(axis)
        reviewers.add(reviewer)
    if axes != {"standards", "spec", "security"}:
        raise LifecycleError("package review axes are incomplete")
    _nonempty(value.get("summary"), "package review summary")
    return value


def validate_definition(definition: Mapping[str, Any]) -> None:
    """Reject a definition that weakens the frozen v3 lifecycle."""

    if definition.get("schema_version") != 3:
        raise LifecycleError("definition schema_version must be 3")
    cells = _mapping(definition.get("cells"), "definition.cells")
    lifecycle = _mapping(definition.get("lifecycle"), "definition.lifecycle")
    run_order = lifecycle.get("run_order")
    if not isinstance(run_order, list) or not run_order:
        raise LifecycleError("lifecycle.run_order must be a non-empty list")
    if any(not isinstance(cell_id, str) or not cell_id for cell_id in run_order):
        raise LifecycleError("lifecycle.run_order contains an invalid cell id")
    if len(run_order) != len(set(run_order)):
        raise LifecycleError("lifecycle.run_order contains a duplicate")
    if set(run_order) != set(cells):
        raise LifecycleError("lifecycle.run_order must contain every cell exactly once")

    canary = lifecycle.get("canary")
    if canary != "use-grok--terra-high" or run_order[0] != canary:
        raise LifecycleError("the exact Terra high canary must run first")
    canary_cells = [
        cell_id
        for cell_id, cell in cells.items()
        if _mapping(cell, f"definition.cells.{cell_id}").get("canary") is True
    ]
    if canary_cells != [canary]:
        raise LifecycleError("exactly the frozen canary must be marked as canary")
    canary_cell = _mapping(cells[canary], f"definition.cells.{canary}")
    if (canary_cell.get("model"), canary_cell.get("effort")) != (
        "gpt-5.6-terra",
        "high",
    ):
        raise LifecycleError("canary route must be Terra high")

    required_lifecycle = {
        "inclusive_cell_deadline_seconds": 600,
        "automatic_retry": False,
        "automatic_repair": False,
        "rereview": False,
        "stop_on_anomaly": True,
        "remaining_cells_require_accepted_canary_audit": True,
    }
    for field, expected in required_lifecycle.items():
        if lifecycle.get(field) != expected:
            raise LifecycleError(f"lifecycle.{field} must remain {expected!r}")

    reviewer = _mapping(definition.get("reviewer"), "definition.reviewer")
    if (
        reviewer.get("model") != "gpt-5.6-luna"
        or reviewer.get("effort") != "max"
        or reviewer.get("read_only") is not True
    ):
        raise LifecycleError("reviewer must remain read-only Luna max")
    evaluator = _mapping(definition.get("evaluator"), "definition.evaluator")
    expected_evaluator_boundary = {
        "prompt_source": "fixed_instructions_plus_exact_canonical_bundle_bytes_and_sha256",
        "prompt_max_bytes": 4194304,
        "standalone_bundle_retained": True,
        "outer_sandbox_executable": "/usr/bin/sandbox-exec",
        "launchd_coalition_outer_supervision": True,
        "tool_free_argv": [
            "--no-leader",
            "--sandbox",
            "off",
            "--no-auto-update",
            "--tools",
            "todo_write",
            "--deny",
            "*",
            "--max-turns",
            "1",
            "--disable-web-search",
            "--no-subagents",
            "--no-plan",
        ],
        "replacement_environment_only": True,
        "fresh_home_grok_home_tmpdir_and_xdg": True,
        "updater_memory_subagents_workflows_web_telemetry_trace_mixpanel_feedback_and_external_otel_disabled": True,
        "explicit_grok_auth_source_cli_argument_required": True,
        "auth_copy": "absolute_owner_0600_regular_single_link_nofollow_exclusive_byte_equal",
        "auth_source_path_content_size_and_digest_absent_from_evidence": True,
        "transient_auth_removed_after_every_terminal_outcome": True,
        "seatbelt": {
            "default_deny": True,
            "imports_system_sb_and_system_network": True,
            "exact_executable_map_and_read": True,
            "exact_prompt_bundle_schema_reads": True,
            "writes_only_fresh_home_tmp_and_xdg_runtime": True,
            "self_process_info_only": True,
            "process_fork_or_process_star": False,
        },
        "network": {
            "outbound_mdns_responder": True,
            "outbound_remote_tcp_443": True,
            "localhost_denied": True,
            "inbound_denied": True,
            "other_ports_denied": True,
            "other_unix_sockets_denied": False,
            "unix_syslog_socket_denial_sampled": True,
            "provider_hostname_attribution_claim": False,
        },
        "no_model_preflight": {
            "same_file_and_network_policy_projection": True,
            "bundle_prompt_schema_positive_reads": True,
            "private_mapping_attempts_sources_memory_direct_and_symlink_denied": True,
            "localhost_ipv4_ipv6_non_443_and_syslog_socket_denials": True,
            "accepted_denial_errnos": [1, 13],
            "sandboxed_pinned_grok_version": True,
        },
        "single_cli_invocation_may_internally_refresh_or_retry_http": True,
    }
    if evaluator.get("boundary") != expected_evaluator_boundary:
        raise LifecycleError("evaluator security boundary differs from the frozen contract")
    execution_surface = _mapping(
        definition.get("execution_surface"), "definition.execution_surface"
    )
    if execution_surface.get("run_all_command") is not False:
        raise LifecycleError("definition must not enable a batch command")
    if execution_surface.get("canary_only_before_audit") is not True:
        raise LifecycleError("definition must keep the canary-only audit gate")


def create_state(
    definition: Mapping[str, Any],
    *,
    definition_sha256: str,
    package_sha256: str,
) -> dict[str, Any]:
    """Create a fresh state that authorizes no cell until preflight passes."""

    validate_definition(definition)
    state = {
        "schema_version": STATE_SCHEMA_VERSION,
        "definition_sha256": _hash(definition_sha256, "definition_sha256"),
        "package_sha256": _hash(package_sha256, "package_sha256"),
        "run_order": list(definition["lifecycle"]["run_order"]),
        "deadline_seconds": definition["lifecycle"][
            "inclusive_cell_deadline_seconds"
        ],
        "preflight": None,
        "canary_audit": None,
        "terminal_cells": [],
        "active_cell": None,
        "stopped": False,
        "stop_reason": None,
    }
    validate_state(state, definition)
    return state


def record_preflight(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    status: str,
    receipt_sha256: str,
    observed_definition_sha256: str,
    observed_package_sha256: str,
) -> dict[str, Any]:
    """Bind the single no-model preflight receipt to the exact package."""

    result = _copy_valid_state(state, definition)
    if result["preflight"] is not None or result["active_cell"] is not None:
        raise LifecycleError("preflight is single-use and must precede every cell")
    if result["terminal_cells"]:
        raise LifecycleError("preflight cannot be replaced after a cell")
    if status not in {"PASS", "FAIL"}:
        raise LifecycleError("preflight status must be PASS or FAIL")
    if observed_definition_sha256 != result["definition_sha256"]:
        raise LifecycleError("preflight definition hash does not match state")
    if observed_package_sha256 != result["package_sha256"]:
        raise LifecycleError("preflight package hash does not match state")
    result["preflight"] = {
        "status": status,
        "receipt_sha256": _hash(receipt_sha256, "preflight receipt_sha256"),
        "definition_sha256": observed_definition_sha256,
        "package_sha256": observed_package_sha256,
    }
    if status == "FAIL":
        result["stopped"] = True
        result["stop_reason"] = "PREFLIGHT_FAILED"
    return _checked(result, definition)


def authorize_canary(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Authorize the exact first cell after a bound passing preflight."""

    result = _copy_valid_state(state, definition)
    _require_runnable(result)
    if result["preflight"] is None or result["preflight"]["status"] != "PASS":
        raise LifecycleError("a passing bound preflight is required")
    if result["terminal_cells"] or result["active_cell"] is not None:
        raise LifecycleError("canary authorization is single-use")
    if result["canary_audit"] is not None:
        raise LifecycleError("canary audit cannot precede the canary")
    return _authorize(result, definition, ordinal=0, now_monotonic_ns=now_monotonic_ns)


def authorize_next(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Authorize exactly the next frozen remaining cell once."""

    result = _copy_valid_state(state, definition)
    _require_runnable(result)
    if result["active_cell"] is not None:
        raise LifecycleError("a cell is already active")
    completed = result["terminal_cells"]
    if not completed:
        raise LifecycleError("the canary has not completed")
    if any(
        cell["terminal"]["status"]
        not in SCORABLE_FAILURE_STATUSES | {"ACCEPTED"}
        for cell in completed
    ):
        raise LifecycleError("a prior safety or integrity failure stopped authorization")
    ordinal = len(completed)
    if ordinal >= len(result["run_order"]):
        raise LifecycleError("all frozen cells have already run")
    audit = result["canary_audit"]
    if audit is None or audit["status"] != "ACCEPT":
        raise LifecycleError("an exact-hash ACCEPT canary audit is required")
    return _authorize(
        result, definition, ordinal=ordinal, now_monotonic_ns=now_monotonic_ns
    )


def record_implementation_complete(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    artifact_sha256: str,
    receipt_sha256: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Record the one completed implementation and advance to verification."""

    result, active = _active_at(state, definition, cell_id, now_monotonic_ns)
    if active["stage"] != "implementation" or active["implementation"] is not None:
        raise LifecycleError("implementation completion is single-use")
    active["implementation"] = {
        "status": "COMPLETED",
        "artifact_sha256": _hash(artifact_sha256, "artifact_sha256"),
        "receipt_sha256": _hash(receipt_sha256, "implementation receipt_sha256"),
        "ended_monotonic_ns": now_monotonic_ns,
    }
    active["stage"] = "verification"
    return _checked(result, definition)


def record_implementation_failure(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    result_sha256: str,
    reason: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Record a blocked implementation without authorizing a retry."""

    result, active = _active_at(state, definition, cell_id, now_monotonic_ns)
    if active["stage"] != "implementation" or active["implementation"] is not None:
        raise LifecycleError("implementation failure is not valid in this stage")
    return _finish(
        result,
        definition,
        status="IMPLEMENTATION_FAILED",
        reason=_nonempty(reason, "implementation failure reason"),
        result_sha256=result_sha256,
        now_monotonic_ns=now_monotonic_ns,
    )


def record_active_failure(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    status: str,
    result_sha256: str,
    reason: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Stop one active attempt for a classified non-candidate failure.

    The transition is valid in every active stage.  It retains any completed
    implementation or verification evidence and never creates retry authority.
    """

    result = _copy_valid_state(state, definition)
    active = _require_active(result, cell_id)
    now = _integer(now_monotonic_ns, "now_monotonic_ns")
    if now < active["started_monotonic_ns"]:
        raise LifecycleError("monotonic clock moved backwards")
    if status not in ACTIVE_FAILURE_STATUSES:
        raise LifecycleError("active failure status is not allowed")
    if now >= active["deadline_monotonic_ns"] and status not in HARD_STOP_STATUSES:
        raise LifecycleError("inclusive deadline reached; expire the active cell")
    return _finish(
        result,
        definition,
        status=status,
        reason=_nonempty(reason, "active failure reason"),
        result_sha256=result_sha256,
        now_monotonic_ns=now,
    )


def record_verification(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    public_passed: bool,
    hidden_passed: bool,
    scope_safe: bool,
    telemetry_safe: bool,
    receipt_sha256: str,
    now_monotonic_ns: int,
    unsafe_result_sha256: str | None = None,
) -> dict[str, Any]:
    """Record deterministic proof and either stop unsafe work or require review."""

    result, active = _active_at(state, definition, cell_id, now_monotonic_ns)
    if active["stage"] != "verification" or active["verification"] is not None:
        raise LifecycleError("verification is single-use and follows implementation")
    for value, field in (
        (public_passed, "public_passed"),
        (hidden_passed, "hidden_passed"),
        (scope_safe, "scope_safe"),
        (telemetry_safe, "telemetry_safe"),
    ):
        if not isinstance(value, bool):
            raise LifecycleError(f"{field} must be boolean")
    active["verification"] = {
        "public_passed": public_passed,
        "hidden_passed": hidden_passed,
        "scope_safe": scope_safe,
        "telemetry_safe": telemetry_safe,
        "receipt_sha256": _hash(receipt_sha256, "verification receipt_sha256"),
        "ended_monotonic_ns": now_monotonic_ns,
    }
    if not scope_safe or not telemetry_safe:
        if unsafe_result_sha256 is None:
            raise LifecycleError("unsafe verification requires its terminal result hash")
        status = "UNSAFE_SCOPE" if not scope_safe else "UNSAFE_TELEMETRY"
        return _finish(
            result,
            definition,
            status=status,
            reason=status,
            result_sha256=unsafe_result_sha256,
            now_monotonic_ns=now_monotonic_ns,
        )
    if unsafe_result_sha256 is not None:
        raise LifecycleError("safe verification cannot supply an unsafe result hash")
    active["stage"] = "review"
    return _checked(result, definition)


def record_review(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    status: str,
    finding_count: int,
    artifact_sha256: str,
    review_range_sha256: str,
    receipt_sha256: str,
    result_sha256: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Record the sole Luna review and finish the cell without rereview."""

    result = _copy_valid_state(state, definition)
    active = _require_active(result, cell_id)
    if active["stage"] != "review" or active["review"] is not None:
        raise LifecycleError("review is single-use and follows safe verification")
    if not isinstance(now_monotonic_ns, int) or isinstance(now_monotonic_ns, bool):
        raise LifecycleError("now_monotonic_ns must be an integer")
    if now_monotonic_ns < active["started_monotonic_ns"]:
        raise LifecycleError("monotonic clock moved backwards")
    if status not in {"PASS", "BLOCKED"}:
        raise LifecycleError("review status must be PASS or BLOCKED")
    if isinstance(finding_count, bool) or not isinstance(finding_count, int):
        raise LifecycleError("finding_count must be an integer")
    if finding_count < 0:
        raise LifecycleError("finding_count must be non-negative")
    expected_artifact = active["implementation"]["artifact_sha256"]
    if artifact_sha256 != expected_artifact:
        raise LifecycleError("review is not bound to the implementation artifact")
    active["review"] = {
        "status": status,
        "finding_count": finding_count,
        "artifact_sha256": artifact_sha256,
        "review_range_sha256": _hash(
            review_range_sha256, "review review_range_sha256"
        ),
        "receipt_sha256": _hash(receipt_sha256, "review receipt_sha256"),
        "ended_monotonic_ns": now_monotonic_ns,
    }
    if now_monotonic_ns >= active["deadline_monotonic_ns"]:
        return _finish(
            result,
            definition,
            status="TIMEOUT",
            reason="INCLUSIVE_CELL_DEADLINE_REACHED",
            result_sha256=result_sha256,
            now_monotonic_ns=now_monotonic_ns,
        )
    verification = active["verification"]
    if status != "PASS" or finding_count:
        terminal_status = "REVIEW_BLOCKED"
    elif not verification["public_passed"] or not verification["hidden_passed"]:
        terminal_status = "VERIFICATION_FAILED"
    else:
        terminal_status = "ACCEPTED"
    return _finish(
        result,
        definition,
        status=terminal_status,
        reason=terminal_status,
        result_sha256=result_sha256,
        now_monotonic_ns=now_monotonic_ns,
    )


def expire_active_cell(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    cell_id: str,
    result_sha256: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    """Record an inclusive deadline timeout; it never authorizes a retry."""

    result = _copy_valid_state(state, definition)
    active = _require_active(result, cell_id)
    if not isinstance(now_monotonic_ns, int) or isinstance(now_monotonic_ns, bool):
        raise LifecycleError("now_monotonic_ns must be an integer")
    if now_monotonic_ns < active["deadline_monotonic_ns"]:
        raise LifecycleError("cell cannot expire before its inclusive deadline")
    return _finish(
        result,
        definition,
        status="TIMEOUT",
        reason="INCLUSIVE_CELL_DEADLINE_REACHED",
        result_sha256=result_sha256,
        now_monotonic_ns=now_monotonic_ns,
    )


def record_canary_audit(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    *,
    audit: Mapping[str, Any],
    audit_sha256: str,
) -> dict[str, Any]:
    """Bind the sole independent audit to the exact accepted canary evidence."""

    result = _copy_valid_state(state, definition)
    if result["canary_audit"] is not None:
        raise LifecycleError("canary audit is single-use")
    if result["active_cell"] is not None:
        raise LifecycleError("canary audit cannot be recorded while a cell is active")
    if len(result["terminal_cells"]) != 1:
        raise LifecycleError("canary audit must immediately follow the canary")
    canary = result["terminal_cells"][0]
    if canary["cell_id"] != result["run_order"][0]:
        raise LifecycleError("first terminal cell is not the frozen canary")
    if canary["terminal"]["status"] != "ACCEPTED":
        raise LifecycleError("only an accepted canary can receive an audit")
    normalized = _validate_audit(audit)
    expected = {
        "definition_sha256": result["definition_sha256"],
        "package_sha256": result["package_sha256"],
        "canary_result_sha256": canary["terminal"]["result_sha256"],
        "canary_artifact_sha256": canary["implementation"]["artifact_sha256"],
    }
    for field, value in expected.items():
        if normalized[field] != value:
            raise LifecycleError(f"canary audit {field} does not match state")
    normalized["audit_sha256"] = _hash(audit_sha256, "audit_sha256")
    result["canary_audit"] = normalized
    if normalized["status"] == "REJECT":
        result["stopped"] = True
        result["stop_reason"] = "CANARY_AUDIT_REJECTED"
    return _checked(result, definition)


def canonical_state_bytes(state: Mapping[str, Any]) -> bytes:
    """Render state in the sole accepted persisted representation."""

    return (
        json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def save_state(path: Path, state: Mapping[str, Any], definition: Mapping[str, Any]) -> None:
    """Validate and atomically persist canonical state with owner-only mode."""

    validate_state(state, definition)
    if not path.parent.is_dir():
        raise LifecycleError("state parent directory must already exist")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_state_bytes(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def load_state(
    path: Path,
    definition: Mapping[str, Any],
    *,
    expected_definition_sha256: str,
    expected_package_sha256: str,
) -> dict[str, Any]:
    """Load only canonical state bound to the expected package identities."""

    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid state: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("state must be an object")
    if raw != canonical_state_bytes(value):
        raise LifecycleError("state is not in canonical persisted form")
    validate_state(value, definition)
    if value["definition_sha256"] != expected_definition_sha256:
        raise LifecycleError("state definition hash does not match expected definition")
    if value["package_sha256"] != expected_package_sha256:
        raise LifecycleError("state package hash does not match expected package")
    return value


def validate_state(state: Mapping[str, Any], definition: Mapping[str, Any]) -> None:
    """Validate ordering, stage, stop, deadline, and evidence invariants."""

    validate_definition(definition)
    expected_keys = {
        "schema_version",
        "definition_sha256",
        "package_sha256",
        "run_order",
        "deadline_seconds",
        "preflight",
        "canary_audit",
        "terminal_cells",
        "active_cell",
        "stopped",
        "stop_reason",
    }
    if set(state) != expected_keys:
        raise LifecycleError("state has missing or unexpected top-level fields")
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise LifecycleError("unsupported lifecycle state schema")
    _hash(state.get("definition_sha256"), "state.definition_sha256")
    _hash(state.get("package_sha256"), "state.package_sha256")
    run_order = state.get("run_order")
    if run_order != definition["lifecycle"]["run_order"]:
        raise LifecycleError("state run order differs from definition")
    if state.get("deadline_seconds") != 600:
        raise LifecycleError("state deadline differs from definition")

    preflight = state.get("preflight")
    if preflight is not None:
        if set(preflight) != {
            "status",
            "receipt_sha256",
            "definition_sha256",
            "package_sha256",
        }:
            raise LifecycleError("preflight record has invalid fields")
        if preflight["status"] not in {"PASS", "FAIL"}:
            raise LifecycleError("invalid preflight status")
        _hash(preflight["receipt_sha256"], "preflight receipt")
        if preflight["definition_sha256"] != state["definition_sha256"]:
            raise LifecycleError("preflight definition binding changed")
        if preflight["package_sha256"] != state["package_sha256"]:
            raise LifecycleError("preflight package binding changed")

    terminal_cells = state.get("terminal_cells")
    if not isinstance(terminal_cells, list):
        raise LifecycleError("terminal_cells must be a list")
    for ordinal, cell in enumerate(terminal_cells):
        _validate_cell(cell, state, ordinal=ordinal, terminal=True)
    active = state.get("active_cell")
    if active is not None:
        _validate_cell(active, state, ordinal=len(terminal_cells), terminal=False)

    audit = state.get("canary_audit")
    if audit is not None:
        normalized = _validate_audit(audit, persisted=True)
        if len(terminal_cells) < 1 or terminal_cells[0]["terminal"]["status"] != "ACCEPTED":
            raise LifecycleError("audit exists without an accepted canary")
        canary = terminal_cells[0]
        bindings = {
            "definition_sha256": state["definition_sha256"],
            "package_sha256": state["package_sha256"],
            "canary_result_sha256": canary["terminal"]["result_sha256"],
            "canary_artifact_sha256": canary["implementation"]["artifact_sha256"],
        }
        if any(normalized[field] != value for field, value in bindings.items()):
            raise LifecycleError("persisted audit binding changed")

    stopped = state.get("stopped")
    if not isinstance(stopped, bool):
        raise LifecycleError("stopped must be boolean")
    stop_reason = state.get("stop_reason")
    if stopped != (stop_reason is not None):
        raise LifecycleError("stopped and stop_reason disagree")
    if stop_reason is not None:
        _nonempty(stop_reason, "stop_reason")
    if active is not None and stopped:
        raise LifecycleError("stopped state cannot retain an active cell")
    if preflight is not None and preflight["status"] == "FAIL" and not stopped:
        raise LifecycleError("failed preflight must stop the lifecycle")
    if (terminal_cells or active is not None) and (
        preflight is None or preflight["status"] != "PASS"
    ):
        raise LifecycleError("cells require a passing bound preflight")
    stopping_terminals = [
        ordinal
        for ordinal, cell in enumerate(terminal_cells)
        if cell["terminal"]["status"] in HARD_STOP_STATUSES
        or (ordinal == 0 and cell["terminal"]["status"] != "ACCEPTED")
    ]
    if stopping_terminals:
        if len(stopping_terminals) != 1 or stopping_terminals[0] != len(terminal_cells) - 1:
            raise LifecycleError("no cell may follow a safety or integrity stop")
        terminal_status = terminal_cells[-1]["terminal"]["status"]
        if not stopped or stop_reason != terminal_status:
            raise LifecycleError("terminal status and lifecycle stop_reason disagree")
    elif terminal_cells and stopped and (
        audit is None or audit["status"] != "REJECT"
    ):
        raise LifecycleError("scored outcomes must not stop the lifecycle")
    if audit is not None and audit["status"] == "REJECT" and not stopped:
        raise LifecycleError("rejected canary audit must stop the lifecycle")
    if len(terminal_cells) > 1 and (audit is None or audit["status"] != "ACCEPT"):
        raise LifecycleError("remaining cells require an accepted canary audit")


def _validate_cell(
    cell: Any, state: Mapping[str, Any], *, ordinal: int, terminal: bool
) -> None:
    value = _mapping(cell, "cell")
    expected_keys = {
        "cell_id",
        "ordinal",
        "attempt",
        "started_monotonic_ns",
        "deadline_monotonic_ns",
        "stage",
        "implementation",
        "verification",
        "review",
        "terminal",
    }
    if set(value) != expected_keys:
        raise LifecycleError("cell has missing or unexpected fields")
    if ordinal >= len(state["run_order"]) or value["cell_id"] != state["run_order"][ordinal]:
        raise LifecycleError("cell does not match the next frozen ordinal")
    if value["ordinal"] != ordinal or value["attempt"] != 1:
        raise LifecycleError("cell ordinal or attempt changed")
    started = _integer(value["started_monotonic_ns"], "started_monotonic_ns")
    deadline = _integer(value["deadline_monotonic_ns"], "deadline_monotonic_ns")
    if deadline != started + state["deadline_seconds"] * 1_000_000_000:
        raise LifecycleError("cell deadline is not the exact inclusive deadline")
    implementation = value["implementation"]
    verification = value["verification"]
    review = value["review"]
    terminal_record = value["terminal"]
    stage = value["stage"]
    if terminal:
        if stage != "terminal" or terminal_record is None:
            raise LifecycleError("terminal cell lacks terminal state")
        _validate_terminal(terminal_record, started, deadline)
    elif stage not in {"implementation", "verification", "review"} or terminal_record is not None:
        raise LifecycleError("active cell has an invalid stage")

    if implementation is not None:
        if set(implementation) != {
            "status",
            "artifact_sha256",
            "receipt_sha256",
            "ended_monotonic_ns",
        } or implementation["status"] != "COMPLETED":
            raise LifecycleError("invalid implementation record")
        _hash(implementation["artifact_sha256"], "implementation artifact")
        _hash(implementation["receipt_sha256"], "implementation receipt")
        _event_time(implementation["ended_monotonic_ns"], started, deadline)
    if stage in {"verification", "review"} and implementation is None:
        raise LifecycleError("later stage lacks a completed implementation")

    if verification is not None:
        if set(verification) != {
            "public_passed",
            "hidden_passed",
            "scope_safe",
            "telemetry_safe",
            "receipt_sha256",
            "ended_monotonic_ns",
        }:
            raise LifecycleError("invalid verification record")
        for field in ("public_passed", "hidden_passed", "scope_safe", "telemetry_safe"):
            if not isinstance(verification[field], bool):
                raise LifecycleError(f"verification {field} must be boolean")
        _hash(verification["receipt_sha256"], "verification receipt")
        _event_time(verification["ended_monotonic_ns"], started, deadline)
        if implementation is None:
            raise LifecycleError("verification exists without completed implementation")
    if stage == "review" and (
        verification is None
        or not verification["scope_safe"]
        or not verification["telemetry_safe"]
    ):
        raise LifecycleError("review requires safe completed verification")

    if review is not None:
        if set(review) != {
            "status",
            "finding_count",
            "artifact_sha256",
            "review_range_sha256",
            "receipt_sha256",
            "ended_monotonic_ns",
        }:
            raise LifecycleError("invalid review record")
        if review["status"] not in {"PASS", "BLOCKED"}:
            raise LifecycleError("invalid review status")
        _integer(review["finding_count"], "review finding_count")
        _hash(review["artifact_sha256"], "review artifact")
        _hash(review["review_range_sha256"], "review range")
        _hash(review["receipt_sha256"], "review receipt")
        if (
            implementation is None
            or review["artifact_sha256"] != implementation["artifact_sha256"]
        ):
            raise LifecycleError("review artifact binding changed")
        if verification is None or not verification["scope_safe"] or not verification["telemetry_safe"]:
            raise LifecycleError("review exists after unsafe verification")
        ended = _integer(review["ended_monotonic_ns"], "review ended_monotonic_ns")
        if ended < started:
            raise LifecycleError("review time precedes cell start")
    if stage == "review" and review is not None:
        raise LifecycleError("completed review must terminalize the cell")
    if terminal and implementation is not None and verification is not None:
        safe = verification["scope_safe"] and verification["telemetry_safe"]
        terminal_status = terminal_record["status"]
        if (
            safe
            and terminal_status not in ACTIVE_FAILURE_STATUSES | {"TIMEOUT"}
            and review is None
        ):
            raise LifecycleError("safe completed implementation lacks its one review")
        if not safe and review is not None:
            raise LifecycleError("unsafe implementation must not be reviewed")
    if terminal:
        terminal_status = terminal_record["status"]
        if terminal_status == "IMPLEMENTATION_FAILED" and any(
            item is not None for item in (implementation, verification, review)
        ):
            raise LifecycleError("implementation failure contains later-stage evidence")
        if terminal_status in ACTIVE_FAILURE_STATUSES and review is not None:
            raise LifecycleError("active failure cannot contain a completed review")
        if terminal_status in {
            "ACCEPTED",
            "VERIFICATION_FAILED",
            "REVIEW_BLOCKED",
        }:
            if implementation is None or verification is None or review is None:
                raise LifecycleError("finished safe cell lacks required stage evidence")
            if not verification["scope_safe"] or not verification["telemetry_safe"]:
                raise LifecycleError("safe terminal status conflicts with unsafe evidence")
            if review["ended_monotonic_ns"] >= deadline:
                raise LifecycleError("non-timeout review reached the inclusive deadline")
        if terminal_status == "ACCEPTED" and (
            not verification["public_passed"]
            or not verification["hidden_passed"]
            or review["status"] != "PASS"
            or review["finding_count"] != 0
        ):
            raise LifecycleError("accepted cell contains failed quality evidence")
        if terminal_status == "VERIFICATION_FAILED" and (
            verification["public_passed"] and verification["hidden_passed"]
        ):
            raise LifecycleError("verification failure lacks a verifier failure")
        if terminal_status == "REVIEW_BLOCKED" and (
            review["status"] == "PASS" and review["finding_count"] == 0
        ):
            raise LifecycleError("review-blocked cell lacks a review finding")
        if terminal_status == "UNSAFE_SCOPE" and (
            implementation is None
            or verification is None
            or verification["scope_safe"]
            or review is not None
        ):
            raise LifecycleError("unsafe-scope terminal conflicts with stage evidence")
        if terminal_status == "UNSAFE_TELEMETRY" and (
            implementation is None
            or verification is None
            or not verification["scope_safe"]
            or verification["telemetry_safe"]
            or review is not None
        ):
            raise LifecycleError("unsafe-telemetry terminal conflicts with stage evidence")
    else:
        if stage == "implementation" and any(
            item is not None for item in (implementation, verification, review)
        ):
            raise LifecycleError("implementation stage contains later-stage evidence")
        if stage == "verification" and (
            implementation is None or verification is not None or review is not None
        ):
            raise LifecycleError("verification stage contains invalid stage evidence")
        if stage == "review" and review is not None:
            raise LifecycleError("review stage already contains a review receipt")


def _validate_terminal(value: Any, started: int, deadline: int) -> None:
    terminal = _mapping(value, "terminal")
    if set(terminal) != {"status", "reason", "result_sha256", "ended_monotonic_ns"}:
        raise LifecycleError("terminal record has invalid fields")
    if terminal["status"] not in TERMINAL_STATUSES:
        raise LifecycleError("invalid terminal status")
    _nonempty(terminal["reason"], "terminal reason")
    _hash(terminal["result_sha256"], "terminal result_sha256")
    ended = _integer(terminal["ended_monotonic_ns"], "terminal ended_monotonic_ns")
    if ended < started:
        raise LifecycleError("terminal time precedes cell start")
    if terminal["status"] == "TIMEOUT":
        if ended < deadline:
            raise LifecycleError("timeout precedes the inclusive cell deadline")
    elif terminal["status"] not in HARD_STOP_STATUSES and ended >= deadline:
        raise LifecycleError("non-timeout terminal reached the inclusive cell deadline")


def _validate_audit(audit: Any, *, persisted: bool = False) -> dict[str, Any]:
    value = dict(_mapping(audit, "canary audit"))
    required = {
        "status",
        "definition_sha256",
        "package_sha256",
        "canary_result_sha256",
        "canary_artifact_sha256",
        "auditor",
        "independent_of_candidate_and_controller",
        "findings",
        "summary",
    }
    expected = required | ({"audit_sha256"} if persisted else set())
    if set(value) != expected:
        raise LifecycleError("canary audit has missing or unexpected fields")
    if value["status"] not in {"ACCEPT", "REJECT"}:
        raise LifecycleError("canary audit status must be ACCEPT or REJECT")
    for field in (
        "definition_sha256",
        "package_sha256",
        "canary_result_sha256",
        "canary_artifact_sha256",
    ):
        _hash(value[field], f"canary audit {field}")
    if persisted:
        _hash(value["audit_sha256"], "canary audit audit_sha256")
    _nonempty(value["auditor"], "canary audit auditor")
    if value["independent_of_candidate_and_controller"] is not True:
        raise LifecycleError("canary auditor independence is not attested")
    if not isinstance(value["findings"], list) or any(
        not isinstance(finding, str) for finding in value["findings"]
    ):
        raise LifecycleError("canary audit findings must be strings")
    if not isinstance(value["summary"], str):
        raise LifecycleError("canary audit summary must be a string")
    if value["status"] == "ACCEPT" and value["findings"]:
        raise LifecycleError("accepted canary audit cannot retain findings")
    return value


def _authorize(
    state: dict[str, Any],
    definition: Mapping[str, Any],
    *,
    ordinal: int,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    now = _integer(now_monotonic_ns, "now_monotonic_ns")
    if state["active_cell"] is not None:
        raise LifecycleError("a cell is already active")
    cell_id = state["run_order"][ordinal]
    if any(cell["cell_id"] == cell_id for cell in state["terminal_cells"]):
        raise LifecycleError("cell has already run")
    state["active_cell"] = {
        "cell_id": cell_id,
        "ordinal": ordinal,
        "attempt": 1,
        "started_monotonic_ns": now,
        "deadline_monotonic_ns": now + state["deadline_seconds"] * 1_000_000_000,
        "stage": "implementation",
        "implementation": None,
        "verification": None,
        "review": None,
        "terminal": None,
    }
    return _checked(state, definition)


def _active_at(
    state: Mapping[str, Any],
    definition: Mapping[str, Any],
    cell_id: str,
    now_monotonic_ns: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = _copy_valid_state(state, definition)
    active = _require_active(result, cell_id)
    now = _integer(now_monotonic_ns, "now_monotonic_ns")
    if now < active["started_monotonic_ns"]:
        raise LifecycleError("monotonic clock moved backwards")
    if now >= active["deadline_monotonic_ns"]:
        raise LifecycleError("inclusive deadline reached; expire the active cell")
    return result, active


def _finish(
    state: dict[str, Any],
    definition: Mapping[str, Any],
    *,
    status: str,
    reason: str,
    result_sha256: str,
    now_monotonic_ns: int,
) -> dict[str, Any]:
    active = state["active_cell"]
    if active is None:
        raise LifecycleError("no active cell")
    active["terminal"] = {
        "status": status,
        "reason": reason,
        "result_sha256": _hash(result_sha256, "result_sha256"),
        "ended_monotonic_ns": _integer(now_monotonic_ns, "now_monotonic_ns"),
    }
    active["stage"] = "terminal"
    state["terminal_cells"].append(active)
    state["active_cell"] = None
    if status in HARD_STOP_STATUSES or (
        active["ordinal"] == 0 and status != "ACCEPTED"
    ):
        state["stopped"] = True
        state["stop_reason"] = status
    return _checked(state, definition)


def _require_active(state: dict[str, Any], cell_id: str) -> dict[str, Any]:
    active = state["active_cell"]
    if active is None:
        raise LifecycleError("no active cell")
    if active["cell_id"] != cell_id:
        raise LifecycleError("receipt cell id does not match active cell")
    return active


def _require_runnable(state: Mapping[str, Any]) -> None:
    if state["stopped"]:
        raise LifecycleError(f"lifecycle is stopped: {state['stop_reason']}")


def _copy_valid_state(
    state: Mapping[str, Any], definition: Mapping[str, Any]
) -> dict[str, Any]:
    validate_state(state, definition)
    return copy.deepcopy(dict(state))


def _checked(state: dict[str, Any], definition: Mapping[str, Any]) -> dict[str, Any]:
    validate_state(state, definition)
    return state


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LifecycleError(f"{field} must be an object")
    return value


def _hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
        raise LifecycleError(f"{field} must be a lowercase SHA-256")
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise LifecycleError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LifecycleError(f"{field} must be a non-negative integer")
    return value


def _event_time(value: Any, started: int, deadline: int) -> int:
    timestamp = _integer(value, "event timestamp")
    if timestamp < started or timestamp >= deadline:
        raise LifecycleError("event timestamp is outside the inclusive cell interval")
    return timestamp
