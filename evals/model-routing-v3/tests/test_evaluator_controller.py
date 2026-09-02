from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import controller  # noqa: E402
import evaluator  # noqa: E402


FIXED_SEED = "ab" * 32


def _score(variant: str, rank: int) -> dict[str, object]:
    return {
        "variant": variant,
        "rank": rank,
        "correctness": 5,
        "regression_safety": 5,
        "scope_discipline": 5,
        "maintainability": 5,
        "test_quality": 5,
        "blocking_findings": [],
        "summary": "The immutable anonymous artifact is complete.",
    }


def _result_for_bundle(bundle: dict[str, object]) -> dict[str, object]:
    tasks = []
    for task in bundle["tasks"]:
        variants = [item["variant"] for item in task["variants"]]
        tasks.append(
            {
                "task_alias": task["task_alias"],
                "preferred_variant": variants[0],
                "ranking": [
                    _score(variant, rank)
                    for rank, variant in enumerate(variants, 1)
                ],
                "rationale": "The first locked variant has the strongest evidence.",
            }
        )
    return {
        "status": "completed",
        "tasks": tasks,
        "cross_task_observations": ["All locked variants were compared once."],
        "blocker": None,
    }


class EvaluatorControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temporary.name)
        self.source = self.test_root / "source"
        self.source.mkdir()
        self.executables: dict[str, Path] = {}
        for name in ("codex", "launcher", "node", "auth", "codexbar"):
            path = self.test_root / name
            path.write_bytes(name.encode("utf-8"))
            path.chmod(0o700)
            self.executables[name] = path
        self.grok = self.test_root / "grok-1.0.13"
        self.grok.write_bytes(b"test-only pinned grok executable\n")
        self.grok.chmod(0o700)
        self.grok_auth_source = self.test_root / "grok-auth.json"
        self.grok_auth_source.write_text(
            json.dumps(
                {
                    "test-account": {
                        "expires_at": "2000-01-01T00:00:00Z",
                        "refresh_token": "test-only-refresh-credential",
                    }
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        self.grok_auth_source.chmod(0o600)
        config = controller.ControllerConfig(
            state_root=self.test_root / "state",
            use_grok_repo=self.source,
            karpathy_repo=self.source,
            openbot_repo=self.source,
            openbot_runtime_source=self.source,
            codex_executable=self.executables["codex"],
            codex_launcher=self.executables["launcher"],
            node_executable=self.executables["node"],
            auth_source=self.executables["auth"],
            codexbar_executable=self.executables["codexbar"],
            memory_root=self.test_root / "memory",
        )
        self.value = controller.Controller(config)
        self.value.root.mkdir(parents=True)
        pinned = self.value.definition["pinned_runtime"]
        pinned["grok_executable"] = str(self.grok)
        pinned["grok_executable_sha256"] = controller.sha256_file(self.grok)
        pinned["grok_cli_version"] = "grok 1.0.13 (test)"
        pinned["grok_isolated_cli_version"] = "grok 1.0.13 (test isolated)"
        self.state = self._write_accepted_evidence()
        self.commands: list[list[str]] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_accepted_evidence(self) -> dict[str, object]:
        terminal_cells = []
        collection_results = []
        run_order = list(self.value.definition["lifecycle"]["run_order"])
        for ordinal, cell_id in enumerate(run_order):
            task_id = self.value.definition["cells"][cell_id]["task"]
            relative = self.value.definition["tasks"][task_id]["allowed_paths"][0]
            attempt = self.value.root / "attempts" / cell_id
            snapshot = attempt / "artifact-snapshot"
            snapshot_file = snapshot / relative
            snapshot_file.parent.mkdir(parents=True)
            snapshot_bytes = f"immutable snapshot for {cell_id}\n".encode("utf-8")
            snapshot_file.write_bytes(snapshot_bytes)
            candidate_file = attempt / "candidate" / relative
            candidate_file.parent.mkdir(parents=True)
            candidate_file.write_text(
                f"mutable candidate decoy for {cell_id}\n", encoding="utf-8"
            )
            snapshot_manifest = controller.strict_tree_manifest(snapshot)
            artifact = {
                "schema_version": 1,
                "scope": {"changed_file_paths": [relative]},
                "snapshot_manifest_sha256": snapshot_manifest["sha256"],
            }
            artifact_path = attempt / "artifact.json"
            artifact_hash = controller._exclusive_json(artifact_path, artifact)
            result = {
                "schema_version": 1,
                "cell_id": cell_id,
                "artifact": artifact,
                "artifact_sha256": artifact_hash,
                "artifact_snapshot_manifest_sha256": snapshot_manifest["sha256"],
            }
            result_hash = controller._exclusive_json(attempt / "result.json", result)
            terminal_cells.append(
                {
                    "cell_id": cell_id,
                    "ordinal": ordinal,
                    "implementation": {"artifact_sha256": artifact_hash},
                    "terminal": {
                        "status": "ACCEPTED",
                        "result_sha256": result_hash,
                    },
                }
            )
            collection_results.append(result)

        state = {
            "schema_version": 1,
            "run_order": run_order,
            "terminal_cells": terminal_cells,
        }
        controller._exclusive_json(self.value.state_path, state)
        collection = {
            "schema_version": 1,
            "definition_sha256": self.value.definition_sha256,
            "package_sha256": self.value.package_sha256,
            "state_sha256": controller.sha256_file(self.value.state_path),
            "results": collection_results,
        }
        controller._exclusive_json(self.value.root / "collection.json", collection)
        return state

    def _fake_process_runner(self, argv, **kwargs):
        command = list(argv)
        self.commands.append(command)
        bundle = json.loads(
            (Path(kwargs["cwd"]) / "evaluator-bundle.json").read_text(
                encoding="utf-8"
            )
        )
        result = _result_for_bundle(bundle)
        envelope = {
            "text": json.dumps(result, sort_keys=True, separators=(",", ":")),
            "stopReason": "end_turn",
            "sessionId": "provider-free-test-session",
            "num_turns": 1,
        }
        kwargs["stdout_path"].write_text(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        kwargs["stderr_path"].write_bytes(b"")
        return {
            "argv": command,
            "returncode": 0,
            "timed_out": False,
            "survivor_pids": [],
            "terminal_process_state": True,
            "broker_usage_observed": False,
            "launch_observation_complete": True,
        }

    def _run_evaluator(
        self,
        *,
        runner=None,
        preflight_failure: BaseException | None = None,
        post_run_mutation=None,
    ) -> dict[str, object]:
        version = SimpleNamespace(
            returncode=0,
            stdout=(
                self.value.definition["pinned_runtime"]["grok_isolated_cli_version"]
                + "\n"
            ),
            stderr="",
        )
        process_runner = runner or self._fake_process_runner
        original_run_grok_evaluator = evaluator.run_grok_evaluator

        def run_and_maybe_mutate(**kwargs):
            outcome = original_run_grok_evaluator(**kwargs)
            if post_run_mutation is not None:
                post_run_mutation(Path(kwargs["run_directory"]), outcome)
            return outcome

        def fake_preflight(**kwargs):
            private = Path(kwargs["private"])
            if preflight_failure is not None:
                for name in ("evaluator-probe", "evaluator.sb", "evaluator-probe.sb"):
                    (private / name).write_bytes(b"partial preflight evidence\n")
                processes = private / "preflight-processes"
                processes.mkdir()
                (processes / "partial.raw").write_bytes(b"partial\n")
                controller._exclusive_json(
                    private / "evaluator-preflight.json",
                    {"schema_version": 1, "status": "PARTIAL"},
                )
                raise preflight_failure
            profile_path = private / "evaluator-production.sb"
            profile_bytes = b"(version 1)(deny default)\n"
            profile_path.write_bytes(profile_bytes)
            profile_hash = controller.sha256_bytes(profile_bytes)
            receipt = {
                "schema_version": 1,
                "status": "PASS",
                "no_model_calls": True,
                "production_profile_sha256": profile_hash,
                "sandboxed_grok_version": {
                    "value": self.value.definition["pinned_runtime"][
                        "grok_isolated_cli_version"
                    ]
                },
            }
            receipt_hash = controller._exclusive_json(
                private / "evaluator-preflight.json", receipt
            )
            return receipt, receipt_hash, profile_path, profile_hash, "f" * 64

        with (
            mock.patch.object(self.value, "_assert_pins"),
            mock.patch.object(self.value, "_require_package_review"),
            mock.patch.object(
                self.value, "_load_state", return_value=copy.deepcopy(self.state)
            ),
            mock.patch.object(controller.subprocess, "run", return_value=version),
            mock.patch.object(
                controller.execution, "run_bounded_process", side_effect=process_runner
            ),
            mock.patch.object(
                controller.evaluator,
                "run_grok_evaluator",
                side_effect=run_and_maybe_mutate,
            ),
            mock.patch.object(
                self.value, "_evaluator_preflight", side_effect=fake_preflight
            ),
            mock.patch.object(
                controller,
                "strict_package_sha256",
                return_value=self.value.package_sha256,
            ),
            mock.patch.object(controller.secrets, "token_hex", return_value=FIXED_SEED),
        ):
            return self.value.run_evaluator(self.grok, self.grok_auth_source)

    def _auth_leaking_runner(self, mode: str):
        def runner(argv, **kwargs):
            receipt = self._fake_process_runner(argv, **kwargs)
            auth_path = Path(kwargs["environment"]["GROK_HOME"]) / "auth.json"
            auth_document = json.loads(auth_path.read_text(encoding="utf-8"))
            secret = auth_document["test-account"]["refresh_token"].encode("utf-8")
            if mode == "success":
                envelope = json.loads(kwargs["stdout_path"].read_text(encoding="utf-8"))
                result = json.loads(envelope["text"])
                result["cross_task_observations"] = [secret.decode("utf-8")]
                envelope["text"] = json.dumps(
                    result, sort_keys=True, separators=(",", ":")
                )
                kwargs["stdout_path"].write_text(
                    json.dumps(envelope, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )
            elif mode == "process_failure":
                kwargs["stderr_path"].write_bytes(secret)
                receipt["returncode"] = 1
            elif mode == "invalid_result":
                kwargs["stdout_path"].write_bytes(secret)
            elif mode == "timeout":
                kwargs["stderr_path"].write_bytes(secret)
                receipt["returncode"] = -9
                receipt["timed_out"] = True
            else:
                raise AssertionError(f"unsupported leak mode: {mode}")
            return receipt

        return runner

    def _assert_evaluator_auth_leak_is_deleted(self, mode: str) -> None:
        with self.assertRaises(controller.BoundaryFailure) as raised:
            self._run_evaluator(runner=self._auth_leaking_runner(mode))

        self.assertNotIn("test-only-refresh-credential", str(raised.exception))
        evaluator_root = self.value.root / "evaluator"
        self.assertFalse((evaluator_root / "run").exists())
        self.assertFalse(
            (evaluator_root / "private" / "controller-result.json").exists()
        )
        for path in evaluator_root.rglob("*"):
            if path.is_file():
                self.assertNotIn(
                    b"test-only-refresh-credential", path.read_bytes()
                )
        self.assertEqual(len(self.commands), 1)
        private = evaluator_root / "private"
        cleanup = json.loads((private / "auth-cleanup.json").read_text())
        self.assertEqual(cleanup["run_evidence_auth_material_scan"], "FAIL")
        self.assertIsNone(cleanup["run_evidence_retention_sha256"])
        self.assertTrue(cleanup["rejected_run_absent"])
        self.assertFalse((private / "evaluator-run-retention.json").exists())
        for name in ("home", "tmp", "runtime"):
            self.assertFalse((private / name).exists())

    def test_success_output_with_grok_auth_material_deletes_all_run_evidence(self) -> None:
        self._assert_evaluator_auth_leak_is_deleted("success")

    def test_process_failure_with_grok_auth_material_deletes_all_run_evidence(self) -> None:
        self._assert_evaluator_auth_leak_is_deleted("process_failure")

    def test_invalid_result_with_grok_auth_material_deletes_all_run_evidence(self) -> None:
        self._assert_evaluator_auth_leak_is_deleted("invalid_result")

    def test_timeout_with_grok_auth_material_deletes_all_run_evidence(self) -> None:
        self._assert_evaluator_auth_leak_is_deleted("timeout")

    def test_preflight_failure_removes_runtime_and_unbound_probe_outputs(self) -> None:
        with self.assertRaisesRegex(
            controller.ControllerError, "injected evaluator preflight failure"
        ):
            self._run_evaluator(
                preflight_failure=controller.ControllerError(
                    "injected evaluator preflight failure"
                )
            )

        private = self.value.root / "evaluator" / "private"
        for name in (
            "home",
            "tmp",
            "runtime",
            "evaluator-probe",
            "evaluator.sb",
            "evaluator-probe.sb",
            "preflight-processes",
            "evaluator-preflight.json",
        ):
            self.assertFalse((private / name).exists())
        self.assertTrue((private / "evaluator-mapping.json").is_file())
        self.assertTrue((private / "evaluator-preparation.json").is_file())

    def test_success_with_missing_run_artifact_fails_closed(self) -> None:
        def remove_usage(run_root: Path, _outcome) -> None:
            (run_root / "after-usage.json").unlink()

        with self.assertRaisesRegex(
            controller.BoundaryFailure, "evidence admission"
        ):
            self._run_evaluator(post_run_mutation=remove_usage)

        evaluator_root = self.value.root / "evaluator"
        self.assertFalse((evaluator_root / "run").exists())
        private = evaluator_root / "private"
        cleanup = json.loads((private / "auth-cleanup.json").read_text())
        self.assertEqual(cleanup["run_evidence_auth_material_scan"], "FAIL")
        self.assertTrue(cleanup["rejected_run_absent"])
        self.assertFalse((private / "controller-result.json").exists())

    def test_success_with_clean_but_changed_run_artifact_fails_closed(self) -> None:
        def replace_stdout(run_root: Path, _outcome) -> None:
            (run_root / "stdout.raw").write_bytes(b"clean but changed output\n")

        with self.assertRaisesRegex(
            controller.BoundaryFailure, "evidence admission"
        ):
            self._run_evaluator(post_run_mutation=replace_stdout)

        evaluator_root = self.value.root / "evaluator"
        self.assertFalse((evaluator_root / "run").exists())
        private = evaluator_root / "private"
        cleanup = json.loads((private / "auth-cleanup.json").read_text())
        self.assertEqual(cleanup["run_evidence_auth_material_scan"], "FAIL")
        self.assertTrue(cleanup["rejected_run_absent"])
        self.assertFalse((private / "controller-result.json").exists())

    def test_payloads_bind_seed_pair_and_read_only_the_immutable_snapshot(self) -> None:
        bundle, mapping, snapshot_bindings = self.value._evaluator_payloads(
            self.state, FIXED_SEED
        )
        seed_hash = controller.sha256_bytes(FIXED_SEED.encode("utf-8"))
        self.assertEqual(bundle["shuffle_seed_sha256"], seed_hash)
        self.assertEqual(mapping["shuffle_seed"], FIXED_SEED)
        self.assertEqual(mapping["seed_sha256"], seed_hash)
        self.assertEqual(set(snapshot_bindings), set(self.state["run_order"]))

        for task in bundle["tasks"]:
            private_task = mapping["tasks"][task["task_alias"]]
            for variant in task["variants"]:
                cell_id = private_task["variants"][variant["variant"]]
                relative, encoded = next(iter(variant["files_base64"].items()))
                snapshot_bytes = (
                    self.value.root
                    / "attempts"
                    / cell_id
                    / "artifact-snapshot"
                    / relative
                ).read_bytes()
                candidate_bytes = (
                    self.value.root / "attempts" / cell_id / "candidate" / relative
                ).read_bytes()
                self.assertEqual(base64.b64decode(encoded), snapshot_bytes)
                self.assertNotEqual(base64.b64decode(encoded), candidate_bytes)

        workspace = self.test_root / "pair-workspace"
        private = self.test_root / "pair-private"
        workspace.mkdir()
        private.mkdir()
        prepared = evaluator.prepare_anonymous_inputs(
            bundle,
            mapping,
            evaluator_workspace=workspace,
            evidence_directory=private,
        )
        binding = evaluator.validate_prepared_inputs(prepared, workspace)
        public_document = json.loads(prepared.bundle_path.read_text())
        private_document = json.loads(prepared.mapping_path.read_text())
        self.assertEqual(public_document["binding"], private_document["binding"])
        self.assertEqual(binding["pair_id"], public_document["binding"]["pair_id"])
        self.assertEqual(
            public_document["binding"]["bundle_payload_sha256"],
            evaluator.sha256_bytes(evaluator.canonical_bytes(bundle)),
        )
        self.assertEqual(
            public_document["binding"]["mapping_payload_sha256"],
            evaluator.sha256_bytes(evaluator.canonical_bytes(mapping)),
        )

    def test_requires_an_exact_completed_collection(self) -> None:
        rejected = copy.deepcopy(self.state)
        rejected["terminal_cells"][-1]["terminal"]["status"] = "REVIEW_BLOCKED"
        with self.assertRaisesRegex(
            controller.ControllerError, "collection does not bind"
        ):
            self.value._evaluator_payloads(rejected, FIXED_SEED)

        collection_path = self.value.root / "collection.json"
        collection = json.loads(collection_path.read_text())
        collection["state_sha256"] = "0" * 64
        controller._atomic_json(collection_path, collection)
        with self.assertRaisesRegex(
            controller.ControllerError, "collection does not bind"
        ):
            self.value._evaluator_payloads(self.state, FIXED_SEED)

    def test_one_shot_controller_uses_exact_pinned_grok_model_and_xhigh_command(self) -> None:
        version = SimpleNamespace(
            returncode=0,
            stdout=self.value.definition["pinned_runtime"]["grok_cli_version"] + "\n",
            stderr="",
        )
        with mock.patch.object(controller.subprocess, "run", return_value=version):
            resolved, identity = self.value._assert_grok_pin(self.grok)
        self.assertEqual(resolved, self.grok.resolve())
        self.assertEqual(identity["sha256"], controller.sha256_file(self.grok))

        result = self._run_evaluator()
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(len(self.commands), 1)
        argv = self.commands[0]
        self.assertEqual(argv[0], "/usr/bin/sandbox-exec")
        self.assertEqual(argv[1], "-f")
        self.assertEqual(argv[3], str(self.grok.resolve()))
        self.assertEqual(argv.count("--model"), 1)
        self.assertEqual(argv[argv.index("--model") + 1], "grok-4.6")
        self.assertEqual(argv.count("--reasoning-effort"), 1)
        self.assertEqual(argv[argv.index("--reasoning-effort") + 1], "xhigh")
        self.assertNotIn("--resume", argv)
        self.assertNotIn("--continue", argv)

        private = self.value.root / "evaluator" / "private"
        run_receipt = json.loads(
            (self.value.root / "evaluator" / "run" / "run-receipt.json").read_text()
        )
        self.assertEqual(run_receipt["invocation_count"], 1)
        self.assertEqual(
            run_receipt["usage_classification"],
            {"category": "experiment_overhead", "scored": False},
        )
        self.assertEqual(
            result["usage_classification"],
            {"category": "experiment_overhead", "scored": False},
        )
        for boundary in ("before", "after"):
            usage = run_receipt["usage_evidence"][boundary]
            self.assertEqual(usage["status"], "UNAVAILABLE")
            self.assertEqual(usage["observer"], "grok-cli-1.0.13")
        reservation = json.loads(
            (private / "evaluator-reservation.json").read_text()
        )
        self.assertEqual(
            reservation["grok_identity"]["sha256"], controller.sha256_file(self.grok)
        )
        self.assertEqual(
            reservation["grok_identity"]["observed_isolated_version"],
            "grok 1.0.13 (test isolated)",
        )
        self.assertEqual(
            reservation["auth"]["admission_category"], "refresh_capable"
        )
        retention_path = private / "evaluator-run-retention.json"
        retention = json.loads(retention_path.read_text())
        retention_sha256 = controller.sha256_file(retention_path)
        self.assertEqual(retention["status"], "PASS")
        self.assertEqual(retention["auth_material_scan"], "PASS")
        self.assertEqual(
            {artifact["path"] for artifact in retention["files"]},
            {f"run/{name}" for name in controller.EVALUATOR_RUN_EVIDENCE_NAMES},
        )
        for artifact in retention["files"]:
            retained_path = self.value.root / "evaluator" / artifact["path"]
            self.assertEqual(artifact["bytes"], retained_path.stat().st_size)
            self.assertEqual(
                artifact["sha256"], controller.sha256_file(retained_path)
            )
        cleanup = json.loads((private / "auth-cleanup.json").read_text())
        self.assertEqual(cleanup["run_evidence_auth_material_scan"], "PASS")
        self.assertIsNone(cleanup["rejected_run_absent"])
        self.assertEqual(
            cleanup["run_evidence_retention_sha256"], retention_sha256
        )
        self.assertEqual(cleanup["run_artifacts"], retention["files"])
        self.assertEqual(
            result["evaluator_run_retention_sha256"], retention_sha256
        )
        self.assertFalse((private / "home").exists())

        with self.assertRaisesRegex(
            controller.ControllerError, "one-shot evaluator lifecycle already exists"
        ):
            self._run_evaluator()
        self.assertEqual(len(self.commands), 1)

    def test_existing_lifecycle_blocks_overwrite_before_any_process_call(self) -> None:
        evaluator_root = self.value.root / "evaluator"
        evaluator_root.mkdir()
        (evaluator_root / "sentinel").write_text("preserve\n", encoding="utf-8")
        with self.assertRaisesRegex(
            controller.ControllerError, "one-shot evaluator lifecycle already exists"
        ):
            self._run_evaluator()
        self.assertEqual(self.commands, [])
        self.assertEqual((evaluator_root / "sentinel").read_text(), "preserve\n")

    def test_post_call_snapshot_drift_is_a_typed_boundary_failure(self) -> None:
        cell_id = self.state["run_order"][0]
        snapshot = self.value.root / "attempts" / cell_id / "artifact-snapshot"

        def mutate_after_review(argv, **kwargs):
            receipt = self._fake_process_runner(argv, **kwargs)
            relative = self.value.definition["tasks"]["use-grok"]["allowed_paths"][0]
            (snapshot / relative).write_text("drift after anonymous review\n")
            return receipt

        with self.assertRaisesRegex(
            controller.BoundaryFailure,
            "accepted artifact changed during Grok evaluation",
        ):
            self._run_evaluator(runner=mutate_after_review)
        self.assertEqual(len(self.commands), 1)
        self.assertFalse(
            (
                self.value.root
                / "evaluator"
                / "private"
                / "controller-result.json"
            ).exists()
        )

    def test_auth_copy_interruption_still_removes_fresh_auth_roots(self) -> None:
        original_copy = controller._copy_evaluator_auth

        def copy_then_interrupt(*args, **kwargs):
            original_copy(*args, **kwargs)
            raise KeyboardInterrupt("injected interruption after auth copy")

        with (
            mock.patch.object(
                controller, "_copy_evaluator_auth", side_effect=copy_then_interrupt
            ),
            self.assertRaisesRegex(KeyboardInterrupt, "injected interruption"),
        ):
            self._run_evaluator()

        private = self.value.root / "evaluator" / "private"
        self.assertFalse((private / "home").exists())
        self.assertFalse((private / "tmp").exists())
        self.assertFalse((private / "runtime").exists())
        cleanup = json.loads((private / "auth-cleanup.json").read_text())
        self.assertFalse(cleanup["source_stable"])
        self.assertTrue(cleanup["auth_destination_absent"])

    def test_exact_grok_pin_rejects_another_executable(self) -> None:
        other = self.test_root / "another-grok"
        other.write_bytes(self.grok.read_bytes())
        other.chmod(0o700)
        with self.assertRaisesRegex(
            controller.ControllerError, "exact path and byte pin"
        ):
            self.value._assert_grok_pin(other)


class EvaluatorBoundaryHelpersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.executable = self.root / "grok"
        self.executable.write_bytes(b"test executable\n")
        self.executable.chmod(0o700)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _auth_source(self, document: dict[str, object]) -> Path:
        source = self.root / "auth-source.json"
        source.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        source.chmod(0o600)
        return source

    def test_auth_copy_accepts_refresh_capability_and_rechecks_source(self) -> None:
        source = self._auth_source(
            {
                "account": {
                    "expires_at": "2000-01-01T00:00:00Z",
                    "refresh_token": "test-refresh",
                }
            }
        )
        destination_root = self.root / "isolated-home"
        destination_root.mkdir(mode=0o700)
        destination = destination_root / "auth.json"
        digest, identity, admission, markers = controller._copy_evaluator_auth(
            source, destination, minimum_valid_seconds=3600
        )
        self.assertEqual(admission, "refresh_capable")
        self.assertIn(b"test-refresh", markers)
        self.assertIn(source.read_bytes(), markers)
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        self.assertEqual(destination.stat().st_nlink, 1)
        self.assertEqual(destination.stat().st_uid, os.geteuid())
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        controller._assert_evaluator_auth_source_stable(
            source, digest=digest, identity=identity
        )

    def test_auth_copy_accepts_deadline_fresh_access_without_refresh(self) -> None:
        source = self._auth_source(
            {
                "account": {
                    "expires_at": datetime(2099, 1, 1, tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                }
            }
        )
        destination = self.root / "fresh-auth.json"
        _digest, _identity, admission, markers = controller._copy_evaluator_auth(
            source, destination, minimum_valid_seconds=3600
        )
        self.assertEqual(admission, "fresh_access")
        self.assertTrue(markers)

    def test_auth_copy_rejects_source_over_fixed_bound_without_destination(self) -> None:
        source = self._auth_source(
            {"account": {"refresh_token": "test-refresh-token"}}
        )
        destination = self.root / "oversized-copy"
        with (
            mock.patch.object(
                controller,
                "MAX_EVALUATOR_AUTH_BYTES",
                source.stat().st_size - 1,
            ),
            self.assertRaisesRegex(controller.ControllerError, "fixed size limit"),
        ):
            controller._copy_evaluator_auth(
                source, destination, minimum_valid_seconds=1
            )
        self.assertFalse(destination.exists())
        self.assertFalse(destination.is_symlink())

    def test_evaluator_run_retention_deletes_an_unexpected_entry(self) -> None:
        run_root = self.root / "run"
        run_root.mkdir(mode=0o700)
        (run_root / "stdout.raw").write_bytes(b"clean output\n")
        (run_root / "unexpected.log").write_bytes(b"not admitted\n")

        with self.assertRaisesRegex(
            controller.BoundaryFailure, "failed its retention boundary"
        ):
            controller._admit_evaluator_run_evidence(run_root, ())

        self.assertFalse(run_root.exists())
        self.assertFalse(run_root.is_symlink())

    def test_evaluator_run_retention_rejects_fifo_without_blocking(self) -> None:
        run_root = self.root / "fifo-run"
        run_root.mkdir(mode=0o700)
        os.mkfifo(run_root / "stdout.raw", mode=0o600)

        with self.assertRaisesRegex(
            controller.BoundaryFailure, "failed its retention boundary"
        ):
            controller._admit_evaluator_run_evidence(run_root, ())

        self.assertFalse(run_root.exists())
        self.assertFalse(run_root.is_symlink())

    def test_private_file_write_failure_removes_partial_destination(self) -> None:
        destination = self.root / "partial-secret"
        original_write = os.write
        writes = 0

        def partial_then_fail(descriptor: int, data: bytes) -> int:
            nonlocal writes
            writes += 1
            if writes == 1:
                return original_write(descriptor, data[: max(1, len(data) // 2)])
            raise OSError("injected private file write failure")

        with (
            mock.patch.object(controller.os, "write", side_effect=partial_then_fail),
            self.assertRaisesRegex(OSError, "injected private file write failure"),
        ):
            controller._write_private_file(
                destination, b"test-only-secret-bytes", mode=0o600
            )
        self.assertFalse(destination.exists())
        self.assertFalse(destination.is_symlink())

    def test_private_file_fsync_failure_removes_complete_destination(self) -> None:
        destination = self.root / "unsynced-secret"
        with (
            mock.patch.object(
                controller.os,
                "fsync",
                side_effect=OSError("injected private file fsync failure"),
            ),
            self.assertRaisesRegex(OSError, "injected private file fsync failure"),
        ):
            controller._write_private_file(
                destination, b"test-only-secret-bytes", mode=0o600
            )
        self.assertFalse(destination.exists())
        self.assertFalse(destination.is_symlink())

    def test_auth_copy_rejects_aliases_links_modes_and_existing_destination(self) -> None:
        source = self._auth_source(
            {"account": {"refresh_token": "test-refresh"}}
        )
        relative = Path(source.name)
        with self.assertRaisesRegex(controller.ControllerError, "absolute"):
            controller._copy_evaluator_auth(
                relative, self.root / "relative-copy", minimum_valid_seconds=1
            )

        symlink = self.root / "auth-symlink"
        symlink.symlink_to(source)
        with self.assertRaisesRegex(controller.ControllerError, "opened safely"):
            controller._copy_evaluator_auth(
                symlink, self.root / "symlink-copy", minimum_valid_seconds=1
            )

        hardlink = self.root / "auth-hardlink"
        os.link(source, hardlink)
        with self.assertRaisesRegex(controller.ControllerError, "single-link"):
            controller._copy_evaluator_auth(
                source, self.root / "hardlink-copy", minimum_valid_seconds=1
            )
        hardlink.unlink()

        source.chmod(0o644)
        with self.assertRaisesRegex(controller.ControllerError, "0600"):
            controller._copy_evaluator_auth(
                source, self.root / "mode-copy", minimum_valid_seconds=1
            )
        source.chmod(0o600)

        destination = self.root / "existing-copy"
        destination.write_bytes(b"preserve\n")
        with self.assertRaises(FileExistsError):
            controller._copy_evaluator_auth(
                source, destination, minimum_valid_seconds=1
            )
        self.assertEqual(destination.read_bytes(), b"preserve\n")

    def test_auth_copy_rejects_fifo_without_blocking(self) -> None:
        source = self.root / "auth-fifo"
        os.mkfifo(source, mode=0o600)
        source.chmod(0o600)
        destination = self.root / "fifo-copy"

        with self.assertRaisesRegex(controller.ControllerError, "regular single-link"):
            controller._copy_evaluator_auth(
                source, destination, minimum_valid_seconds=1
            )

        self.assertFalse(destination.exists())
        self.assertFalse(destination.is_symlink())

    def test_evaluator_profile_and_environment_freeze_the_local_boundary(self) -> None:
        readable = self.root / "bundle.json"
        readable.write_bytes(b"{}\n")
        writable = self.root / "private"
        writable.mkdir(mode=0o700)
        profile, profile_hash = controller._evaluator_sandbox_profile(
            executable=self.executable,
            readable_files=[readable],
            writable_roots=[writable],
            metadata_only_paths=[self.root],
        )
        self.assertEqual(
            profile_hash, controller.sha256_bytes(profile.encode("utf-8"))
        )
        resolved_executable = self.executable.resolve(strict=True)
        for clause in (
            "(deny default)",
            '(import "system.sb")',
            "(system-network)",
            '(deny network-outbound (remote tcp "localhost:*"))',
            '(allow network-outbound (literal "/private/var/run/mDNSResponder"))',
            '(remote tcp "*:443")',
            f'(allow process-exec (literal "{resolved_executable}"))',
            f'(allow file-map-executable (literal "{resolved_executable}"))',
        ):
            self.assertIn(clause, profile)
        self.assertNotIn("process-fork", profile)
        self.assertNotIn("(allow process*)", profile)

        private = self.root / "environment-private"
        private.mkdir(mode=0o700)
        environment, roots = controller.Controller._evaluator_environment(private)
        self.assertEqual(environment["HOME"], str(roots["home"]))
        self.assertEqual(environment["GROK_HOME"], str(roots["grok_home"]))
        self.assertEqual(environment["TMPDIR"], str(roots["tmp"]))
        self.assertEqual(environment["XDG_RUNTIME_DIR"], str(roots["runtime"]))
        self.assertEqual(environment["GROK_SANDBOX"], "off")
        self.assertEqual(environment["GROK_AUTH_EARLY_INVALIDATION_SECS"], "0")
        self.assertNotIn("SSH_AUTH_SOCK", environment)
        self.assertNotIn("HTTP_PROXY", environment)

    @unittest.skipUnless(
        Path("/usr/bin/sandbox-exec").is_file(), "requires macOS sandbox-exec"
    )
    def test_exact_profile_denies_local_non_443_and_sample_unix_connections(self) -> None:
        probe = self.root / "evaluator-probe"
        controller._build_evaluator_probe(probe)
        readable = self.root / "readable-control"
        readable.write_bytes(b"control\n")
        writable = self.root / "writable"
        writable.mkdir(mode=0o700)
        profile, _profile_hash = controller._evaluator_sandbox_profile(
            executable=probe,
            readable_files=[readable],
            writable_roots=[writable],
            metadata_only_paths=[self.root],
        )
        profile_path = self.root / "evaluator.sb"
        controller._write_private_file(
            profile_path, profile.encode("utf-8"), mode=0o600
        )
        for label, arguments in {
            "localhost_ipv4": ["connect-localhost"],
            "localhost_ipv6": ["connect-localhost6"],
            "documentation_non_443": ["connect-other-port"],
            "unix_syslog": ["connect-unix", "/private/var/run/syslog"],
        }.items():
            completed = subprocess.run(
                [
                    "/usr/bin/sandbox-exec",
                    "-f",
                    str(profile_path),
                    str(probe),
                    *arguments,
                ],
                cwd=self.root,
                env=controller.SAFE_ENV,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=10,
            )
            self.assertEqual(
                completed.returncode,
                77,
                (label, completed.stdout, completed.stderr),
            )
            result = json.loads(completed.stdout)
            self.assertEqual(result["category"], "policy_denied", label)
            self.assertIn(result["errno"], {1, 13}, label)


if __name__ == "__main__":
    unittest.main()
