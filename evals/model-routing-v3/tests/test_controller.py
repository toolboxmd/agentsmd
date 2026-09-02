from __future__ import annotations

import base64
import inspect
import json
import os
from dataclasses import replace
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import controller  # noqa: E402
import lifecycle  # noqa: E402


def quota_snapshot(percent: float = 10.0) -> dict:
    return {
        "captured_at": "2026-09-01T00:00:00Z",
        "raw_sha256": "a" * 64,
        "primary": {
            "id": None,
            "used_percent": percent,
            "window_minutes": 300,
            "resets_at": 123,
        },
        "secondary": None,
        "tertiary": None,
        "extra_rate_windows": [],
    }


class ControllerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.files: dict[str, Path] = {}
        for name in ("codex", "launcher", "node", "auth"):
            path = self.root / name
            path.write_bytes(name.encode())
            path.chmod(0o700)
            self.files[name] = path
        self.config = controller.ControllerConfig(
            state_root=self.root / "state",
            use_grok_repo=self.source,
            karpathy_repo=self.source,
            openbot_repo=self.source,
            openbot_runtime_source=self.source,
            codex_executable=self.files["codex"],
            codex_launcher=self.files["launcher"],
            node_executable=self.files["node"],
            auth_source=self.files["auth"],
            codexbar_executable=self.files["codex"],
            memory_root=self.root / "memory",
        )
        self.config.memory_root.mkdir()
        (self.config.memory_root / "marker").write_text("marker")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def make_controller(self, hooks: controller.ControllerHooks | None = None) -> controller.Controller:
        value = controller.Controller(self.config, hooks)
        value.root.mkdir(parents=True, exist_ok=True)
        return value

    def prepare_runnable(self, value: controller.Controller) -> None:
        fixture = value.root / "fixture"
        fixture.mkdir()
        (fixture / "TASK.md").write_text("task")
        (fixture / "VERSION").write_text("0.1.0\n")
        frozen = controller.fixtures.load_frozen_v2(
            value.definition, package_root=controller.PACKAGE_ROOT
        )
        candidate_manifest = frozen.tree_manifest.build_tree_manifest(fixture)
        preflight = {
            "schema_version": 1,
            "status": "PASS",
            "no_model_calls": True,
            "definition_sha256": value.definition_sha256,
            "package_sha256": value.package_sha256,
            "fixture_sha256": {"use-grok": candidate_manifest["sha256"]},
            "discrimination": {},
            "native": {},
            "telemetry_compatibility": {},
            "quota_compatibility": {},
        }
        preflight_hash = controller._atomic_json(
            value.root / "preflight-receipt.json", preflight
        )
        state = lifecycle.create_state(
            value.definition,
            definition_sha256=value.definition_sha256,
            package_sha256=value.package_sha256,
        )
        state = lifecycle.record_preflight(
            state,
            value.definition,
            status="PASS",
            receipt_sha256=preflight_hash,
            observed_definition_sha256=value.definition_sha256,
            observed_package_sha256=value.package_sha256,
        )
        lifecycle.save_state(value.state_path, state, value.definition)
        review = {
            "status": "ACCEPT",
            "definition_sha256": value.definition_sha256,
            "package_sha256": value.package_sha256,
            "reviews": [
                {"axis": axis, "reviewer": f"reviewer-{axis}", "status": "PASS", "findings": [], "summary": "clean"}
                for axis in ("standards", "spec", "security")
            ],
            "summary": "all axes pass",
        }
        controller._atomic_json(value.root / "package-review.json", review)
        controller._atomic_json(
            value.fixtures_path,
            {
                "use-grok": {
                    "paths": {"candidate": str(fixture)},
                    "candidate_manifest": candidate_manifest,
                }
            },
        )
        value._assert_pins = lambda: None  # type: ignore[method-assign]


class SurfaceAndGateTests(ControllerCase):
    def test_v2_docker_verifier_helper_is_public_only(self) -> None:
        helper = controller.Controller._v2_public_docker_verifier
        self.assertEqual(
            list(inspect.signature(helper).parameters),
            [
                "self",
                "frozen",
                "definition",
                "verifier",
                "candidate",
                "task_id",
                "manifest_sha256",
                "deadline",
            ],
        )
        self.assertNotIn("--task", inspect.getsource(helper))
        self.assertFalse(hasattr(controller.Controller, "_v2_docker_verifier"))

    def test_cli_has_no_batch_or_arbitrary_cell_surface(self) -> None:
        parser = controller.build_parser()
        choices = set(parser._subparsers._group_actions[0].choices)
        self.assertEqual(
            choices,
            {
                "preflight",
                "run-canary",
                "validate-canary-audit",
                "run-next",
                "collect",
                "run-evaluator",
            },
        )
        for forbidden in ("run-all", "run-cell", "retry", "repair", "rereview"):
            self.assertNotIn(forbidden, choices)

    def test_state_root_inside_repository_is_rejected(self) -> None:
        invalid = replace(self.config, state_root=controller.REPOSITORY_ROOT / ".benchmark-state")
        with self.assertRaises(controller.ControllerError):
            invalid.normalized()

    def test_runtime_roots_require_the_exact_openssl_config(self) -> None:
        value = self.make_controller()
        runtime_bin = value.root / "runtime" / "bin"
        runtime_bin.mkdir(parents=True)
        runtime_node = runtime_bin / "node"
        runtime_node.write_bytes(self.files["node"].read_bytes())
        runtime_node.chmod(0o500)
        value.definition["pinned_runtime"]["node_sha256"] = controller.sha256_file(
            runtime_node
        )
        command_line_tools = self.root / "command-line-tools"
        command_line_tools.mkdir()
        openssl_config = self.root / "openssl.cnf"
        openssl_config.write_text("openssl_conf = default_conf\n", encoding="utf-8")
        value.definition["pinned_runtime"]["openssl_config_sha256"] = (
            controller.sha256_file(openssl_config)
        )
        with (
            mock.patch.object(controller, "COMMAND_LINE_TOOLS", command_line_tools),
            mock.patch.object(controller, "NODE_OPENSSL_CONFIG", openssl_config),
        ):
            self.assertEqual(
                value._profile_runtime_roots(),
                (runtime_node, command_line_tools, openssl_config),
            )
            openssl_config.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(controller.ControllerError):
                value._profile_runtime_roots()

    def test_package_review_requires_exact_hashes_and_three_unique_clean_axes(self) -> None:
        valid = {
            "status": "ACCEPT",
            "definition_sha256": "1" * 64,
            "package_sha256": "2" * 64,
            "reviews": [
                {"axis": axis, "reviewer": axis, "status": "PASS", "findings": [], "summary": "clean"}
                for axis in ("standards", "spec", "security")
            ],
            "summary": "clean",
        }
        controller.validate_package_review(valid, definition_sha256="1" * 64, package_sha256="2" * 64)
        for mutation in ("hash", "duplicate_axis", "duplicate_reviewer", "finding"):
            changed = json.loads(json.dumps(valid))
            if mutation == "hash":
                changed["package_sha256"] = "3" * 64
            elif mutation == "duplicate_axis":
                changed["reviews"][2]["axis"] = "spec"
            elif mutation == "duplicate_reviewer":
                changed["reviews"][2]["reviewer"] = "spec"
            else:
                changed["reviews"][0]["findings"] = ["P2"]
            with self.subTest(mutation=mutation), self.assertRaises(controller.ControllerError):
                controller.validate_package_review(changed, definition_sha256="1" * 64, package_sha256="2" * 64)

    def test_model_output_schemas_match_the_local_strict_subset(self) -> None:
        value = self.make_controller()
        receipt = value._model_output_schema_compatibility()

        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(set(receipt["schemas"]), {"implementation", "review"})
        for schema in receipt["schemas"].values():
            self.assertRegex(schema["sha256"], r"^[a-f0-9]{64}$")
            self.assertNotIn("uniqueItems", schema["keywords"])

    def test_model_output_schema_rejects_unique_items_before_preflight_work(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "implementation.schema.json").read_text(
                encoding="utf-8"
            )
        )
        schema["properties"]["changed_paths"]["uniqueItems"] = True
        with self.assertRaisesRegex(
            controller.ControllerError, "unsupported strict-schema keywords"
        ):
            controller.validate_openai_strict_output_schema(
                schema, label="implementation.schema.json"
            )

        value = self.make_controller()
        build = mock.Mock()
        with (
            mock.patch.object(value, "_assert_pins"),
            mock.patch.object(value, "_require_package_review"),
            mock.patch.object(
                value,
                "_model_output_schema_compatibility",
                side_effect=controller.ControllerError("schema rejected"),
            ),
            mock.patch.object(controller.fixtures, "build_fixtures", build),
        ):
            with self.assertRaisesRegex(controller.ControllerError, "schema rejected"):
                value.preflight()
        build.assert_not_called()

    def test_stage_response_semantics_replace_unsupported_schema_constraints(self) -> None:
        implementation = {
            "status": "completed",
            "summary": "done",
            "changed_paths": ["README.md"],
            "public_verifier": "passed",
            "blocker": None,
        }
        controller.Controller._validate_stage_response(
            implementation, reviewer=False
        )
        duplicated = json.loads(json.dumps(implementation))
        duplicated["changed_paths"] = ["README.md", "README.md"]
        with self.assertRaisesRegex(controller.ControllerError, "values are invalid"):
            controller.Controller._validate_stage_response(
                duplicated, reviewer=False
            )

        review = {
            "status": "BLOCKED",
            "artifact_sha256": "a" * 64,
            "review_range_sha256": "b" * 64,
            "summary": "one finding",
            "findings": [
                {
                    "severity": "P2",
                    "path": "README.md",
                    "line_start": 2,
                    "line_end": 3,
                    "reason": "incorrect claim",
                }
            ],
        }
        controller.Controller._validate_stage_response(review, reviewer=True)
        review["findings"][0]["line_start"] = True
        with self.assertRaisesRegex(
            controller.ControllerError, "finding values are invalid"
        ):
            controller.Controller._validate_stage_response(review, reviewer=True)

    def test_attempt_reservation_is_atomic_and_single_use(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        _, cell_id, attempt = value._reserve(True)
        self.assertEqual(cell_id, "use-grok--terra-high")
        self.assertTrue((attempt / "reservation.json").is_file())
        with self.assertRaises((controller.ControllerError, lifecycle.LifecycleError)):
            value._reserve(True)

    def test_native_preflight_protects_every_active_split_package_path(self) -> None:
        value = self.make_controller()
        built: dict[str, dict] = {}
        for task_id in ("use-grok", "karpathy-pointer", "openbot-acp"):
            task_root = self.root / task_id
            paths: dict[str, str] = {}
            for name in ("candidate", "known_good", "historical_export"):
                tree = task_root / name
                tree.mkdir(parents=True)
                (tree / "answer.txt").write_text(name, encoding="utf-8")
                paths[name] = str(tree)
            built[task_id] = {
                "changed_paths": ["answer.txt"],
                "paths": paths,
            }
        captured: dict[str, Path] = {}

        fake_module = mock.Mock()
        fake_module.PreflightBindings.side_effect = lambda **kwargs: kwargs

        def run_native_preflight(**kwargs):
            captured.update(kwargs["protected_read_paths"])
            return {"status": "PASS"}

        fake_module.run_native_preflight.side_effect = run_native_preflight
        with (
            mock.patch.object(
                controller.importlib, "import_module", return_value=fake_module
            ),
            mock.patch.object(value, "_profile_runtime_roots", return_value=()),
        ):
            receipt = value._native_preflight(
                built, {task_id: "a" * 64 for task_id in built}
            )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(
            {
                key.removeprefix("split_"): path
                for key, path in captured.items()
                if key.startswith("split_")
            },
            controller._split_package_paths(),
        )
        obsolete = (
            controller.PACKAGE_ROOT
            / "verifiers"
            / "hidden"
            / "openbot_acp_hidden.test.ts"
        )
        self.assertFalse(obsolete.exists())
        self.assertNotIn(obsolete, captured.values())

    def test_split_separation_failure_gates_overall_preflight(self) -> None:
        value = self.make_controller(
            controller.ControllerHooks(quota=lambda: quota_snapshot())
        )
        built: dict[str, dict] = {}
        for index, task_id in enumerate(
            ("use-grok", "karpathy-pointer", "openbot-acp"), start=1
        ):
            candidate = self.root / f"candidate-{index}"
            known = self.root / f"known-{index}"
            candidate.mkdir()
            known.mkdir()
            built[task_id] = {
                "paths": {"candidate": str(candidate), "known_good": str(known)},
                "candidate_manifest": {"sha256": f"{index}" * 64},
            }

        def verify(_task, candidate, _deadline):
            passed = Path(candidate).name.startswith("known-")
            return {
                "public": "PASS" if passed else "FAIL",
                "hidden": "PASS" if passed else "FAIL",
            }

        expected = {"package_sha256": value.package_sha256, "fixture_trees": {}}
        with (
            mock.patch.object(value, "_assert_pins"),
            mock.patch.object(value, "_require_package_review"),
            mock.patch.object(value, "_runtime_node"),
            mock.patch.object(controller.fixtures, "build_fixtures", return_value=built),
            mock.patch.object(value, "_verify", side_effect=verify),
            mock.patch.object(
                value, "_expected_preflight_bindings", return_value=expected
            ),
            mock.patch.object(
                value, "_observe_preflight_bindings", return_value=expected
            ),
            mock.patch.object(
                value, "_native_preflight", return_value={"status": "PASS"}
            ),
            mock.patch.object(
                value,
                "_split_separation_preflight",
                return_value={"status": "FAIL"},
            ),
            mock.patch.object(
                controller.telemetry,
                "telemetry_compatibility_receipt",
                return_value={},
            ),
        ):
            with self.assertRaisesRegex(
                controller.BoundaryFailure,
                "split separation receipt",
            ):
                value.preflight()
        self.assertFalse((value.root / "preflight-receipt.json").exists())


class SplitSeparationTests(ControllerCase):
    def valid_separation_receipt(self) -> dict:
        target = self.root / "bound-target"
        control = self.root / "bound-control"
        target.write_bytes(b"target")
        control.write_bytes(b"control")

        def probe(category: str) -> dict:
            denied = category == "policy_denied"
            return {
                "category": category,
                "errno": 1 if denied else None,
                "returncode": 77 if denied else 0,
                "elapsed_seconds": 0.01,
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
            }

        def signal_zero(category: str, target_kind: str) -> dict:
            return {
                **probe(category),
                "target_kind": target_kind,
                "target_pid": 12345,
            }

        signal_checks = {
            "control": {
                "alive_after": True,
                "alive_before": True,
                "launch": "separate_sandbox_exec_invocation",
                "process_group_id": 12345,
                "process_id": 12345,
                "worker_profile_sha256": "d" * 64,
            },
            "driver_pgid_observation": signal_zero("success", "pgid"),
            "driver_pid_observation": signal_zero("success", "pid"),
            "worker_same_sandbox_signaling": {
                "category": "success",
                "descendant_after_errno": controller.errno.ESRCH,
                "descendant_observed_after_leader_exit": True,
                "elapsed_seconds": 0.01,
                "errno": None,
                "group_after_errno": controller.errno.ESRCH,
                "group_leader_pid": 12347,
                "group_leader_returncode": 0,
                "group_observed_after_leader_exit": True,
                "group_signal": "SIGKILL",
                "inherited_descendant_pid": 12348,
                "pid_after_errno": controller.errno.ESRCH,
                "pid_child_pid": 12346,
                "pid_returncode": -controller.signal.SIGTERM,
                "returncode": 0,
                "stderr_sha256": "b" * 64,
                "stdout_sha256": "a" * 64,
            },
            "worker_unrelated_pgid_denial": signal_zero("policy_denied", "pgid"),
            "worker_unrelated_pid_denial": signal_zero("policy_denied", "pid"),
        }

        denial = {
            "target": str(target.resolve()),
            "target_sha256": controller.sha256_file(target),
            "control": str(control.resolve()),
            "control_sha256": controller.sha256_file(control),
            "unsandboxed_target_control": probe("success"),
            "sandboxed_allowed_control": probe("success"),
            "sandboxed_target": probe("policy_denied"),
        }
        read = {
            "target": str(target.resolve()),
            "target_sha256": controller.sha256_file(target),
            "unsandboxed": probe("success"),
            "sandboxed": probe("success"),
        }
        common = {
            name: json.loads(json.dumps(denial))
            for name in (
                "v2_hidden_driver",
                "openbot_hidden_driver",
                "hidden_package",
                "protocol_source",
                "runner_source",
            )
        }
        tasks = {}
        for task_id in ("use-grok", "karpathy-pointer", "openbot-acp"):
            worker_denials = json.loads(json.dumps(common))
            if task_id != "openbot-acp":
                worker_denials["frozen_hidden_source"] = json.loads(
                    json.dumps(denial)
                )
                driver_checks = {
                    "candidate_read_is_intentionally_allowed": json.loads(
                        json.dumps(read)
                    ),
                    "candidate_command_execution_owner": "worker",
                }
            else:
                driver_checks = {
                    "candidate_acp": json.loads(json.dumps(denial)),
                    "candidate_tsx_loader": json.loads(json.dumps(denial)),
                }
            tasks[task_id] = {
                "status": "PASS",
                "driver_profile_sha256": "c" * 64,
                "worker_profile_sha256": "d" * 64,
                "worker_denials": worker_denials,
                "driver_checks": driver_checks,
                "peer_source_checks": {
                    "driver": json.loads(json.dumps(read)),
                    "worker": json.loads(json.dumps(read)),
                },
                "signal_checks": (
                    json.loads(json.dumps(signal_checks))
                    if task_id == "openbot-acp"
                    else None
                ),
            }
        return {
            "status": "PASS",
            "no_model_calls": True,
            "accepted_denial_errnos": [1, 13],
            "tasks": tasks,
        }

    def test_split_separation_receipt_rejects_missing_controls_and_wrong_errno(self) -> None:
        value = self.make_controller()
        valid = self.valid_separation_receipt()
        value._validate_split_separation_receipt(valid)
        mutations = []
        missing_control = json.loads(json.dumps(valid))
        del missing_control["tasks"]["use-grok"]["worker_denials"][
            "protocol_source"
        ]["sandboxed_allowed_control"]
        mutations.append(missing_control)
        wrong_errno = json.loads(json.dumps(valid))
        wrong_errno["tasks"]["openbot-acp"]["driver_checks"]["candidate_acp"][
            "sandboxed_target"
        ]["errno"] = 2
        mutations.append(wrong_errno)
        wrong_profile = json.loads(json.dumps(valid))
        wrong_profile["tasks"]["karpathy-pointer"][
            "worker_profile_sha256"
        ] = "not-a-hash"
        mutations.append(wrong_profile)
        wrong_target = json.loads(json.dumps(valid))
        wrong_target["tasks"]["openbot-acp"]["worker_denials"][
            "runner_source"
        ]["target_sha256"] = "e" * 64
        mutations.append(wrong_target)
        wrong_control_profile = json.loads(json.dumps(valid))
        wrong_control_profile["tasks"]["openbot-acp"]["signal_checks"][
            "control"
        ]["worker_profile_sha256"] = "e" * 64
        mutations.append(wrong_control_profile)
        wrong_post_signal_errno = json.loads(json.dumps(valid))
        wrong_post_signal_errno["tasks"]["openbot-acp"]["signal_checks"][
            "worker_same_sandbox_signaling"
        ]["descendant_after_errno"] = controller.errno.EPERM
        mutations.append(wrong_post_signal_errno)
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                with self.assertRaises(controller.BoundaryFailure):
                    value._validate_split_separation_receipt(mutation)

    def test_lifecycle_hash_rejects_mutated_split_profile_receipt(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state = value._load_state()
        preflight_path = value.root / "preflight-receipt.json"
        preflight = controller._load_canonical(preflight_path)
        preflight["native"]["split_separation"] = {
            "driver_profile_sha256": "f" * 64
        }
        controller._atomic_json(preflight_path, preflight)
        with self.assertRaisesRegex(
            controller.ControllerError,
            "preflight receipt no longer binds lifecycle state",
        ):
            value._copy_bound_fixture(
                state,
                "use-grok",
                value.root / "copied-fixture",
            )

    def test_openbot_driver_launch_is_direct_native_node(self) -> None:
        argv = controller._openbot_driver_argv(
            sandbox=Path("/usr/bin/sandbox-exec"),
            profile="profile",
            node=Path("/pinned/node"),
            driver=Path("/hidden/driver.test.ts"),
        )
        self.assertEqual(
            argv,
            [
                "/usr/bin/sandbox-exec",
                "-p",
                "profile",
                "/pinned/node",
                "--experimental-strip-types",
                "/hidden/driver.test.ts",
            ],
        )
        self.assertNotIn("--test", argv)
        self.assertNotIn("--import", argv)

    def test_openbot_signal_profiles_separate_observer_from_child_owner(self) -> None:
        candidate = self.root / "candidate"
        shared = self.root / "shared"
        candidate.mkdir()
        shared.mkdir()
        node = self.root / "node-runtime"
        node.write_bytes(b"node")
        profiles = controller._openbot_split_profiles(
            node=node,
            candidate=candidate,
            shared=shared,
        )
        self.assertIn("(allow signal)", profiles["driver"][0])
        self.assertNotIn("(allow signal (target children))", profiles["driver"][0])
        self.assertNotIn("(allow signal (target same-sandbox))", profiles["driver"][0])
        self.assertNotIn("(allow signal (target children))", profiles["worker"][0])
        self.assertIn("(allow signal (target same-sandbox))", profiles["worker"][0])
        self.assertNotIn("(allow signal)", profiles["worker"][0].replace(
            "(allow signal (target same-sandbox))", ""
        ))

    def test_split_preflight_selects_an_existing_changed_answer(self) -> None:
        candidate = self.root / "candidate-answer-selection"
        existing = candidate / ".codex-plugin" / "plugin.json"
        existing.parent.mkdir(parents=True)
        existing.write_text("{}\n", encoding="utf-8")
        selected = controller.Controller._existing_candidate_answer(
            candidate,
            [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"],
        )
        self.assertEqual(selected, existing.resolve(strict=True))

        with self.assertRaisesRegex(
            controller.BoundaryFailure, "no existing changed answer file"
        ):
            controller.Controller._existing_candidate_answer(
                candidate, [".claude-plugin/plugin.json"]
            )

    @unittest.skipUnless(
        sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(),
        "requires macOS Seatbelt",
    )
    def test_openbot_worker_eof_reaps_sigterm_ignoring_child_group(self) -> None:
        node_name = controller.shutil.which("node")
        if node_name is None:
            self.skipTest("Node.js is unavailable")
        node = Path(node_name).resolve(strict=True)
        definition = json.loads(
            (controller.PACKAGE_ROOT / "definition.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            controller.sha256_file(node),
            definition["pinned_runtime"]["node_sha256"],
            "Node.js on PATH does not match the exact benchmark pin",
        )
        candidate = self.root / "candidate"
        shared = self.root / "shared"
        candidate.mkdir()
        shared.mkdir()
        candidate_module = candidate / "candidate.mjs"
        relay = candidate / "relay.mjs"
        candidate_module.write_text(
            """
import { spawn } from "node:child_process";

export class AcpClient {
  constructor(_command, _cwd, _handlers, timing) {
    this.timing = timing;
    this.child = spawn(process.execPath, [
      "-e",
      "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);",
    ], { detached: true, stdio: "ignore" });
    this.child.unref();
    this.pid = this.child.pid;
  }

  close() {
    try { process.kill(-this.pid, "SIGTERM"); } catch (error) {
      if (error?.code !== "ESRCH") throw error;
    }
    setTimeout(() => {
      try { process.kill(-this.pid, "SIGKILL"); } catch (error) {
        if (error?.code !== "ESRCH") throw error;
      }
    }, this.timing.terminateGraceMs).unref();
  }
}
""",
            encoding="utf-8",
        )
        relay.write_text("// constructor does not execute this relay\n", encoding="utf-8")
        profiles = controller._openbot_split_profiles(
            node=node,
            candidate=candidate,
            shared=shared,
        )
        driver_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='driver')
created = endpoint.request('create', {
    'amount': 0,
    'mode': 'healthy',
    'option': '',
    'timing': {'startDeadlineMs': 750, 'terminateGraceMs': 25},
})
pid = created['pid']
assert isinstance(pid, int) and pid > 1
import os
os.kill(-pid, 0)
print(f'live-child-group:{pid}')
"""
        deadline_monotonic = time.monotonic() + 10
        binding = controller.split_verifier.Binding(
            nonce="0" * 64,
            task="openbot-acp",
            candidate_manifest_sha256="1" * 64,
            driver_sha256="2" * 64,
            worker_sha256="3" * 64,
            deadline_unix_ms=int((time.time() + 10) * 1000),
        )
        environment = {
            "HOME": str(self.root),
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": str(controller.PACKAGE_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": str(shared),
        }
        worker_environment = {
            **environment,
            "ROUTING_CANDIDATE_ACP": str(candidate_module),
            "ROUTING_CANDIDATE_ROOT": str(candidate),
            "ROUTING_OPENBOT_AGENT_RELAY": str(relay),
        }
        outputs = {
            name: shared / name
            for name in (
                "driver.stderr",
                "driver.stdout",
                "transcript",
                "worker.stderr",
                "worker.stdout",
            )
        }
        child_group: int | None = None
        try:
            receipt = controller.split_verifier.run_split_verifier(
                [str(controller.SPLIT_PYTHON), "-B", "-c", driver_program],
                [
                    "/usr/bin/sandbox-exec",
                    "-p",
                    profiles["worker"][0],
                    str(node),
                    str(controller._split_package_paths()["openbot_worker"]),
                ],
                driver_cwd=shared,
                worker_cwd=shared,
                driver_environment=environment,
                worker_environment=worker_environment,
                binding=binding,
                deadline_monotonic=deadline_monotonic,
                transcript_path=outputs["transcript"],
                driver_stdout_path=outputs["driver.stdout"],
                driver_stderr_path=outputs["driver.stderr"],
                worker_stdout_path=outputs["worker.stdout"],
                worker_stderr_path=outputs["worker.stderr"],
            )
            driver_stdout = outputs["driver.stdout"].read_text(encoding="utf-8").strip()
            self.assertTrue(receipt.passed, {
                **receipt.as_dict(),
                "driver_stdout": driver_stdout,
                "driver_stderr": outputs["driver.stderr"].read_text(encoding="utf-8"),
                "worker_stderr": outputs["worker.stderr"].read_text(encoding="utf-8"),
            })
            child_group = int(driver_stdout.removeprefix("live-child-group:"))
            with self.assertRaises(ProcessLookupError):
                controller.os.killpg(child_group, 0)
        finally:
            if child_group is not None:
                try:
                    controller.os.killpg(child_group, controller.signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_policy_denial_rejects_non_permission_errno(self) -> None:
        value = self.make_controller()
        target = self.root / "target"
        target.write_bytes(b"x")
        completed = controller.subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=controller.canonical_bytes({"category": "error", "errno": 2}),
            stderr=b"",
        )
        with mock.patch.object(controller.subprocess, "run", return_value=completed):
            with self.assertRaises(controller.BoundaryFailure):
                value._run_seatbelt_read_probe(
                    target=target,
                    cwd=self.root,
                    expected_category="policy_denied",
                    profile="(version 1)(deny default)",
                )

    def test_split_python_drift_is_typed_before_hidden_verification(self) -> None:
        value = self.make_controller()
        candidate = self.root / "candidate"
        candidate.mkdir()
        with mock.patch.object(
            value,
            "_assert_split_python_pin",
            side_effect=controller.BoundaryFailure("drift"),
        ) as check:
            with self.assertRaises(controller.BoundaryFailure):
                value._split_hidden_verifier(
                    "use-grok", candidate, time.monotonic() + 10
                )
        check.assert_called_once_with(controller.BoundaryFailure)
        self.assertEqual(
            list(candidate.parent.glob("split-hidden-*")),
            [],
        )

    def test_split_python_oserror_is_a_stable_controller_error(self) -> None:
        value = self.make_controller()
        with mock.patch.object(
            controller, "sha256_file", side_effect=PermissionError("denied")
        ):
            with self.assertRaisesRegex(
                controller.ControllerError,
                "cannot inspect pinned split-verifier Python",
            ):
                value._assert_split_python_pin(controller.ControllerError)

    def test_split_python_timeout_is_a_stable_boundary_failure(self) -> None:
        value = self.make_controller()
        value.definition["pinned_runtime"]["split_python_sha256"] = (
            controller.sha256_file(controller.SPLIT_PYTHON)
        )
        with mock.patch.object(
            controller.subprocess,
            "run",
            side_effect=controller.subprocess.TimeoutExpired("python", 10),
        ):
            with self.assertRaisesRegex(
                controller.BoundaryFailure,
                "cannot inspect pinned split-verifier Python",
            ):
                value._assert_split_python_pin(controller.BoundaryFailure)

    @unittest.skipUnless(
        sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(),
        "requires macOS Seatbelt",
    )
    def test_openbot_profiles_enforce_driver_and_worker_read_separation(self) -> None:
        value = self.make_controller()
        candidate = self.root / "candidate"
        shared = self.root / "shared"
        candidate_acp = candidate / "daemon" / "src" / "acp.ts"
        loader = candidate / "node_modules" / "tsx" / "dist" / "loader.mjs"
        candidate_acp.parent.mkdir(parents=True)
        loader.parent.mkdir(parents=True)
        shared.mkdir()
        candidate_acp.write_bytes(b"answer")
        loader.write_bytes(b"loader")
        node = self.root / "node-runtime"
        node.write_bytes(b"node")
        profiles = controller._openbot_split_profiles(
            node=node,
            candidate=candidate,
            shared=shared,
        )
        control = shared / "control"
        control.write_bytes(b"control")
        driver_denial = value._prove_seatbelt_denial(
            profile=profiles["driver"][0],
            target=candidate_acp,
            control=control,
            cwd=shared,
        )
        worker_read = value._prove_seatbelt_read(
            profile=profiles["worker"][0],
            target=candidate_acp,
            cwd=shared,
        )
        package_paths = controller._split_package_paths()
        worker_denials = {
            name: value._prove_seatbelt_denial(
                profile=profiles["worker"][0],
                target=package_paths[name],
                control=control,
                cwd=shared,
            )
            for name in (
                "v2_driver",
                "openbot_driver",
                "hidden_package",
                "protocol",
                "runner",
            )
        }
        signal_checks = value._prove_openbot_signal_scope(
            driver_profile=profiles["driver"][0],
            worker_profile=profiles["worker"][0],
            cwd=shared,
        )
        self.assertEqual(driver_denial["target"], str(candidate_acp.resolve()))
        self.assertEqual(
            driver_denial["target_sha256"], controller.sha256_file(candidate_acp)
        )
        self.assertIn(driver_denial["sandboxed_target"]["errno"], {1, 13})
        self.assertEqual(worker_read["sandboxed"]["category"], "success")
        self.assertTrue(
            all(
                receipt["sandboxed_target"]["errno"] in {1, 13}
                for receipt in worker_denials.values()
            )
        )
        self.assertNotIn(str(candidate.resolve()), profiles["driver"][0])
        self.assertIn(str(candidate.resolve()), profiles["worker"][0])
        self.assertEqual(
            signal_checks["driver_pid_observation"]["category"], "success"
        )
        self.assertEqual(
            signal_checks["driver_pgid_observation"]["category"], "success"
        )
        self.assertEqual(
            signal_checks["worker_same_sandbox_signaling"]["category"],
            "success",
        )
        same_sandbox = signal_checks["worker_same_sandbox_signaling"]
        self.assertTrue(same_sandbox["group_observed_after_leader_exit"])
        self.assertTrue(same_sandbox["descendant_observed_after_leader_exit"])
        self.assertEqual(same_sandbox["pid_after_errno"], controller.errno.ESRCH)
        self.assertEqual(same_sandbox["group_after_errno"], controller.errno.ESRCH)
        self.assertEqual(
            same_sandbox["descendant_after_errno"], controller.errno.ESRCH
        )
        self.assertEqual(
            signal_checks["control"]["worker_profile_sha256"],
            profiles["worker"][1],
        )
        self.assertEqual(
            signal_checks["worker_unrelated_pid_denial"]["category"],
            "policy_denied",
        )
        self.assertEqual(
            signal_checks["worker_unrelated_pgid_denial"]["category"],
            "policy_denied",
        )

    @unittest.skipUnless(
        sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(),
        "requires macOS Seatbelt",
    )
    def test_v2_driver_may_read_candidate_while_worker_cannot_read_hidden(self) -> None:
        value = self.make_controller()
        candidate = self.root / "candidate"
        shared = self.root / "shared"
        hidden = self.root / "hidden.py"
        driver_runtime = self.root / "driver-runtime"
        worker_runtime = self.root / "worker-runtime"
        for path in (candidate, shared, driver_runtime, worker_runtime):
            path.mkdir()
        answer = candidate / "answer.txt"
        answer.write_bytes(b"answer")
        hidden.write_bytes(b"hidden")
        profiles = controller._v2_split_profiles(
            candidate=candidate,
            shared=shared,
            hidden=hidden,
            driver_runtime=driver_runtime,
            worker_runtime=worker_runtime,
        )
        driver_read = value._prove_seatbelt_read(
            profile=profiles["driver"][0], target=answer, cwd=shared
        )
        control = shared / "control"
        control.write_bytes(b"control")
        package_paths = controller._split_package_paths()
        denial_targets = {
            "frozen_hidden": hidden,
            "v2_driver": package_paths["v2_driver"],
            "openbot_driver": package_paths["openbot_driver"],
            "hidden_package": package_paths["hidden_package"],
            "protocol": package_paths["protocol"],
            "runner": package_paths["runner"],
        }
        worker_denials = {
            name: value._prove_seatbelt_denial(
                profile=profiles["worker"][0],
                target=target,
                control=control,
                cwd=shared,
            )
            for name, target in denial_targets.items()
        }
        self.assertEqual(driver_read["sandboxed"]["category"], "success")
        self.assertTrue(
            all(
                receipt["sandboxed_target"]["errno"] in {1, 13}
                for receipt in worker_denials.values()
            )
        )


class ReviewRangeTests(ControllerCase):
    def _range_fixture(self) -> tuple[Path, Path, dict, dict, dict]:
        baseline = self.root / "range-baseline"
        artifact = self.root / "range-artifact"
        baseline.mkdir()
        (baseline / "binary.bin").write_bytes(b"\x00old\xff")
        (baseline / "deleted.txt").write_text("deleted\n", encoding="utf-8")
        (baseline / "unchanged.txt").write_text("same\n", encoding="utf-8")
        controller._copy_ordinary(baseline, artifact)
        (artifact / "binary.bin").write_bytes(b"\x00new\xfe")
        (artifact / "deleted.txt").unlink()
        created = artifact / "new-dir"
        created.mkdir()
        (created / "created.bin").write_bytes(b"\x10\x00created")
        before = controller.strict_tree_manifest(baseline)
        after = controller.strict_tree_manifest(artifact)
        allowed = ["binary.bin", "deleted.txt", "new-dir/created.bin"]
        scope = controller._scope_receipt(before, after, allowed, allowed)
        self.assertTrue(scope["safe"])
        return baseline, artifact, before, after, scope

    def test_canonical_range_covers_binary_create_delete_and_directory(self) -> None:
        baseline, artifact, before, after, scope = self._range_fixture()
        value = controller._build_review_range(
            baseline,
            artifact,
            baseline_manifest_sha256=before["sha256"],
            artifact_manifest_sha256=after["sha256"],
            scope=scope,
            allowed_paths=["binary.bin", "deleted.txt", "new-dir/created.bin"],
        )

        self.assertEqual(value["changed_paths"], sorted(value["changed_paths"]))
        by_path = {change["path"]: change for change in value["changes"]}
        self.assertEqual(
            base64.b64decode(by_path["binary.bin"]["before"]["content_base64"]),
            b"\x00old\xff",
        )
        self.assertEqual(
            base64.b64decode(by_path["binary.bin"]["after"]["content_base64"]),
            b"\x00new\xfe",
        )
        self.assertIsNone(by_path["deleted.txt"]["after"])
        self.assertIsNone(by_path["new-dir"]["before"])
        self.assertEqual(by_path["new-dir"]["after"]["entry"]["kind"], "directory")
        self.assertIsNone(by_path["new-dir"]["after"]["content_base64"])
        self.assertIsNone(by_path["new-dir/created.bin"]["before"])
        self.assertEqual(
            base64.b64decode(
                by_path["new-dir/created.bin"]["after"]["content_base64"]
            ),
            b"\x10\x00created",
        )
        self.assertNotIn("unchanged.txt", by_path)

    def test_range_rejects_snapshot_drift_and_scope_mismatch(self) -> None:
        baseline, artifact, before, after, scope = self._range_fixture()
        cases = []
        cases.append(("baseline hash", "0" * 64, after["sha256"], scope))
        cases.append(("artifact hash", before["sha256"], "0" * 64, scope))
        mismatched_scope = json.loads(json.dumps(scope))
        mismatched_scope["declared_paths"] = ["binary.bin"]
        cases.append(
            ("scope", before["sha256"], after["sha256"], mismatched_scope)
        )
        for name, baseline_hash, artifact_hash, supplied_scope in cases:
            with self.subTest(name=name), self.assertRaises(controller.ControllerError):
                controller._build_review_range(
                    baseline,
                    artifact,
                    baseline_manifest_sha256=baseline_hash,
                    artifact_manifest_sha256=artifact_hash,
                    scope=supplied_scope,
                    allowed_paths=[
                        "binary.bin",
                        "deleted.txt",
                        "new-dir/created.bin",
                    ],
                )

        (artifact / "binary.bin").write_bytes(b"drift")
        with self.assertRaises(controller.ControllerError):
            controller._build_review_range(
                baseline,
                artifact,
                baseline_manifest_sha256=before["sha256"],
                artifact_manifest_sha256=after["sha256"],
                scope=scope,
                allowed_paths=["binary.bin", "deleted.txt", "new-dir/created.bin"],
            )


class CellLifecycleTests(ControllerCase):
    def _run(
        self,
        *,
        breach: bool,
        verifier_pass: bool,
        wrong_range_echo: bool = False,
    ) -> tuple[dict, list[str]]:
        calls: list[str] = []
        self.baseline_seen_before_implementation = False
        self.review_prompts: list[str] = []

        def codex_stage(**kwargs):
            calls.append(kwargs["stage"])
            if kwargs["stage"] == "implementation":
                self.baseline_seen_before_implementation = (
                    kwargs["attempt"] / "baseline-snapshot"
                ).is_dir()
                target = kwargs["candidate"] / ("forbidden.txt" if breach else "VERSION")
                target.write_text("changed\n")
                return {
                    "stage": "implementation",
                    "response": {
                        "status": "completed",
                        "summary": "done",
                        "changed_paths": [target.relative_to(kwargs["candidate"]).as_posix()],
                        "public_verifier": "not_run",
                        "blocker": None,
                    },
                }
            self.review_prompts.append(kwargs["prompt"])
            artifact = re.search(r"Artifact SHA-256: ([a-f0-9]{64})", kwargs["prompt"]).group(1)
            review_range = re.search(
                r"Review range SHA-256: ([a-f0-9]{64})", kwargs["prompt"]
            ).group(1)
            return {
                "stage": "review",
                "response": {
                    "status": "PASS",
                    "artifact_sha256": artifact,
                    "review_range_sha256": (
                        "0" * 64 if wrong_range_echo else review_range
                    ),
                    "summary": "clean",
                    "findings": [],
                },
            }

        hooks = controller.ControllerHooks(
            codex_stage=codex_stage,
            verifier=lambda task, candidate, deadline: {
                "public": "PASS" if verifier_pass else "FAIL",
                "hidden": "PASS" if verifier_pass else "FAIL",
            },
            quota=lambda: quota_snapshot(),
        )
        value = self.make_controller(hooks)
        self.last_controller = value
        self.prepare_runnable(value)
        state, cell_id, attempt = value._reserve(True)
        self.last_attempt = attempt
        return value._run_reserved_cell(state, cell_id, attempt), calls

    def _run_review_failure(
        self, failure: controller.ControllerError
    ) -> tuple[controller.Controller, dict, list[str], Path]:
        calls: list[str] = []

        def codex_stage(**kwargs):
            calls.append(kwargs["stage"])
            if kwargs["stage"] == "review":
                raise failure
            target = kwargs["candidate"] / "VERSION"
            target.write_text("changed\n", encoding="utf-8")
            return {
                "stage": "implementation",
                "response": {
                    "status": "completed",
                    "summary": "done",
                    "changed_paths": ["VERSION"],
                    "public_verifier": "not_run",
                    "blocker": None,
                },
            }

        value = self.make_controller(
            controller.ControllerHooks(
                codex_stage=codex_stage,
                verifier=lambda _task, _candidate, _deadline: {
                    "public": "PASS",
                    "hidden": "PASS",
                },
                quota=lambda: quota_snapshot(),
            )
        )
        self.prepare_runnable(value)
        result = value.run_canary()
        attempt = value.root / "attempts" / "use-grok--terra-high"
        return value, result, calls, attempt

    def test_safe_completed_implementation_is_reviewed_after_verifier_failure(self) -> None:
        result, calls = self._run(breach=False, verifier_pass=False)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertEqual(calls, ["implementation", "review"])
        self.assertTrue(self.baseline_seen_before_implementation)
        artifact_path = self.last_attempt / "artifact.json"
        self.assertEqual(result["artifact_evidence_file"], "artifact.json")
        self.assertEqual(result["artifact_sha256"], controller.sha256_file(artifact_path))
        self.assertTrue((self.last_attempt / "artifact-snapshot").is_dir())
        self.assertTrue((self.last_attempt / "baseline-snapshot").is_dir())
        review_range_path = self.last_attempt / "review-range.json"
        workspace_range_path = (
            self.last_attempt
            / "review-workspace"
            / ".benchmark"
            / "review-range.json"
        )
        self.assertEqual(review_range_path.read_bytes(), workspace_range_path.read_bytes())
        review_range_sha256 = controller.sha256_file(review_range_path)
        self.assertIn(review_range_sha256, self.review_prompts[0])
        review_receipt = controller._load_canonical(
            self.last_attempt / "review-receipt.json"
        )
        self.assertEqual(
            review_receipt["response"]["review_range_sha256"],
            review_range_sha256,
        )
        self.assertEqual(
            review_receipt["artifact_binding"]["review_workspace_before_sha256"],
            review_receipt["artifact_binding"]["review_workspace_after_sha256"],
        )
        terminal = self.last_controller._load_state()["terminal_cells"][0]
        self.assertEqual(
            terminal["review"]["review_range_sha256"], review_range_sha256
        )
        (self.last_attempt / "candidate" / "VERSION").write_text(
            "mutable candidate drift\n", encoding="utf-8"
        )
        rebuilt, rebuilt_hash, _baseline, _snapshot = (
            self.last_controller._rebuild_attempt_review_range(
                self.last_attempt,
                controller._load_canonical(artifact_path),
            )
        )
        self.assertEqual(rebuilt, controller._load_canonical(review_range_path))
        self.assertEqual(rebuilt_hash, review_range_sha256)
        self.assertEqual(
            result["artifact_snapshot_manifest_sha256"],
            result["artifact"]["snapshot_manifest_sha256"],
        )

    def test_unsafe_scope_stops_before_review(self) -> None:
        result, calls = self._run(breach=True, verifier_pass=True)
        self.assertEqual(result["status"], "UNSAFE_SCOPE")
        self.assertEqual(calls, ["implementation"])
        self.assertFalse((self.last_attempt / "review-range.json").exists())

    def test_wrong_review_range_echo_blocks_review(self) -> None:
        result, calls = self._run(
            breach=False, verifier_pass=True, wrong_range_echo=True
        )
        self.assertEqual(result["status"], "REVIEW_BLOCKED")
        self.assertEqual(calls, ["implementation", "review"])

    def test_generic_luna_failure_terminalizes_with_stage_evidence(self) -> None:
        failure = controller.ControllerError("Luna invocation failed")
        failure.evidence = {
            "stage_evidence": {"stage": "review", "files": ["review/exec.jsonl"]}
        }

        value, result, calls, attempt = self._run_review_failure(failure)

        self.assertEqual(calls, ["implementation", "review"])
        self.assertEqual(result["status"], "CONTROLLER_ERROR")
        self.assertEqual(result["failure_evidence"], failure.evidence)
        self.assertIsNotNone(result["implementation"])
        self.assertIsNotNone(result["verification"])
        self.assertIsNotNone(result["artifact"])
        self.assertIsNone(result["review"])
        self.assertFalse((attempt / "review-receipt.json").exists())
        self.assertEqual(controller._load_canonical(attempt / "result.json"), result)
        self.assertEqual(
            value._load_state()["terminal_cells"][0]["terminal"]["status"],
            "CONTROLLER_ERROR",
        )
        with self.assertRaises((controller.ControllerError, lifecycle.LifecycleError)):
            value.run_canary()
        self.assertEqual(calls, ["implementation", "review"])

    def test_luna_stage_timeout_terminalizes_with_stage_evidence(self) -> None:
        failure = controller.StageTimeout("Luna reached the shared deadline")
        failure.evidence = {
            "stage_evidence": {"stage": "review", "files": ["review/exec.jsonl"]}
        }

        value, result, calls, attempt = self._run_review_failure(failure)

        self.assertEqual(calls, ["implementation", "review"])
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertEqual(result["failure_evidence"], failure.evidence)
        self.assertIsNotNone(result["implementation"])
        self.assertIsNotNone(result["verification"])
        self.assertIsNotNone(result["artifact"])
        self.assertIsNone(result["review"])
        self.assertFalse((attempt / "review-receipt.json").exists())
        self.assertEqual(controller._load_canonical(attempt / "result.json"), result)
        self.assertEqual(
            value._load_state()["terminal_cells"][0]["terminal"]["status"],
            "TIMEOUT",
        )
        with self.assertRaises((controller.ControllerError, lifecycle.LifecycleError)):
            value.run_canary()
        self.assertEqual(calls, ["implementation", "review"])

    def test_typed_telemetry_failure_terminalizes_without_retry(self) -> None:
        value = self.make_controller(
            controller.ControllerHooks(
                codex_stage=lambda **_kwargs: (_ for _ in ()).throw(
                    controller.TelemetryFailure(
                        "quota observer is malformed", evidence={"observer": "test"}
                    )
                )
            )
        )
        self.prepare_runnable(value)

        result = value.run_canary()

        self.assertEqual(result["status"], "TELEMETRY_FAILURE")
        self.assertEqual(result["failure_evidence"], {"observer": "test"})
        state = value._load_state()
        self.assertTrue(state["stopped"])
        self.assertEqual(state["terminal_cells"][0]["terminal"]["status"], "TELEMETRY_FAILURE")
        with self.assertRaises((controller.ControllerError, lifecycle.LifecycleError)):
            value.run_canary()

    def test_generic_controller_failure_persists_attached_evidence(self) -> None:
        failure = controller.ControllerError("generic stage failure")
        failure.evidence = {"stage_evidence": {"stage": "implementation"}}
        value = self.make_controller(
            controller.ControllerHooks(
                codex_stage=lambda **_kwargs: (_ for _ in ()).throw(failure)
            )
        )
        self.prepare_runnable(value)

        result = value.run_canary()

        self.assertEqual(result["status"], "CONTROLLER_ERROR")
        self.assertEqual(result["failure_evidence"], failure.evidence)

    def test_stage_timeout_persists_attached_evidence(self) -> None:
        failure = controller.StageTimeout("stage deadline")
        failure.evidence = {"stage_evidence": {"stage": "implementation"}}
        value = self.make_controller(
            controller.ControllerHooks(
                codex_stage=lambda **_kwargs: (_ for _ in ()).throw(failure)
            )
        )
        self.prepare_runnable(value)

        result = value.run_canary()

        self.assertEqual(result["status"], "TIMEOUT")
        self.assertEqual(result["failure_evidence"], failure.evidence)

    def test_late_safety_failure_is_not_reclassified_as_timeout(self) -> None:
        deadline = 100 + 600 * 1_000_000_000
        for failure_type, expected in (
            (controller.BoundaryFailure, "BOUNDARY_FAILURE"),
            (controller.ControllerError, "CONTROLLER_ERROR"),
            (controller.TelemetryFailure, "TELEMETRY_FAILURE"),
        ):
            config = replace(
                self.config,
                state_root=self.root / f"state-{expected.lower()}",
            )
            value = controller.Controller(
                config,
                controller.ControllerHooks(
                    codex_stage=lambda **_kwargs: (_ for _ in ()).throw(
                        failure_type("late safety failure")
                    )
                ),
            )
            value.root.mkdir(parents=True)
            self.prepare_runnable(value)

            with mock.patch.object(
                controller.time,
                "monotonic_ns",
                side_effect=[100, deadline],
            ):
                result = value.run_canary()

            with self.subTest(status=expected):
                self.assertEqual(result["status"], expected)
                self.assertTrue(value._load_state()["stopped"])

    def test_unsafe_scope_discovered_at_deadline_is_not_a_scored_timeout(self) -> None:
        deadline = 100 + 600 * 1_000_000_000

        def codex_stage(**kwargs):
            target = kwargs["candidate"] / "forbidden.txt"
            target.write_text("out of scope\n", encoding="utf-8")
            return {
                "stage": "implementation",
                "response": {
                    "status": "completed",
                    "summary": "done",
                    "changed_paths": ["forbidden.txt"],
                    "public_verifier": "not_run",
                    "blocker": None,
                },
            }

        value = self.make_controller(
            controller.ControllerHooks(codex_stage=codex_stage)
        )
        self.prepare_runnable(value)
        with mock.patch.object(
            controller.time,
            "monotonic_ns",
            side_effect=[100, 101, deadline, deadline],
        ):
            result = value.run_canary()

        self.assertEqual(result["status"], "BOUNDARY_FAILURE")
        self.assertTrue(value._load_state()["stopped"])

    def test_missing_bound_artifact_takes_precedence_over_stage_timeout(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state, cell_id, attempt = value._reserve(True)
        active = state["active_cell"]
        state = lifecycle.record_implementation_complete(
            state,
            value.definition,
            cell_id=cell_id,
            artifact_sha256="a" * 64,
            receipt_sha256="b" * 64,
            now_monotonic_ns=active["started_monotonic_ns"] + 1,
        )
        value._save_state(state)

        with (
            mock.patch.object(
                value,
                "_run_reserved_cell",
                side_effect=controller.StageTimeout("stage timeout"),
            ),
            mock.patch.object(
                controller.time,
                "monotonic_ns",
                return_value=active["deadline_monotonic_ns"],
            ),
        ):
            result = value._run_reserved_fail_closed(state, cell_id, attempt)

        self.assertEqual(result["status"], "CONTROLLER_ERROR")
        self.assertIn("artifact_evidence_error", result["failure_evidence"])
        self.assertTrue(value._load_state()["stopped"])


class CollectionGateTests(ControllerCase):
    def _complete_evidence(
        self,
        value: controller.Controller,
        *,
        failed_ordinal: int | None = None,
        failed_after_implementation_ordinal: int | None = None,
    ) -> dict:
        state = value._load_state()
        attempts = value.root / "attempts"
        attempts.mkdir()
        now = 1_000
        for ordinal, cell_id in enumerate(state["run_order"]):
            state = (
                lifecycle.authorize_canary(
                    state, value.definition, now_monotonic_ns=now
                )
                if ordinal == 0
                else lifecycle.authorize_next(
                    state, value.definition, now_monotonic_ns=now
                )
            )
            task_id = value.definition["cells"][cell_id]["task"]
            allowed_path = value.definition["tasks"][task_id]["allowed_paths"][0]
            attempt = attempts / cell_id
            attempt.mkdir()
            if ordinal == failed_ordinal:
                implementation_receipt = {
                    "stage": "implementation",
                    "response": {
                        "status": "blocked",
                        "blocker": "candidate failed",
                    },
                }
                controller._exclusive_json(
                    attempt / "implementation-receipt.json",
                    implementation_receipt,
                )
                result = value._terminal_payload(
                    cell_id,
                    "IMPLEMENTATION_FAILED",
                    implementation_receipt,
                    None,
                    None,
                    error="candidate failed",
                )
                result_sha256 = controller.sha256_bytes(
                    controller.canonical_bytes(result)
                )
                state = lifecycle.record_implementation_failure(
                    state,
                    value.definition,
                    cell_id=cell_id,
                    result_sha256=result_sha256,
                    reason="single implementation attempt did not complete",
                    now_monotonic_ns=now + 1,
                )
                self.assertEqual(
                    controller._exclusive_json(attempt / "result.json", result),
                    result_sha256,
                )
                now += 10
                continue
            baseline_root = attempt / "baseline-snapshot"
            artifact_root = attempt / "artifact-snapshot"
            baseline_root.mkdir()
            artifact_root.mkdir()
            changed = artifact_root / allowed_path
            changed.parent.mkdir(parents=True, exist_ok=True)
            changed.write_bytes(f"artifact {cell_id}\n".encode())
            baseline = controller.strict_tree_manifest(baseline_root)
            artifact_manifest = controller.strict_tree_manifest(artifact_root)
            scope = controller._scope_receipt(
                baseline,
                artifact_manifest,
                [allowed_path],
                value.definition["tasks"][task_id]["allowed_paths"],
            )
            self.assertTrue(scope["safe"])
            artifact = value._artifact_receipt(
                cell_id=cell_id,
                task_id=task_id,
                before=baseline,
                after=artifact_manifest,
                baseline_snapshot=baseline,
                snapshot=artifact_manifest,
                scope=scope,
                fixture_binding={"test_fixture": True},
            )
            implementation_receipt = {
                "stage": "implementation",
                "response": {"status": "completed"},
            }
            implementation_sha256 = controller._exclusive_json(
                attempt / "implementation-receipt.json", implementation_receipt
            )
            artifact_sha256 = controller._exclusive_json(
                attempt / "artifact.json", artifact
            )
            state = lifecycle.record_implementation_complete(
                state,
                value.definition,
                cell_id=cell_id,
                artifact_sha256=artifact_sha256,
                receipt_sha256=implementation_sha256,
                now_monotonic_ns=now + 1,
            )
            if ordinal == failed_after_implementation_ordinal:
                result = value._terminal_payload(
                    cell_id,
                    "PROVIDER_UNAVAILABLE",
                    implementation_receipt,
                    None,
                    None,
                    artifact=artifact,
                    artifact_sha256=artifact_sha256,
                    error="provider unavailable",
                )
                result_sha256 = controller.sha256_bytes(
                    controller.canonical_bytes(result)
                )
                state = lifecycle.record_active_failure(
                    state,
                    value.definition,
                    cell_id=cell_id,
                    status="PROVIDER_UNAVAILABLE",
                    result_sha256=result_sha256,
                    reason="provider unavailable",
                    now_monotonic_ns=now + 2,
                )
                self.assertEqual(
                    controller._exclusive_json(attempt / "result.json", result),
                    result_sha256,
                )
                now += 10
                continue
            verification_receipt = {
                "scope_safe": True,
                "telemetry_safe": True,
                "scope": scope,
                "public": "PASS",
                "hidden": "PASS",
            }
            verification_sha256 = controller._exclusive_json(
                attempt / "verification-receipt.json", verification_receipt
            )
            state = lifecycle.record_verification(
                state,
                value.definition,
                cell_id=cell_id,
                public_passed=True,
                hidden_passed=True,
                scope_safe=True,
                telemetry_safe=True,
                receipt_sha256=verification_sha256,
                now_monotonic_ns=now + 2,
            )
            review_range = controller._build_review_range(
                baseline_root,
                artifact_root,
                baseline_manifest_sha256=baseline["sha256"],
                artifact_manifest_sha256=artifact_manifest["sha256"],
                scope=scope,
                allowed_paths=value.definition["tasks"][task_id]["allowed_paths"],
            )
            review_range_sha256 = controller._exclusive_json(
                attempt / "review-range.json", review_range
            )
            review_workspace = attempt / "review-workspace"
            copied = controller._copy_bound_snapshot(
                artifact_root,
                review_workspace,
                expected_manifest_sha256=artifact_manifest["sha256"],
            )
            workspace_range_sha256 = controller._exclusive_json(
                review_workspace / ".benchmark" / "review-range.json",
                review_range,
            )
            workspace = controller.strict_tree_manifest(review_workspace)
            self.assertEqual(workspace_range_sha256, review_range_sha256)
            review_receipt = {
                "stage": "review",
                "response": {
                    "status": "PASS",
                    "artifact_sha256": artifact_sha256,
                    "review_range_sha256": review_range_sha256,
                    "summary": "clean",
                    "findings": [],
                },
                "artifact_binding": {
                    "artifact_evidence_sha256": artifact_sha256,
                    "baseline_manifest_sha256": baseline["sha256"],
                    "artifact_manifest_sha256": artifact_manifest["sha256"],
                    "review_range_sha256": review_range_sha256,
                    "review_workspace_range_sha256": review_range_sha256,
                    "review_workspace_artifact_manifest_sha256": copied["sha256"],
                    "review_workspace_before_sha256": workspace["sha256"],
                    "review_workspace_after_sha256": workspace["sha256"],
                    "baseline_before_sha256": baseline["sha256"],
                    "baseline_after_sha256": baseline["sha256"],
                    "artifact_before_sha256": artifact_manifest["sha256"],
                    "artifact_after_sha256": artifact_manifest["sha256"],
                },
            }
            review_sha256 = controller._exclusive_json(
                attempt / "review-receipt.json", review_receipt
            )
            result = value._terminal_payload(
                cell_id,
                "ACCEPTED",
                implementation_receipt,
                verification_receipt,
                review_receipt,
                artifact=artifact,
                artifact_sha256=artifact_sha256,
            )
            result_sha256 = controller.sha256_bytes(
                controller.canonical_bytes(result)
            )
            state = lifecycle.record_review(
                state,
                value.definition,
                cell_id=cell_id,
                status="PASS",
                finding_count=0,
                artifact_sha256=artifact_sha256,
                review_range_sha256=review_range_sha256,
                receipt_sha256=review_sha256,
                result_sha256=result_sha256,
                now_monotonic_ns=now + 3,
            )
            self.assertEqual(
                controller._exclusive_json(attempt / "result.json", result),
                result_sha256,
            )
            candidate = attempt / "candidate"
            candidate.mkdir()
            (candidate / "mutable").write_text("not evidence", encoding="utf-8")
            if ordinal == 0:
                audit = {
                    "status": "ACCEPT",
                    "definition_sha256": value.definition_sha256,
                    "package_sha256": value.package_sha256,
                    "canary_result_sha256": result_sha256,
                    "canary_artifact_sha256": artifact_sha256,
                    "auditor": "independent-test-auditor",
                    "independent_of_candidate_and_controller": True,
                    "findings": [],
                    "summary": "accepted",
                }
                audit_sha256 = controller._atomic_json(
                    value.root / "canary-audit.json", audit
                )
                state = lifecycle.record_canary_audit(
                    state,
                    value.definition,
                    audit=audit,
                    audit_sha256=audit_sha256,
                )
            now += 10
        lifecycle.save_state(value.state_path, state, value.definition)
        return state

    def test_collect_rejects_incomplete_or_unsafe_state_before_publish(self) -> None:
        value = self.make_controller()
        base_terminal = lambda cell_id, status="ACCEPTED": {
            "cell_id": cell_id,
            "terminal": {"status": status},
        }
        cases = {
            "active": {
                "active_cell": {"cell_id": "a"},
                "run_order": ["a"],
                "terminal_cells": [],
                "canary_audit": None,
            },
            "partial": {
                "active_cell": None,
                "run_order": ["a", "b"],
                "terminal_cells": [base_terminal("a")],
                "canary_audit": {"status": "ACCEPT"},
            },
            "out_of_order": {
                "active_cell": None,
                "run_order": ["a", "b"],
                "terminal_cells": [base_terminal("b"), base_terminal("a")],
                "canary_audit": {"status": "ACCEPT"},
            },
            "unsafe": {
                "active_cell": None,
                "run_order": ["a"],
                "terminal_cells": [base_terminal("a", "BOUNDARY_FAILURE")],
                "canary_audit": {"status": "ACCEPT"},
            },
            "missing_audit": {
                "active_cell": None,
                "run_order": ["a"],
                "terminal_cells": [base_terminal("a")],
                "canary_audit": None,
            },
            "rejected_audit": {
                "active_cell": None,
                "run_order": ["a"],
                "terminal_cells": [base_terminal("a")],
                "canary_audit": {"status": "REJECT"},
            },
        }
        for name, state in cases.items():
            with (
                self.subTest(name=name),
                mock.patch.object(value, "_load_state", return_value=state),
                mock.patch.object(controller, "_exclusive_json") as publish,
                self.assertRaises(controller.ControllerError),
            ):
                value.collect()
            publish.assert_not_called()
            self.assertFalse((value.root / "collection.json").exists())

    def test_complete_collection_uses_snapshots_after_candidates_are_deleted(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state = self._complete_evidence(value)
        for cell_id in state["run_order"]:
            candidate = value.root / "attempts" / cell_id / "candidate"
            (candidate / "mutable").unlink()
            candidate.rmdir()

        collection = value.collect()

        self.assertEqual(
            [result["cell_id"] for result in collection["results"]],
            state["run_order"],
        )
        self.assertEqual(
            collection["state_sha256"], controller.sha256_file(value.state_path)
        )
        self.assertTrue((value.root / "collection.json").is_file())

    def test_complete_collection_includes_scored_failures(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state = self._complete_evidence(value, failed_ordinal=1)

        collection = value.collect()

        self.assertEqual(
            [result["cell_id"] for result in collection["results"]],
            state["run_order"],
        )
        self.assertEqual(collection["results"][1]["status"], "IMPLEMENTATION_FAILED")

    def test_collection_requires_artifact_and_snapshot_for_completed_implementation(self) -> None:
        for missing in ("artifact", "snapshot"):
            config = replace(
                self.config,
                state_root=self.root / f"state-missing-{missing}",
            )
            value = controller.Controller(config)
            value.root.mkdir(parents=True)
            self.prepare_runnable(value)
            state = self._complete_evidence(
                value,
                failed_after_implementation_ordinal=4,
            )
            attempt = value.root / "attempts" / state["run_order"][4]
            if missing == "artifact":
                (attempt / "artifact.json").unlink()
            else:
                controller.shutil.rmtree(attempt / "artifact-snapshot")

            expected = (
                "expected artifact evidence"
                if missing == "artifact"
                else "artifact snapshot is not a real directory"
            )
            with self.subTest(missing=missing), self.assertRaisesRegex(
                controller.ControllerError,
                expected,
            ):
                value.collect()

    def test_evaluator_uses_only_accepted_artifacts_after_scored_failure(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state = self._complete_evidence(value, failed_ordinal=4)
        collection = value.collect()

        bundle, mapping, snapshot_bindings = value._evaluator_payloads(
            state, "fixed-seed"
        )

        self.assertEqual(len(bundle["tasks"]), 3)
        karpathy = next(
            task
            for task in mapping["tasks"].values()
            if task["task_id"] == "karpathy-pointer"
        )
        self.assertEqual(len(karpathy["variants"]), 2)
        self.assertNotIn(
            state["run_order"][4], karpathy["variants"].values()
        )
        self.assertNotIn(state["run_order"][4], snapshot_bindings)
        self.assertEqual(collection["results"][4]["status"], "IMPLEMENTATION_FAILED")

    def test_evaluator_requires_two_accepted_artifacts_per_task(self) -> None:
        value = self.make_controller()
        self.prepare_runnable(value)
        state = self._complete_evidence(value, failed_ordinal=1)
        value.collect()

        with self.assertRaisesRegex(
            controller.ControllerError,
            "at least two accepted artifacts",
        ):
            value._evaluator_payloads(state, "fixed-seed")


class FakeCodexExecutableTests(ControllerCase):
    def test_session_entry_cap_stops_before_consuming_remaining_entries(self) -> None:
        codex_home = self.root / "bounded-codex-home"
        sessions = codex_home / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "rollout.jsonl").write_text("{}\n", encoding="utf-8")
        (sessions / "second.txt").write_text("second\n", encoding="utf-8")
        with controller.os.scandir(sessions) as iterator:
            entries = list(iterator)

        class GuardedScandir:
            def __init__(self) -> None:
                self.index = 0

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def __iter__(self):
                return self

            def __next__(self):
                if self.index >= 2:
                    raise AssertionError("scanner consumed past the entry cap")
                entry = entries[self.index]
                self.index += 1
                return entry

        with (
            mock.patch.object(controller, "MAX_CODEX_STATE_ENTRIES", 1),
            mock.patch.object(
                controller.os, "scandir", return_value=GuardedScandir()
            ),
            self.assertRaises(controller.BoundaryFailure),
        ):
            controller._snapshot_codex_rollout(
                codex_home,
                self.root / "bounded-rollout.jsonl",
                required=False,
            )

    def _prepare_stage(
        self,
        *,
        leak_to_stderr: bool = False,
        provider_error: bool = False,
        unclassified_error: bool = False,
        rollout_variant: str = "ordinary",
    ) -> tuple[controller.Controller, dict, Path, Path, str]:
        access_token = "access-token-routing-v3-unique-123456789"
        self.files["auth"].write_text(
            json.dumps(
                {
                    "OPENAI_API_KEY": None,
                    "tokens": {
                        "access_token": access_token,
                        "account_id": "account-routing-v3-unique-123456789",
                        "id_token": "id-token-routing-v3-unique-123456789",
                        "refresh_token": "refresh-token-routing-v3-unique-123456789",
                    },
                }
            ),
            encoding="utf-8",
        )
        self.files["auth"].chmod(0o600)
        fake = self.root / "fake-codex"
        leak_statement = (
            "print(auth['tokens']['access_token'], file=sys.stderr)"
            if leak_to_stderr
            else "pass"
        )
        terminal_statement = (
            "print(json.dumps({'type':'error','error':{'code':'service_unavailable'}})); sys.exit(1)"
            if provider_error
            else ("sys.exit(2)" if unclassified_error else "pass")
        )
        rollout_statements = {
            "ordinary": "pass",
            "multiple": "(p.parent/'second.jsonl').write_text(p.read_text())",
            "symlink": "target=p.parent/'rollout.txt'; p.rename(target); p.symlink_to(target)",
            "hardlink": "os.link(p,p.parent/'rollout-copy.txt')",
            "directory_symlink": "target=pathlib.Path(os.environ['HOME'])/'hidden-sessions'; target.mkdir(); p.rename(target/'hidden.jsonl'); (p.parent/'linked').symlink_to(target,target_is_directory=True)",
        }
        anomaly_statement = rollout_statements[rollout_variant]
        script = """#!/usr/bin/python3
import json, os, pathlib, re, sys
args=sys.argv[1:]
last=pathlib.Path(args[args.index('--output-last-message')+1])
model=args[args.index('-m')+1]
assert re.fullmatch(r'routing-v3-[a-f0-9]{32}', os.environ['ROUTING_RUN_MARKER'])
assert pathlib.Path(os.environ['ROUTING_CANDIDATE_ACP']).name == 'acp.ts'
auth_path=pathlib.Path(os.environ['CODEX_HOME'])/'auth.json'
auth_bytes=auth_path.read_bytes()
auth=json.loads(auth_bytes)
for root in ('HOME','CODEX_HOME','CODEX_SQLITE_HOME'):
    duplicate=pathlib.Path(os.environ[root])/('duplicate-auth-' + root.lower() + '.json')
    duplicate.parent.mkdir(parents=True,exist_ok=True)
    duplicate.write_bytes(auth_bytes)
__LEAK_STATEMENT__
response={'status':'completed','summary':'done','changed_paths':[],'public_verifier':'not_run','blocker':None}
last.write_text(json.dumps(response))
usage={'input_tokens':100,'cached_input_tokens':40,'cache_write_input_tokens':7,'output_tokens':20,'reasoning_output_tokens':10}
thread='thread-fake'
for event in ({'type':'thread.started','thread_id':thread},{'type':'turn.started'},{'type':'turn.completed','usage':usage}): print(json.dumps(event,separators=(',',':')))
rollout=[
 {'type':'session_meta','payload':{'id':thread,'cli_version':'0.149.1','model_provider':'openai'}},
 {'type':'turn_context','payload':{'turn_id':'turn-1','model':model,'effort':'high','active_permission_profile':{'id':'routing_candidate'}}},
 {'type':'event_msg','payload':{'type':'token_count','info':{'last_token_usage':usage}}},
 {'type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-1'}}]
p=pathlib.Path(os.environ['CODEX_HOME'])/'sessions'/'rollout.jsonl'; p.parent.mkdir(parents=True)
p.write_text(''.join(json.dumps(x,separators=(',',':'))+'\\n' for x in rollout))
__ROLLOUT_ANOMALY__
__TERMINAL_STATEMENT__
"""
        fake.write_text(
            script.replace("__LEAK_STATEMENT__", leak_statement)
            .replace("__ROLLOUT_ANOMALY__", anomaly_statement)
            .replace("__TERMINAL_STATEMENT__", terminal_statement)
        )
        fake.chmod(0o700)
        config = replace(self.config, codex_executable=fake)
        value = controller.Controller(config, controller.ControllerHooks(quota=lambda: quota_snapshot()))
        value.root.mkdir(parents=True)
        runtime_bin = value.root / "runtime" / "bin"
        runtime_bin.mkdir(parents=True)
        runtime_node = runtime_bin / "node"
        runtime_node.write_bytes(self.files["node"].read_bytes())
        runtime_node.chmod(0o500)
        value.definition["pinned_runtime"]["node_sha256"] = controller.sha256_file(runtime_node)
        candidate = value.root / "candidate"
        candidate.mkdir()
        (candidate / "TASK.md").write_text("task")
        candidate_acp = candidate / "daemon" / "src" / "acp.ts"
        candidate_acp.parent.mkdir(parents=True)
        candidate_acp.write_text("export class AcpClient {}\n")
        attempt = value.root / "attempt"
        attempt.mkdir()
        kwargs = {
            "attempt": attempt,
            "stage": "implementation",
            "task_id": "openbot-acp",
            "candidate": candidate,
            "model": "gpt-5.6-terra",
            "effort": "high",
            "schema": ROOT / "schemas" / "implementation.schema.json",
            "prompt": "prompt",
            "reviewer": False,
            "writable_paths": (".runner-tmp",),
            "deadline": time.monotonic() + 10,
        }
        return value, kwargs, attempt, candidate, access_token

    def test_stage_binds_rollout_then_discards_all_runtime_state(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage()
        receipt = value._codex_stage(**kwargs)
        stage_root = attempt / "implementation"

        self.assertTrue(receipt["telemetry"]["valid"])
        self.assertEqual(
            receipt["telemetry"]["rollout"]["active_permission_profile"],
            "routing_candidate",
        )
        self.assertEqual(receipt["quota"]["before_raw_sha256"], "a" * 64)
        self.assertEqual(
            receipt["evidence_files"]["rollout_jsonl"],
            "implementation/rollout.jsonl",
        )
        evidence = receipt["evidence_files"]
        self.assertEqual(
            set(evidence), {"exec_jsonl", "rollout_jsonl", "stderr", "last_message"}
        )
        for relative in evidence.values():
            self.assertTrue((attempt / relative).is_file())
        self.assertEqual(
            {path.name for path in stage_root.iterdir()},
            {"exec.jsonl", "rollout.jsonl", "stderr.txt", "last-message.json"},
        )
        for discarded in ("home", "codex-home", "sqlite", "auth-target.json"):
            self.assertFalse((stage_root / discarded).exists())
        self.assertFalse((candidate / ".runner-tmp").exists())
        self.assertEqual(
            receipt["evidence_retention"],
            {
                "status": "PASS",
                "exact_allowlist_satisfied": True,
                "retained_files": [
                    "exec.jsonl",
                    "last-message.json",
                    "rollout.jsonl",
                    "stderr.txt",
                ],
                "retained_artifacts": [
                    {
                        "name": name,
                        "bytes": (stage_root / name).stat().st_size,
                        "sha256": controller.sha256_file(stage_root / name),
                    }
                    for name in (
                        "exec.jsonl",
                        "last-message.json",
                        "rollout.jsonl",
                        "stderr.txt",
                    )
                ],
                "discarded_runtime_roots": [
                    "home",
                    "codex-home",
                    "sqlite",
                    ".runner-tmp",
                ],
                "runtime_roots_absent": True,
                "auth_destination_absent": True,
                "retained_artifacts_scanned": [
                    "exec.jsonl",
                    "last-message.json",
                    "rollout.jsonl",
                    "stderr.txt",
                ],
                "auth_material_scan": "PASS",
            },
        )

    def test_stage_deletes_all_evidence_when_stderr_contains_auth_value(self) -> None:
        value, kwargs, attempt, candidate, access_token = self._prepare_stage(
            leak_to_stderr=True
        )
        with self.assertRaises(controller.BoundaryFailure) as raised:
            value._codex_stage(**kwargs)

        self.assertNotIn(access_token, str(raised.exception))
        self.assertEqual(list((attempt / "implementation").iterdir()), [])
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_pre_run_quota_failure_cleans_every_fresh_runtime_root(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage()
        value.hooks.quota = mock.Mock(side_effect=controller.TelemetryFailure("quota"))
        with self.assertRaises(controller.TelemetryFailure):
            value._codex_stage(**kwargs)

        self.assertEqual(list((attempt / "implementation").iterdir()), [])
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_setup_failure_cleans_every_fresh_runtime_root(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage()
        with (
            mock.patch.object(
                value,
                "_profile_runtime_roots",
                side_effect=controller.ControllerError("setup"),
            ),
            self.assertRaises(controller.ControllerError),
        ):
            value._codex_stage(**kwargs)

        self.assertEqual(list((attempt / "implementation").iterdir()), [])
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_provider_failure_retains_clean_rollout_but_no_runtime_state(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage(
            provider_error=True
        )
        with self.assertRaises(controller.ProviderUnavailable) as raised:
            value._codex_stage(**kwargs)

        stage_root = attempt / "implementation"
        self.assertIsInstance(raised.exception.evidence, dict)
        self.assertIn("process", raised.exception.evidence)
        stage_evidence = raised.exception.evidence["stage_evidence"]
        self.assertEqual(stage_evidence["stage"], "implementation")
        self.assertEqual(
            {path.name for path in stage_root.iterdir()},
            {"exec.jsonl", "rollout.jsonl", "stderr.txt", "last-message.json"},
        )
        self.assertEqual(
            stage_evidence["files"],
            [
                {
                    "path": f"implementation/{name}",
                    "bytes": (stage_root / name).stat().st_size,
                    "sha256": controller.sha256_file(stage_root / name),
                }
                for name in (
                    "exec.jsonl",
                    "last-message.json",
                    "rollout.jsonl",
                    "stderr.txt",
                )
            ],
        )
        self.assertEqual(
            stage_evidence["retention"]["retained_artifacts"],
            [
                {
                    "name": name,
                    "bytes": (stage_root / name).stat().st_size,
                    "sha256": controller.sha256_file(stage_root / name),
                }
                for name in (
                    "exec.jsonl",
                    "last-message.json",
                    "rollout.jsonl",
                    "stderr.txt",
                )
            ],
        )
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_unclassified_nonzero_exit_attaches_bound_stage_evidence(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage(
            unclassified_error=True
        )
        with self.assertRaises(controller.ControllerError) as raised:
            value._codex_stage(**kwargs)

        self.assertNotIsInstance(raised.exception, controller.TerminalControllerError)
        stage_root = attempt / "implementation"
        stage_evidence = raised.exception.evidence["stage_evidence"]
        self.assertEqual(
            stage_evidence["files"],
            [
                {
                    "path": f"implementation/{name}",
                    "bytes": (stage_root / name).stat().st_size,
                    "sha256": controller.sha256_file(stage_root / name),
                }
                for name in (
                    "exec.jsonl",
                    "last-message.json",
                    "rollout.jsonl",
                    "stderr.txt",
                )
            ],
        )
        self.assertFalse((candidate / ".runner-tmp").exists())

    def _assert_provider_rollout_anomaly_is_boundary_failure(
        self, rollout_variant: str
    ) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage(
            provider_error=True,
            rollout_variant=rollout_variant,
        )
        with self.assertRaises(controller.BoundaryFailure):
            value._codex_stage(**kwargs)

        stage_root = attempt / "implementation"
        for discarded in ("home", "codex-home", "sqlite", "auth-target.json"):
            self.assertFalse((stage_root / discarded).exists())
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_provider_failure_with_multiple_rollouts_is_boundary_failure(self) -> None:
        self._assert_provider_rollout_anomaly_is_boundary_failure("multiple")

    def test_provider_failure_with_symlinked_rollout_is_boundary_failure(self) -> None:
        self._assert_provider_rollout_anomaly_is_boundary_failure("symlink")

    def test_provider_failure_with_hardlinked_rollout_is_boundary_failure(self) -> None:
        self._assert_provider_rollout_anomaly_is_boundary_failure("hardlink")

    def test_provider_failure_with_directory_symlink_is_boundary_failure(self) -> None:
        self._assert_provider_rollout_anomaly_is_boundary_failure("directory_symlink")

    def test_provider_failure_with_unreadable_session_tree_is_boundary_failure(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage(
            provider_error=True
        )
        sessions = attempt / "implementation" / "codex-home" / "sessions"
        original_scandir = controller.os.scandir
        denied = False

        def deny_sessions(path):
            nonlocal denied
            if not denied and not isinstance(path, int) and Path(path) == sessions:
                denied = True
                raise PermissionError("session tree denied")
            return original_scandir(path)

        with (
            mock.patch.object(controller.os, "scandir", side_effect=deny_sessions),
            self.assertRaises(controller.BoundaryFailure),
        ):
            value._codex_stage(**kwargs)

        self.assertTrue(denied)
        stage_root = attempt / "implementation"
        for discarded in ("home", "codex-home", "sqlite", "auth-target.json"):
            self.assertFalse((stage_root / discarded).exists())
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_runtime_root_symlink_is_unlinked_without_touching_target(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage()
        external = self.root / "external-runtime"
        external.mkdir()
        sentinel = external / "sentinel"
        sentinel.write_text("keep", encoding="utf-8")

        def replace_codex_home() -> tuple[Path, ...]:
            codex_home = attempt / "implementation" / "codex-home"
            codex_home.rmdir()
            codex_home.symlink_to(external, target_is_directory=True)
            raise controller.ControllerError("setup")

        with (
            mock.patch.object(value, "_profile_runtime_roots", replace_codex_home),
            self.assertRaises(controller.BoundaryFailure),
        ):
            value._codex_stage(**kwargs)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertFalse((attempt / "implementation" / "codex-home").exists())
        self.assertFalse((candidate / ".runner-tmp").exists())

    def test_stage_root_symlink_is_not_traversed_during_cleanup(self) -> None:
        value, kwargs, attempt, candidate, _access_token = self._prepare_stage()
        external = self.root / "external-stage"
        external.mkdir()
        sentinel = external / "sentinel"
        sentinel.write_text("keep", encoding="utf-8")

        def replace_stage_root() -> tuple[Path, ...]:
            stage_root = attempt / "implementation"
            stage_root.rename(self.root / "displaced-stage")
            stage_root.symlink_to(external, target_is_directory=True)
            raise controller.ControllerError("setup")

        with (
            mock.patch.object(value, "_profile_runtime_roots", replace_stage_root),
            self.assertRaises(controller.BoundaryFailure),
        ):
            value._codex_stage(**kwargs)

        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        self.assertFalse((attempt / "implementation").exists())
        self.assertFalse((candidate / ".runner-tmp").exists())


if __name__ == "__main__":
    unittest.main()
