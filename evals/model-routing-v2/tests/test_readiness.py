from __future__ import annotations

from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "model_routing_v2_readiness", ROOT / "readiness.py"
)
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)

ENTRYPOINT_SPEC = importlib.util.spec_from_file_location(
    "model_routing_v2_verifier_entrypoint", ROOT / "verifiers/entrypoint.py"
)
assert ENTRYPOINT_SPEC and ENTRYPOINT_SPEC.loader
verifier_entrypoint = importlib.util.module_from_spec(ENTRYPOINT_SPEC)
ENTRYPOINT_SPEC.loader.exec_module(verifier_entrypoint)


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repository), *arguments],
        env=readiness.safe_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class DefinitionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = json.loads(
            (ROOT / "definition.json").read_text(encoding="utf-8")
        )

    def test_current_definition_is_the_only_accepted_semantics(self) -> None:
        readiness.validate_definition_files(self.definition)

    def test_semantic_drift_is_rejected(self) -> None:
        mutations = {
            "unsafe allowed path": lambda value: value["tasks"]["use-grok"].__setitem__(
                "allowed_paths", ["../../outside"]
            ),
            "arbitrary route": lambda value: value["routes"]["adaptive"]["use-grok"].update(
                {"model": "arbitrary", "effort": "low"}
            ),
            "arbitrary cells": lambda value: value["lifecycle"].__setitem__(
                "run_order", [f"arbitrary-{index}" for index in range(6)]
            ),
            "repair enabled": lambda value: value["reviewer"].__setitem__(
                "repair_calls", 1
            ),
            "paid stage deadline changed": lambda value: value["lifecycle"][
                "model_stage_timeout"
            ].__setitem__("maximum_seconds", 599),
            "runtime network": lambda value: value["offline_verifier_runtime"].__setitem__(
                "network", "host"
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                value = deepcopy(self.definition)
                mutate(value)
                with self.assertRaises(readiness.ReadinessError):
                    readiness.validate_definition_files(value)

    def test_safe_environment_excludes_user_configuration_and_tools(self) -> None:
        environment = readiness.safe_environment()
        self.assertEqual(environment["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")
        self.assertNotIn("SSH_AUTH_SOCK", environment)


class SourceIsolationTests(unittest.TestCase):
    def test_symlinked_git_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            metadata = root / "metadata"
            metadata.mkdir()
            (source / ".git").symlink_to(metadata, target_is_directory=True)
            with self.assertRaises(readiness.ReadinessError):
                readiness.clone_source(source, root / "clone.git")

    def test_repository_fsmonitor_cannot_execute_during_object_import(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            source.mkdir()
            git(source, "init", "-q")
            (source / "tracked.txt").write_text("trusted\n", encoding="utf-8")
            git(source, "add", "tracked.txt")
            git(
                source,
                "-c",
                "user.name=Readiness Test",
                "-c",
                "user.email=readiness@example.invalid",
                "commit",
                "-q",
                "-m",
                "fixture",
            )
            commit = git(source, "rev-parse", "HEAD")
            tree = git(source, "rev-parse", "HEAD^{tree}")
            sentinel = root / "fsmonitor-executed"
            monitor = root / "monitor.sh"
            monitor.write_text(
                f"#!/bin/sh\n/usr/bin/touch '{sentinel}'\nexit 0\n",
                encoding="utf-8",
            )
            monitor.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            git(source, "config", "core.fsmonitor", str(monitor))

            bare = root / "controller" / "source.git"
            bare.parent.mkdir()
            readiness.clone_source(source, bare)
            evidence = readiness.verify_source_objects(
                source,
                bare,
                base_commit=commit,
                base_tree=tree,
                historical_commit=commit,
                historical_tree=tree,
            )
            readiness.finish_source_check(bare, evidence)
            self.assertFalse(sentinel.exists())
            self.assertTrue(evidence["object_evidence_rechecked"])

    def test_known_good_patch_scope_is_recomputed_from_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "inside.txt").write_text("before\n", encoding="utf-8")
            before = readiness.build_tree_manifest(workspace)
            patch = root / "change.patch"
            patch.write_text(
                "diff --git a/inside.txt b/inside.txt\n"
                "index 90be1bd..81c545e 100644\n"
                "--- a/inside.txt\n"
                "+++ b/inside.txt\n"
                "@@ -1 +1 @@\n"
                "-before\n"
                "+after\n",
                encoding="utf-8",
            )
            with self.assertRaises(readiness.ReadinessError):
                readiness.apply_known_good_patch(
                    workspace,
                    patch,
                    before_manifest=before,
                    allowed_paths=["different.txt"],
                )


class FileIdentityTests(unittest.TestCase):
    def test_hard_linked_evidence_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            first = root / "first"
            second = root / "second"
            first.write_text("evidence", encoding="utf-8")
            os.link(first, second)
            with self.assertRaises(readiness.ReadinessError):
                readiness.read_file_bytes(first)


class VerifierWorkspaceBindingTests(unittest.TestCase):
    def test_container_entrypoint_rejects_mounted_manifest_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            workspace.mkdir()
            (workspace / "attacker.txt").write_text("attacker\n", encoding="utf-8")
            stderr = io.StringIO()
            with mock.patch.object(sys, "stderr", stderr):
                returncode = verifier_entrypoint.main(
                    [
                        "--workspace",
                        str(workspace),
                        "--expected-manifest-sha256",
                        "a" * 64,
                        "--verifier",
                        "verifiers/public/use_grok_three_host.py",
                    ]
                )
            self.assertEqual(returncode, 2)
            self.assertIn("container workspace snapshot differs", stderr.getvalue())

    def test_container_entrypoint_runs_only_against_private_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw) / "workspace"
            workspace.mkdir()
            source = workspace / "trusted.txt"
            source.write_text("trusted\n", encoding="utf-8")
            expected = readiness.build_tree_manifest(workspace)["sha256"]
            observed: list[str] = []

            def mutate_host_and_read_snapshot(
                _verifier: Path, arguments: list[str]
            ) -> int:
                source.write_text("mutated\n", encoding="utf-8")
                snapshot = Path(arguments[arguments.index("--workspace") + 1])
                observed.append((snapshot / "trusted.txt").read_text(encoding="utf-8"))
                self.assertNotEqual(snapshot, workspace)
                return 0

            with mock.patch.object(
                verifier_entrypoint,
                "_run_verifier",
                side_effect=mutate_host_and_read_snapshot,
            ):
                returncode = verifier_entrypoint.main(
                    [
                        "--workspace",
                        str(workspace),
                        "--expected-manifest-sha256",
                        expected,
                        "--verifier",
                        "verifiers/public/use_grok_three_host.py",
                    ]
                )
            self.assertEqual(returncode, 0)
            self.assertEqual(observed, ["trusted\n"])
            self.assertEqual(source.read_text(encoding="utf-8"), "mutated\n")

    def test_verifier_entrypoint_rejects_aba_mounted_rebind(self) -> None:
        definition = json.loads((ROOT / "definition.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workspace = root / "workspace"
            replacement = root / "replacement"
            attacker = root / "attacker"
            workspace.mkdir()
            (workspace / "trusted.txt").write_text("trusted\n", encoding="utf-8")
            expected = readiness.build_tree_manifest(workspace)["sha256"]

            def replace_on_run(
                command: list[str], **_kwargs: object
            ) -> subprocess.CompletedProcess[bytes]:
                if len(command) > 1 and command[1] == "run":
                    self.assertIn("/package/verifiers/entrypoint.py", command)
                    expected_index = command.index("--expected-manifest-sha256") + 1
                    self.assertEqual(command[expected_index], expected)
                    workspace.rename(replacement)
                    workspace.mkdir()
                    (workspace / "attacker.txt").write_text("attacker\n", encoding="utf-8")
                    workspace.rename(attacker)
                    replacement.rename(workspace)
                    return subprocess.CompletedProcess(command, 2, b"", b"mismatch")
                return subprocess.CompletedProcess(command, 0, b"", b"")

            with mock.patch.object(readiness, "run_command", side_effect=replace_on_run):
                result = readiness.verifier_status(
                    ROOT / "verifiers/public/use_grok_three_host.py",
                    workspace,
                    task_id="use-grok",
                    hidden=False,
                    workspace_manifest_sha256=expected,
                    definition=definition,
                )
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["returncode"], 2)


if __name__ == "__main__":
    unittest.main()
