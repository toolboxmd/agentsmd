#!/usr/bin/env python3
"""Host-neutral validator for the Persistent Host Automation contract."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_MAPPING_FIELDS = {
    "canonical_source",
    "runtime_destination",
    "owner",
    "group",
    "mode",
    "source_validation",
    "restart_scope",
    "health_proof",
    "drift_check",
    "rollback_guidance",
}
REQUIRED_SECRET_FIELDS = {
    "name",
    "purpose",
    "required_permissions",
    "protected_runtime_location",
    "template_reference",
}
FORBIDDEN_SECRET_FIELDS = {
    "credential_value",
    "password",
    "private_key",
    "secret_value",
    "token_value",
    "value",
}
REQUIRED_STATES = {
    "issue",
    "branch",
    "implementation",
    "commit",
    "push",
    "pr",
    "merge",
    "release",
    "installation",
    "deployment",
    "restart",
    "live_verification",
}
OUTSIDE_ACTIONS = {
    "project-local-or-one-off": "keep-in-owning-project",
    "unrelated-symlink-architecture": "preserve-owning-architecture",
}
SECRET_PATTERNS = (
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|access[_-]?token|"
            r"auth[_-]?token|bearer[_-]?token|client[_-]?secret|"
            r"refresh[_-]?token|service[_-]?(?:credential|secret|token)|"
            r"(?:credential|secret|token)[_-]?value|password|"
            r"private[_-]?key)\b\s*[:=]\s*"
            r"[\"']?(?!<|redacted|example|placeholder|none|null)"
            r"[A-Za-z0-9+/_=-]{12,}"
        ),
    ),
    (
        "bearer credential",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9+/_=-]{16,}"),
    ),
    (
        "private key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
)


def _present(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Return contract violations without mutating or executing the plan."""
    errors: list[str] = []
    scope = plan.get("scope")
    if scope == "outside-boundary":
        reason = plan.get("outside_reason")
        expected_action = OUTSIDE_ACTIONS.get(reason)
        if expected_action is None:
            errors.append("outside-boundary plan has an unknown reason")
        elif plan.get("outside_action") != expected_action:
            errors.append("outside-boundary plan changes its owning architecture")
        return errors
    if scope != "persistent-host-automation":
        return ["scope must identify Persistent Host Automation or an exclusion"]

    ownership = plan.get("ownership")
    if not isinstance(ownership, dict):
        errors.append("canonical ownership is missing")
    else:
        closer = ownership.get("closer_project_repository")
        selected = ownership.get("user_selected_repository")
        resolved = ownership.get("resolved_repository")
        expected = closer if _present(closer) else selected
        if not _present(expected):
            if (
                ownership.get("creates_new_operational_surface")
                and not ownership.get("user_confirmed_new_surface")
            ):
                errors.append("new operational ownership surface needs user authority")
            else:
                errors.append("canonical repository is unresolved")
        elif resolved != expected:
            errors.append("closer project instructions must win repository precedence")

    mutation = plan.get("external_mutation")
    if not isinstance(mutation, dict):
        errors.append("external mutation state is missing")
    elif mutation.get("requested") and not mutation.get("human_gate_authorized"):
        errors.append("installation, deployment, or restart needs its Human Gate")

    artifacts = plan.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("at least one persistent runtime artifact is required")
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                errors.append(f"artifact {index} is not an object")
                continue
            missing = sorted(
                field
                for field in REQUIRED_MAPPING_FIELDS
                if not _present(artifact.get(field))
            )
            if missing:
                errors.append(
                    f"artifact {index} lacks mapping fields: {', '.join(missing)}"
                )
            if artifact.get("runtime_model") != "controlled-copy":
                errors.append(f"artifact {index} runtime model must be controlled-copy")
            if (
                artifact.get("privileged")
                and artifact.get("runtime_model") == "checkout-symlink"
                and artifact.get("checkout_writable")
            ):
                errors.append(
                    f"artifact {index} privileged entrypoint resolves through "
                    "a writable checkout"
                )
            if artifact.get("artifact_kind") in {"health-check", "recovery"}:
                if not _present(artifact.get("associated_service_source")):
                    errors.append(
                        f"artifact {index} must map to its associated service source"
                    )

    secrets = plan.get("secrets", [])
    if not isinstance(secrets, list):
        errors.append("secrets must be a list of contracts")
    else:
        for index, secret in enumerate(secrets):
            if not isinstance(secret, dict):
                errors.append(f"secret {index} is not an object")
                continue
            forbidden = sorted(FORBIDDEN_SECRET_FIELDS & set(secret))
            if forbidden:
                errors.append(
                    f"secret {index} contains value fields: {', '.join(forbidden)}"
                )
            missing = sorted(
                field
                for field in REQUIRED_SECRET_FIELDS
                if not _present(secret.get(field))
            )
            if missing:
                errors.append(
                    f"secret {index} lacks contract fields: {', '.join(missing)}"
                )
            unexpected = sorted(
                set(secret) - REQUIRED_SECRET_FIELDS - FORBIDDEN_SECRET_FIELDS
            )
            if unexpected:
                errors.append(
                    f"secret {index} has unknown fields: {', '.join(unexpected)}"
                )

    states = plan.get("reported_states")
    if not isinstance(states, dict):
        errors.append("reported delivery states are missing")
    else:
        missing_states = sorted(REQUIRED_STATES - set(states))
        extra_states = sorted(set(states) - REQUIRED_STATES)
        blank_states = sorted(
            key for key, value in states.items() if not _present(value)
        )
        if missing_states:
            errors.append(
                f"reported delivery states missing: {', '.join(missing_states)}"
            )
        if extra_states:
            errors.append(
                f"reported delivery states unknown: {', '.join(extra_states)}"
            )
        if blank_states:
            errors.append(f"reported delivery states blank: {', '.join(blank_states)}")
    return errors


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Expand shared fixture defaults into independent validation inputs."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError("fixture schema must be 1")
    plan_defaults = payload.get("plan_defaults", {})
    artifact_defaults = payload.get("artifact_defaults", {})
    expanded: list[dict[str, Any]] = []
    for case in payload.get("cases", []):
        plan = copy.deepcopy(plan_defaults)
        plan.update(copy.deepcopy(case["plan"]))
        if "artifacts" in plan:
            plan["artifacts"] = [
                {**copy.deepcopy(artifact_defaults), **artifact}
                for artifact in plan["artifacts"]
            ]
        expanded.append({"id": case["id"], "plan": plan})
    return expanded


def scan_text(label: str, text: str) -> list[str]:
    """Return redaction-safe finding labels without echoing matched material."""
    return [
        f"{label}: possible {name}"
        for name, pattern in SECRET_PATTERNS
        if pattern.search(text)
    ]


def scan_paths(paths: list[Path]) -> list[str]:
    """Scan text files under explicit paths without following symlinks."""
    findings: list[str] = []
    seen: set[Path] = set()
    for supplied in paths:
        candidates = supplied.rglob("*") if supplied.is_dir() else (supplied,)
        for candidate in candidates:
            if candidate in seen or candidate.is_symlink() or not candidate.is_file():
                continue
            seen.add(candidate)
            if any(part in {".git", "__pycache__"} for part in candidate.parts):
                continue
            payload = candidate.read_bytes()
            if b"\0" in payload:
                continue
            try:
                text = payload.decode("utf-8")
            except UnicodeDecodeError:
                continue
            findings.extend(scan_text(str(candidate), text))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    cases_parser = commands.add_parser("validate-cases")
    cases_parser.add_argument("path", type=Path)
    scan_parser = commands.add_parser("scan")
    scan_parser.add_argument("paths", nargs="+", type=Path)
    stdin_parser = commands.add_parser("scan-stdin")
    stdin_parser.add_argument("label")
    args = parser.parse_args(argv)

    if args.command == "validate-cases":
        errors = [
            f"{case['id']}: {error}"
            for case in load_cases(args.path)
            for error in validate_plan(case["plan"])
        ]
    elif args.command == "scan":
        errors = scan_paths(args.paths)
    else:
        errors = scan_text(args.label, sys.stdin.read())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
