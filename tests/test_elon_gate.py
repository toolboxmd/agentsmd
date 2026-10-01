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

    def test_text_that_only_mentions_creation_passes(self) -> None:
        # Regression from 2026-10-01: a research spawn was blocked because its
        # task text quoted the command under investigation.
        mention = "Find why this was blocked:\ngh issue create --title x\nDo not run it."
        for tool_input in ({"command": "ls", "description": mention},
                           {"prompt": mention, "description": "Research gate"},
                           {"task": mention}):
            with self.subTest(tool_input=tool_input):
                self.assertEqual(self.hook(tool_input).returncode, 0)
        self.assertBlocked(self.hook({"command": "gh issue create --title x", "description": mention}))

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

    # Regressions for #172: a body file written earlier in the same command.
    def test_body_file_written_by_a_heredoc_in_the_same_command(self) -> None:
        target = self.cwd / "rollup.md"
        for write in (f"cat > {target} <<'EOF'", f"cat <<'EOF' > {target}", f"cat >{target} <<EOF",
                      f"tee {target} <<'EOF' >/dev/null", "cat > rollup.md <<-EOF"):
            create = f"gh issue create -R o/r --title x --body-file {target}"
            # The heredoc body starts on the line after the one that declares it.
            for command in (write + "\n" + RECORD + "EOF\n" + create,
                            write + " && " + create + "\n" + RECORD + "EOF",
                            write + "; " + create + "\n" + RECORD + "EOF"):
                with self.subTest(command=command):
                    self.assertEqual(self.hook({"command": command}).returncode, 0, command)
                    self.assertFalse(target.exists())
                    missing = command.replace(RECORD, RECORD.replace("- **Bottleneck:** agents skip the procedure\n", ""))
                    self.assertBlocked(self.hook({"command": missing}), "Bottleneck")

    def test_heredoc_written_to_another_path_does_not_count(self) -> None:
        command = "cat > other.md <<'EOF'\n" + RECORD + "EOF\ngh pr create --body-file body.md"
        result = self.hook({"command": command})
        self.assertBlocked(result)
        self.assertIn("body.md does not exist", result.stderr)
        self.assertIn("--body-file -", result.stderr)

    def test_only_the_heredoc_that_feeds_stdin_counts(self) -> None:
        # Regression from the independent review of PR #187: bash feeds only the
        # last stdin heredoc to the command; another fd or a later `<` replaces it.
        for write in ("cat > b.md <<'FIRST' <<'SECOND'\n" + RECORD + "FIRST\nSECOND",
                      "cat > b.md 3<<'EOF'\n" + RECORD + "EOF",
                      "cat > b.md <<'EOF' < /dev/null\n" + RECORD + "EOF",
                      "cat > b.md <<'EOF' <<< ''\n" + RECORD + "EOF"):
            for create in ("gh issue create --body-file b.md", None):
                command = write + "\n" + (create or "")
                if create is None:
                    head, _, rest = write.partition("\n")
                    command = head + " | gh issue create --body-file -\n" + rest
                with self.subTest(command=command):
                    self.assertBlocked(self.hook({"command": command}))
        last = "cat > b.md <<'FIRST' <<'SECOND'\nnothing\nFIRST\n" + RECORD + "SECOND\ngh issue create --body-file b.md"
        self.assertEqual(self.hook({"command": last}).returncode, 0)
        stdin = "gh issue create --body-file - <<'EOF' < /dev/null\n" + RECORD + "EOF"
        self.assertBlocked(self.hook({"command": stdin}))

    def test_later_writes_replace_the_body_file(self) -> None:
        # Regressions from the second independent review of PR #187: the file
        # holds what the last write left, and only the last stdout target is filled.
        full = "cat > b.md <<'EOF'\n" + RECORD + "EOF\n"
        create = "gh issue create --body-file b.md"
        (self.cwd / "b.md").write_text(RECORD, encoding="utf-8")
        for command in ("cat > b.md > /dev/null <<'EOF'\n" + RECORD + "EOF\n" + create,
                        full + "cat > b.md <<'EMPTY'\nEMPTY\n" + create,
                        full + "printf '%s' \"$X\" > b.md\n" + create,
                        full + "echo x 2> b.md\n" + create,
                        ": > b.md && " + create,
                        "cat > b.md\n" + create):
            with self.subTest(command=command):
                self.assertBlocked(self.hook({"command": command}))
        for command in ("cat > /dev/null > b.md <<'EOF'\n" + RECORD + "EOF\n" + create,
                        ": > b.md\n" + full + create,
                        "cat <<'EOF' | tee b.md\n" + RECORD + "EOF\n" + create,
                        "cat > b.md <<'EOF' 2>/dev/null\n" + RECORD + "EOF\n" + create,
                        "echo start >> log.txt && " + create):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0, command)
        appended = "cat > b.md <<'EOF'\n- **Deleted:** x\nEOF\ncat >> b.md <<'EOF'\n" + RECORD + "EOF\n" + create
        self.assertEqual(self.hook({"command": appended}).returncode, 0)

    def test_body_file_written_after_cd_in_the_same_command(self) -> None:
        (self.cwd / "sub").mkdir()
        command = "cd sub && cat > b.md <<'EOF'\n" + RECORD + "EOF\ngh issue create --body-file ./b.md"
        self.assertEqual(self.hook({"command": command}).returncode, 0)

    def test_stdin_heredoc_and_inline_body_forms(self) -> None:
        stdin = "gh issue create --title x --body-file - <<'EOF'\n{}EOF"
        chained = "gh issue create --body-file - <<'EOF' && echo done\n{}EOF"
        piped = "cat <<'EOF' | gh issue create --body-file -\n{}EOF"
        inline = "gh pr create --title x --body {}"
        for template, quote in ((stdin, str), (chained, str), (piped, str), (inline, shlex.quote)):
            with self.subTest(template=template):
                self.assertEqual(self.hook({"command": template.format(quote(RECORD))}).returncode, 0)
                partial = RECORD.replace("- **Deleted:** the per-prompt reminder\n", "")
                self.assertBlocked(self.hook({"command": template.format(quote(partial))}), "Deleted")

    def test_accepted_label_forms(self) -> None:
        fields = ("Requirements and who asked", "Deleted", "Bottleneck", "Checked myself")
        accepted = ("- **{}:** v", "- **{}**: v", "**{}:** v", "* **{}**: v", "{}: v", "- {}: v",
                    "**{}:**\n  v")
        for form in accepted:
            with self.subTest(form=form):
                body = "\n".join(form.format(f) for f in fields)
                self.assertEqual(self.hook({"command": "gh issue create --body " + shlex.quote(body)}).returncode,
                                 0, body)
        rejected = ("- **{}** v", "{} v", "### {}\nv", "- **{}s:** v")
        for form in rejected:
            with self.subTest(form=form):
                body = "\n".join(form.format(f) for f in fields)
                self.assertBlocked(self.hook({"command": "gh issue create --body " + shlex.quote(body)}),
                                   *fields)

    def test_block_message_documents_the_accepted_forms(self) -> None:
        result = self.hook({"command": "gh issue create --body hi"})
        self.assertBlocked(result)
        self.assertIn("**Deleted:** value", result.stderr)
        self.assertIn("**Deleted**: value", result.stderr)
        self.assertIn("Deleted: value", result.stderr)

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
        core = " ".join((ROOT / "global/AGENTS.md").read_text(encoding="utf-8").split())
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
