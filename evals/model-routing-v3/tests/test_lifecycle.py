from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lifecycle  # noqa: E402
from lifecycle import (  # noqa: E402
    LifecycleError,
    authorize_canary,
    authorize_next,
    canonical_state_bytes,
    create_state,
    expire_active_cell,
    load_state,
    read_definition,
    record_active_failure,
    record_canary_audit,
    record_implementation_complete,
    record_implementation_failure,
    record_preflight,
    record_review,
    record_verification,
    save_state,
    validate_definition,
    validate_package_review,
    validate_state,
)


DEFINITION_PATH = ROOT / "definition.json"
HASHES = {
    "definition": "1" * 64,
    "package": "2" * 64,
    "preflight": "3" * 64,
    "implementation": "4" * 64,
    "artifact": "5" * 64,
    "verification": "6" * 64,
    "review": "7" * 64,
    "review_range": "a" * 64,
    "result": "8" * 64,
    "audit": "9" * 64,
}


class LifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))

    def fresh(self) -> dict:
        return create_state(
            self.definition,
            definition_sha256=HASHES["definition"],
            package_sha256=HASHES["package"],
        )

    def preflight(self, state: dict, status: str = "PASS") -> dict:
        return record_preflight(
            state,
            self.definition,
            status=status,
            receipt_sha256=HASHES["preflight"],
            observed_definition_sha256=HASHES["definition"],
            observed_package_sha256=HASHES["package"],
        )

    def canary_started(self, now: int = 100) -> dict:
        return authorize_canary(
            self.preflight(self.fresh()),
            self.definition,
            now_monotonic_ns=now,
        )

    def implementation_complete(self, state: dict, *, now: int = 101) -> dict:
        return record_implementation_complete(
            state,
            self.definition,
            cell_id=state["active_cell"]["cell_id"],
            artifact_sha256=HASHES["artifact"],
            receipt_sha256=HASHES["implementation"],
            now_monotonic_ns=now,
        )

    def verified(
        self,
        state: dict,
        *,
        now: int = 102,
        public: bool = True,
        hidden: bool = True,
    ) -> dict:
        return record_verification(
            state,
            self.definition,
            cell_id=state["active_cell"]["cell_id"],
            public_passed=public,
            hidden_passed=hidden,
            scope_safe=True,
            telemetry_safe=True,
            receipt_sha256=HASHES["verification"],
            now_monotonic_ns=now,
        )

    def accepted_canary(self) -> dict:
        state = self.verified(self.implementation_complete(self.canary_started()))
        return record_review(
            state,
            self.definition,
            cell_id="use-grok--terra-high",
            status="PASS",
            finding_count=0,
            artifact_sha256=HASHES["artifact"],
            review_range_sha256=HASHES["review_range"],
            receipt_sha256=HASHES["review"],
            result_sha256=HASHES["result"],
            now_monotonic_ns=103,
        )

    def accepted_audit(self, state: dict, status: str = "ACCEPT") -> dict:
        audit = {
            "status": status,
            "definition_sha256": HASHES["definition"],
            "package_sha256": HASHES["package"],
            "canary_result_sha256": HASHES["result"],
            "canary_artifact_sha256": HASHES["artifact"],
            "auditor": "independent-auditor",
            "independent_of_candidate_and_controller": True,
            "findings": [],
            "summary": "bound audit",
        }
        return record_canary_audit(
            state,
            self.definition,
            audit=audit,
            audit_sha256=HASHES["audit"],
        )


class DefinitionTests(LifecycleTestCase):
    def test_reads_and_hashes_exact_definition(self) -> None:
        definition, digest = read_definition(DEFINITION_PATH)
        self.assertEqual(definition, self.definition)
        self.assertEqual(len(digest), 64)

    def test_rejects_every_lifecycle_weakening(self) -> None:
        mutations = {
            "wrong canary": lambda value: value["lifecycle"].__setitem__(
                "canary", value["lifecycle"]["run_order"][1]
            ),
            "duplicate order": lambda value: value["lifecycle"]["run_order"].__setitem__(
                1, value["lifecycle"]["run_order"][0]
            ),
            "short deadline": lambda value: value["lifecycle"].__setitem__(
                "inclusive_cell_deadline_seconds", 599
            ),
            "retry": lambda value: value["lifecycle"].__setitem__("automatic_retry", True),
            "repair": lambda value: value["lifecycle"].__setitem__("automatic_repair", True),
            "rereview": lambda value: value["lifecycle"].__setitem__("rereview", True),
            "continue anomaly": lambda value: value["lifecycle"].__setitem__(
                "stop_on_anomaly", False
            ),
            "skip audit": lambda value: value["lifecycle"].__setitem__(
                "remaining_cells_require_accepted_canary_audit", False
            ),
            "batch surface": lambda value: value["execution_surface"].__setitem__(
                "run_all_command", True
            ),
            "Spark canary": lambda value: value["cells"]["use-grok--terra-high"].__setitem__(
                "model", "gpt-5.3-codex-spark"
            ),
            "mutable reviewer": lambda value: value["reviewer"].__setitem__(
                "read_only", False
            ),
            "evaluator tool surface": lambda value: value["evaluator"][
                "boundary"
            ]["tool_free_argv"].remove("--no-plan"),
            "evaluator auth cleanup": lambda value: value["evaluator"][
                "boundary"
            ].__setitem__("transient_auth_removed_after_every_terminal_outcome", False),
            "evaluator network claim": lambda value: value["evaluator"][
                "boundary"
            ]["network"].__setitem__("provider_hostname_attribution_claim", True),
        }
        for label, mutate in mutations.items():
            value = copy.deepcopy(self.definition)
            mutate(value)
            with self.subTest(label=label), self.assertRaises(LifecycleError):
                validate_definition(value)


class GateTests(LifecycleTestCase):
    def test_package_review_requires_three_distinct_clean_axes(self) -> None:
        review = {
            "status": "ACCEPT",
            "definition_sha256": HASHES["definition"],
            "package_sha256": HASHES["package"],
            "reviews": [
                {"axis": axis, "reviewer": f"reviewer-{axis}", "status": "PASS", "findings": [], "summary": "pass"}
                for axis in ("standards", "spec", "security")
            ],
            "summary": "accepted",
        }
        self.assertEqual(
            validate_package_review(
                review,
                definition_sha256=HASHES["definition"],
                package_sha256=HASHES["package"],
            )["status"],
            "ACCEPT",
        )
        review["reviews"][0]["findings"] = ["unresolved"]
        with self.assertRaises(LifecycleError):
            validate_package_review(
                review,
                definition_sha256=HASHES["definition"],
                package_sha256=HASHES["package"],
            )

    def test_module_exposes_no_batch_arbitrary_retry_repair_or_rereview_surface(self) -> None:
        for name in (
            "run_all",
            "authorize_cell",
            "retry_cell",
            "repair_cell",
            "rereview_cell",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(lifecycle, name))

    def test_happy_path_authorizes_exact_next_cell_once(self) -> None:
        state = self.accepted_audit(self.accepted_canary())
        state = authorize_next(state, self.definition, now_monotonic_ns=200)
        self.assertEqual(state["active_cell"]["cell_id"], "use-grok--spark-high")
        self.assertEqual(state["active_cell"]["attempt"], 1)
        with self.assertRaises(LifecycleError):
            authorize_next(state, self.definition, now_monotonic_ns=201)
        with self.assertRaises(LifecycleError):
            authorize_canary(state, self.definition, now_monotonic_ns=201)

    def test_happy_path_runs_every_frozen_cell_in_order(self) -> None:
        state = self.accepted_audit(self.accepted_canary())
        observed = [state["terminal_cells"][0]["cell_id"]]
        now = 1_000
        while len(state["terminal_cells"]) < len(state["run_order"]):
            state = authorize_next(state, self.definition, now_monotonic_ns=now)
            cell_id = state["active_cell"]["cell_id"]
            state = self.implementation_complete(state, now=now + 1)
            state = self.verified(state, now=now + 2)
            state = record_review(
                state,
                self.definition,
                cell_id=cell_id,
                status="PASS",
                finding_count=0,
                artifact_sha256=HASHES["artifact"],
                review_range_sha256=HASHES["review_range"],
                receipt_sha256=HASHES["review"],
                result_sha256=HASHES["result"],
                now_monotonic_ns=now + 3,
            )
            observed.append(cell_id)
            now += 1_000
        self.assertEqual(observed, state["run_order"])
        self.assertFalse(state["stopped"])
        with self.assertRaises(LifecycleError):
            authorize_next(state, self.definition, now_monotonic_ns=now)

    def test_scored_implementation_failure_continues_to_next_frozen_cell(self) -> None:
        state = self.accepted_audit(self.accepted_canary())
        state = authorize_next(state, self.definition, now_monotonic_ns=200)
        self.assertEqual(state["active_cell"]["cell_id"], "use-grok--spark-high")

        state = record_implementation_failure(
            state,
            self.definition,
            cell_id="use-grok--spark-high",
            result_sha256=HASHES["result"],
            reason="candidate failed",
            now_monotonic_ns=201,
        )

        self.assertFalse(state["stopped"])
        self.assertIsNone(state["stop_reason"])
        state = authorize_next(state, self.definition, now_monotonic_ns=202)
        self.assertEqual(state["active_cell"]["cell_id"], "openbot-acp--sol-high")

    def test_later_scored_timeout_and_route_failures_continue(self) -> None:
        for status in ("PROVIDER_UNAVAILABLE", "QUOTA_EXHAUSTED"):
            state = self.accepted_audit(self.accepted_canary())
            state = authorize_next(state, self.definition, now_monotonic_ns=200)
            state = record_active_failure(
                state,
                self.definition,
                cell_id="use-grok--spark-high",
                status=status,
                result_sha256=HASHES["result"],
                reason=status,
                now_monotonic_ns=201,
            )
            with self.subTest(status=status):
                self.assertFalse(state["stopped"])
                next_state = authorize_next(
                    state,
                    self.definition,
                    now_monotonic_ns=202,
                )
                self.assertEqual(
                    next_state["active_cell"]["cell_id"],
                    "openbot-acp--sol-high",
                )

        state = self.accepted_audit(self.accepted_canary())
        state = authorize_next(state, self.definition, now_monotonic_ns=1_000)
        deadline = state["active_cell"]["deadline_monotonic_ns"]
        state = expire_active_cell(
            state,
            self.definition,
            cell_id="use-grok--spark-high",
            result_sha256=HASHES["result"],
            now_monotonic_ns=deadline,
        )
        self.assertFalse(state["stopped"])
        state = authorize_next(
            state,
            self.definition,
            now_monotonic_ns=deadline + 1,
        )
        self.assertEqual(state["active_cell"]["cell_id"], "openbot-acp--sol-high")

    def test_later_verification_or_review_failure_continues(self) -> None:
        for public_passed, finding_count, terminal_status in (
            (False, 0, "VERIFICATION_FAILED"),
            (True, 1, "REVIEW_BLOCKED"),
        ):
            state = self.accepted_audit(self.accepted_canary())
            state = authorize_next(state, self.definition, now_monotonic_ns=200)
            state = self.implementation_complete(state, now=201)
            state = self.verified(
                state,
                now=202,
                public=public_passed,
            )
            state = record_review(
                state,
                self.definition,
                cell_id="use-grok--spark-high",
                status="PASS",
                finding_count=finding_count,
                artifact_sha256=HASHES["artifact"],
                review_range_sha256=HASHES["review_range"],
                receipt_sha256=HASHES["review"],
                result_sha256=HASHES["result"],
                now_monotonic_ns=203,
            )
            with self.subTest(terminal_status=terminal_status):
                self.assertEqual(
                    state["terminal_cells"][-1]["terminal"]["status"],
                    terminal_status,
                )
                self.assertFalse(state["stopped"])
                next_state = authorize_next(
                    state,
                    self.definition,
                    now_monotonic_ns=204,
                )
                self.assertEqual(
                    next_state["active_cell"]["cell_id"],
                    "openbot-acp--sol-high",
                )

    def test_later_safety_or_integrity_failure_stops_remaining_cells(self) -> None:
        for status in (
            "BOUNDARY_FAILURE",
            "CONTROLLER_ERROR",
            "TELEMETRY_FAILURE",
        ):
            state = self.accepted_audit(self.accepted_canary())
            state = authorize_next(state, self.definition, now_monotonic_ns=200)
            state = record_active_failure(
                state,
                self.definition,
                cell_id="use-grok--spark-high",
                status=status,
                result_sha256=HASHES["result"],
                reason=status,
                now_monotonic_ns=201,
            )
            with self.subTest(status=status):
                self.assertTrue(state["stopped"])
                with self.assertRaises(LifecycleError):
                    authorize_next(state, self.definition, now_monotonic_ns=202)

    def test_late_safety_failure_takes_precedence_over_timeout(self) -> None:
        for status in (
            "BOUNDARY_FAILURE",
            "CONTROLLER_ERROR",
            "TELEMETRY_FAILURE",
        ):
            state = self.accepted_audit(self.accepted_canary())
            state = authorize_next(state, self.definition, now_monotonic_ns=200)
            deadline = state["active_cell"]["deadline_monotonic_ns"]

            state = record_active_failure(
                state,
                self.definition,
                cell_id="use-grok--spark-high",
                status=status,
                result_sha256=HASHES["result"],
                reason=status,
                now_monotonic_ns=deadline,
            )

            with self.subTest(status=status):
                self.assertTrue(state["stopped"])
                self.assertEqual(
                    state["terminal_cells"][-1]["terminal"]["status"], status
                )

    def test_rejects_multiple_hard_stop_terminals(self) -> None:
        state = self.accepted_audit(self.accepted_canary())
        state = authorize_next(state, self.definition, now_monotonic_ns=200)
        state = record_active_failure(
            state,
            self.definition,
            cell_id="use-grok--spark-high",
            status="BOUNDARY_FAILURE",
            result_sha256=HASHES["result"],
            reason="BOUNDARY_FAILURE",
            now_monotonic_ns=201,
        )
        forged = copy.deepcopy(state["terminal_cells"][-1])
        forged["cell_id"] = "openbot-acp--sol-high"
        forged["ordinal"] = 2
        forged["started_monotonic_ns"] = 300
        forged["deadline_monotonic_ns"] = 300 + 600 * 1_000_000_000
        forged["terminal"]["ended_monotonic_ns"] = 301
        state["terminal_cells"].append(forged)

        with self.assertRaises(LifecycleError):
            validate_state(state, self.definition)

    def test_canary_requires_passing_exact_bound_preflight(self) -> None:
        with self.assertRaises(LifecycleError):
            authorize_canary(self.fresh(), self.definition, now_monotonic_ns=1)
        failed = self.preflight(self.fresh(), status="FAIL")
        self.assertTrue(failed["stopped"])
        with self.assertRaises(LifecycleError):
            authorize_canary(failed, self.definition, now_monotonic_ns=1)
        with self.assertRaises(LifecycleError):
            record_preflight(
                self.fresh(),
                self.definition,
                status="PASS",
                receipt_sha256=HASHES["preflight"],
                observed_definition_sha256="a" * 64,
                observed_package_sha256=HASHES["package"],
            )

    def test_remaining_cell_requires_exact_hash_accept_audit(self) -> None:
        state = self.accepted_canary()
        with self.assertRaises(LifecycleError):
            authorize_next(state, self.definition, now_monotonic_ns=200)
        wrong = {
            "status": "ACCEPT",
            "definition_sha256": HASHES["definition"],
            "package_sha256": HASHES["package"],
            "canary_result_sha256": "a" * 64,
            "canary_artifact_sha256": HASHES["artifact"],
            "auditor": "auditor",
            "independent_of_candidate_and_controller": True,
            "findings": [],
            "summary": "wrong result",
        }
        with self.assertRaises(LifecycleError):
            record_canary_audit(
                state, self.definition, audit=wrong, audit_sha256=HASHES["audit"]
            )
        rejected = self.accepted_audit(state, status="REJECT")
        self.assertTrue(rejected["stopped"])
        with self.assertRaises(LifecycleError):
            authorize_next(rejected, self.definition, now_monotonic_ns=200)

    def test_audit_requires_independence_and_is_single_use(self) -> None:
        state = self.accepted_canary()
        accepted = self.accepted_audit(state)
        with self.assertRaises(LifecycleError):
            self.accepted_audit(accepted)
        audit = copy.deepcopy(accepted["canary_audit"])
        audit.pop("audit_sha256")
        audit["independent_of_candidate_and_controller"] = False
        with self.assertRaises(LifecycleError):
            record_canary_audit(
                state, self.definition, audit=audit, audit_sha256=HASHES["audit"]
            )
        audit = copy.deepcopy(accepted["canary_audit"])
        audit.pop("audit_sha256")
        audit["findings"] = ["unresolved"]
        with self.assertRaises(LifecycleError):
            record_canary_audit(
                state, self.definition, audit=audit, audit_sha256=HASHES["audit"]
            )


class CellLifecycleTests(LifecycleTestCase):
    def test_classified_active_failures_stop_from_every_stage_and_preserve_evidence(self) -> None:
        statuses = (
            "PROVIDER_UNAVAILABLE",
            "QUOTA_EXHAUSTED",
            "BOUNDARY_FAILURE",
            "TELEMETRY_FAILURE",
            "CONTROLLER_ERROR",
        )
        for status in statuses:
            for stage in ("implementation", "verification", "review"):
                state = self.canary_started()
                if stage in {"verification", "review"}:
                    state = self.implementation_complete(state)
                if stage == "review":
                    state = self.verified(state)
                implementation = copy.deepcopy(state["active_cell"]["implementation"])
                verification = copy.deepcopy(state["active_cell"]["verification"])
                state = record_active_failure(
                    state,
                    self.definition,
                    cell_id="use-grok--terra-high",
                    status=status,
                    result_sha256=HASHES["result"],
                    reason=f"classified {status}",
                    now_monotonic_ns=103,
                )
                terminal = state["terminal_cells"][0]
                with self.subTest(status=status, stage=stage):
                    self.assertEqual(terminal["terminal"]["status"], status)
                    self.assertEqual(state["stop_reason"], status)
                    self.assertEqual(terminal["implementation"], implementation)
                    self.assertEqual(terminal["verification"], verification)
                    self.assertIsNone(terminal["review"])
                    self.assertIsNone(state["active_cell"])
                    self.assertTrue(state["stopped"])
                    with self.assertRaises(LifecycleError):
                        authorize_next(state, self.definition, now_monotonic_ns=104)

    def test_active_failure_rejects_unclassified_and_late_scorable_status(self) -> None:
        state = self.canary_started(now=1_000)
        with self.assertRaises(LifecycleError):
            record_active_failure(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                status="IMPLEMENTATION_FAILED",
                result_sha256=HASHES["result"],
                reason="wrong transition",
                now_monotonic_ns=1_001,
            )
        with self.assertRaises(LifecycleError):
            record_active_failure(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                status="PROVIDER_UNAVAILABLE",
                result_sha256=HASHES["result"],
                reason="at deadline",
                now_monotonic_ns=state["active_cell"]["deadline_monotonic_ns"],
            )

    def test_safe_completed_implementation_cannot_skip_review(self) -> None:
        state = self.verified(self.implementation_complete(self.canary_started()))
        self.assertEqual(state["active_cell"]["stage"], "review")
        with self.assertRaises(LifecycleError):
            authorize_next(state, self.definition, now_monotonic_ns=104)
        with self.assertRaises(LifecycleError):
            record_verification(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                public_passed=True,
                hidden_passed=True,
                scope_safe=True,
                telemetry_safe=True,
                receipt_sha256=HASHES["verification"],
                now_monotonic_ns=104,
            )

    def test_review_is_bound_single_use_and_findings_stop(self) -> None:
        state = self.verified(self.implementation_complete(self.canary_started()))
        with self.assertRaises(LifecycleError):
            record_review(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                status="PASS",
                finding_count=0,
                artifact_sha256="a" * 64,
                review_range_sha256=HASHES["review_range"],
                receipt_sha256=HASHES["review"],
                result_sha256=HASHES["result"],
                now_monotonic_ns=103,
            )
        stopped = record_review(
            state,
            self.definition,
            cell_id="use-grok--terra-high",
            status="PASS",
            finding_count=1,
            artifact_sha256=HASHES["artifact"],
            review_range_sha256=HASHES["review_range"],
            receipt_sha256=HASHES["review"],
            result_sha256=HASHES["result"],
            now_monotonic_ns=103,
        )
        self.assertEqual(stopped["terminal_cells"][0]["terminal"]["status"], "REVIEW_BLOCKED")
        self.assertTrue(stopped["stopped"])
        with self.assertRaises(LifecycleError):
            record_review(
                stopped,
                self.definition,
                cell_id="use-grok--terra-high",
                status="PASS",
                finding_count=0,
                artifact_sha256=HASHES["artifact"],
                review_range_sha256=HASHES["review_range"],
                receipt_sha256=HASHES["review"],
                result_sha256=HASHES["result"],
                now_monotonic_ns=104,
            )

    def test_verifier_failure_still_requires_review_then_stops(self) -> None:
        state = self.verified(
            self.implementation_complete(self.canary_started()), public=False
        )
        self.assertEqual(state["active_cell"]["stage"], "review")
        state = record_review(
            state,
            self.definition,
            cell_id="use-grok--terra-high",
            status="PASS",
            finding_count=0,
            artifact_sha256=HASHES["artifact"],
            review_range_sha256=HASHES["review_range"],
            receipt_sha256=HASHES["review"],
            result_sha256=HASHES["result"],
            now_monotonic_ns=103,
        )
        self.assertEqual(state["stop_reason"], "VERIFICATION_FAILED")

    def test_unsafe_scope_or_telemetry_stops_without_review(self) -> None:
        for scope_safe, telemetry_safe, expected in (
            (False, True, "UNSAFE_SCOPE"),
            (True, False, "UNSAFE_TELEMETRY"),
        ):
            state = self.implementation_complete(self.canary_started())
            state = record_verification(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                public_passed=True,
                hidden_passed=True,
                scope_safe=scope_safe,
                telemetry_safe=telemetry_safe,
                receipt_sha256=HASHES["verification"],
                unsafe_result_sha256=HASHES["result"],
                now_monotonic_ns=102,
            )
            with self.subTest(expected=expected):
                self.assertEqual(state["stop_reason"], expected)
                self.assertIsNone(state["terminal_cells"][0]["review"])
                with self.assertRaises(LifecycleError):
                    record_review(
                        state,
                        self.definition,
                        cell_id="use-grok--terra-high",
                        status="PASS",
                        finding_count=0,
                        artifact_sha256=HASHES["artifact"],
                        review_range_sha256=HASHES["review_range"],
                        receipt_sha256=HASHES["review"],
                        result_sha256=HASHES["result"],
                        now_monotonic_ns=103,
                    )

    def test_implementation_failure_stops_without_retry(self) -> None:
        state = record_implementation_failure(
            self.canary_started(),
            self.definition,
            cell_id="use-grok--terra-high",
            result_sha256=HASHES["result"],
            reason="candidate failed",
            now_monotonic_ns=101,
        )
        self.assertEqual(state["stop_reason"], "IMPLEMENTATION_FAILED")
        with self.assertRaises(LifecycleError):
            authorize_canary(state, self.definition, now_monotonic_ns=102)
        with self.assertRaises(LifecycleError):
            authorize_next(state, self.definition, now_monotonic_ns=102)
        completed = self.implementation_complete(self.canary_started())
        with self.assertRaises(LifecycleError):
            record_implementation_failure(
                completed,
                self.definition,
                cell_id="use-grok--terra-high",
                result_sha256=HASHES["result"],
                reason="not a blocked implementation result",
                now_monotonic_ns=102,
            )

    def test_inclusive_deadline_covers_all_stages(self) -> None:
        start = 1_000
        state = self.canary_started(now=start)
        deadline = state["active_cell"]["deadline_monotonic_ns"]
        state = expire_active_cell(
            state,
            self.definition,
            cell_id="use-grok--terra-high",
            result_sha256=HASHES["result"],
            now_monotonic_ns=deadline,
        )
        self.assertEqual(state["stop_reason"], "TIMEOUT")

        state = self.verified(
            self.implementation_complete(self.canary_started(now=start), now=start + 1),
            now=start + 2,
        )
        deadline = state["active_cell"]["deadline_monotonic_ns"]
        state = record_review(
            state,
            self.definition,
            cell_id="use-grok--terra-high",
            status="PASS",
            finding_count=0,
            artifact_sha256=HASHES["artifact"],
            review_range_sha256=HASHES["review_range"],
            receipt_sha256=HASHES["review"],
            result_sha256=HASHES["result"],
            now_monotonic_ns=deadline,
        )
        self.assertEqual(state["stop_reason"], "TIMEOUT")

    def test_cannot_expire_early_or_record_stage_at_deadline(self) -> None:
        state = self.canary_started(now=1_000)
        deadline = state["active_cell"]["deadline_monotonic_ns"]
        with self.assertRaises(LifecycleError):
            expire_active_cell(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                result_sha256=HASHES["result"],
                now_monotonic_ns=deadline - 1,
            )
        with self.assertRaises(LifecycleError):
            record_implementation_complete(
                state,
                self.definition,
                cell_id="use-grok--terra-high",
                artifact_sha256=HASHES["artifact"],
                receipt_sha256=HASHES["implementation"],
                now_monotonic_ns=deadline,
            )


class PersistenceTests(LifecycleTestCase):
    def test_canonical_round_trip_and_hash_binding(self) -> None:
        state = self.preflight(self.fresh())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_state(path, state, self.definition)
            self.assertEqual(path.read_bytes(), canonical_state_bytes(state))
            loaded = load_state(
                path,
                self.definition,
                expected_definition_sha256=HASHES["definition"],
                expected_package_sha256=HASHES["package"],
            )
            self.assertEqual(loaded, state)
            with self.assertRaises(LifecycleError):
                load_state(
                    path,
                    self.definition,
                    expected_definition_sha256="a" * 64,
                    expected_package_sha256=HASHES["package"],
                )

    def test_rejects_noncanonical_and_tampered_state(self) -> None:
        state = self.preflight(self.fresh())
        validate_state(state, self.definition)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            with self.assertRaises(LifecycleError):
                load_state(
                    path,
                    self.definition,
                    expected_definition_sha256=HASHES["definition"],
                    expected_package_sha256=HASHES["package"],
                )
        tampered = copy.deepcopy(self.accepted_canary())
        tampered["terminal_cells"][0]["attempt"] = 2
        with self.assertRaises(LifecycleError):
            validate_state(tampered, self.definition)

    def test_rejects_fabricated_acceptance_and_missing_preflight(self) -> None:
        accepted = self.accepted_canary()
        fabricated = copy.deepcopy(accepted)
        fabricated["terminal_cells"][0]["review"] = None
        with self.assertRaises(LifecycleError):
            validate_state(fabricated, self.definition)
        missing_preflight = copy.deepcopy(accepted)
        missing_preflight["preflight"] = None
        with self.assertRaises(LifecycleError):
            validate_state(missing_preflight, self.definition)

    def test_rejects_terminal_status_stop_reason_mismatch_and_bad_deadlines(self) -> None:
        failed = record_active_failure(
            self.canary_started(),
            self.definition,
            cell_id="use-grok--terra-high",
            status="PROVIDER_UNAVAILABLE",
            result_sha256=HASHES["result"],
            reason="provider unavailable",
            now_monotonic_ns=101,
        )
        mismatched = copy.deepcopy(failed)
        mismatched["stop_reason"] = "CONTROLLER_ERROR"
        with self.assertRaises(LifecycleError):
            validate_state(mismatched, self.definition)

        late_failure = copy.deepcopy(failed)
        late_failure["terminal_cells"][0]["terminal"]["ended_monotonic_ns"] = (
            late_failure["terminal_cells"][0]["deadline_monotonic_ns"]
        )
        with self.assertRaises(LifecycleError):
            validate_state(late_failure, self.definition)

        timeout = expire_active_cell(
            self.canary_started(now=1_000),
            self.definition,
            cell_id="use-grok--terra-high",
            result_sha256=HASHES["result"],
            now_monotonic_ns=600_000_001_000,
        )
        early_timeout = copy.deepcopy(timeout)
        early_timeout["terminal_cells"][0]["terminal"]["ended_monotonic_ns"] = 1_001
        with self.assertRaises(LifecycleError):
            validate_state(early_timeout, self.definition)


if __name__ == "__main__":
    unittest.main()
