from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import evaluator  # noqa: E402
from evaluator import (  # noqa: E402
    EvaluatorError,
    EvaluatorRunError,
    PROMPT_BUNDLE_BEGIN,
    PROMPT_BUNDLE_END,
    prepare_anonymous_inputs,
    prepare_evaluator_prompt,
    run_grok_evaluator,
    sha256_file,
    validate_evaluator_result,
    validate_prepared_inputs,
)

TEST_SEED = "test-seed"
TEST_SEED_SHA256 = "d63cd08d82aa4eb48e0cc64fb466e909bfc3879664c5caa8d8cdeda73c044190"


def make_bundle() -> dict[str, object]:
    tasks = []
    for task_number in range(1, 4):
        variants = []
        for variant_number in range(1, 3):
            variants.append(
                {
                    "variant": f"variant-{variant_number}",
                    "artifact_sha256": f"{task_number}{variant_number}" * 32,
                    "files_base64": {"answer.txt": "YWNjb3VudGVkIGJ5dGVz\n"},
                }
            )
        tasks.append(
            {
                "task_alias": f"task-{task_number}",
                "task": f"Evaluate locked task {task_number}.",
                "variants": variants,
            }
        )
    return {
        "schema_version": 1,
        "anonymous": True,
        "shuffle_seed_sha256": TEST_SEED_SHA256,
        "tasks": tasks,
    }


def make_mapping() -> dict[str, object]:
    return {
        "schema_version": 1,
        "shuffle_seed": TEST_SEED,
        "seed_sha256": TEST_SEED_SHA256,
        "tasks": {
            f"task-{task_number}": {
                "task_id": f"private-task-{task_number}",
                "variants": {
                    f"variant-{variant_number}": (
                        f"private-cell-{task_number}-{variant_number}"
                    )
                    for variant_number in range(1, 3)
                },
            }
            for task_number in range(1, 4)
        },
    }


def make_result() -> dict[str, object]:
    tasks = []
    for task_number in range(1, 4):
        ranking = []
        for variant_number in range(1, 3):
            ranking.append(
                {
                    "variant": f"variant-{variant_number}",
                    "rank": variant_number,
                    "correctness": 5,
                    "regression_safety": 5,
                    "scope_discipline": 5,
                    "maintainability": 4,
                    "test_quality": 4,
                    "blocking_findings": [],
                    "summary": "Anonymous evidence reviewed.",
                }
            )
        tasks.append(
            {
                "task_alias": f"task-{task_number}",
                "preferred_variant": "variant-1",
                "ranking": ranking,
                "rationale": "Variant one has the strongest locked evidence.",
            }
        )
    return {
        "status": "completed",
        "tasks": tasks,
        "cross_task_observations": ["All variants were compared anonymously."],
        "blocker": None,
    }


FAKE_GROK = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
required = [
    "--prompt-file", "--verbatim", "--cwd", "--always-approve",
    "--model", "grok-4.6", "--output-format", "json",
    "--reasoning-effort", "xhigh", "--json-schema",
    "--no-leader", "--sandbox", "off", "--no-auto-update",
    "--tools", "todo_write", "--deny", "*", "--max-turns", "1",
    "--disable-web-search", "--no-subagents", "--no-plan",
]
for value in required:
    if value not in args:
        print("missing exact argument: " + value, file=sys.stderr)
        raise SystemExit(91)
if any(value in args for value in ("--resume", "--continue", "-c", "-r")):
    raise SystemExit(92)
cwd = Path(args[args.index("--cwd") + 1])
if cwd.resolve() != Path.cwd().resolve():
    raise SystemExit(93)
prompt = Path(args[args.index("--prompt-file") + 1]).read_text()
if "private-task" in prompt or "private-cell" in prompt or "evaluator-mapping" in prompt:
    raise SystemExit(94)
json.loads(args[args.index("--json-schema") + 1])
with Path(os.environ["FAKE_CALLS"]).open("a", encoding="utf-8") as handle:
    handle.write("called\n")
mode = os.environ.get("FAKE_MODE", "success")
if mode == "mutate":
    (cwd / "mutation.txt").write_text("changed", encoding="utf-8")
if mode == "nonzero":
    print("provider failed", file=sys.stderr)
    raise SystemExit(1)
result = json.loads(Path(os.environ["FAKE_RESULT"]).read_text())
if mode == "invalid":
    result["tasks"][0]["preferred_variant"] = "unknown"
stop_reason = "max_tokens" if mode == "incomplete" else "end_turn"
print(json.dumps({
    "text": json.dumps(result, sort_keys=True, separators=(",", ":")),
    "stopReason": stop_reason,
    "sessionId": "fake-session",
    "num_turns": 2 if mode == "multi_turn" else 1,
}, sort_keys=True, separators=(",", ":")))
'''


FAKE_SANDBOX = r'''#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if len(args) < 3 or args[0] != "-f":
    raise SystemExit(81)
if not Path(args[1]).is_file():
    raise SystemExit(82)
command = args[2:]
os.execvpe(command[0], command, os.environ)
'''


class EvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.evidence = self.root / "evidence"
        self.workspace.mkdir()
        self.evidence.mkdir()
        self.schema = ROOT / "schemas" / "evaluator.schema.json"
        self.workspace_schema = self.workspace / "evaluator-schema.json"
        self.fake = self.root / "fake-grok"
        self.fake.write_text(FAKE_GROK, encoding="utf-8")
        self.fake.chmod(0o700)
        self.sandbox = self.root / "fake-sandbox-exec"
        self.sandbox.write_text(FAKE_SANDBOX, encoding="utf-8")
        self.sandbox.chmod(0o700)
        self.sandbox_profile = self.evidence / "evaluator.sb"
        self.sandbox_profile.write_text(
            "(version 1)\n(allow default)\n", encoding="utf-8"
        )
        self.result = self.root / "fake-result.json"
        self.result.write_text(json.dumps(make_result()), encoding="utf-8")
        self.calls = self.root / "calls"
        self.run_directory = self.root / "run"
        self.usage_calls: list[str] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare(self):
        return prepare_anonymous_inputs(
            make_bundle(),
            make_mapping(),
            evaluator_workspace=self.workspace,
            evidence_directory=self.evidence,
        )

    def stage_schema(self) -> None:
        schema = json.loads(self.schema.read_text(encoding="utf-8"))
        self.workspace_schema.write_bytes(evaluator.canonical_bytes(schema))

    def hook(self, label: str):
        def capture():
            self.usage_calls.append(label)
            return {
                "schema_version": 1,
                "observer": "fake-quota-observer",
                "label": label,
            }

        return capture

    @staticmethod
    def fake_process_runner(argv, **kwargs):
        receipt = evaluator._run_blocking_process(argv, **kwargs)
        return {
            **receipt,
            "terminal_process_state": True,
            "broker_usage_observed": False,
            "launch_observation_complete": True,
        }

    def execute(
        self,
        prepared,
        *,
        mode: str = "success",
        grok_model: str = "grok-4.6",
        sandbox_preflight: dict[str, object] | None = None,
        process_runner=None,
    ):
        if not self.workspace_schema.exists():
            self.stage_schema()
        prompt_path = self.workspace / "evaluator-prompt.txt"
        if not prompt_path.exists():
            prepare_evaluator_prompt(prepared, self.workspace)
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "FAKE_CALLS": str(self.calls),
            "FAKE_RESULT": str(self.result),
            "FAKE_MODE": mode,
        }
        return run_grok_evaluator(
            prepared=prepared,
            evaluator_workspace=self.workspace,
            run_directory=self.run_directory,
            schema_path=self.workspace_schema,
            grok_executable=self.fake,
            sandbox_executable=self.sandbox,
            sandbox_profile_path=self.sandbox_profile,
            grok_model=grok_model,
            grok_identity_evidence={"version": "fake-grok 1.0.5"},
            environment=environment,
            environment_evidence={"auth": "test-only", "keys": sorted(environment)},
            sandbox_preflight_evidence=sandbox_preflight
            or {
                "schema_version": 1,
                "status": "PASS",
                "no_model_calls": True,
                "production_profile_sha256": sha256_file(self.sandbox_profile),
            },
            before_usage=self.hook("before"),
            after_usage=self.hook("after"),
            deadline_monotonic=time.monotonic() + 10,
            process_runner=process_runner or self.fake_process_runner,
        )

    def test_prepares_mutually_bound_pair_outside_workspace(self) -> None:
        prepared = self.prepare()
        binding = validate_prepared_inputs(prepared, self.workspace)
        bundle = json.loads(prepared.bundle_path.read_text())
        mapping = json.loads(prepared.mapping_path.read_text())
        self.assertEqual(bundle["binding"], mapping["binding"])
        self.assertEqual(binding["pair_id"], prepared.pair_id)
        self.assertEqual(sha256_file(prepared.bundle_path), prepared.bundle_sha256)
        self.assertNotIn("private-task-1", prepared.bundle_path.read_text())
        self.assertFalse(prepared.mapping_path.is_relative_to(self.workspace))
        with self.assertRaises(EvaluatorError):
            prepare_anonymous_inputs(
                make_bundle(),
                make_mapping(),
                evaluator_workspace=self.workspace,
                evidence_directory=self.evidence,
            )

    def test_rejects_mapping_destination_inside_workspace(self) -> None:
        with self.assertRaises(EvaluatorError):
            prepare_anonymous_inputs(
                make_bundle(),
                make_mapping(),
                evaluator_workspace=self.workspace,
                evidence_directory=self.workspace,
            )

    def test_rejects_tampered_pair_before_any_evaluator_call(self) -> None:
        prepared = self.prepare()
        prepared.mapping_path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(EvaluatorError):
            self.execute(prepared)
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.usage_calls, [])

    def test_one_blocking_xhigh_call_retains_and_binds_all_evidence(self) -> None:
        prepared = self.prepare()
        outcome = self.execute(prepared)
        self.assertEqual(self.calls.read_text(), "called\n")
        self.assertEqual(self.usage_calls, ["before", "after"])
        self.assertEqual(outcome.run_receipt["invocation_count"], 1)
        self.assertEqual(
            outcome.run_receipt["usage_classification"],
            {"category": "experiment_overhead", "scored": False},
        )
        argv = outcome.run_receipt["process"]["argv"]
        self.assertEqual(
            argv[:4],
            [
                str(self.sandbox.resolve()),
                "-f",
                str(self.sandbox_profile.resolve()),
                str(self.fake.resolve()),
            ],
        )
        self.assertEqual(argv.count("--prompt-file"), 1)
        self.assertEqual(argv[argv.index("--reasoning-effort") + 1], "xhigh")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "off")
        self.assertEqual(argv[argv.index("--tools") + 1], "todo_write")
        self.assertEqual(argv[argv.index("--deny") + 1], "*")
        self.assertEqual(argv[argv.index("--max-turns") + 1], "1")
        for option in ("--sandbox", "--tools", "--deny", "--max-turns"):
            self.assertEqual(argv.count(option), 1)
        for flag in (
            "--no-leader",
            "--no-auto-update",
            "--disable-web-search",
            "--no-subagents",
            "--no-plan",
        ):
            self.assertEqual(argv.count(flag), 1)
        self.assertNotIn("--resume", argv)
        self.assertNotIn(str(prepared.mapping_path), argv)
        self.assertEqual(
            sha256_file(outcome.run_receipt_path), outcome.run_receipt_sha256
        )
        self.assertEqual(sha256_file(outcome.result_path), outcome.result_sha256)
        self.assertEqual(
            sha256_file(self.root / "run" / "stdout.raw"),
            outcome.run_receipt["raw_evidence"]["stdout_sha256"],
        )
        prompt = (self.workspace / "evaluator-prompt.txt").read_bytes()
        bundle = prepared.bundle_path.read_bytes()
        embedded_start = prompt.index(PROMPT_BUNDLE_BEGIN) + len(PROMPT_BUNDLE_BEGIN)
        embedded_end = embedded_start + len(bundle)
        self.assertEqual(prompt[embedded_start:embedded_end], bundle)
        self.assertEqual(
            prompt[embedded_end : embedded_end + len(PROMPT_BUNDLE_END)],
            PROMPT_BUNDLE_END,
        )
        self.assertIn(prepared.bundle_sha256.encode("ascii"), prompt)
        self.assertNotIn(b"private-task", prompt)
        self.assertNotIn(b"evaluator-mapping", prompt)
        inputs = outcome.run_receipt["inputs"]
        self.assertEqual(inputs["bundle_sha256"], prepared.bundle_sha256)
        self.assertEqual(
            inputs["prompt_sha256"],
            sha256_file(self.workspace / "evaluator-prompt.txt"),
        )
        self.assertEqual(
            inputs["sandbox_profile_sha256"], sha256_file(self.sandbox_profile)
        )
        self.assertEqual(
            inputs["sandbox_profile_after_sha256"],
            inputs["sandbox_profile_sha256"],
        )
        self.assertEqual(
            inputs["sandbox_preflight_evidence"]["production_profile_sha256"],
            inputs["sandbox_profile_sha256"],
        )
        self.assertEqual(inputs["prompt_bytes"], len(prompt))
        self.assertLessEqual(inputs["prompt_bytes"], inputs["prompt_max_bytes"])

    def test_prompt_preflight_is_exclusive_and_size_bounded(self) -> None:
        prepared = self.prepare()
        self.stage_schema()
        with mock.patch.object(evaluator, "MAX_EVALUATOR_PROMPT_BYTES", 1):
            with self.assertRaisesRegex(EvaluatorError, "exceeds the fixed"):
                prepare_evaluator_prompt(prepared, self.workspace)
        self.assertFalse((self.workspace / "evaluator-prompt.txt").exists())
        prompt_path, prompt_hash = prepare_evaluator_prompt(prepared, self.workspace)
        self.assertEqual(prompt_hash, sha256_file(prompt_path))
        self.assertEqual(prepared.bundle_sha256, sha256_file(prepared.bundle_path))
        with self.assertRaises(EvaluatorError):
            prepare_evaluator_prompt(prepared, self.workspace)

    def test_tampered_prompt_is_rejected_before_usage_or_process(self) -> None:
        prepared = self.prepare()
        self.stage_schema()
        prompt_path, _ = prepare_evaluator_prompt(prepared, self.workspace)
        prompt_path.write_bytes(prompt_path.read_bytes() + b"tampered\n")
        with self.assertRaisesRegex(EvaluatorError, "exact locked bundle"):
            self.execute(prepared)
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.usage_calls, [])

    def test_failed_or_stale_sandbox_preflight_blocks_before_usage(self) -> None:
        for index, preflight in enumerate(
            (
                {
                    "status": "FAIL",
                    "no_model_calls": True,
                    "production_profile_sha256": sha256_file(self.sandbox_profile),
                },
                {
                    "status": "PASS",
                    "no_model_calls": True,
                    "production_profile_sha256": "0" * 64,
                },
            )
        ):
            with self.subTest(index=index):
                if index:
                    self.workspace = self.root / f"preflight-workspace-{index}"
                    self.evidence = self.root / f"preflight-evidence-{index}"
                    self.workspace.mkdir()
                    self.evidence.mkdir()
                    self.workspace_schema = self.workspace / "evaluator-schema.json"
                prepared = self.prepare()
                with self.assertRaisesRegex(EvaluatorError, "production profile"):
                    self.execute(prepared, sandbox_preflight=preflight)
                self.assertFalse(self.calls.exists())
                self.assertEqual(self.usage_calls, [])

    def test_wrong_model_blocks_before_usage_or_process(self) -> None:
        prepared = self.prepare()
        with self.assertRaisesRegex(EvaluatorError, "exactly grok-4.6"):
            self.execute(prepared, grok_model="grok-other")
        self.assertFalse(self.calls.exists())
        self.assertEqual(self.usage_calls, [])

    def test_missing_process_boundary_fields_fail_closed(self) -> None:
        prepared = self.prepare()

        def incomplete_runner(argv, **kwargs):
            return evaluator._run_blocking_process(argv, **kwargs)

        with self.assertRaises(EvaluatorRunError) as raised:
            self.execute(prepared, process_runner=incomplete_runner)
        self.assertEqual(raised.exception.receipt["status"], "BOUNDARY_FAILURE")
        self.assertEqual(self.calls.read_text(), "called\n")

    def test_invalid_result_is_not_retried_and_keeps_failure_receipt(self) -> None:
        prepared = self.prepare()
        with self.assertRaises(EvaluatorRunError) as raised:
            self.execute(prepared, mode="invalid")
        self.assertEqual(self.calls.read_text(), "called\n")
        self.assertEqual(self.usage_calls, ["before", "after"])
        self.assertEqual(raised.exception.receipt["status"], "INVALID_RESULT")
        self.assertEqual(raised.exception.receipt["invocation_count"], 1)
        self.assertTrue((self.root / "run" / "stdout.raw").is_file())
        self.assertTrue((self.root / "run" / "run-receipt.json").is_file())
        self.assertFalse((self.root / "run" / "result.json").exists())

    def test_incomplete_and_workspace_mutation_never_trigger_second_call(self) -> None:
        for index, (mode, status) in enumerate(
            (
                ("incomplete", "INVALID_RESULT"),
                ("multi_turn", "INVALID_RESULT"),
                ("mutate", "WORKSPACE_MUTATED"),
            )
        ):
            with self.subTest(mode=mode):
                if index:
                    self.workspace = self.root / f"workspace-{index}"
                    self.evidence = self.root / f"evidence-{index}"
                    self.workspace.mkdir()
                    self.evidence.mkdir()
                    self.workspace_schema = self.workspace / "evaluator-schema.json"
                    self.calls = self.root / f"calls-{index}"
                    self.run_directory = self.root / f"run-{index}"
                    self.usage_calls = []
                prepared = self.prepare()
                with self.assertRaises(EvaluatorRunError) as raised:
                    self.execute(prepared, mode=mode)
                self.assertEqual(self.calls.read_text(), "called\n")
                self.assertEqual(raised.exception.receipt["status"], status)

    def test_semantic_validation_rejects_duplicate_ranks(self) -> None:
        result = make_result()
        result["tasks"][0]["ranking"][1]["rank"] = 1
        schema = json.loads(self.schema.read_text())
        aliases = {f"task-{number}": ["variant-1", "variant-2"] for number in range(1, 4)}
        with self.assertRaises(EvaluatorError):
            validate_evaluator_result(result, schema=schema, public_aliases=aliases)


if __name__ == "__main__":
    unittest.main()
