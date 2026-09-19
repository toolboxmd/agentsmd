#!/usr/bin/env python3
"""Deterministic contract tests for the owned global Grok hook file."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "bin/agentsmd-grok-hook"
BLOCK_START = "<<<AGENTSMD_PROJECT_DIRECTION_V1>>>"
BLOCK_END = "<<<END_AGENTSMD_PROJECT_DIRECTION_V1>>>"
STUB_LOADER = "#!/bin/sh\nexit 0\n"


class GrokHookFixture(unittest.TestCase):
    """Isolated GROK_HOME and HOME for every hook file test."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.home = self.base / "home"
        self.grok_home = self.home / ".grok"
        self.home.mkdir()
        self.source = self.make_source("canonical-clone")
        self.target = self.grok_home / "hooks/agentsmd.json"

    def make_source(self, name: str, loader: bool = True) -> Path:
        source = self.base / name
        (source / "bin").mkdir(parents=True)
        if loader:
            script = source / "bin/project-direction"
            script.write_text(STUB_LOADER, encoding="utf-8")
            script.chmod(0o755)
        return source

    def environment(self, **extra: str) -> dict[str, str]:
        environment = os.environ.copy()
        # No test may read or write the real Grok or user home.
        environment["HOME"] = str(self.home)
        environment["GROK_HOME"] = str(self.grok_home)
        environment.pop("AGENTSMD_HOST", None)
        environment.pop("GROK_HOOK_NAME", None)
        environment.update(extra)
        return environment

    def run_command(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(COMMAND), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=self.environment(),
            check=False,
        )

    def report(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertTrue(result.stdout, result.stderr)
        return json.loads(result.stdout)

    def install(self, *arguments: str, source: Path | None = None) -> dict[str, object]:
        result = self.run_command(
            "install", "--source", str(source or self.source), *arguments
        )
        return self.report(result) | {"exit_code": result.returncode}

    def expected_document(self, source: Path | None = None) -> dict[str, object]:
        source = source or self.source
        return {
            "agentsmd": {
                "installer": "agentsmd-grok-hook",
                "source": str(source),
            },
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'"{source}/bin/project-direction" hook',
                                "timeout": 15,
                                "env": {
                                    "AGENTSMD_PROJECT_DIRECTION_DATA": str(
                                        self.grok_home / "agentsmd"
                                    )
                                },
                            }
                        ]
                    }
                ]
            },
        }


class GrokHookTests(GrokHookFixture):
    def test_install_writes_the_expected_grok_hook_file(self) -> None:
        report = self.install()

        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["action"], "installed")
        self.assertIsNone(report["backup"])
        self.assertEqual(report["target"], str(self.target))
        self.assertEqual(report["after"]["status"], "owned-current")
        self.assertTrue(report["after"]["owned"])
        self.assertEqual(json.loads(self.target.read_text()), self.expected_document())
        self.assertTrue(self.target.read_text().endswith("\n"))
        self.assertFalse((self.target.parent / "agentsmd-backups").exists())

    def test_repeat_install_reports_unchanged_and_writes_no_backup(self) -> None:
        self.install()
        content = self.target.read_bytes()

        report = self.install()

        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["action"], "unchanged")
        self.assertEqual(self.target.read_bytes(), content)
        self.assertFalse((self.target.parent / "agentsmd-backups").exists())

    def test_divergent_file_is_preserved_and_names_its_source(self) -> None:
        other = self.make_source("other-clone")
        self.install(source=other)
        content = self.target.read_bytes()

        report = self.install()

        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["action"], "preserved")
        self.assertEqual(report["error"], "replacement-required")
        self.assertEqual(report["before"]["status"], "divergent")
        self.assertEqual(report["before"]["installed_source"], str(other))
        self.assertFalse(report["before"]["owned"])
        self.assertEqual(self.target.read_bytes(), content)

    def test_user_owned_file_is_preserved_and_reported(self) -> None:
        self.target.parent.mkdir(parents=True)
        content = '{"hooks": {"PreToolUse": [{"hooks": [{"type": "command", '\
                  '"command": "bin/mine.sh"}]}]}}\n'
        self.target.write_text(content, encoding="utf-8")

        report = self.install()

        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["action"], "preserved")
        self.assertEqual(report["error"], "replacement-required")
        self.assertEqual(report["before"]["status"], "user-owned")
        self.assertEqual(self.target.read_text(), content)

    def test_unparsed_file_is_preserved_as_user_owned(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("not json at all\n", encoding="utf-8")

        report = self.install()

        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["before"]["status"], "user-owned")
        self.assertEqual(self.target.read_text(), "not json at all\n")

    def test_replace_backs_up_the_previous_file_then_writes(self) -> None:
        self.target.parent.mkdir(parents=True)
        previous = '{"hooks": {"PostToolUse": []}}\n'
        self.target.write_text(previous, encoding="utf-8")

        report = self.install("--replace")

        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["action"], "replaced")
        backup = Path(str(report["backup"]))
        self.assertEqual(backup.parent, self.target.parent / "agentsmd-backups")
        self.assertEqual(backup.read_text(), previous)
        self.assertEqual(json.loads(self.target.read_text()), self.expected_document())

    def test_replace_honors_an_explicit_backup_directory(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("previous\n", encoding="utf-8")
        elsewhere = self.base / "kept"

        report = self.install("--replace", "--backup-dir", str(elsewhere))

        self.assertEqual(report["exit_code"], 0)
        backup = Path(str(report["backup"]))
        self.assertEqual(backup.parent, elsewhere)
        self.assertEqual(backup.read_text(), "previous\n")
        self.assertFalse((self.target.parent / "agentsmd-backups").exists())

    def test_uninstall_removes_only_the_owned_file(self) -> None:
        self.install()

        report = self.report(
            self.run_command("uninstall", "--source", str(self.source))
        )

        self.assertEqual(report["action"], "uninstalled")
        self.assertFalse(self.target.exists())

    def test_uninstall_preserves_a_file_that_is_not_owned(self) -> None:
        self.target.parent.mkdir(parents=True)
        self.target.write_text("mine\n", encoding="utf-8")

        result = self.run_command("uninstall", "--source", str(self.source))

        self.assertEqual(result.returncode, 2)
        report = self.report(result)
        self.assertEqual(report["action"], "preserved")
        self.assertEqual(report["error"], "not-owned")
        self.assertEqual(self.target.read_text(), "mine\n")

    def test_uninstall_without_a_file_reports_absent(self) -> None:
        result = self.run_command("uninstall", "--source", str(self.source))

        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.report(result)["action"], "absent")

    def test_status_exits_zero_only_for_an_owned_current_file(self) -> None:
        missing = self.run_command("status", "--source", str(self.source))
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(self.report(missing)["before"]["status"], "missing")

        self.install()
        owned = self.run_command("status", "--source", str(self.source))
        self.assertEqual(owned.returncode, 0)
        self.assertEqual(self.report(owned)["before"]["status"], "owned-current")

        other = self.make_source("newer-clone")
        divergent = self.run_command("status", "--source", str(other))
        self.assertEqual(divergent.returncode, 2)
        self.assertEqual(self.report(divergent)["before"]["status"], "divergent")

    def test_status_reports_a_hand_edited_owned_file_as_divergent(self) -> None:
        self.install()
        document = json.loads(self.target.read_text())
        document["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 5
        self.target.write_text(json.dumps(document), encoding="utf-8")

        result = self.run_command("status", "--source", str(self.source))

        self.assertEqual(result.returncode, 2)
        report = self.report(result)
        self.assertEqual(report["before"]["status"], "divergent")
        self.assertEqual(report["before"]["installed_source"], str(self.source))

    def test_directory_targets_are_never_replaced(self) -> None:
        self.target.mkdir(parents=True)

        report = self.install("--replace")

        self.assertEqual(report["exit_code"], 2)
        self.assertEqual(report["error"], "unsupported-target")
        self.assertTrue(self.target.is_dir())

    def test_cache_bound_sources_are_rejected(self) -> None:
        cached = self.make_source("plugins/cache/toolboxmd/agentsmd/11.1.0")

        report = self.install(source=cached)

        self.assertEqual(report["exit_code"], 2)
        self.assertIn("plugin caches", str(report["error"]))
        self.assertFalse(self.target.exists())

    def test_symlink_alias_sources_are_rejected(self) -> None:
        alias = self.base / "alias"
        alias.symlink_to(self.source, target_is_directory=True)

        report = self.install(source=alias)

        self.assertEqual(report["exit_code"], 2)
        self.assertIn("symlink alias", str(report["error"]))
        self.assertFalse(self.target.exists())

    def test_sources_without_a_regular_loader_are_rejected(self) -> None:
        empty = self.make_source("no-loader", loader=False)
        linked = self.make_source("linked-loader", loader=False)
        (linked / "bin/project-direction").symlink_to(self.source / "bin/project-direction")

        for source in (empty, linked, self.base / "absent"):
            with self.subTest(source=source.name):
                report = self.install(source=source)
                self.assertEqual(report["exit_code"], 2)
                self.assertFalse(self.target.exists())

    def test_sources_holding_shell_expansion_characters_are_rejected(self) -> None:
        unsafe = self.make_source("clone$HOME")

        report = self.install(source=unsafe)

        self.assertEqual(report["exit_code"], 2)
        self.assertIn("dollar", str(report["error"]))
        self.assertFalse(self.target.exists())


class GrokHookDeliveryTests(GrokHookFixture):
    """The generated command must deliver the payload on Grok's own stdin."""

    def setUp(self) -> None:
        super().setUp()
        self.source = self.make_canonical_clone()
        self.repository = self.base / "repository"
        self.repository.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.repository)], check=True)
        self.triad = {
            "VISION.md": "# Vision\n\nMake agent work purposeful.\n",
            "MISSION.md": "# Mission\n\nTurn direction into delivery.\n",
            "OBJECTIVE.md": "# Objective\n\nShip Project Direction on Grok.\n",
        }
        for name, content in self.triad.items():
            (self.repository / name).write_text(content, encoding="utf-8")

    def make_canonical_clone(self) -> Path:
        source = self.base / "grok-clone"
        (source / "bin").mkdir(parents=True)
        for name in ("project-direction", "agentsmd_instructions.py"):
            shutil.copy2(ROOT / "bin" / name, source / "bin" / name)
        return source

    def call_hook(self, session: str = "grok-session") -> subprocess.CompletedProcess[str]:
        handler = json.loads(self.target.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]
        # Grok sets GROK_HOOK_NAME for a global hook and applies the env map.
        environment = self.environment(
            GROK_HOOK_NAME="agentsmd", **handler["env"]
        )
        stdin = {
            "session_id": session,
            "sessionId": session,
            "cwd": str(self.repository),
            "hook_event_name": "PreToolUse",
            "hookEventName": "PreToolUse",
            "tool_name": "run_terminal_command",
            "toolName": "run_terminal_command",
            "tool_input": {"command": "ls"},
            "toolInput": {"command": "ls"},
        }
        return subprocess.run(
            handler["command"],
            shell=True,
            cwd=self.repository,
            input=json.dumps(stdin),
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )

    def test_installed_command_delivers_direction_once_per_grok_session(self) -> None:
        self.install()

        first = self.call_hook()
        second = self.call_hook()

        self.assertEqual(first.returncode, 0, first.stderr)
        output = json.loads(first.stdout)
        self.assertEqual(
            output["hookSpecificOutput"]["hookEventName"], "PreToolUse"
        )
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(context.startswith(f"{BLOCK_START}\n"))
        self.assertTrue(context.endswith(f"\n{BLOCK_END}"))
        payload = json.loads(context[len(BLOCK_START) + 1 : -(len(BLOCK_END) + 1)])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(
            [item["content"] for item in payload["files"]],
            [self.triad[name] for name in ("VISION.md", "MISSION.md", "OBJECTIVE.md")],
        )
        # The env map keeps the session fingerprint under GROK_HOME.
        cache = self.grok_home / "agentsmd/project-direction"
        self.assertEqual(len(list(cache.glob("*.json"))), 1)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(second.stdout, "")


if __name__ == "__main__":
    unittest.main()
