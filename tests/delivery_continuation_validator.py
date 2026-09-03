#!/usr/bin/env python3
"""Host-neutral validator for Delivery Authority and continuation fixtures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


def load_cases(path: Path) -> dict[str, Any]:
    """Load one versioned fixture contract without changing repository state."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError("fixture schema must be 1")
    if not isinstance(payload.get("contract"), dict):
        raise ValueError("fixture contract is required")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("fixture cases are required")
    defaults = payload.pop("case_defaults", {})
    expanded: list[dict[str, Any]] = []
    for case in cases:
        merged = copy.deepcopy(defaults)
        for key, value in case.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(copy.deepcopy(value))
            else:
                merged[key] = copy.deepcopy(value)
        expanded.append(merged)
    payload["cases"] = expanded
    return payload


def _decision(case: dict[str, Any], contract: dict[str, Any]) -> str:
    authority = case.get("authority")
    request = case.get("request", {})
    if case.get("explicit_stop"):
        return "stop-explicit"

    def valid_scope(value: Any) -> bool:
        return (
            isinstance(value, dict)
            and isinstance(value.get("repository"), str)
            and bool(value["repository"].strip())
            and isinstance(value.get("issue"), int)
            and not isinstance(value["issue"], bool)
            and value["issue"] > 0
        )

    if not valid_scope(authority) or not valid_scope(request):
        return "authority-required"
    if (
        authority.get("repository") != request.get("repository")
        or authority.get("issue") != request.get("issue")
    ):
        return "authority-required"
    if case.get("material_changes"):
        return "reauthorization-required"
    authorized = set(authority.get("operations", []))
    requested = set(request.get("operations", []))
    allowed = set(contract["implementation_operations"]) | set(
        contract["separately_authorized_operations"]
    )
    if not requested or (authorized | requested) - allowed:
        return "authority-required"
    if not requested <= authorized:
        return "authority-required"
    for operation in requested & set(contract["separately_authorized_operations"]):
        target = request.get("targets", {}).get(operation)
        if not isinstance(target, str) or not target.strip():
            return "authority-required"
        if authority.get("targets", {}).get(operation) != target:
            return "authority-required"
    if case.get("proof_state") == "failed":
        return "failed"
    event = case.get("event")
    if event == "fresh-start":
        return "start-fresh"
    if event == "report-back":
        return "report-back"
    if event == "next-issue":
        if not case.get("blockers_clear"):
            return "blocked"
        if case.get("coordinator_verified_git_and_github"):
            return "start-next-fresh"
        return "failed"
    if event == "interrupted":
        if case.get("same_issue") and case.get("context_useful"):
            return "resume-same-context"
        return "start-fresh"
    if event == "recovery":
        return "recover"
    if event == "completed-work":
        return "advance-without-recreation"
    return "continue"


def validate_case(case: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    """Return semantic contract violations for one state transition fixture."""
    errors: list[str] = []
    request = case.get("request", {})
    if case.get("contract_location") != contract.get("authoritative_location"):
        errors.append("case does not trace to the authoritative contract")
    material_changes = set(case.get("material_changes", []))
    unknown_changes = material_changes - set(contract["material_change_fields"])
    if unknown_changes:
        errors.append("case names an unknown material-change field")
    if case.get("proof_state") not in set(contract["proof_states"]):
        errors.append("case names an unknown proof state")
    event = case.get("event")
    if event is not None and event not in set(contract["events"]):
        errors.append("case names an unknown event")
    expected = case.get("expected", {})
    decision = _decision(case, contract)
    if expected.get("decision") != decision:
        errors.append(
            f"decision is {decision}, expected {expected.get('decision')}"
        )
    expected_prompts = 1 if decision in {
        "authority-required",
        "reauthorization-required",
    } else 0
    if expected.get("reauthorization_prompts") != expected_prompts:
        errors.append("reauthorization prompt count does not match decision")

    context_mode = expected.get("context_mode")
    if context_mode == "fresh":
        if case.get("fresh_context_seed") != contract["fresh_context_fields"]:
            errors.append("fresh context seed is not the minimal durable packet")
        if case.get("prior_transcript_included"):
            errors.append("fresh context includes a prior transcript")
    if decision == "start-next-fresh":
        if not case.get("coordinator_verified_git_and_github"):
            errors.append("coordinator did not verify current Git and GitHub state")
        if not case.get("blockers_clear"):
            errors.append("next Issue is still blocked")
    if decision == "resume-same-context":
        if not case.get("same_issue") or not case.get("context_useful"):
            errors.append("interruption cannot resume this context")

    handoff = case.get("handoff")
    if event in {"report-back", "next-issue"} and handoff is None:
        errors.append("event requires a durable handoff")
    if handoff is not None:
        if set(handoff) != set(contract["handoff_fields"]):
            errors.append("durable handoff fields are incomplete or unknown")
        elif any(value in {None, ""} for value in handoff.values()):
            errors.append("durable handoff has a blank field")
        if case.get("handoff_channels") != ["issue", "pr"]:
            errors.append("durable handoff must be recorded on the Issue and PR")

    recovered = case.get("recovered_state")
    if event == "recovery" and recovered is None:
        errors.append("recovery event requires recovered state")
    if recovered is not None:
        if set(recovered) != set(contract["recovery_fields"]):
            errors.append("recovery state fields are incomplete or unknown")
        elif any(value in {None, ""} for value in recovered.values()):
            errors.append("recovery state has a blank field")
        required_sources = {
            "git",
            "github",
            "project-instructions",
            "durable-handoff",
        }
        if set(case.get("recovery_sources", [])) != required_sources:
            errors.append("recovery sources are incomplete or transcript-dependent")

    if decision == "advance-without-recreation":
        if not case.get("completed_evidence_verified"):
            errors.append("completed work was not verified before advancement")
        if expected.get("recreate_completed_work") is not False:
            errors.append("completed work would be recreated")
        if expected.get("request_completed_approval") is not False:
            errors.append("completed approval would be requested again")

    reported = case.get("reported_delivery_states")
    if case.get("proof_state") == "failed" and reported is None:
        errors.append("failed proof requires reported delivery states")
    if reported is not None:
        if set(reported) != set(contract["reported_delivery_states"]):
            errors.append("reported delivery states are incomplete or unknown")
        else:
            state_values = contract["delivery_state_values"]
            successful = contract["successful_delivery_states"]
            for state, value in reported.items():
                if value not in set(state_values[state]):
                    errors.append(f"{state} has an unknown delivery-state value")
            verified_results = case.get("verified_external_results", {})
            for operation in contract["separately_authorized_operations"]:
                if reported.get(operation) != successful[operation]:
                    continue
                result = verified_results.get(operation)
                target = request.get("targets", {}).get(operation)
                if not isinstance(result, dict) or result != {
                    "target": target,
                    "state": successful[operation],
                }:
                    errors.append(
                        f"successful {operation} lacks an exact verified result"
                    )
            if decision == "failed":
                if reported.get("proof") != "failed":
                    errors.append("failed proof is not reported truthfully")
                proof_index = contract["reported_delivery_states"].index("proof")
                for state in contract["reported_delivery_states"][proof_index:]:
                    if reported.get(state) == successful[state]:
                        errors.append(
                            f"failed proof is followed by successful {state}"
                        )
            if decision in {
                "authority-required",
                "reauthorization-required",
                "stop-explicit",
                "blocked",
                "failed",
            }:
                for operation in contract["separately_authorized_operations"]:
                    if reported.get(operation) == successful[operation]:
                        errors.append(
                            f"stopped work reports successful {operation}"
                        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    cases_parser = commands.add_parser("validate-cases")
    cases_parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    payload = load_cases(args.path)
    errors = [
        f"{case['id']}: {error}"
        for case in payload["cases"]
        for error in validate_case(case, payload["contract"])
    ]
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"{len(payload['cases'])} cases valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
