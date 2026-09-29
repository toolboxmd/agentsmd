#!/usr/bin/env python3
"""The canonical clone is unhealthy when it leaves main or a release tag (#191)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLOBAL = ROOT / "bin/agentsmd-global-instructions"
DIRECTION = ROOT / "bin/project-direction"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


class LiveCheckoutGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = {**os.environ, **GIT_ENV, "CODEX_HOME": str(self.root / "codex")}
        self.clone = self.repository("agentsmd", "# AgentsMD contract\n")
        self.git(self.clone, "tag", "v1.0.0")
        (self.clone / "global/AGENTS.md").write_text("# Newer contract\n")
        self.git(self.clone, "commit", "-qam", "newer")
        self.target = self.root / "codex/AGENTS.md"
        self.target.parent.mkdir()
        self.target.symlink_to(self.clone / "global/AGENTS.md")

    def git(self, cwd: Path, *arguments: str) -> str:
        return subprocess.run(["git", *arguments], cwd=cwd, env=self.env, text=True,
                              capture_output=True, check=True).stdout.strip()

    def repository(self, name: str, contract: str) -> Path:
        path = self.root / name
        (path / "global").mkdir(parents=True)
        (path / "global/AGENTS.md").write_text(contract)
        self.git(path, "init", "-q", "-b", "main")
        self.git(path, "add", ".")
        self.git(path, "commit", "-qm", "initial")
        return path

    def inspect(self) -> tuple[int, dict[str, object]]:
        result = subprocess.run([str(GLOBAL), "inspect", "--target", str(self.target)],
                                env=self.env, text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)

    def restore(self, report: dict[str, object], index: int = 0) -> None:
        command = re.findall(r"`([^`]+)`", str(report["action"]))[index]
        subprocess.run(command, shell=True, env=self.env, check=True, capture_output=True)

    def test_main_is_healthy(self) -> None:
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "valid-stable-link"))

    def test_release_tag_is_healthy(self) -> None:
        self.git(self.clone, "checkout", "-q", "v1.0.0")
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "valid-stable-link"))

    def test_foreign_fetch_head_is_unhealthy_until_main_is_restored(self) -> None:
        other = self.repository("other", "# Another repository\n")
        self.git(self.clone, "fetch", "-q", str(other), "main")
        self.git(self.clone, "checkout", "-q", "FETCH_HEAD")

        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (2, "source-checkout-off-release"))
        self.assertFalse(report["healthy"])
        self.assertIn("switch main", str(report["action"]))

        self.restore(report)
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "valid-stable-link"))

    def test_other_branch_is_unhealthy(self) -> None:
        self.git(self.clone, "switch", "-q", "-c", "feature")
        code, report = self.inspect()
        self.assertEqual((code, report["checkout_head"]), (2, "feature"))

    def test_deleted_tracked_file_is_unhealthy_until_restored(self) -> None:
        (self.clone / "README.md").write_text("readme\n")
        self.git(self.clone, "add", "README.md")
        self.git(self.clone, "commit", "-qm", "readme")
        (self.clone / "README.md").unlink()

        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (2, "source-checkout-files-missing"))
        self.assertEqual(report["missing_files"], ["README.md"])

        self.restore(report)
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "valid-stable-link"))

    def test_session_hook_inspect_reports_foreign_checkout(self) -> None:
        self.git(self.clone, "checkout", "-q", "--detach", "HEAD~1")
        self.git(self.clone, "commit", "-q", "--allow-empty", "-m", "foreign")
        result = subprocess.run([str(DIRECTION), "inspect", "--host", "codex"],
                                cwd=self.root, env=self.env, text=True, capture_output=True)
        instructions = json.loads(result.stdout)["instructions"]
        self.assertEqual(result.returncode, 2)
        self.assertEqual(instructions["status"], "source-checkout-off-release")
        self.assertIn("switch main", instructions["action"])


if __name__ == "__main__":
    unittest.main()
