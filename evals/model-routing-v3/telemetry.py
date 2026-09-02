"""Fail-closed telemetry parsing for the model-routing v3 benchmark.

This module intentionally has no dependency on the runner, router, or
verifier.  Its inputs are immutable evidence files and planned route values;
callers either receive a normalized receipt or a ``TelemetryError``.  Router
observations are retained only as supplemental diagnostics and never make an
otherwise valid receipt invalid.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any


USAGE_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)
EXPECTED_CODEX_CLI_VERSION = "0.149.1"
EXPECTED_MODEL_PROVIDER = "openai"


class TelemetryError(ValueError):
    """Raised when benchmark telemetry cannot be proven exact."""


def parse_jsonl(text: str, *, label: str = "JSONL") -> list[dict[str, Any]]:
    """Return a strict JSONL document made exclusively of object records.

    Empty lines, malformed JSON, non-object values, and a final unterminated
    line are all rejected.  A missing newline commonly means a process was
    interrupted while it was writing the evidence file, so accepting it would
    turn a truncated capture into apparently complete evidence.
    """

    if not isinstance(text, str):
        raise TelemetryError(f"{label} must be text")
    if not text:
        raise TelemetryError(f"{label} is empty")
    if not text.endswith("\n"):
        raise TelemetryError(f"{label} has an unterminated final line")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise TelemetryError(f"{label} line {line_number} is blank")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TelemetryError(
                f"{label} line {line_number} is malformed JSON: {exc.msg}"
            ) from exc
        if not isinstance(value, dict):
            raise TelemetryError(f"{label} line {line_number} is not an object")
        records.append(value)
    if not records:
        raise TelemetryError(f"{label} has no records")
    return records


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TelemetryError(f"{field} must be an object")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise TelemetryError(f"{field} must be a non-empty string")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TelemetryError(f"{field} must be an integer")
    if value < 0:
        raise TelemetryError(f"{field} must be non-negative")
    return value


def normalize_usage(usage: Mapping[str, Any], *, label: str = "usage") -> dict[str, int]:
    """Validate one exact usage snapshot and derive uncached input once."""

    normalized = {
        field: _integer(usage.get(field), f"{label}.{field}")
        for field in USAGE_FIELDS
    }
    if normalized["cached_input_tokens"] > normalized["input_tokens"]:
        raise TelemetryError(f"{label}.cached_input_tokens exceeds input_tokens")
    if normalized["reasoning_output_tokens"] > normalized["output_tokens"]:
        raise TelemetryError(
            f"{label}.reasoning_output_tokens exceeds output_tokens"
        )
    normalized["uncached_input_tokens"] = (
        normalized["input_tokens"] - normalized["cached_input_tokens"]
    )
    return normalized


def extract_exec_telemetry(exec_jsonl: str) -> dict[str, Any]:
    """Extract the sole completed Codex execution from its ``--json`` output."""

    events = parse_jsonl(exec_jsonl, label="Codex execution JSONL")
    starts = [event for event in events if event.get("type") == "thread.started"]
    if len(starts) != 1:
        raise TelemetryError(
            f"Codex execution must contain exactly one thread.started, found {len(starts)}"
        )
    thread_id = _string(starts[0].get("thread_id"), "thread.started.thread_id")

    turn_starts = [event for event in events if event.get("type") == "turn.started"]
    if len(turn_starts) != 1:
        raise TelemetryError(
            f"Codex execution must contain exactly one turn.started, found {len(turn_starts)}"
        )

    terminals = [event for event in events if event.get("type") == "turn.completed"]
    if len(terminals) != 1:
        raise TelemetryError(
            f"Codex execution must contain exactly one turn.completed, found {len(terminals)}"
        )
    terminal = terminals[0]
    start_index = events.index(starts[0])
    turn_start_index = events.index(turn_starts[0])
    terminal_index = events.index(terminal)
    if not start_index < turn_start_index < terminal_index:
        raise TelemetryError("Codex execution lifecycle events are out of order")
    if terminal_index != len(events) - 1:
        raise TelemetryError("turn.completed must be the terminal execution event")
    terminal_thread_id = terminal.get("thread_id")
    if terminal_thread_id is not None and terminal_thread_id != thread_id:
        raise TelemetryError("turn.completed.thread_id conflicts with thread.started")
    usage = normalize_usage(_mapping(terminal.get("usage"), "turn.completed.usage"), label="turn.completed.usage")

    for event in events:
        event_thread_id = event.get("thread_id")
        if event_thread_id is not None and event_thread_id != thread_id:
            raise TelemetryError("execution JSONL contains conflicting thread ids")

    return {
        "thread_id": thread_id,
        "turn_id": terminal.get("turn_id"),
        "usage": usage,
        "event_count": len(events),
        "raw_sha256": sha256_text(exec_jsonl),
    }


def _profile_id(value: Any, field: str) -> str:
    if isinstance(value, str):
        return _string(value, field)
    mapping = _mapping(value, field)
    return _string(mapping.get("id"), f"{field}.id")


def bind_rollout(
    rollout_jsonl: str,
    *,
    exec_thread_id: str,
    planned_model: str,
    planned_effort: str,
    planned_permission_profile: str,
    planned_cli_version: str = EXPECTED_CODEX_CLI_VERSION,
    planned_model_provider: str = EXPECTED_MODEL_PROVIDER,
) -> dict[str, Any]:
    """Bind isolated persisted rollout evidence to a planned execution.

    The v3 controller persists one fresh rollout per stage.  It requires one
    exact context and one matching task completion event.  The final token
    count must occur between them, so another turn cannot supply usage.
    """

    events = parse_jsonl(rollout_jsonl, label="persisted rollout JSONL")
    session_meta = [
        (index, event)
        for index, event in enumerate(events)
        if event.get("type") == "session_meta"
    ]
    if len(session_meta) != 1:
        raise TelemetryError(
            f"persisted rollout must contain exactly one session_meta, found {len(session_meta)}"
        )
    session_index, session_event = session_meta[0]
    session_payload = _mapping(session_event.get("payload"), "session_meta.payload")
    session_id = _string(session_payload.get("id"), "session_meta.payload.id")
    if session_id != exec_thread_id:
        raise TelemetryError(
            "session_meta.payload.id does not match execution JSONL thread.started"
        )
    cli_version = _string(
        session_payload.get("cli_version"), "session_meta.payload.cli_version"
    )
    if cli_version != planned_cli_version:
        raise TelemetryError(
            f"session CLI version {cli_version!r} does not match pin {planned_cli_version!r}"
        )
    model_provider = _string(
        session_payload.get("model_provider"), "session_meta.payload.model_provider"
    )
    if model_provider != planned_model_provider:
        raise TelemetryError(
            f"session model provider {model_provider!r} does not match pin {planned_model_provider!r}"
        )

    all_contexts: list[tuple[int, Mapping[str, Any]]] = []
    for index, event in enumerate(events):
        if event.get("type") != "turn_context":
            continue
        payload = _mapping(event.get("payload"), "turn_context.payload")
        all_contexts.append((index, payload))
    if len(all_contexts) != 1:
        raise TelemetryError(
            "fresh persisted rollout must contain exactly one turn_context, "
            f"found {len(all_contexts)}"
        )
    context_index, context = all_contexts[0]
    if not (
        context.get("model") == planned_model
        and context.get("effort") == planned_effort
        and _profile_id(
            context.get("active_permission_profile"),
            "turn_context.payload.active_permission_profile",
        )
        == planned_permission_profile
    ):
        raise TelemetryError("persisted turn_context does not match planned route")
    if context_index <= session_index:
        raise TelemetryError("turn_context does not follow session_meta")
    turn_id = _string(context.get("turn_id"), "turn_context.payload.turn_id")

    completions: list[tuple[int, Mapping[str, Any]]] = []
    token_counts: list[tuple[int, Mapping[str, Any]]] = []
    for index, event in enumerate(events):
        if event.get("type") != "event_msg":
            continue
        payload = _mapping(event.get("payload"), "event_msg.payload")
        if payload.get("type") == "task_complete":
            completions.append((index, payload))
        elif payload.get("type") == "token_count":
            token_counts.append((index, payload))
    if len(completions) != 1:
        raise TelemetryError(
            "persisted rollout must contain exactly one task_complete, "
            f"found {len(completions)}"
        )
    completion_index, completion = completions[0]
    completion_thread_id = completion.get("thread_id")
    if completion_thread_id is not None and (
        _string(completion_thread_id, "task_complete.thread_id") != exec_thread_id
    ):
        raise TelemetryError("task_complete.thread_id does not match execution JSONL")
    if _string(completion.get("turn_id"), "task_complete.turn_id") != turn_id:
        raise TelemetryError("task_complete.turn_id does not match planned turn_context")
    if completion_index <= context_index:
        raise TelemetryError("task_complete precedes its planned turn_context")

    relevant_tokens = [
        (index, payload)
        for index, payload in token_counts
        if context_index < index < completion_index
    ]
    if not relevant_tokens:
        raise TelemetryError("no token_count precedes task_complete")
    token_index, final_token_count = relevant_tokens[-1]
    last_usage = normalize_usage(
        _mapping(
            _mapping(final_token_count.get("info"), "token_count.info").get(
                "last_token_usage"
            ),
            "token_count.info.last_token_usage",
        ),
        label="token_count.info.last_token_usage",
    )

    return {
        "session_id": session_id,
        "cli_version": cli_version,
        "model_provider": model_provider,
        "thread_id": exec_thread_id,
        "turn_id": turn_id,
        "model": planned_model,
        "effort": planned_effort,
        "active_permission_profile": planned_permission_profile,
        "last_token_usage": last_usage,
        "turn_context_event_index": context_index,
        "final_token_count_event_index": token_index,
        "task_complete_event_index": completion_index,
        "raw_sha256": sha256_text(rollout_jsonl),
    }


def build_telemetry_receipt(
    exec_jsonl: str,
    rollout_jsonl: str,
    *,
    planned_model: str,
    planned_effort: str,
    planned_permission_profile: str,
    planned_cli_version: str = EXPECTED_CODEX_CLI_VERSION,
    planned_model_provider: str = EXPECTED_MODEL_PROVIDER,
    router_observation: Any = None,
) -> dict[str, Any]:
    """Create an exact execution receipt; router data remains non-authoritative."""

    execution = extract_exec_telemetry(exec_jsonl)
    rollout = bind_rollout(
        rollout_jsonl,
        exec_thread_id=execution["thread_id"],
        planned_model=planned_model,
        planned_effort=planned_effort,
        planned_permission_profile=planned_permission_profile,
        planned_cli_version=planned_cli_version,
        planned_model_provider=planned_model_provider,
    )
    if execution["usage"] != rollout["last_token_usage"]:
        raise TelemetryError(
            "turn.completed.usage does not match persisted final token_count"
        )
    execution_turn_id = execution.get("turn_id")
    if execution_turn_id is not None and execution_turn_id != rollout["turn_id"]:
        raise TelemetryError(
            "turn.completed.turn_id does not match persisted turn_context"
        )
    return {
        "valid": True,
        "execution": execution,
        "rollout": rollout,
        "router_observation": {
            "present": router_observation is not None,
            "raw_sha256": (
                sha256_json(router_observation) if router_observation is not None else None
            ),
        },
    }


def telemetry_compatibility_receipt() -> dict[str, Any]:
    """Prove the pinned telemetry contract without making a model call.

    Both documents are fixed literal captures shaped like the native Codex
    evidence.  They pass through ``build_telemetry_receipt`` itself so this
    check exercises the same route binding and token attribution used by a
    scored cell.  A second pass deliberately plans the wrong model and must
    fail closed.
    """

    exec_jsonl = (
        '{"type":"thread.started","thread_id":"telemetry-preflight-thread"}\n'
        '{"type":"turn.started"}\n'
        '{"type":"turn.completed","thread_id":"telemetry-preflight-thread",'
        '"turn_id":"telemetry-preflight-turn","usage":{"input_tokens":173,'
        '"cached_input_tokens":61,"cache_write_input_tokens":11,'
        '"output_tokens":29,"reasoning_output_tokens":17}}\n'
    )
    rollout_jsonl = (
        '{"type":"session_meta","payload":{"id":"telemetry-preflight-thread",'
        '"cli_version":"0.149.1","model_provider":"openai"}}\n'
        '{"type":"turn_context","payload":{"turn_id":"telemetry-preflight-turn",'
        '"model":"gpt-5.6-terra","effort":"high",'
        '"active_permission_profile":{"id":"routing_candidate"}}}\n'
        '{"type":"event_msg","payload":{"type":"token_count","info":{'
        '"last_token_usage":{"input_tokens":173,"cached_input_tokens":61,'
        '"cache_write_input_tokens":11,"output_tokens":29,'
        '"reasoning_output_tokens":17}}}}\n'
        '{"type":"event_msg","payload":{"type":"task_complete",'
        '"thread_id":"telemetry-preflight-thread",'
        '"turn_id":"telemetry-preflight-turn"}}\n'
    )
    receipt = build_telemetry_receipt(
        exec_jsonl,
        rollout_jsonl,
        planned_model="gpt-5.6-terra",
        planned_effort="high",
        planned_permission_profile="routing_candidate",
    )
    expected_usage = {
        "input_tokens": 173,
        "cached_input_tokens": 61,
        "cache_write_input_tokens": 11,
        "output_tokens": 29,
        "reasoning_output_tokens": 17,
        "uncached_input_tokens": 112,
    }
    rollout = receipt["rollout"]
    assertions = {
        "model": rollout["model"] == "gpt-5.6-terra",
        "effort": rollout["effort"] == "high",
        "permission_profile": (
            rollout["active_permission_profile"] == "routing_candidate"
        ),
        "cli_version": rollout["cli_version"] == EXPECTED_CODEX_CLI_VERSION,
        "model_provider": rollout["model_provider"] == EXPECTED_MODEL_PROVIDER,
        "token_attribution": (
            receipt["execution"]["usage"] == expected_usage
            and rollout["last_token_usage"] == expected_usage
        ),
    }
    if not all(assertions.values()):
        raise TelemetryError("fixed telemetry compatibility assertions failed")

    mismatch_error: TelemetryError | None = None
    try:
        build_telemetry_receipt(
            exec_jsonl,
            rollout_jsonl,
            planned_model="gpt-5.6-sol",
            planned_effort="high",
            planned_permission_profile="routing_candidate",
        )
    except TelemetryError as exc:
        mismatch_error = exc
    if mismatch_error is None:
        raise TelemetryError("deliberate telemetry route mismatch was accepted")

    return {
        "valid": True,
        "no_model_calls": True,
        "planned_route": {
            "model": rollout["model"],
            "effort": rollout["effort"],
            "active_permission_profile": rollout["active_permission_profile"],
            "cli_version": rollout["cli_version"],
            "model_provider": rollout["model_provider"],
        },
        "token_attribution": expected_usage,
        "assertions": assertions,
        "evidence": {
            "execution_raw_sha256": receipt["execution"]["raw_sha256"],
            "rollout_raw_sha256": rollout["raw_sha256"],
            "telemetry_receipt_sha256": sha256_json(receipt),
        },
        "route_mismatch_rejection": {
            "rejected": True,
            "planned_model": "gpt-5.6-sol",
            "error_type": type(mismatch_error).__name__,
            "error_sha256": sha256_text(str(mismatch_error)),
        },
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise TelemetryError(f"value is not JSON-serializable: {exc}") from exc
    return sha256_text(encoded)


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TelemetryError(f"{field} must be numeric")
    result = float(value)
    if not 0.0 <= result <= 100.0:
        raise TelemetryError(f"{field} must be between 0 and 100")
    return result


def _optional_nonnegative_integer(value: Any, field: str) -> int | None:
    if value is None:
        return None
    return _integer(value, field)


def _usage_window(value: Any, *, label: str, identifier: str | None = None) -> dict[str, Any]:
    window = _mapping(value, label)
    used = window.get("used_percent", window.get("usedPercent"))
    minutes = window.get("window_minutes", window.get("windowMinutes"))
    resets = window.get("resets_at", window.get("resetsAt"))
    return {
        "id": identifier,
        "used_percent": _number(used, f"{label}.used_percent"),
        "window_minutes": _optional_nonnegative_integer(minutes, f"{label}.window_minutes"),
        "resets_at": resets if isinstance(resets, (str, int, float)) and not isinstance(resets, bool) else None,
    }


_NORMALIZED_QUOTA_FIELDS = frozenset(
    {
        "captured_at",
        "raw_sha256",
        "primary",
        "secondary",
        "tertiary",
        "extra_rate_windows",
    }
)
_NORMALIZED_WINDOW_FIELDS = frozenset(
    {"id", "used_percent", "window_minutes", "resets_at"}
)


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise TelemetryError(
            f"{label} fields do not match contract; "
            f"missing={missing!r}, unexpected={unexpected!r}"
        )


def _valid_captured_at(value: Any) -> str:
    captured_at = _string(value, "snapshot.captured_at")
    try:
        parsed = datetime.fromisoformat(
            captured_at[:-1] + "+00:00" if captured_at.endswith("Z") else captured_at
        )
    except ValueError as exc:
        raise TelemetryError("snapshot.captured_at must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TelemetryError("snapshot.captured_at must include a UTC offset")
    return captured_at


def _validate_normalized_window(
    value: Any, *, label: str, expected_id: str | None
) -> None:
    window = _mapping(value, label)
    _exact_fields(window, _NORMALIZED_WINDOW_FIELDS, label)
    identifier = window.get("id")
    if expected_id is None:
        if identifier is not None:
            raise TelemetryError(f"{label}.id must be null")
    elif _string(identifier, f"{label}.id") != expected_id:
        raise TelemetryError(f"{label}.id does not match its extra window id")
    _number(window.get("used_percent"), f"{label}.used_percent")
    _optional_nonnegative_integer(
        window.get("window_minutes"), f"{label}.window_minutes"
    )
    resets_at = window.get("resets_at")
    if isinstance(resets_at, bool) or not (
        resets_at is None
        or (isinstance(resets_at, str) and bool(resets_at.strip()))
        or (
            isinstance(resets_at, (int, float))
            and math.isfinite(resets_at)
            and resets_at >= 0
        )
    ):
        raise TelemetryError(
            f"{label}.resets_at must be null, a non-empty string, or numeric"
        )


def validate_normalized_quota_snapshot(snapshot: Any) -> None:
    """Reject normalized quota evidence that drifts from the exact contract."""

    normalized = _mapping(snapshot, "normalized quota snapshot")
    _exact_fields(normalized, _NORMALIZED_QUOTA_FIELDS, "normalized quota snapshot")
    _valid_captured_at(normalized.get("captured_at"))
    raw_sha256 = _string(normalized.get("raw_sha256"), "snapshot.raw_sha256")
    if len(raw_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in raw_sha256
    ):
        raise TelemetryError("snapshot.raw_sha256 must be a lowercase SHA-256 digest")

    observed_windows = 0
    for name in ("primary", "secondary", "tertiary"):
        value = normalized.get(name)
        if value is not None:
            _validate_normalized_window(
                value, label=f"snapshot.{name}", expected_id=None
            )
            observed_windows += 1

    extras = normalized.get("extra_rate_windows")
    if not isinstance(extras, list):
        raise TelemetryError("snapshot.extra_rate_windows must be a list")
    seen_ids: set[str] = set()
    for index, value in enumerate(extras):
        window = _mapping(value, f"snapshot.extra_rate_windows[{index}]")
        identifier = _string(
            window.get("id"), f"snapshot.extra_rate_windows[{index}].id"
        )
        if not identifier.strip():
            raise TelemetryError(
                f"snapshot.extra_rate_windows[{index}].id must not be whitespace"
            )
        if identifier in seen_ids:
            raise TelemetryError(f"duplicate normalized extra rate window id: {identifier}")
        seen_ids.add(identifier)
        _validate_normalized_window(
            window,
            label=f"snapshot.extra_rate_windows[{index}]",
            expected_id=identifier,
        )
        observed_windows += 1
    if observed_windows == 0:
        raise TelemetryError("normalized quota snapshot contains no quota windows")


def normalize_codexbar_snapshot(raw: Any, *, captured_at: str) -> dict[str, Any]:
    """Whitelist non-identifying quota fields and retain only the raw hash.

    CodexBar's raw response can contain account identity data.  The benchmark
    evidence never persists it: it records an immutable raw hash plus selected
    percentage windows.  This is an observation, not a quota ceiling.
    """

    _string(captured_at, "captured_at")
    record: Mapping[str, Any]
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        if len(raw) != 1:
            raise TelemetryError("CodexBar response must contain exactly one provider record")
        record = _mapping(raw[0], "CodexBar provider record")
    else:
        record = _mapping(raw, "CodexBar provider record")
    usage = _mapping(record.get("usage"), "CodexBar usage")

    normalized: dict[str, Any] = {
        "captured_at": captured_at,
        "raw_sha256": sha256_json(raw),
        "primary": None,
        "secondary": None,
        "tertiary": None,
        "extra_rate_windows": [],
    }
    for name in ("primary", "secondary", "tertiary"):
        if usage.get(name) is not None:
            normalized[name] = _usage_window(
                usage[name], label=f"CodexBar usage.{name}"
            )
    extras = usage.get("extraRateWindows", usage.get("extra_rate_windows", []))
    if not isinstance(extras, list):
        raise TelemetryError("CodexBar usage.extraRateWindows must be a list")
    seen_ids: set[str] = set()
    for index, extra in enumerate(extras):
        extra_mapping = _mapping(extra, f"CodexBar usage.extraRateWindows[{index}]")
        identifier = _string(extra_mapping.get("id"), f"extraRateWindows[{index}].id")
        if identifier in seen_ids:
            raise TelemetryError(f"duplicate CodexBar extra rate window id: {identifier}")
        seen_ids.add(identifier)
        source_window = extra_mapping.get("window", extra_mapping)
        normalized["extra_rate_windows"].append(
            _usage_window(
                source_window,
                label=f"CodexBar usage.extraRateWindows[{index}].window",
                identifier=identifier,
            )
        )
    if not any(normalized[name] is not None for name in ("primary", "secondary", "tertiary")) and not normalized["extra_rate_windows"]:
        raise TelemetryError("CodexBar response contains no observable quota windows")
    return normalized


def quota_movement(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two normalized snapshots without imposing a consumption ceiling."""

    def windows(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for name in ("primary", "secondary", "tertiary"):
            if snapshot.get(name) is not None:
                result[name] = _mapping(snapshot[name], f"snapshot.{name}")
        extras = snapshot.get("extra_rate_windows", [])
        if not isinstance(extras, list):
            raise TelemetryError("snapshot.extra_rate_windows must be a list")
        for index, extra in enumerate(extras):
            window = _mapping(extra, f"snapshot.extra_rate_windows[{index}]")
            identifier = _string(window.get("id"), f"snapshot.extra_rate_windows[{index}].id")
            key = f"extra:{identifier}"
            if key in result:
                raise TelemetryError(f"duplicate normalized quota window: {key}")
            result[key] = window
        return result

    before_windows = windows(before)
    after_windows = windows(after)
    movement: list[dict[str, Any]] = []
    for key in sorted(set(before_windows) | set(after_windows)):
        old = before_windows.get(key)
        new = after_windows.get(key)
        old_percent = _number(old.get("used_percent"), f"before.{key}.used_percent") if old else None
        new_percent = _number(new.get("used_percent"), f"after.{key}.used_percent") if new else None
        comparison = "comparable"
        if old is None or new is None:
            comparison = "window_missing"
        elif old.get("window_minutes") != new.get("window_minutes"):
            comparison = "window_changed"
        elif old.get("resets_at") is None or new.get("resets_at") is None:
            comparison = "boundary_unknown"
        elif old.get("resets_at") != new.get("resets_at"):
            comparison = "reset_boundary"
        movement.append(
            {
                "window": key,
                "before_used_percent": old_percent,
                "after_used_percent": new_percent,
                "used_percent_delta": (
                    round(new_percent - old_percent, 6)
                    if comparison == "comparable"
                    and old_percent is not None
                    and new_percent is not None
                    else None
                ),
                "before_resets_at": old.get("resets_at") if old else None,
                "after_resets_at": new.get("resets_at") if new else None,
                "reset_boundary_observed": comparison == "reset_boundary",
                "comparison": comparison,
            }
        )
    return {
        "before_raw_sha256": _string(before.get("raw_sha256"), "before.raw_sha256"),
        "after_raw_sha256": _string(after.get("raw_sha256"), "after.raw_sha256"),
        "windows": movement,
    }
