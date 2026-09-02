from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("model_routing_v3_fixtures", ROOT / "fixtures.py")
assert SPEC and SPEC.loader
fixtures = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fixtures
SPEC.loader.exec_module(fixtures)


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repository), *arguments],
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": "/var/empty",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_TERMINAL_PROMPT": "0",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def commit(repository: Path, message: str) -> tuple[str, str]:
    git(repository, "add", ".")
    git(
        repository,
        "-c",
        "user.name=Fixture Test",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-q",
        "-m",
        message,
    )
    return git(repository, "rev-parse", "HEAD"), git(repository, "rev-parse", "HEAD^{tree}")


class FrozenDependencyTests(unittest.TestCase):
    def test_current_v2_manifest_is_verified_before_loading(self) -> None:
        definition = fixtures.load_definition()
        loaded = fixtures.load_frozen_v2(definition)
        self.assertEqual(
            loaded.manifest_sha256,
            definition["frozen_v2_dependency"]["tree_manifest_sha256"],
        )
        drifted = deepcopy(definition)
        drifted["frozen_v2_dependency"]["tree_manifest_sha256"] = "0" * 64
        with self.assertRaises(fixtures.FixtureError):
            fixtures.load_frozen_v2(drifted)

    def test_rejects_project_local_configuration_channels(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".codex").mkdir()
            (root / ".codex" / "config.toml").write_text("model = 'wrong'\n")
            with self.assertRaises(fixtures.FixtureError):
                fixtures.reject_candidate_configuration(root)


class OpenBotFixtureTests(unittest.TestCase):
    def _make_runtime(self, root: Path) -> Path:
        runtime = root / "runtime"
        packages = (
            runtime / "tsx",
            runtime / "esbuild",
            runtime / "@esbuild" / "darwin-arm64",
        )
        for index, package in enumerate(packages):
            package.mkdir(parents=True)
            binary = package / "runtime.bin"
            binary.write_bytes(f"runtime-{index}\n".encode())
            binary.chmod(0o755 if index == 2 else 0o644)
            outside = root / f"outside-{index}.bin"
            os.link(binary, outside)
            self.assertEqual(binary.stat().st_nlink, 2)
        return runtime

    def _make_repo(self, root: Path, *, change_outside_scope: bool = False) -> tuple[Path, str, str, str, str]:
        repository = root / "source"
        repository.mkdir()
        git(repository, "init", "-q")
        source = repository / "daemon" / "src"
        source.mkdir(parents=True)
        (source / "acp.ts").write_text("export const state = 'base';\n", encoding="utf-8")
        (repository / "README.md").write_text("base\n", encoding="utf-8")
        base_commit, base_tree = commit(repository, "base")
        (source / "acp.ts").write_text("export const state = 'accepted';\n", encoding="utf-8")
        if change_outside_scope:
            (repository / "README.md").write_text("historical drift\n", encoding="utf-8")
        historical_commit, historical_tree = commit(repository, "accepted")
        return repository, base_commit, base_tree, historical_commit, historical_tree

    def _definition(self, repository_data: tuple[Path, str, str, str, str], runtime: Path) -> dict:
        _, base_commit, base_tree, historical_commit, historical_tree = repository_data
        definition = fixtures.load_definition()
        task = definition["tasks"]["openbot-acp"]
        task["base_commit"] = base_commit
        task["base_tree"] = base_tree
        task["historical_source_commit"] = historical_commit
        task["historical_source_tree"] = historical_tree
        definition["pinned_runtime"]["tsx_tree_sha256"] = fixtures.content_tree_sha256(runtime / "tsx")
        definition["pinned_runtime"]["esbuild_tree_sha256"] = fixtures.content_tree_sha256(runtime / "esbuild")
        definition["pinned_runtime"]["esbuild_darwin_arm64_tree_sha256"] = fixtures.content_tree_sha256(
            runtime / "@esbuild" / "darwin-arm64"
        )
        return definition

    def test_builds_exact_answer_hidden_fixture_with_single_link_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repository_data = self._make_repo(root)
            runtime = self._make_runtime(root)
            definition = self._definition(repository_data, runtime)
            repository = repository_data[0]
            status_before = git(repository, "status", "--short")
            controller = root / "controller"
            controller.mkdir()

            evidence = fixtures.build_task_fixture(
                definition=definition,
                task_id="openbot-acp",
                source_repo=repository,
                controller_root=controller,
                openbot_runtime_source=runtime,
            )

            candidate = Path(evidence["paths"]["candidate"])
            known_good = Path(evidence["paths"]["known_good"])
            self.assertEqual(evidence["changed_paths"], ["daemon/src/acp.ts"])
            self.assertIn(".benchmark/public/openbot_acp_public.test.ts", evidence["public_overlay_paths"])
            self.assertIn(".benchmark/public/implementation.schema.json", evidence["public_overlay_paths"])
            self.assertFalse((candidate / ".git").exists())
            self.assertEqual((candidate / "daemon/src/acp.ts").read_text(), "export const state = 'base';\n")
            self.assertEqual((known_good / "daemon/src/acp.ts").read_text(), "export const state = 'accepted';\n")
            for workspace in (candidate, known_good):
                for package, _ in fixtures.RUNTIME_PACKAGES:
                    for path in (workspace / "node_modules" / package).rglob("*"):
                        if path.is_file():
                            self.assertEqual(path.stat().st_nlink, 1)
            self.assertEqual(git(repository, "status", "--short"), status_before)
            self.assertTrue(evidence["source"]["object_evidence_rechecked"])

    def test_openbot_known_good_uses_only_the_declared_historical_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repository_data = self._make_repo(root, change_outside_scope=True)
            runtime = self._make_runtime(root)
            definition = self._definition(repository_data, runtime)
            controller = root / "controller"
            controller.mkdir()
            evidence = fixtures.build_task_fixture(
                definition=definition,
                task_id="openbot-acp",
                source_repo=repository_data[0],
                controller_root=controller,
                openbot_runtime_source=runtime,
            )
            known_good = Path(evidence["paths"]["known_good"])
            self.assertEqual(evidence["changed_paths"], ["daemon/src/acp.ts"])
            self.assertEqual((known_good / "README.md").read_text(), "base\n")

    def test_rejects_controller_root_symlink_into_source_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repository_data = self._make_repo(root)
            repository = repository_data[0]
            controller = root / "controller-alias"
            controller.symlink_to(repository / "daemon", target_is_directory=True)
            status_before = git(repository, "status", "--short")
            state_path = repository / "daemon" / "openbot-acp"

            with self.assertRaisesRegex(
                fixtures.FixtureError,
                "controller root must not be inside the source repository",
            ):
                fixtures.build_task_fixture(
                    definition=fixtures.load_definition(),
                    task_id="openbot-acp",
                    source_repo=repository,
                    controller_root=controller,
                )

            self.assertFalse(state_path.exists())
            self.assertEqual(git(repository, "status", "--short"), status_before)


if __name__ == "__main__":
    unittest.main()
