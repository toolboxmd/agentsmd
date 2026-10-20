#!/usr/bin/env python3
"""The canonical clone is unhealthy when it leaves main or a release tag (#191)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import agentsmd_instructions as instructions

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

    def merged_branch(self) -> str:
        """Leave main behind both a merged task and newer instruction contents."""
        self.git(self.clone, "switch", "-qc", "feature")
        self.git(self.clone, "commit", "-q", "--allow-empty", "-m", "task")
        task = self.git(self.clone, "rev-parse", "HEAD")
        (self.clone / "global/AGENTS.md").write_text("# Latest contract\n")
        self.git(self.clone, "commit", "-qam", "latest")
        self.git(self.clone, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.git(self.clone, "reset", "--hard", task)
        return task

    def snapshot(self) -> tuple[str, str, str, bytes]:
        return (self.git(self.clone, "symbolic-ref", "-q", "HEAD"),
                self.git(self.clone, "show-ref"),
                self.git(self.clone, "status", "--porcelain", "--untracked-files=all"),
                (self.clone / "global/AGENTS.md").read_bytes())

    def test_merged_clean_branch_restores_and_refreshes_hash(self) -> None:
        task = self.merged_branch()
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "source-checkout-restored"))
        self.assertTrue(report["healthy"])
        self.assertEqual(report["restored_from"], "feature")
        self.assertEqual(self.git(self.clone, "branch", "--show-current"), "main")
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"),
                         self.git(self.clone, "rev-parse", "origin/main"))
        self.assertEqual(self.git(self.clone, "rev-parse", "feature"), task)
        self.assertEqual(report["sha256"], instructions.digest(self.clone / "global/AGENTS.md"))
        self.assertEqual(self.inspect()[1]["status"], "valid-stable-link")

    def test_unsafe_branches_keep_report_and_checkout(self) -> None:
        self.merged_branch()
        baseline_action = None
        for state in ("modified", "staged", "untracked", "unmerged", "diverged-main", "missing-main", "missing-origin"):
            with self.subTest(state=state):
                main = self.git(self.clone, "rev-parse", "main")
                origin = self.git(self.clone, "rev-parse", "origin/main")
                feature = self.git(self.clone, "rev-parse", "feature")
                extra = self.clone / "extra"
                if state in ("modified", "staged"):
                    (self.clone / "global/AGENTS.md").write_text("# Dirty\n")
                    if state == "staged":
                        self.git(self.clone, "add", ".")
                elif state == "untracked":
                    extra.write_text("untracked\n")
                elif state == "unmerged":
                    self.git(self.clone, "commit", "-q", "--allow-empty", "-m", "unmerged")
                elif state == "diverged-main":
                    self.git(self.clone, "update-ref", "refs/heads/main", "v1.0.0")
                    self.git(self.clone, "switch", "-q", "main")
                    self.git(self.clone, "commit", "-q", "--allow-empty", "-m", "diverged")
                    self.git(self.clone, "switch", "-q", "feature")
                else:
                    self.git(self.clone, "update-ref", "-d", "refs/heads/main" if state == "missing-main" else "refs/remotes/origin/main")
                before = self.snapshot()
                code, report = self.inspect()
                self.assertEqual((code, report["status"]), (2, "source-checkout-off-release"))
                self.assertEqual(report["checkout_head"], "feature")
                baseline_action = baseline_action or report["action"]
                self.assertEqual(report["action"], baseline_action)
                self.assertEqual(self.snapshot(), before)
                if extra.exists():
                    extra.unlink()
                self.git(self.clone, "reset", "--hard", feature)
                self.git(self.clone, "update-ref", "refs/heads/main", main)
                self.git(self.clone, "update-ref", "refs/remotes/origin/main", origin)

    def test_restore_git_errors_roll_back_checkout_and_refs(self) -> None:
        self.merged_branch()
        real_git = instructions._git
        for command in ("tag", "status", "rev-parse", "merge-base", "switch", "merge", "ls-files", "symbolic-ref"):
            for after_effect in (False, True):
                with self.subTest(command=command, after_effect=after_effect):
                    before = self.snapshot()
                    failed = False
                    switched = False

                    def git(root, *args):
                        nonlocal failed, switched
                        self.assertEqual(root, self.clone)
                        self.assertNotIn(args[0], ("fetch", "branch"))
                        should_fail = (args[0] == command and not failed and
                                       (command not in ("ls-files", "symbolic-ref") or switched))
                        if should_fail:
                            failed = True
                            if after_effect:
                                real_git(root, *args)
                            return None
                        result = real_git(root, *args)
                        if args[0] == "switch":
                            switched = True
                        return result

                    with mock.patch.object(instructions, "_git", side_effect=git):
                        report = instructions.guard_checkout(instructions.inspect_target(self.target))
                    self.assertTrue(failed)
                    self.assertEqual(report["status"], "source-checkout-off-release")
                    self.assertEqual(self.snapshot(), before)

    def test_hook_inspect_reports_restoration(self) -> None:
        self.merged_branch()
        result = subprocess.run([str(DIRECTION), "inspect", "--host", "codex"],
                                cwd=self.root, env=self.env, text=True, capture_output=True)
        report = json.loads(result.stdout)["instructions"]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["status"], "source-checkout-restored")
        self.assertEqual(report["restored_from"], "feature")

    def test_merge_ref_lock_failure_leaves_checkout_unchanged(self) -> None:
        self.merged_branch()
        before = self.snapshot()
        lock = self.clone / ".git/refs/heads/main.lock"
        lock.write_text("locked\n")
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (2, "source-checkout-off-release"))
        self.assertEqual(self.snapshot(), before)

    def test_branch_tag_collision_rolls_back(self) -> None:
        self.merged_branch()
        self.git(self.clone, "tag", "feature", "v1.0.0")
        before = self.snapshot()
        (self.clone / ".git/refs/heads/main.lock").write_text("locked\n")
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (2, "source-checkout-off-release"))
        self.assertEqual(self.snapshot(), before)

    def test_branch_tag_collisions_restore_with_actual_branch_name(self) -> None:
        self.merged_branch()
        for name in ("main", "feature"):
            self.git(self.clone, "tag", name, "v1.0.0")
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (0, "source-checkout-restored"))
        self.assertEqual(report["restored_from"], "feature")
        self.assertEqual(self.git(self.clone, "symbolic-ref", "HEAD"), "refs/heads/main")

    def test_restoring_at_session_start_requests_reread_on_every_host(self) -> None:
        self.merged_branch()
        for host in instructions.HARNESSES:
            with self.subTest(host=host):
                self.git(self.clone, "switch", "-q", "feature")
                old_sha = instructions.digest(self.clone / "global/AGENTS.md")
                env = dict(self.env, AGENTSMD_HOST=host,
                           CODEX_HOME=str(self.root / "codex"),
                           GROK_HOME=str(self.root / "grok"),
                           CLAUDE_CONFIG_DIR=str(self.root / "claude"),
                           OPENCODE_CONFIG_DIR=str(self.root / "opencode"),
                           XDG_CONFIG_HOME=str(self.root / "xdg"),
                           AGENTSMD_PROJECT_DIRECTION_DATA=str(self.root / "cache"),
                           GROK_HOOK_NAME="agentsmd")
                target = {"codex": self.target, "grok": self.root / "grok/AGENTS.md",
                          "claude": self.root / "claude/CLAUDE.md",
                          "opencode": self.root / "opencode/AGENTS.md",
                          "muse": self.root / "xdg/muse/AGENTS.md"}[host]
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.symlink_to(self.clone / "global/AGENTS.md")
                events = {"grok": ("PreToolUse", "PreToolUse"),
                          "opencode": ("SessionStart", "SessionStart")}.get(
                              host, ("SessionStart", "SubagentStart"))
                for index, event in enumerate(events):
                    event_input = {"cwd": str(self.root), "session_id": host,
                                   "hook_event_name": event, "tool_name": "Bash",
                                   "tool_input": {"command": "ls"}}
                    result = subprocess.run(
                        [str(DIRECTION), "hook", "--host", host], cwd=self.root, env=env,
                        input=json.dumps(event_input), text=True, capture_output=True, check=True)
                    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                    report = json.loads(context.splitlines()[1])["instructions"]
                    self.assertEqual(report["status"], "source-checkout-restored" if index == 0 else "valid-stable-link")
                    self.assertNotEqual(report["sha256"], old_sha)
                    self.assertEqual(report["action"], instructions.CHANGED_ACTION)

    def test_detached_contained_non_release_is_unchanged(self) -> None:
        self.merged_branch()
        self.git(self.clone, "checkout", "-q", "--detach")
        refs = self.git(self.clone, "show-ref")
        head = self.git(self.clone, "rev-parse", "HEAD")
        code, report = self.inspect()
        self.assertEqual((code, report["status"]), (2, "source-checkout-off-release"))
        self.assertEqual(self.git(self.clone, "branch", "--show-current"), "")
        self.assertEqual(self.git(self.clone, "show-ref"), refs)
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), head)

    def test_restore_when_main_already_matches_origin(self) -> None:
        self.merged_branch()
        self.git(self.clone, "update-ref", "refs/heads/main", "origin/main")
        self.assertEqual(self.inspect()[1]["status"], "source-checkout-restored")
        self.assertEqual(self.git(self.clone, "branch", "--show-current"), "main")

    def test_release_tag_with_contained_branch_is_not_restored(self) -> None:
        self.merged_branch()
        self.git(self.clone, "tag", "-am", "release", "v2.0.0")
        before = self.snapshot()
        self.assertEqual(self.inspect()[1]["status"], "valid-stable-link")
        self.assertEqual(self.snapshot(), before)
        self.git(self.clone, "checkout", "-q", "--detach", "v2.0.0")
        refs = self.git(self.clone, "show-ref")
        self.assertEqual(self.inspect()[1]["status"], "valid-stable-link")
        self.assertEqual(self.git(self.clone, "show-ref"), refs)

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

    def test_git_failure_is_unhealthy(self) -> None:
        tools = self.root / "tools"
        tools.mkdir()
        (tools / "python3").symlink_to(sys.executable)
        failing = tools / "failing"
        failing.mkdir()
        (failing / "git").write_text("#!/bin/sh\nexit 128\n")
        (failing / "git").chmod(0o755)
        for path in (str(tools), f"{failing}:{tools}"):
            with self.subTest(path=path):
                self.env["PATH"] = path
                code, report = self.inspect()
                self.assertEqual((code, report["status"]), (2, "source-checkout-unverified"))

    def test_non_git_source_is_not_checked(self) -> None:
        plain = self.root / "plain/global/AGENTS.md"
        plain.parent.mkdir(parents=True)
        plain.write_text("# Contract\n")
        self.target.unlink()
        self.target.symlink_to(plain)
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
