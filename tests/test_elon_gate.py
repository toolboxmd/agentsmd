#!/usr/bin/env python3
"""The Project Direction hook blocks gh Issue and PR creation without an Elon record."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "bin/project-direction"
PLUGIN = ROOT / "opencode/agentsmd-project-direction.js"
NODE = shutil.which("node")

RECORD = (
    "- **Requirements and who asked:** the user asked for enforcement\n"
    "- **Deleted:** the per-prompt reminder\n"
    "- **Bottleneck:** agents skip the procedure\n"
    "- **Checked myself:** ran the hook on four hosts\n"
)


class ElonGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.cwd)], check=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("GROK_HOOK_NAME", "AGENTSMD_HOST")}

    def hook(self, tool_input: object, host: str = "claude", env: dict[str, str] | None = None,
             **extra: object) -> subprocess.CompletedProcess[str]:
        event = {"hook_event_name": "PreToolUse", "cwd": str(self.cwd), "session_id": "s",
                 "tool_input": tool_input, **extra}
        return subprocess.run(
            [str(LOADER), "hook", "--host", host], input=json.dumps(event),
            capture_output=True, text=True, env={**self.env, **(env or {})}, check=False,
        )

    def assertBlocked(self, result: subprocess.CompletedProcess[str], *missing: str) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("AgentsMD blocked", result.stderr)
        for field in missing:
            self.assertIn(field, result.stderr.split("Missing or empty:", 1)[1])

    def test_blocks_issue_without_record_and_names_every_field(self) -> None:
        result = self.hook({"command": 'gh issue create --title x --body "hello"'}, tool_name="Bash")
        self.assertBlocked(result, "Requirements and who asked", "Deleted", "Bottleneck", "Checked myself")

    def test_allows_pr_whose_body_file_has_the_record(self) -> None:
        (self.cwd / "body.md").write_text("**What:** x\n\n### Elon record\n\n" + RECORD, encoding="utf-8")
        result = self.hook({"command": "gh pr create --title x --body-file body.md"}, tool_name="Bash")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_heredoc_body_is_read_from_the_command(self) -> None:
        command = "gh issue create --title x --body-file - <<'EOF'\n" + RECORD + "EOF"
        self.assertEqual(self.hook({"command": command}).returncode, 0)

    def test_placeholder_and_empty_fields_count_as_missing(self) -> None:
        body = RECORD.replace("the per-prompt reminder", "<what was cut>").replace(
            "agents skip the procedure", "")
        result = self.hook({"command": "gh pr create --body " + shlex.quote(body)})
        self.assertBlocked(result, "Deleted", "Bottleneck")
        self.assertNotIn("Checked myself", result.stderr.split("Missing or empty:", 1)[1].split(".")[0])

    def test_value_on_following_line_counts(self) -> None:
        body = RECORD.replace("**Deleted:** the per-prompt reminder", "**Deleted:**\n  - the reminder")
        self.assertEqual(self.hook({"command": "gh issue create --body " + shlex.quote(body)}).returncode, 0)

    def test_missing_body_file_blocks(self) -> None:
        self.assertBlocked(self.hook({"command": "gh pr create --body-file absent.md"}))

    def test_codex_and_grok_shapes_are_checked(self) -> None:
        # Shapes observed live on 2026-09-29: Codex 0.159.0 sends Bash with
        # tool_input.command; Grok 1.0.44 sends run_terminal_command.
        self.assertBlocked(self.hook({"command": "gh issue create --body hi ."}, host="codex",
                                     tool_name="Bash"))
        grok = self.hook({"command": "gh pr create --fill", "description": "Open PR"}, host="grok",
                         env={"GROK_HOOK_NAME": "agentsmd"}, tool_name="run_terminal_command")
        self.assertBlocked(grok)

    def test_other_tool_calls_pass_silently(self) -> None:
        for tool_input in ({"command": "gh issue list"}, {"command": "ls"}, {"file_path": "a.md"}):
            with self.subTest(tool_input=tool_input):
                result = self.hook(tool_input)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    # Regressions from the Luna max review of PR #163.
    def test_quoted_subcommand_is_still_checked(self) -> None:
        self.assertBlocked(self.hook({"command": 'gh "issue" create --title x --body "hello"'}))

    def test_each_chained_command_is_checked_on_its_own(self) -> None:
        command = ("gh issue create --title first --body missing && gh pr create --title second --body "
                   + shlex.quote(RECORD))
        self.assertBlocked(self.hook({"command": command}))
        both = "gh issue create --body " + shlex.quote(RECORD) + " ; gh pr create --body " + shlex.quote(RECORD)
        self.assertEqual(self.hook({"command": both}).returncode, 0)

    def test_attached_body_file_forms(self) -> None:
        command = "gh issue create --title x -F=- <<'EOF'\n" + RECORD + "EOF"
        self.assertEqual(self.hook({"command": command}).returncode, 0)
        (self.cwd / "r.md").write_text(RECORD, encoding="utf-8")
        self.assertEqual(self.hook({"command": "gh pr create -Fr.md"}).returncode, 0)

    def test_piped_variable_body_blocks_with_guidance(self) -> None:
        result = self.hook({"command": "printf '%s\\n' \"$ELON\" | gh issue create --title x --body-file -"})
        self.assertBlocked(result)
        self.assertIn("cannot read piped variables", result.stderr)

    def test_body_file_follows_cd_in_the_same_command(self) -> None:
        (self.cwd / "sub").mkdir()
        (self.cwd / "sub/record.md").write_text(RECORD, encoding="utf-8")
        self.assertEqual(self.hook({"command": "cd sub && gh issue create --body-file record.md"}).returncode, 0)

    def test_quoted_double_angle_does_not_truncate_the_body(self) -> None:
        body = RECORD.replace("the per-prompt reminder", "reminder << literal")
        self.assertEqual(self.hook({"command": "gh issue create --body " + shlex.quote(body)}).returncode, 0)

    def test_hash_reference_is_a_value_not_a_heading(self) -> None:
        body = RECORD.replace("**Bottleneck:** agents skip the procedure", "**Bottleneck:**\n#161 is the waiting PR")
        self.assertEqual(self.hook({"command": "gh issue create --body " + shlex.quote(body)}).returncode, 0)

    # Regressions from the Luna max re-review of PR #163.
    def test_background_operator_splits_commands(self) -> None:
        command = "gh issue create --body hi & gh issue create --body " + shlex.quote(RECORD)
        self.assertBlocked(self.hook({"command": command}))
        redirect = "gh issue create --body " + shlex.quote(RECORD) + " 2>&1 >/dev/null"
        self.assertEqual(self.hook({"command": redirect}).returncode, 0)

    def test_global_value_flags_before_the_subcommand(self) -> None:
        for command in ("gh --repo toolboxmd/agentsmd issue create --body hi",
                        "gh -R toolboxmd/agentsmd pr create --body hi"):
            with self.subTest(command=command):
                self.assertBlocked(self.hook({"command": command}))

    @unittest.skipIf(NODE is None, "node is not on PATH")
    def test_opencode_plugin_fails_closed_without_loader(self) -> None:
        plugin_dir = self.cwd / "orphan/opencode"
        plugin_dir.mkdir(parents=True)
        shutil.copy(PLUGIN, plugin_dir / PLUGIN.name)
        driver = self.cwd / "orphan.mjs"
        driver.write_text(
            "import { pathToFileURL } from 'node:url';\n"
            "const [modulePath, directory] = process.argv.slice(2);\n"
            "const hooks = await (await import(pathToFileURL(modulePath).href)).default({ directory });\n"
            "try { await hooks['tool.execute.before']({ tool: 'bash' }, { args: { command: 'gh issue create --body hi' } });\n"
            "  process.stdout.write('allowed'); } catch (e) { process.stdout.write('blocked:' + e.message); }\n",
            encoding="utf-8",
        )
        out = subprocess.run([NODE, str(driver), str(plugin_dir / PLUGIN.name), str(self.cwd)],
                             capture_output=True, text=True, env=self.env, check=True).stdout
        self.assertTrue(out.startswith("blocked:AgentsMD could not run its Elon check"), out)

    @unittest.skipIf(NODE is None, "node is not on PATH")
    def test_opencode_plugin_throws_on_blocked_call(self) -> None:
        driver = self.cwd / "driver.mjs"
        driver.write_text(
            "import { pathToFileURL } from 'node:url';\n"
            "const [modulePath, directory, command] = process.argv.slice(2);\n"
            "const hooks = await (await import(pathToFileURL(modulePath).href)).default({ directory });\n"
            "try {\n"
            "  await hooks['tool.execute.before']({ tool: 'bash', sessionID: 's' }, { args: { command } });\n"
            "  process.stdout.write('allowed');\n"
            "} catch (error) { process.stdout.write('blocked:' + error.message); }\n",
            encoding="utf-8",
        )

        def run(command: str) -> str:
            return subprocess.run([NODE, str(driver), str(PLUGIN), str(self.cwd), command],
                                  capture_output=True, text=True, env=self.env, check=True).stdout

        self.assertTrue(run("gh issue create --body hi").startswith("blocked:AgentsMD blocked"))
        self.assertEqual(run("gh issue create --body " + shlex.quote(RECORD)), "allowed")
        self.assertEqual(run("ls"), "allowed")



class ElonContractTests(unittest.TestCase):
    def test_core_states_three_tests_and_the_enforced_record(self) -> None:
        core = " ".join((ROOT / "AGENTS.md").read_text(encoding="utf-8").split())
        for required in (
            "**Question the requirement.** Name who asked for each requirement and what breaks without it;",
            "**Work on the bottleneck.** Find where work waits and fix that first;",
            "**Go and see.** Run it, open it, read the real output.",
            "**Requirements and who asked**, **Deleted**, **Bottleneck**, **Checked myself**",
            "the Project Direction hook blocks `gh issue create` and `gh pr create` when a field is missing or empty.",
            "Create and edit Issues and PRs with `gh issue` and `gh pr` in the shell, not the raw API or another GitHub tool, so the Elon gate sees them.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, core)
        for template in ("skills/operations/workflows/to-spec/index.md",
                         "skills/operations/workflows/to-tickets/references/ticket-decomposition.md"):
            with self.subTest(template=template):
                self.assertIn("- **Checked myself:** <what you ran or read>",
                              (ROOT / template).read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
