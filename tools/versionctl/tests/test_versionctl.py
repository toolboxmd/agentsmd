from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src"
FIXTURE_MATRIX = Path(__file__).parent / "fixtures" / "case-matrix.json"


class FixtureRepository:
    def __init__(self, *, mirrors: list[dict[str, str]] | None = None) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.mirrors = mirrors or [
            {"path": "pyproject.toml", "pointer": "/project/version"}
        ]
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Versionctl Tests")
        self.git("config", "user.email", "versionctl@example.invalid")

    def close(self) -> None:
        self._temporary.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def write(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, relative: str) -> str:
        return (self.root / relative).read_text(encoding="utf-8")

    def policy(self) -> None:
        self.write(
            ".version-policy.json",
            json.dumps(
                {
                    "schema": 1,
                    "bumpPolicy": "every-deliverable",
                    "versionSource": "VERSION",
                    "tagPattern": "v{version}",
                    "tagPolicy": "every-version",
                    "githubReleasePolicy": "on-version-commit",
                    "distributionPolicy": "released-tags-only",
                    "publishPolicy": "manual",
                    "releaseBranch": "main",
                    "wipPrefixes": ["wip:"],
                    "mirrors": self.mirrors,
                },
                indent=2,
            )
            + "\n",
        )

    def seed(self, version: str = "0.1.0", *, tag: bool = True) -> str:
        self.policy()
        self.write("README.md", "# Fixture\n")
        self.write("VERSION", f"{version}\n")
        self.write(
            "CHANGELOG.md",
            f"# Changelog\n\n## [{version}] - 2026-08-21\n\n### Added\n\n- Initial fixture\n",
        )
        for mirror in self.mirrors:
            if mirror["path"].endswith(".toml"):
                tokens = mirror["pointer"].strip("/").split("/")
                section = ".".join(tokens[:-1])
                key = tokens[-1]
                self.write(
                    mirror["path"],
                    (f"[{section}]\n" if section else "") + f'{key} = "{version}" # keep\n',
                )
            else:
                self._write_json_mirror(mirror, version)
        self.git("add", ".")
        self.git("commit", "-m", f"chore: adopt {version}")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        if tag:
            self.git("tag", "-a", f"v{version}", "-m", f"Release v{version}")
        return sha

    def _write_json_mirror(self, mirror: dict[str, str], version: str) -> None:
        tokens = mirror["pointer"].strip("/").split("/")
        document: dict[str, object] = {}
        current = document
        for token in tokens[:-1]:
            child: dict[str, object] = {}
            current[token] = child
            current = child
        current[tokens[-1]] = version
        self.write(mirror["path"], json.dumps(document, indent=2) + "\n")

    def run(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        runtime = os.environ.copy()
        runtime["PYTHONPATH"] = str(SOURCE_ROOT)
        if env:
            runtime.update(env)
        return subprocess.run(
            [sys.executable, "-m", "versionctl", *args],
            cwd=self.root,
            env=runtime,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )


class VersionCtlIntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.repos: list[FixtureRepository] = []

    def tearDown(self) -> None:
        for repo in self.repos:
            repo.close()

    def repo(self, **kwargs: object) -> FixtureRepository:
        repo = FixtureRepository(**kwargs)
        self.repos.append(repo)
        return repo

    def test_docs_only_doctor_is_read_only_and_prepare_is_transactional(self) -> None:
        repo = self.repo()
        repo.seed()
        repo.write("README.md", "# Fixture\n\nCorrected wording.\n")
        before = self._hash_tree(repo.root)

        doctor = repo.run("doctor", "--json")
        self.assertEqual(doctor.returncode, 16, doctor.stderr or doctor.stdout)
        self.assertEqual(json.loads(doctor.stdout)["issues"][0]["code"], "BUMP_REQUIRED")
        self.assertEqual(before, self._hash_tree(repo.root))

        dry_run = repo.run(
            "prepare",
            "patch",
            "--reason",
            "Correct fixture wording",
            "--dry-run",
            "--json",
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertEqual(before, self._hash_tree(repo.root))

        prepared = repo.run(
            "prepare",
            "patch",
            "--reason",
            "Correct fixture wording",
            "--json",
        )
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(repo.read("VERSION"), "0.1.1\n")
        self.assertIn('version = "0.1.1" # keep', repo.read("pyproject.toml"))
        self.assertIn("## [0.1.1]", repo.read("CHANGELOG.md"))

        repo.git("add", ".")
        repo.git("commit", "-m", "docs: correct fixture wording")
        checked = repo.run("release-check", "--json")
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertFalse(json.loads(checked.stdout)["tagExists"])

    def test_node_python_plugin_and_nested_mirrors_move_together(self) -> None:
        mirrors = [
            {"path": "package.json", "pointer": "/version"},
            {"path": "pyproject.toml", "pointer": "/project/version"},
            {"path": "plugins/example/plugin.json", "pointer": "/version"},
            {"path": "packages/nested/package.json", "pointer": "/version"},
        ]
        repo = self.repo(mirrors=mirrors)
        repo.seed()
        repo.write("feature.md", "New capability.\n")
        result = repo.run("prepare", "minor", "--reason", "Add nested capability", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(repo.read("VERSION"), "0.2.0\n")
        self.assertEqual(json.loads(repo.read("package.json"))["version"], "0.2.0")
        self.assertIn('version = "0.2.0" # keep', repo.read("pyproject.toml"))
        self.assertEqual(json.loads(repo.read("plugins/example/plugin.json"))["version"], "0.2.0")
        self.assertEqual(json.loads(repo.read("packages/nested/package.json"))["version"], "0.2.0")

    def test_adoption_and_wip_hook_contract(self) -> None:
        repo = self.repo()
        repo.policy()
        repo.write("README.md", "# Unadopted fixture\n")
        repo.write("pyproject.toml", '[project]\nversion = "0.0.0"\n')
        repo.write("CHANGELOG.md", "# Changelog\n")

        adopted = repo.run(
            "adopt",
            "0.1.0",
            "--reason",
            "Adopt repository versioning",
            "--json",
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        repo.git("add", ".")
        staged = repo.run("doctor", "--staged", "--json")
        self.assertEqual(staged.returncode, 0, staged.stderr or staged.stdout)
        repo.git("commit", "-m", "chore: adopt versioning")
        repo.git("tag", "-a", "v0.1.0", "-m", "Release v0.1.0")

        repo.git("config", "core.hooksPath", ".githooks")
        hooks = repo.run("install-hooks", "--json")
        self.assertEqual(hooks.returncode, 0, hooks.stderr)
        self.assertTrue((repo.root / ".githooks/pre-commit").stat().st_mode & 0o111)
        self.assertTrue((repo.root / ".githooks/commit-msg").stat().st_mode & 0o111)
        repeated = repo.run("install-hooks", "--json")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)["installed"], [])

        repo.write("README.md", "# WIP fixture\n")
        repo.git("add", "README.md")
        blocked = repo.run("hook-check", "pre-commit", "--json")
        self.assertEqual(blocked.returncode, 16, blocked.stderr or blocked.stdout)
        deferred = repo.run(
            "hook-check",
            "pre-commit",
            "--json",
            env={"VERSIONCTL_WIP": "1"},
        )
        self.assertEqual(deferred.returncode, 0, deferred.stderr)
        message = repo.root / "message.txt"
        message.write_text("wip: checkpoint\n", encoding="utf-8")
        allowed = repo.run(
            "hook-check",
            "commit-msg",
            "--message-file",
            str(message),
            "--json",
            env={"VERSIONCTL_WIP": "1"},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        unmarked = repo.run(
            "hook-check",
            "commit-msg",
            "--message-file",
            str(message),
            "--json",
        )
        self.assertEqual(unmarked.returncode, 21, unmarked.stderr or unmarked.stdout)

    def test_dirty_stale_reused_and_distribution_failures(self) -> None:
        with self.subTest("dirty-tree"):
            repo = self.repo()
            repo.seed()
            repo.write("README.md", "dirty\n")
            result = repo.run("release-check", "--json")
            self.assertEqual(result.returncode, 20, result.stderr or result.stdout)

        with self.subTest("stale-mirror"):
            repo = self.repo()
            repo.seed()
            repo.write("pyproject.toml", '[project]\nversion = "0.1.1"\n')
            result = repo.run("doctor", "--json")
            self.assertEqual(result.returncode, 15, result.stderr or result.stdout)

        with self.subTest("reused-tag"):
            repo = self.repo()
            repo.seed()
            repo.write("README.md", "new content\n")
            repo.git("add", "README.md")
            repo.git("commit", "-m", "docs: unversioned content")
            result = repo.run("release-check", "--json")
            self.assertEqual(result.returncode, 19, result.stderr or result.stdout)

        with self.subTest("post-release-channel-drift"):
            repo = self.repo()
            previous = repo.seed(tag=False)
            repo.write("README.md", "candidate\n")
            prepared = repo.run("prepare", "patch", "--reason", "Prepare candidate")
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            repo.git("add", ".")
            repo.git("commit", "-m", "docs: prepare candidate")
            result = repo.run("release-check", "--sha", previous, "--json")
            self.assertEqual(result.returncode, 18, result.stderr or result.stdout)

    def test_ci_rejects_skips_and_accepts_exact_annotated_tag_offline(self) -> None:
        with self.subTest("skipped-version"):
            repo = self.repo()
            base = repo.seed(tag=False)
            repo.write("README.md", "changed\n")
            repo.write("VERSION", "0.1.2\n")
            repo.write("pyproject.toml", '[project]\nversion = "0.1.2" # keep\n')
            repo.write(
                "CHANGELOG.md",
                repo.read("CHANGELOG.md")
                + "\n## [0.1.2] - 2026-08-21\n\n### Changed\n\n- Skipped\n",
            )
            repo.git("add", ".")
            repo.git("commit", "-m", "docs: invalid skip")
            result = repo.run("doctor", "--ci", "--base", base, "--json")
            self.assertEqual(result.returncode, 16, result.stderr or result.stdout)

        with self.subTest("bot-created-tag-and-no-enrichment"):
            repo = self.repo()
            repo.seed()
            env = {
                "GITHUB_TOKEN": "deliberately-invalid-and-unused",
                "HTTPS_PROXY": "http://127.0.0.1:1",
                "HTTP_PROXY": "http://127.0.0.1:1",
            }
            result = repo.run("release-check", "--tag", "v0.1.0", "--json", env=env)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(report["tagExists"])
            self.assertEqual(report["tagSha"], report["sha"])

    def test_fixture_matrix_names_every_required_plan_case(self) -> None:
        matrix = json.loads(FIXTURE_MATRIX.read_text(encoding="utf-8"))
        identifiers = {case["id"] for case in matrix["cases"]}
        self.assertEqual(
            identifiers,
            {
                "docs-only",
                "node",
                "python",
                "plugin",
                "dirty-tree",
                "stale-mirror",
                "reused-tag",
                "skipped-version",
                "post-release-channel-drift",
                "bot-created-tag",
                "remote-enrichment-failure",
                "monorepo-adjacent",
            },
        )

    @staticmethod
    def _hash_tree(root: Path) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if not path.is_file() or ".git" in path.parts:
                continue
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hashes


if __name__ == "__main__":
    unittest.main()
