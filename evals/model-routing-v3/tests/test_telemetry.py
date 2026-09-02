from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from telemetry import (  # noqa: E402
    TelemetryError,
    bind_rollout,
    build_telemetry_receipt,
    extract_exec_telemetry,
    normalize_codexbar_snapshot,
    normalize_usage,
    parse_jsonl,
    quota_movement,
    telemetry_compatibility_receipt,
    validate_normalized_quota_snapshot,
)


def jsonl(*records: dict) -> str:
    return "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records)


def usage(**overrides: int) -> dict[str, int]:
    result = {
        "input_tokens": 100,
        "cached_input_tokens": 40,
        "cache_write_input_tokens": 7,
        "output_tokens": 20,
        "reasoning_output_tokens": 10,
    }
    result.update(overrides)
    return result


def execution(*, thread_id: str = "thread-1", terminal_usage: dict | None = None) -> str:
    return jsonl(
        {"type": "thread.started", "thread_id": thread_id},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": terminal_usage or usage()},
    )


def rollout(
    *,
    thread_id: str = "thread-1",
    model: str = "gpt-5.6-terra",
    effort: str = "high",
    profile: str = "bench",
    token_usage: dict | None = None,
) -> str:
    return jsonl(
        {
            "type": "session_meta",
            "payload": {
                "id": thread_id,
                "cli_version": "0.149.1",
                "model_provider": "openai",
            },
        },
        {
            "type": "turn_context",
            "payload": {
                "turn_id": "turn-1",
                "model": model,
                "effort": effort,
                "active_permission_profile": {"id": profile},
            },
        },
        {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"last_token_usage": token_usage or usage()}},
        },
        {
            "type": "event_msg",
            "payload": {"type": "task_complete", "thread_id": thread_id, "turn_id": "turn-1"},
        },
    )


def codexbar(*, primary: float = 10, secondary: float | None = 20, spark: float = 8) -> list[dict]:
    data: dict = {
        "account": {"email": "private@example.test", "name": "Private Person"},
        "usage": {
            "primary": {"usedPercent": primary, "windowMinutes": 300, "resetsAt": 123},
            "extraRateWindows": [
                {
                    "id": "spark-weekly",
                    "title": "Spark weekly",
                    "window": {"usedPercent": spark, "windowMinutes": 10080, "resetsAt": 456},
                }
            ],
        },
    }
    if secondary is not None:
        data["usage"]["secondary"] = {
            "usedPercent": secondary,
            "windowMinutes": 10080,
            "resetsAt": 456,
        }
    return [data]


class ParseJsonlTests(unittest.TestCase):
    def test_parses_object_lines(self) -> None:
        self.assertEqual(parse_jsonl('{"a":1}\n'), [{"a": 1}])

    def test_rejects_malformed_blank_nonobject_and_truncated_input(self) -> None:
        for text in ("", "\n", "{bad}\n", "[]\n", '{"a":1}'):
            with self.subTest(text=text), self.assertRaises(TelemetryError):
                parse_jsonl(text)


class UsageTests(unittest.TestCase):
    def test_derives_uncached_without_double_counting(self) -> None:
        self.assertEqual(normalize_usage(usage())["uncached_input_tokens"], 60)

    def test_rejects_missing_boolean_negative_and_inconsistent_values(self) -> None:
        invalid = [
            {key: value for key, value in usage().items() if key != "output_tokens"},
            usage(input_tokens=True),
            usage(output_tokens=-1),
            usage(cached_input_tokens=101),
            usage(reasoning_output_tokens=21),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(TelemetryError):
                normalize_usage(value)


class ExecutionTests(unittest.TestCase):
    def test_extracts_one_exact_terminal_snapshot(self) -> None:
        receipt = extract_exec_telemetry(execution())
        self.assertEqual(receipt["thread_id"], "thread-1")
        self.assertEqual(receipt["usage"]["uncached_input_tokens"], 60)
        self.assertEqual(receipt["event_count"], 3)

    def test_rejects_missing_duplicate_and_conflicting_terminals(self) -> None:
        cases = [
            jsonl({"type": "thread.started", "thread_id": "thread-1"}),
            jsonl(
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.completed", "usage": usage()},
                {"type": "turn.completed", "usage": usage()},
            ),
            jsonl(
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.started"},
                {"type": "turn.completed", "thread_id": "thread-2", "usage": usage()},
            ),
            jsonl(
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.started"},
                {"type": "turn.started"},
                {"type": "turn.completed", "usage": usage()},
            ),
            jsonl(
                {"type": "turn.started"},
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.completed", "usage": usage()},
            ),
            jsonl(
                {"type": "thread.started", "thread_id": "thread-1"},
                {"type": "turn.started"},
                {"type": "turn.completed", "usage": usage()},
                {"type": "item.completed"},
            ),
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(TelemetryError):
                extract_exec_telemetry(value)


class RolloutBindingTests(unittest.TestCase):
    def bind(self, document: str, **kwargs: str) -> dict:
        return bind_rollout(
            document,
            exec_thread_id="thread-1",
            planned_model="gpt-5.6-terra",
            planned_effort="high",
            planned_permission_profile="bench",
            **kwargs,
        )

    def test_binds_session_route_token_usage_and_completion(self) -> None:
        receipt = self.bind(rollout())
        self.assertEqual(receipt["session_id"], "thread-1")
        self.assertEqual(receipt["cli_version"], "0.149.1")
        self.assertEqual(receipt["turn_id"], "turn-1")
        self.assertEqual(receipt["last_token_usage"]["uncached_input_tokens"], 60)

    def test_rejects_missing_duplicate_or_mismatched_binding_evidence(self) -> None:
        valid = parse_jsonl(rollout())
        duplicate_meta = jsonl(valid[0], *valid)
        wrong_thread = rollout(thread_id="thread-2")
        wrong_route = rollout(model="gpt-5.6-sol")
        missing_usage = rollout(token_usage=usage(output_tokens=0, reasoning_output_tokens=1))
        no_completion = jsonl(*valid[:-1])
        for value in (duplicate_meta, wrong_thread, wrong_route, missing_usage, no_completion):
            with self.subTest(value=value), self.assertRaises(TelemetryError):
                self.bind(value)

    def test_rejects_token_count_after_completion(self) -> None:
        records = parse_jsonl(rollout())
        records[2], records[3] = records[3], records[2]
        with self.assertRaises(TelemetryError):
            self.bind(jsonl(*records))

    def test_rejects_extra_context_old_token_and_wrong_cli_pin(self) -> None:
        records = parse_jsonl(rollout())
        extra_context = records[1].copy()
        with self.assertRaises(TelemetryError):
            self.bind(jsonl(records[0], records[1], extra_context, *records[2:]))
        with self.assertRaises(TelemetryError):
            self.bind(jsonl(records[0], records[2], records[1], records[3]))
        with self.assertRaises(TelemetryError):
            self.bind(rollout(), planned_cli_version="0.149.2")
        with self.assertRaises(TelemetryError):
            self.bind(rollout(), planned_model_provider="not-openai")

    def test_accepts_task_complete_without_redundant_thread_id(self) -> None:
        records = parse_jsonl(rollout())
        records[-1]["payload"].pop("thread_id")
        self.assertEqual(self.bind(jsonl(*records))["thread_id"], "thread-1")

    def test_rejects_exec_and_rollout_usage_disagreement(self) -> None:
        with self.assertRaises(TelemetryError):
            build_telemetry_receipt(
                execution(terminal_usage=usage(input_tokens=101)),
                rollout(),
                planned_model="gpt-5.6-terra",
                planned_effort="high",
                planned_permission_profile="bench",
            )

    def test_router_observation_never_changes_validity(self) -> None:
        without_router = build_telemetry_receipt(
            execution(), rollout(), planned_model="gpt-5.6-terra", planned_effort="high", planned_permission_profile="bench"
        )
        with_router = build_telemetry_receipt(
            execution(), rollout(), planned_model="gpt-5.6-terra", planned_effort="high", planned_permission_profile="bench", router_observation={"bad": "untrusted"}
        )
        self.assertTrue(without_router["valid"])
        self.assertTrue(with_router["valid"])
        self.assertFalse(without_router["router_observation"]["present"])
        self.assertTrue(with_router["router_observation"]["present"])


class QuotaTests(unittest.TestCase):
    def test_redacts_identity_and_preserves_only_whitelisted_windows(self) -> None:
        snapshot = normalize_codexbar_snapshot(codexbar(), captured_at="2026-09-01T00:00:00Z")
        rendered = json.dumps(snapshot)
        self.assertNotIn("private@example.test", rendered)
        self.assertNotIn("Private Person", rendered)
        self.assertEqual(snapshot["primary"]["used_percent"], 10.0)
        self.assertEqual(snapshot["extra_rate_windows"][0]["id"], "spark-weekly")

    def test_accepts_current_codexbar_shape_with_null_primary(self) -> None:
        raw = codexbar()
        raw[0]["usage"]["primary"] = None
        raw[0]["usage"]["tertiary"] = None
        snapshot = normalize_codexbar_snapshot(raw, captured_at="now")
        self.assertIsNone(snapshot["primary"])
        self.assertEqual(snapshot["secondary"]["used_percent"], 20.0)
        movement = quota_movement(snapshot, snapshot)
        self.assertEqual(
            {item["window"] for item in movement["windows"]},
            {"secondary", "extra:spark-weekly"},
        )

    def test_quota_movement_has_no_ceiling_or_consumption_assumption(self) -> None:
        before = normalize_codexbar_snapshot(codexbar(primary=10, secondary=None, spark=8), captured_at="before")
        after = normalize_codexbar_snapshot(codexbar(primary=7, secondary=21, spark=9), captured_at="after")
        movement = quota_movement(before, after)
        self.assertNotIn("ceiling", json.dumps(movement).lower())
        values = {item["window"]: item for item in movement["windows"]}
        self.assertEqual(values["primary"]["used_percent_delta"], -3.0)
        self.assertEqual(values["secondary"]["before_used_percent"], None)
        self.assertEqual(values["extra:spark-weekly"]["used_percent_delta"], 1.0)

    def test_rejects_malformed_quota_windows(self) -> None:
        bad = codexbar()
        bad[0]["usage"]["primary"]["usedPercent"] = 101
        with self.assertRaises(TelemetryError):
            normalize_codexbar_snapshot(bad, captured_at="now")

    def test_quota_delta_is_null_across_reset_or_window_change(self) -> None:
        before = normalize_codexbar_snapshot(codexbar(primary=10), captured_at="before")
        reset = codexbar(primary=2)
        reset[0]["usage"]["primary"]["resetsAt"] = 999
        after_reset = normalize_codexbar_snapshot(reset, captured_at="after")
        item = {x["window"]: x for x in quota_movement(before, after_reset)["windows"]}["primary"]
        self.assertIsNone(item["used_percent_delta"])
        self.assertEqual(item["comparison"], "reset_boundary")

        changed = codexbar(primary=11)
        changed[0]["usage"]["primary"]["windowMinutes"] = 60
        after_changed = normalize_codexbar_snapshot(changed, captured_at="after")
        item = {x["window"]: x for x in quota_movement(before, after_changed)["windows"]}["primary"]
        self.assertIsNone(item["used_percent_delta"])
        self.assertEqual(item["comparison"], "window_changed")

    def test_strict_validator_accepts_exact_normalized_snapshot(self) -> None:
        snapshot = normalize_codexbar_snapshot(
            codexbar(), captured_at="2026-09-01T00:00:00Z"
        )
        self.assertIsNone(validate_normalized_quota_snapshot(snapshot))

    def test_strict_validator_rejects_timestamp_digest_and_empty_snapshot(self) -> None:
        valid = normalize_codexbar_snapshot(
            codexbar(), captured_at="2026-09-01T00:00:00+00:00"
        )
        cases = []
        for field, value in (
            ("captured_at", "now"),
            ("captured_at", "2026-09-01T00:00:00"),
            ("raw_sha256", "A" * 64),
            ("raw_sha256", "0" * 63),
        ):
            candidate = dict(valid)
            candidate[field] = value
            cases.append(candidate)
        cases.append(
            {
                **valid,
                "primary": None,
                "secondary": None,
                "tertiary": None,
                "extra_rate_windows": [],
            }
        )
        for candidate in cases:
            with self.subTest(candidate=candidate), self.assertRaises(TelemetryError):
                validate_normalized_quota_snapshot(candidate)

    def test_strict_validator_rejects_field_drift_and_invalid_windows(self) -> None:
        valid = normalize_codexbar_snapshot(
            codexbar(), captured_at="2026-09-01T00:00:00Z"
        )
        unexpected_top = {**valid, "account": "leak"}
        missing_top = dict(valid)
        missing_top.pop("tertiary")
        primary_extra = {**valid, "primary": {**valid["primary"], "title": "drift"}}
        primary_id = {**valid, "primary": {**valid["primary"], "id": "primary"}}
        bad_percent = {
            **valid,
            "primary": {**valid["primary"], "used_percent": 101},
        }
        bad_minutes = {
            **valid,
            "primary": {**valid["primary"], "window_minutes": True},
        }
        bad_reset = {
            **valid,
            "primary": {**valid["primary"], "resets_at": ""},
        }
        negative_reset = {
            **valid,
            "primary": {**valid["primary"], "resets_at": -1},
        }
        for candidate in (
            unexpected_top,
            missing_top,
            primary_extra,
            primary_id,
            bad_percent,
            bad_minutes,
            bad_reset,
            negative_reset,
        ):
            with self.subTest(candidate=candidate), self.assertRaises(TelemetryError):
                validate_normalized_quota_snapshot(candidate)

    def test_strict_validator_requires_unique_nonempty_exact_extra_ids(self) -> None:
        valid = normalize_codexbar_snapshot(
            codexbar(), captured_at="2026-09-01T00:00:00Z"
        )
        extra = valid["extra_rate_windows"][0]
        cases = [
            {**valid, "extra_rate_windows": [{**extra, "id": ""}]},
            {**valid, "extra_rate_windows": [{**extra, "id": "   "}]},
            {**valid, "extra_rate_windows": [extra, dict(extra)]},
            {**valid, "extra_rate_windows": [{**extra, "label": "drift"}]},
        ]
        for candidate in cases:
            with self.subTest(candidate=candidate), self.assertRaises(TelemetryError):
                validate_normalized_quota_snapshot(candidate)


class CompatibilityReceiptTests(unittest.TestCase):
    def test_exercises_real_parser_with_pinned_route_and_exact_tokens(self) -> None:
        receipt = telemetry_compatibility_receipt()
        self.assertTrue(receipt["valid"])
        self.assertTrue(receipt["no_model_calls"])
        self.assertEqual(
            receipt["planned_route"],
            {
                "model": "gpt-5.6-terra",
                "effort": "high",
                "active_permission_profile": "routing_candidate",
                "cli_version": "0.149.1",
                "model_provider": "openai",
            },
        )
        self.assertEqual(
            receipt["token_attribution"],
            {
                "input_tokens": 173,
                "cached_input_tokens": 61,
                "cache_write_input_tokens": 11,
                "output_tokens": 29,
                "reasoning_output_tokens": 17,
                "uncached_input_tokens": 112,
            },
        )
        self.assertTrue(all(receipt["assertions"].values()))
        self.assertTrue(receipt["route_mismatch_rejection"]["rejected"])
        self.assertEqual(
            receipt["route_mismatch_rejection"]["error_type"], "TelemetryError"
        )

    def test_is_deterministic_and_contains_only_hashes_for_raw_evidence(self) -> None:
        first = telemetry_compatibility_receipt()
        second = telemetry_compatibility_receipt()
        self.assertEqual(first, second)
        self.assertEqual(set(first["evidence"]), {
            "execution_raw_sha256",
            "rollout_raw_sha256",
            "telemetry_receipt_sha256",
        })
        for digest in first["evidence"].values():
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
