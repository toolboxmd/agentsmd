#!/usr/bin/env python3
"""Deterministic contract tests for global AgentsMD instruction repair."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "bin/agentsmd-global-instructions"


class GlobalInstructionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "canonical-clone/AGENTS.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("# Current AgentsMD contract\n", encoding="utf-8")
        self.target = self.root / "codex/AGENTS.md"

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(COMMAND), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def report(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertTrue(result.stdout, result.stderr)
        return json.loads(result.stdout)

    def inspect(self) -> subprocess.CompletedProcess[str]:
        return self.run_command("inspect", "--target", str(self.target))

    def install(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return self.run_command(
            "install",
            "--source",
            str(self.source),
            "--target",
            str(self.target),
            *arguments,
        )

    def test_inspect_reports_missing_target(self) -> None:
        result = self.inspect()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "missing")

    def test_install_creates_missing_target_without_backup(self) -> None:
        result = self.install()
        report = self.report(result)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["action"], "installed")
        self.assertIsNone(report["backup"])
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(self.target.resolve(), self.source.resolve())
        self.assertFalse((self.target.parent / "agentsmd-backups").exists())

    def test_inspect_reports_broken_link(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(self.root / "removed/AGENTS.md")

        result = self.inspect()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "broken-link")

    def test_inspect_rejects_existing_cache_bound_link(self) -> None:
        cached = (
            self.root
            / "plugins/cache/toolboxmd/agentsmd/5.1.0/AGENTS.md"
        )
        cached.parent.mkdir(parents=True)
        cached.write_text("disposable\n", encoding="utf-8")
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(cached)

        result = self.inspect()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "cache-bound-link")

    def test_inspect_rejects_cache_link_that_redirects_to_stable_source(self) -> None:
        cached = (
            self.root
            / "plugins/cache/toolboxmd/agentsmd/5.1.0/AGENTS.md"
        )
        cached.parent.mkdir(parents=True)
        cached.symlink_to(self.source)
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(cached)

        result = self.inspect()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "cache-bound-link")

    def test_inspect_rejects_target_location_inside_cache(self) -> None:
        cached_target = (
            self.root
            / "plugins/cache/toolboxmd/agentsmd/5.1.0/AGENTS.md"
        )
        cached_target.parent.mkdir(parents=True)
        cached_target.symlink_to(self.source)

        result = self.run_command("inspect", "--target", str(cached_target))

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "cache-bound-target")

    def test_inspect_accepts_valid_stable_link(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(self.source)

        result = self.inspect()
        report = self.report(result)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["status"], "valid-stable-link")
        self.assertTrue(report["healthy"])
        self.assertEqual(report["sha256"], report["target_sha256"])

    def test_inspect_rejects_link_to_non_agents_file(self) -> None:
        other = self.root / "canonical-clone/README.md"
        other.write_text("not global instructions\n", encoding="utf-8")
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(other)

        result = self.inspect()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "invalid-link-target")

    def test_inspect_reports_preexisting_non_symlink_file(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("user instructions\n", encoding="utf-8")

        result = self.inspect()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["status"], "non-symlink")

    def test_install_does_not_overwrite_without_replace_authority(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("user instructions\n", encoding="utf-8")

        result = self.install()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["error"], "replacement-required")
        self.assertFalse(self.target.is_symlink())
        self.assertEqual(self.target.read_text(), "user instructions\n")
        self.assertFalse((self.target.parent / "agentsmd-backups").exists())

    def test_replace_backs_up_preexisting_user_file(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("user instructions\n", encoding="utf-8")

        result = self.install("--replace")
        report = self.report(result)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["action"], "repaired")
        backup = Path(str(report["backup"]))
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_text(), "user instructions\n")
        self.assertTrue(self.target.is_symlink())
        self.assertEqual(self.target.resolve(), self.source.resolve())

    def test_broken_link_repair_is_idempotent(self) -> None:
        self.target.parent.mkdir(parents=True)
        removed = self.root / "plugins/cache/toolboxmd/agentsmd/5.0.0/AGENTS.md"
        self.target.symlink_to(removed)

        first = self.install("--replace")
        first_report = self.report(first)
        backups = self.target.parent / "agentsmd-backups"
        first_backups = list(backups.iterdir())

        second = self.install()
        second_report = self.report(second)

        self.assertEqual(first.returncode, 0)
        self.assertEqual(first_report["previous_status"], "cache-bound-link")
        self.assertEqual(len(first_backups), 1)
        self.assertTrue(first_backups[0].is_symlink())
        self.assertEqual(second.returncode, 0)
        self.assertEqual(second_report["action"], "unchanged")
        self.assertEqual(list(backups.iterdir()), first_backups)

    def test_install_rejects_cache_source(self) -> None:
        cached = (
            self.root
            / "plugins/cache/toolboxmd/agentsmd/5.1.0/AGENTS.md"
        )
        cached.parent.mkdir(parents=True)
        cached.write_text("disposable\n", encoding="utf-8")

        result = self.run_command(
            "install",
            "--source",
            str(cached),
            "--target",
            str(self.target),
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["error"], "cache-bound-source")
        self.assertFalse(self.target.exists())

    def test_install_rejects_target_inside_cache(self) -> None:
        cached_target = (
            self.root
            / "plugins/cache/toolboxmd/agentsmd/5.1.0/AGENTS.md"
        )

        result = self.run_command(
            "install",
            "--source",
            str(self.source),
            "--target",
            str(cached_target),
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["error"], "cache-bound-target")
        self.assertFalse(cached_target.exists())

    def test_install_rejects_source_as_target_without_mutation(self) -> None:
        original = self.source.read_bytes()

        result = self.run_command(
            "install",
            "--source",
            str(self.source),
            "--target",
            str(self.source),
            "--replace",
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.report(result)["error"], "source-equals-target")
        self.assertFalse(self.source.is_symlink())
        self.assertEqual(self.source.read_bytes(), original)
        self.assertFalse((self.source.parent / "agentsmd-backups").exists())


if __name__ == "__main__":
    unittest.main()
