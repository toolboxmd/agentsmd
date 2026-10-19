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
from unittest import mock
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

    def bash_argv(self, command: str, *, succeeds: bool = True, capture_stdin: bool = False) -> list[list[str]]:
        """Run real Bash with only gh replaced at the external-effect boundary."""
        binary = self.cwd / "fake-bin"
        binary.mkdir(exist_ok=True)
        gh = binary / "gh"
        gh.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['GH_ARGV_LOG'], 'a') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if os.environ.get('GH_STDIN_LOG'):\n"
            "    with open(os.environ['GH_STDIN_LOG'], 'w') as log:\n"
            "        log.write(sys.stdin.read())\n",
            encoding="utf-8",
        )
        gh.chmod(0o755)
        log = self.cwd / "argv.jsonl"
        log.write_text("", encoding="utf-8")
        pinned_path = str(binary) + os.pathsep + self.env["PATH"]
        guard = ("export PATH=" + shlex.quote(pinned_path) + "; "
                 "[ \"$(command -v gh)\" = " + shlex.quote(str(gh)) + " ] || exit 97; ")
        if command.startswith("zsh "):
            args = shlex.split(command)
            args[-1] = guard + args[-1]
            command = shlex.join(args)
        command = guard + command
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", command], cwd=self.cwd,
            env={**self.env, "PATH": str(binary) + os.pathsep + self.env["PATH"],
                 "GH_ARGV_LOG": str(log),
                 "GH_STDIN_LOG": str(self.cwd / "stdin.log") if capture_stdin else ""}, capture_output=True, text=True, timeout=10,
        )
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in log.read_text().splitlines()]

    def test_new_aliases_are_gated_and_accept_a_record(self) -> None:
        for kind in ("issue", "pr"):
            command = f"gh {kind} new --title x --body hello"
            with self.subTest(kind=kind):
                self.assertEqual(self.bash_argv(command),
                                 [[kind, "new", "--title", "x", "--body", "hello"]])
                self.assertBlocked(self.hook({"command": command}))
                self.assertEqual(self.hook({"command": f"gh {kind} new --body "
                                           + shlex.quote(RECORD)}).returncode, 0)

    @staticmethod
    def wrappers(call: str) -> tuple[str, ...]:
        return (f"URL=$({call})", f'URL="$({call})"', f"URL=`{call}`",
                f"({call})", "sh -c " + shlex.quote(call),
                "bash -c " + shlex.quote(call), "zsh -f -c " + shlex.quote(call))

    def test_confident_wrappers_check_their_own_body(self) -> None:
        for kind in ("issue", "pr"):
            for verb in ("create", "new"):
                for complete in (True, False):
                    record = RECORD if complete else "hello\n"
                    (self.cwd / "f.md").write_text(record, encoding="utf-8")
                    for args in ("--body-file f.md", "-F f.md",
                                 "--body " + shlex.quote(record),
                                 "--body-file - <<'EOF'\n" + record + "EOF\n"):
                        call = f"gh {kind} {verb} --title t " + args
                        for command in self.wrappers(call):
                            with self.subTest(command=command, complete=complete):
                                if not command.startswith("zsh") or shutil.which("zsh"):
                                    argv = self.bash_argv(command)
                                    self.assertEqual(argv[0][:4], [kind, verb, "--title", "t"])
                                result = self.hook({"command": command})
                                if complete:
                                    self.assertEqual(result.returncode, 0, result.stderr)
                                else:
                                    self.assertBlocked(result)

    def test_plain_commit_echo_and_printf_mentions_are_data(self) -> None:
        for command in (r'printf %s "gh issue create"',
                        r'printf "%s\n" "gh issue create"',
                        r'git commit -m "mention \"gh issue create\""',
                        r'echo "\$(gh issue create --body hello)"',
                        r'printf "%s" "\`gh issue create --body hello\`"'):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
                if command.startswith(("echo ", "printf ")):
                    self.assertEqual(self.bash_argv(command), [])
        for data in ("mention gh issue create", "mention gh pr new",
                     "$(gh issue create --body hello)", "`gh pr create --body hello`",
                     "sh -c 'gh issue create'", "{gh,} issue create", "gh $'issue' create"):
            commands = ("git commit -m " + shlex.quote(data),
                        "echo " + shlex.quote(data), "printf '%s' " + shlex.quote(data))
            if "$" not in data and "`" not in data and '"' not in data:
                commands += ('git commit -m "' + data + '"', 'echo "' + data + '"',
                             'printf "%s" "' + data + '"')
            for command in commands:
                with self.subTest(command=command):
                    self.assertEqual(self.hook({"command": command}).returncode, 0)
                if command.startswith(("echo ", "printf ")):
                    self.assertEqual(self.bash_argv(command), [])
            if data.startswith("mention"):
                for command in (f'git commit -m "{data}"', f'echo "{data}"',
                                f'printf "%s" "{data}"'):
                    self.assertEqual(self.hook({"command": command}).returncode, 0)
                if command.startswith(("echo ", "printf ")):
                    self.assertEqual(self.bash_argv(command), [])

    def test_nested_commands_check_each_visible_create(self) -> None:
        (self.cwd / "f.md").write_text(RECORD, encoding="utf-8")
        for call in ('echo $(gh pr create --body-file f.md)',
                     '(gh pr create --body-file f.md)'):
            for command in self.wrappers(call):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        for command in ('git commit -m "$(gh issue create --body hello)"',
                        'echo "$(gh issue create --body hello)"',
                        'gh pr create --body-file f.md --title $(gh issue create --body hello)'):
            self.assertBlocked(self.hook({"command": command}))

    def test_outer_blank_lines_preserve_wrappers_and_literal_data(self) -> None:
        for command in ('git commit -m "gh issue create"',
                        'echo "gh issue create"', 'printf "%s\\n" "gh issue create"'):
            self.assertEqual(self.hook({"command": "\n\t" + command + "\n"}).returncode, 0)
        for complete in (True, False):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello", encoding="utf-8")
            command = "\nURL=$(gh pr create --title t --body-file f.md)\n"
            self.assertEqual(self.bash_argv(command), [["pr", "create", "--title", "t", "--body-file", "f.md"]])
            result = self.hook({"command": command})
            if complete:
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                self.assertBlocked(result)

    def test_data_and_compound_wrappers_pass(self) -> None:
        (self.cwd / "f.md").write_text(RECORD, encoding="utf-8")
        for command in ('echo "$HOME gh issue create"',
                        "echo 'gh issue create' > log",
                        "echo 'gh issue create'; echo done",
                        "git -C repo commit -m 'gh issue create'",
                        "bash -lc 'gh pr create --body-file f.md'",
                        "URL=$(gh\tpr create --body-file f.md)",
                        "URL=$(gh pr create --body-file - <<EOF\n" + RECORD + "EOF\n)"):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        command = ("URL=$(gh pr create --body-file - <<'EOF'\nhello\nEOF\n"
                   "gh issue create --body " + shlex.quote(RECORD) + "\n)")
        argv = self.bash_argv(command)
        self.assertEqual(argv[0], ["pr", "create", "--body-file", "-"])
        self.assertEqual(argv[1], ["issue", "create", "--body", RECORD])
        self.assertBlocked(self.hook({"command": command}))

    def test_visible_wrapped_creates_require_records(self) -> None:
        for kind in ("issue", "pr"):
            for verb in ("create", "new"):
                call = f"gh {kind} {verb} --title x --body hello"
                forms = (
                    f"({call})", f"( ( {call} ) )", f"echo $({call})",
                    f'echo "$({call})"', f"echo `{call}`", f'echo "`{call}`"',
                    f"echo $(echo $({call}))", f"(echo $({call}))",
                    f"echo $( ({call}) )", f"sh -c '{call}'",
                    f"bash -c '{call}'",
                    f"s'h' -c '{call}'",
                    f"g'h' '{kind}' '{verb}' --title x --body hello",
                    f'gh "{kind}" "{verb}" --title x --body hello',
                    f'gh "{kind[:1]}\\\n{kind[1:]}" {verb} --title x --body hello',
                    f'gh {kind} "{verb[:1]}\\\n{verb[1:]}" --title x --body hello',
                )
                for command in forms:
                    with self.subTest(command=command):
                        self.assertIn([kind, verb, "--title", "x", "--body", "hello"],
                                      self.bash_argv(command))
                        self.assertBlocked(self.hook({"command": command}))

    def test_zsh_c_is_gated(self) -> None:
        command = "zsh -f -c 'gh issue create --body hello'"
        self.assertBlocked(self.hook({"command": command}))
        if shutil.which("zsh"):
            self.assertEqual(self.bash_argv(command), [["issue", "create", "--body", "hello"]])

    def test_250_bypasses_still_block_with_bash_argv_proof(self) -> None:
        for kind in ("issue", "pr"):
            for verb in ("create", "new"):
                call = f"gh {kind} {verb} --title x --body hello"
                cases = (
                    (call + " # --help", [kind, verb, "--title", "x", "--body", "hello"]),
                    (call + " \\\n# --help", [kind, verb, "--title", "x", "--body", "hello"]),
                    (f"gh {kind} {verb} --help <<< foo\n{call}",
                     [kind, verb, "--title", "x", "--body", "hello"]),
                    (f"gh {kind} {verb} -dt --help -b x", [kind, verb, "-dt", "--help", "-b", "x"]),
                    (f"gh {kind} {verb} -fb --help", [kind, verb, "-fb", "--help"]),
                    (f"gh {kind} {verb} --title '--help'", [kind, verb, "--title", "--help"]),
                )
                for command, argv in cases:
                    with self.subTest(command=command):
                        self.assertIn(argv, self.bash_argv(command))
                        self.assertBlocked(self.hook({"command": command}))
        # Bash's exec interface rejects NUL before execution. It must still be
        # blocked by the hook, rather than receiving the bare-help exemption.
        self.assertBlocked(self.hook({"command": "gh issue create --body hello\x00 --help"}))

    def test_each_visible_create_needs_its_own_record(self) -> None:
        for call in ("(gh issue create --body hello)",
                     "$(gh issue new --body hello)",
                     "`gh pr create --body hello`",
                     "sh -c 'gh pr new --body hello'"):
            with self.subTest(call=call):
                command = "gh issue create --body " + shlex.quote(RECORD) + "; " + call
                self.assertBlocked(self.hook({"command": command}))
        command = "(gh pr create --body " + shlex.quote(RECORD) + ")"
        self.assertEqual(self.hook({"command": command}).returncode, 0)

    def test_literal_create_mentions_remain_data_in_plain_commands(self) -> None:
        for data in ("gh issue create", "gh pr new"):
            for command in ("cat <<'EOF'\n" + data + "\nEOF",
                            "gh issue create --body " + shlex.quote(RECORD + data)):
                with self.subTest(command=command):
                    self.assertEqual(self.hook({"command": command}).returncode, 0)
            self.assertEqual(self.hook({"command": "printf '%s' " + shlex.quote(data)}).returncode, 0)

    def test_separate_body_file_avoids_dynamic_data_false_positive(self) -> None:
        data = RECORD + "\nExample: $(gh issue create) and sh -c 'gh pr new'\n"
        (self.cwd / "record.md").write_text(data, encoding="utf-8")
        self.assertEqual(self.hook({"command": "gh issue create --body-file record.md"}).returncode, 0)
        self.assertEqual(self.hook({"command": "gh pr new --body-file record.md"}).returncode, 0)

    def test_wrapped_help_never_uses_the_bare_help_exemption(self) -> None:
        for kind in ("issue", "pr"):
            for verb in ("create", "new"):
                call = f"gh {kind} {verb} --help"
                for command in (f"({call})", f"echo $({call})", f"echo `{call}`",
                                f"sh -c '{call}'"):
                    with self.subTest(command=command):
                        self.assertIn([kind, verb, "--help"], self.bash_argv(command))
                        self.assertBlocked(self.hook({"command": command}))

    def test_dynamic_looking_data_stays_literal(self) -> None:
        for data in ("$(gh issue create)", "`gh pr new`", "{gh,} issue create",
                     "gh $'issue' create", "sh -c 'gh issue create'"):
            for command in ("printf '%s' " + shlex.quote(data),
                            "cat <<'EOF'\n" + data + "\nEOF",
                            "gh issue create --body " + shlex.quote(RECORD + data)):
                with self.subTest(command=command):
                    result = self.hook({"command": command})
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_shell_fed_scripts_record_check_and_real_argv(self) -> None:
        for complete in (False, True):
            body = RECORD if complete else "hello"
            for kind, verb in (("issue", "create"), ("pr", "new")):
                call = f"gh {kind} {verb} --body " + shlex.quote(body)
                commands = []
                for shell in ("sh", "bash"):
                    for flags in ("", " -s"):
                        for operator in ("<<EOF", "<<'EOF'", '<<"EOF"', "<<-EOF", "0<<EOF"):
                            commands.append(f"{shell}{flags} {operator}\n{call}\nEOF\n")
                    commands.append(f"cat <<'EOF' | {shell}\n{call}\nEOF\n")
                commands.append("bash <<< " + shlex.quote(call))
                for command in commands:
                    with self.subTest(command=command, complete=complete):
                        self.assertEqual(self.bash_argv(command), [[kind, verb, "--body", body]])
                        result = self.hook({"command": command})
                        if complete and not command.startswith("cat "):
                            self.assertEqual(result.returncode, 0, result.stderr)
                        else:
                            self.assertBlocked(result)

    def test_create_heredoc_is_opaque_data(self) -> None:
        body = RECORD + "Examples: `gh issue create` $HOME $(gh pr new) (parentheses)\n"
        for command in ("gh pr create --body-file - <<'EOF'\n" + body + "EOF\n",
                        "URL=$(gh pr create --body-file - <<'EOF'\n" + body + "EOF\n) && echo \"$URL\""):
            self.assertEqual(self.bash_argv(command), [["pr", "create", "--body-file", "-"]])
            self.assertEqual(self.hook({"command": command}).returncode, 0)

    def test_compound_url_capture_checks_record(self) -> None:
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            command = 'URL=$(gh pr create --title t --body-file f.md) && echo "$URL"'
            self.assertEqual(self.bash_argv(command), [["pr", "create", "--title", "t", "--body-file", "f.md"]])
            self.assertEqual(self.hook({"command": command}).returncode, 0 if complete else 2)

    def test_read_only_searches_are_data(self) -> None:
        for command in ("rg gh issue create", "grep 'gh issue create' README.md",
                        "gh issue list --search 'gh issue create'",
                        "gh pr list --search 'gh pr create'",
                        "gh issue view 1 --json body", "gh pr search 'gh issue create'"):
            self.assertEqual(self.hook({"command": command}).returncode, 0, command)

    def test_repeated_body_options_block(self) -> None:
        (self.cwd / "good.md").write_text(RECORD)
        (self.cwd / "bad.md").write_text("hello")
        for options in ("--body-file good.md --body-file bad.md",
                        "--body-file bad.md --body-file good.md",
                        "--body " + shlex.quote(RECORD) + " --body hello",
                        "--body-file good.md --body hello"):
            command = "gh pr create " + options
            self.assertEqual(self.bash_argv(command), [["pr", "create"] + shlex.split(options)])
            self.assertBlocked(self.hook({"command": command}))

    def test_dynamic_shell_limits_are_not_inferred_from_raw_words(self) -> None:
        (self.cwd / "earlier.sh").write_text("gh issue create\n")
        for command in ("{gh,} issue create", "gh${IFS}issue${IFS}create",
                        "cmd=gh; $cmd issue create", "gh issue ${verb:-create}",
                        "eval '$SCRIPT'",
                        "alias c='gh issue create'; c",
                        "echo 'issue create --body hello' | xargs gh",
                        "sh earlier.sh"):
            self.assertEqual(self.hook({"command": command}).returncode, 0, command)
        self.assertBlocked(self.hook({"command": "cat > later.sh <<'EOF'\ngh issue create\nEOF\nsh later.sh"}))

    def test_literal_scripts_for_all_named_shells(self) -> None:
        for shell in ("sh", "bash", "zsh", "dash", "ksh"):
            for complete in (False, True):
                call = "gh pr new --body " + shlex.quote(RECORD if complete else "hello")
                command = shell + " -c " + shlex.quote(call)
                self.assertEqual(self.hook({"command": command}).returncode, 0 if complete else 2)

    @staticmethod
    def prefixed_creates(call: str) -> tuple[str, ...]:
        return tuple(prefix + call for prefix in
                     ("time ", "nohup ", "nice ", "timeout 2 ", "sudo ",
                      "echo x | xargs ", "find . -maxdepth 0 -exec ", "! ", "{ ", "then ", "do ", "else ",
                      "if ", "while ", "until ", "case x in x) ", "unknown-prefix "))

    def test_prefix_positions_cannot_hide_creates(self) -> None:
        for kind in ("issue", "pr"):
            for verb in ("create", "new"):
                for command in self.prefixed_creates(f"gh {kind} {verb} --body hello"):
                    with self.subTest(command=command):
                        self.assertBlocked(self.hook({"command": command}))
                for command in self.prefixed_creates(f"gh {kind} {verb} --body " + shlex.quote(RECORD)):
                    self.assertEqual(self.hook({"command": command}).returncode, 0)
        for command in ("time gh issue create --body hello",
                        "nohup gh issue create --body hello",
                        "nice gh issue create --body hello",
                        "timeout 2 gh issue create --body hello",
                        "{ gh issue create --body hello; }",
                        "if true; then gh issue create --body hello; fi",
                        "for x in a; do gh issue create --body hello; done",
                        "case x in x) gh issue create --body hello;; esac",
                        "case x in x)gh issue create --body hello;; esac",
                        "echo x | xargs gh issue create --body hello",
                        "i=0; while test $i = 0; do i=1; gh issue create --body hello; done",
                        "i=0; until test $i = 1; do i=1; gh issue create --body hello; done",
                        "while gh issue create --body hello; do break; done",
                        "until gh issue create --body hello; do break; done",
                        "find . -maxdepth 0 -exec gh issue create --body hello \\;"):
            prefix = shlex.split(command)[0]
            if prefix in ("{", "if", "for", "case", "while", "until") or "=" in prefix or shutil.which(prefix):
                self.assertEqual(self.bash_argv(command)[0][:2], ["issue", "create"])
            self.assertBlocked(self.hook({"command": command}))

    def test_prefix_oracle_keeps_hooks_when_timeout_is_unavailable(self) -> None:
        real_which, real_oracle = shutil.which, self.bash_argv
        observed = []
        def oracle(command: str) -> list[list[str]]:
            self.assertFalse(command.startswith("timeout "))
            observed.append(command)
            return real_oracle(command)
        with mock.patch("shutil.which", side_effect=lambda name: None if name == "timeout" else real_which(name)):
            with mock.patch.object(self, "bash_argv", side_effect=oracle):
                self.test_prefix_positions_cannot_hide_creates()
        self.assertTrue(observed)

    def test_literal_cat_heredoc_substitution_is_a_body(self) -> None:
        for complete in (False, True):
            body = RECORD if complete else "hello\n"
            for delimiter in ("EOF", "'EOF'", '\"EOF\"'):
                for quotes in ('"', ''):
                    command = ('gh pr create --title x --body ' + quotes
                               + '$(cat <<' + delimiter + '\n' + body + 'EOF\n)' + quotes)
                    with self.subTest(command=command):
                        self.assertEqual(self.hook({"command": command}).returncode,
                                         0 if complete and quotes else 2)
                        if quotes:
                            self.assertEqual(self.bash_argv(command),
                                             [["pr", "create", "--title", "x", "--body", body.rstrip('\n')]])

    def test_shell_script_arguments_and_literal_pipes(self) -> None:
        for complete in (False, True):
            body = RECORD if complete else "hello"
            call = "gh issue create --body " + shlex.quote(body)
            commands = [prefix + " <<'EOF'\n" + call + "\nEOF\n"
                        for prefix in ("bash -s foo", "bash -s -- foo", "bash /dev/stdin")]
            commands += ["bash -c -- " + shlex.quote(call)]
            for shell in ("sh", "bash"):
                commands += ["echo " + shlex.quote(call) + " | " + shell,
                             "printf '%s' " + shlex.quote(call) + " | " + shell,
                             "printf '%s\\n' " + shlex.quote(call) + " | " + shell]
            for command in commands:
                with self.subTest(command=command):
                    self.assertEqual(self.bash_argv(command), [["issue", "create", "--body", body]])
                    expected = 0 if complete and not command.startswith(("echo ", "printf ")) else 2
                    self.assertEqual(self.hook({"command": command}).returncode, expected)

    def test_array_literals_are_data_but_substitutions_execute(self) -> None:
        command = 'arr=(gh issue create); echo "${arr[@]}"'
        self.assertEqual(self.bash_argv(command), [])
        self.assertEqual(self.hook({"command": command}).returncode, 0)
        self.assertBlocked(self.hook({"command": 'arr=($(gh issue create --body hello))'}))

    @staticmethod
    def prefixed_shell_scripts(call: str) -> tuple[str, ...]:
        script = shlex.quote(call)
        return ("if true; then bash -c " + script + "; fi",
                "time bash -c " + script, "nohup bash -c " + script,
                "nice bash -c " + script, "sudo -n bash -c " + script,
                "{ bash -c " + script + "; }", "! bash -c " + script + "; true",
                ">/dev/null bash -c " + script,
                "<<< " + script + " bash",
                "find . -maxdepth 0 -exec sh -c " + script + " \\;",
                "nice sh <<'EOF'\n" + call + "\nEOF\n",
                "if true; then echo " + script + " | sh; fi")

    def test_prefixed_shells_use_the_same_positions_as_gh(self) -> None:
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            call = "gh issue create --body-file f.md"
            for command in self.prefixed_shell_scripts(call):
                with self.subTest(command=command, complete=complete):
                    prefix = shlex.split(command)[0]
                    if prefix != "sudo" and (prefix in ("if", "{", "!", ">/dev/null", "<<<") or shutil.which(prefix)):
                        self.assertEqual(self.bash_argv(command), [["issue", "create", "--body-file", "f.md"]])
                    conservative = command.startswith(("nice sh ", "<<< ")) or " | sh" in command
                    self.assertEqual(self.hook({"command": command}).returncode,
                                     0 if complete and not conservative else 2)

    def test_function_bodies_are_scanned_like_subshells(self) -> None:
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            command = "f() { gh issue create --body-file f.md; }; f"
            self.assertEqual(self.bash_argv(command), [["issue", "create", "--body-file", "f.md"]])
            self.assertEqual(self.hook({"command": command}).returncode, 0 if complete else 2)
        self.assertBlocked(self.hook({"command": "f() { gh issue create; }; f"}))

    def test_unquoted_heredoc_substitutions_execute_but_quoted_are_data(self) -> None:
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            call = "gh pr new --body-file f.md"
            for delimiter in ("EOF", "'EOF'", '\"EOF\"'):
                for body in ("$(" + call + ")", "`" + call + "`", "'$(" + call + ")'",
                             '\"$(' + call + ')\"'):
                    command = "cat <<" + delimiter + "\n" + body + "\nEOF\n"
                    with self.subTest(command=command, complete=complete):
                        unquoted = delimiter == "EOF"
                        self.assertEqual(self.bash_argv(command),
                                         [["pr", "new", "--body-file", "f.md"]] if unquoted else [])
                        self.assertEqual(self.hook({"command": command}).returncode,
                                         2 if unquoted and not complete else 0)
        for body in ("gh issue create", r"\$(gh issue create)", r"\`gh issue create\`"):
            command = "cat <<EOF\n" + body + "\nEOF\n"
            self.assertEqual(self.bash_argv(command), [])
            self.assertEqual(self.hook({"command": command}).returncode, 0)

    @staticmethod
    def shell_option_scripts(call: str) -> tuple[str, ...]:
        return tuple("bash " + flags + " <<EOF\n" + call + "\nEOF\n"
                     for flags in ("-o pipefail", "-O extglob", "+o pipefail",
                                   "--init-file foo", "--rcfile foo", "-euo pipefail", "+euo pipefail"))

    def test_shell_option_values_do_not_become_script_files(self) -> None:
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            commands = list(self.shell_option_scripts("gh issue create --body-file f.md"))
            commands.append("bash -eco pipefail 'gh issue create --body-file f.md'")
            for command in commands:
                with self.subTest(command=command, complete=complete):
                    self.assertEqual(self.bash_argv(command), [["issue", "create", "--body-file", "f.md"]])
                    self.assertEqual(self.hook({"command": command}).returncode, 0 if complete else 2)

    def test_arithmetic_is_data_but_nested_substitutions_execute(self) -> None:
        for command in ("echo $((gh issue create))", "echo $(( gh issue create ))"):
            with self.subTest(command=command):
                self.assertEqual(self.bash_argv(command, succeeds=False), [])
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        command = "echo $(( (1+2) * (4+5) ))"
        self.assertEqual(self.bash_argv(command), [])
        self.assertEqual(self.hook({"command": command}).returncode, 0)
        for complete in (False, True):
            (self.cwd / "f.md").write_text(RECORD if complete else "hello")
            command = "echo $((0$(gh issue create --body-file f.md)))"
            self.assertEqual(self.bash_argv(command), [["issue", "create", "--body-file", "f.md"]])
            self.assertEqual(self.hook({"command": command}).returncode, 0 if complete else 2)

    @staticmethod
    def round_four_commands() -> list[str]:
        return [
            "echo " + shlex.quote("x\\c\n" + RECORD) + " | gh issue create -t x -F -",
            "gh issue --title T create -b y",
            "gh pr -B main new -t x -b y",
            "cat <<BODY-X\nbody\nBODY-X\ngh issue create -b y",
            "cat <<EOF.\nbody\nEOF.\ngh pr new -b y",
            "gh pr create --body-file - <<'PR-BODY'\n" + RECORD + "PR-BODY\n",
        ]

    def test_echo_backslashes_and_options_are_unknown_body_sources(self) -> None:
        for flag in ("", "-n ", "-e ", "-E "):
            body = "x\\c\n" + RECORD if not flag else RECORD
            command = "echo " + flag + shlex.quote(body) + " | gh issue create -t x -F -"
            with self.subTest(command=command):
                self.assertBlocked(self.hook({"command": command}))
                self.assertEqual(self.bash_argv(command), [["issue", "create", "-t", "x", "-F", "-"]])
        if shutil.which("zsh"):
            command = "zsh -f -c " + shlex.quote(self.round_four_commands()[0])
            self.assertBlocked(self.hook({"command": command}))
            self.assertEqual(self.bash_argv(command, capture_stdin=True), [["issue", "create", "-t", "x", "-F", "-"]])
            self.assertEqual((self.cwd / "stdin.log").read_text(), "x")

    def test_create_flags_before_verb_do_not_hide_creates(self) -> None:
        for prefix in ("gh issue --title T", "gh pr -B main", "gh issue --title create"):
            for verb in ("create", "new"):
                for body, expected in (("hello", 2), (RECORD, 0)):
                    command = prefix + " " + verb + " -b " + shlex.quote(body)
                    with self.subTest(command=command):
                        self.assertEqual(self.bash_argv(command), [shlex.split(command)[1:]])
                        self.assertEqual(self.hook({"command": command}).returncode, expected)

    def test_full_heredoc_delimiter_words(self) -> None:
        for raw, delimiter in (("BODY-X", "BODY-X"), ("EOF.", "EOF."),
                               ("'PR-BODY'", "PR-BODY"), ('E"OF"', "EOF"),
                               (r"E\OF", "EOF"), ('"PR-BODY"', "PR-BODY")):
            for body, expected in (("hello\n", 2), (RECORD, 0)):
                for prefix in ("gh pr create --body-file -", "bash"):
                    content = body if prefix != "bash" else "gh pr new -b " + shlex.quote(body) + "\n"
                    command = prefix + " <<" + raw + "\n" + content + delimiter + "\n"
                    with self.subTest(command=command):
                        argv = (["pr", "create", "--body-file", "-"] if prefix != "bash"
                                else ["pr", "new", "-b", body])
                        self.assertEqual(self.bash_argv(command), [argv])
                        self.assertEqual(self.hook({"command": command}).returncode, expected)
            command = "cat <<" + raw + "\ndata\n" + delimiter + "\ngh issue create -b y"
            with self.subTest(command=command):
                self.assertEqual(self.bash_argv(command), [["issue", "create", "-b", "y"]])
                self.assertBlocked(self.hook({"command": command}))

    @staticmethod
    def unknown_producer_scripts(body: str) -> list[str]:
        call = "gh issue create --body " + shlex.quote(body)
        quoted = shlex.quote(call)
        rows = ["echo " + flag + " " + quoted + " | sh"
                for flag in ("-n", "-e", "-E", "-ne")]
        rows += ["echo 'gh issue' " + shlex.quote("create --body " + shlex.quote(body)) + " | bash",
                 "echo " + shlex.quote("true\\n" + call) + " | bash",
                 "printf -- '%s\\n' " + quoted + " | sh",
                 "printf " + quoted + " | sh",
                 "printf " + shlex.quote(call + "\\n") + " | sh"]
        rows += [prefix + " <<'EOF' | " + shell + "\n" + call + "\nEOF\n"
                 for prefix in ("cat -", "cat --", "cat -u", "cat -s", "grep issue", "head -1")
                 for shell in ("sh", "bash")]
        rows += ["echo -n " + quoted + " | head -1 | sh",
                 "if true; then echo -n " + quoted + " | sh; fi",
                 "echo -n " + quoted + " | nice sh"]
        return rows

    def test_unmodeled_producers_with_visible_creates_fail_closed(self) -> None:
        for body in ("hello", RECORD):
            for command in self.unknown_producer_scripts(body):
                with self.subTest(command=command):
                    self.assertBlocked(self.hook({"command": command}))
                    # Backslash echo is shell-dependent; zsh covers it below.
                    if "true\\n" not in command:
                        truncated = body == RECORD and ("grep issue" in command or "head -1" in command)
                        if truncated:
                            self.assertEqual(self.bash_argv(command, succeeds=False), [])
                        else:
                            self.assertEqual(self.bash_argv(command), [["issue", "create", "--body", body]])
        for command in ("echo -n hello | sh", "grep foo file | sh"):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        if shutil.which("zsh"):
            command = "zsh -f -c " + shlex.quote("echo " + shlex.quote("true\\ngh issue create --body hello") + " | bash")
            self.assertBlocked(self.hook({"command": command}))
            self.assertEqual(self.bash_argv(command), [["issue", "create", "--body", "hello"]])

    @staticmethod
    def unreadable_shell_scripts(body: str) -> list[tuple[str, list[str]]]:
        call = "gh issue create -b " + shlex.quote(body)
        return [
            ("echo -n " + shlex.quote("gh issue --title T create -b " + shlex.quote(body)) + " | sh",
             ["issue", "--title", "T", "create", "-b", body]),
            ("echo -n " + shlex.quote("gh -R o/r issue create -b " + shlex.quote(body)) + " | sh",
             ["-R", "o/r", "issue", "create", "-b", body]),
            ("cat -s <<'EOF' | sh\ngh issue \\\ncreate -b " + shlex.quote(body) + "\nEOF\n",
             ["issue", "create", "-b", body]),
            ('bash <<< "$(echo -n ' + shlex.quote(call) + ')"', ["issue", "create", "-b", body]),
            ("bash <<EOF\n$(echo -n " + shlex.quote(call) + ")\nEOF\n", ["issue", "create", "-b", body]),
            ("sh <<EOF\n`echo -n " + shlex.quote(call) + "`\nEOF\n", ["issue", "create", "-b", body]),
        ]

    def test_unreadable_shell_scripts_use_normal_create_classification(self) -> None:
        for body in ("hello", RECORD):
            for command, argv in self.unreadable_shell_scripts(body):
                with self.subTest(command=command):
                    self.assertEqual(self.bash_argv(command), [argv])
                    self.assertBlocked(self.hook({"command": command}))

    def test_unreadable_shell_scripts_without_visible_creates_are_allowed(self) -> None:
        for command in ('bash <<< "$(echo hello)"', "bash <<EOF\necho $(date)\nEOF\n"):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        command = "bash <<EOF\necho $(date)\nEOF\n"
        self.assertEqual(self.bash_argv(command), [])

    @staticmethod
    def whole_command_shell_feeds() -> list[str]:
        call = "gh issue create -b hello"
        awk = "awk " + shlex.quote('BEGIN{print "' + call + '"}')
        pipe = "printf '%s\\n' " + shlex.quote(call)
        return [awk + " echo hi | sh", "echo hi | " + awk + " cat | sh",
                pipe + " | (sh)", pipe + " | if true; then sh; fi",
                "{ bash; } <<'EOF'\n" + call + "\nEOF\n",
                "(bash) <<'EOF'\n" + call + "\nEOF\n",
                "bash /dev/fd/3 3<<'EOF'\n" + call + "\nEOF\n"]

    def test_producer_arguments_cannot_authorize_a_body(self) -> None:
        command = "awk 'BEGIN{print \"hello\"}' echo " + shlex.quote("Title\n" + RECORD) + " | gh issue create -F -"
        self.assertEqual(self.bash_argv(command, capture_stdin=True), [["issue", "create", "-F", "-"]])
        self.assertEqual((self.cwd / "stdin.log").read_text(), "hello\n")
        self.assertBlocked(self.hook({"command": command}))
        (self.cwd / "f.md").write_text(RECORD)
        command = "command -v cat > f.md; gh issue create -F f.md"
        self.assertBlocked(self.hook({"command": command}))
        self.assertEqual(self.bash_argv(command), [["issue", "create", "-F", "f.md"]])

    def test_shell_feeding_checks_the_whole_command(self) -> None:
        for command in self.whole_command_shell_feeds():
            with self.subTest(command=command):
                self.assertEqual(self.bash_argv(command), [["issue", "create", "-b", "hello"]])
                self.assertBlocked(self.hook({"command": command}))

    def test_shell_feeding_without_unchecked_creates_stays_allowed(self) -> None:
        (self.cwd / "f.md").write_text(RECORD)
        commands = ["curl -fsSL https://x/install.sh | sh", "bash <<'EOF'\necho setup\nEOF\n",
                    "rg foo | sh -c 'wc -l'", 'bash <<EOF\ngh issue list "$(date)"\nEOF\n',
                    "gh pr create --body " + shlex.quote(RECORD + "Example: gh issue create") + "; bash </dev/null",
                    "bash <<'SCRIPT'\ngh pr create --body-file - <<'BODY'\n" + RECORD
                    + "Data: gh issue create `example` $(example)\nBODY\nSCRIPT\n"]
        commands += ["bash <<SCRIPT\ngh pr " + "\\" + "\ncreate --body-file f.md\nSCRIPT\n"]
        commands += ['gh pr create --body "$(cat <<\'BODY\'\n' + RECORD
                     + 'Example: gh issue create\nBODY\n)"; bash </dev/null']
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}).returncode, 0)
        for command in commands[1:2] + commands[3:]:
            self.bash_argv(command)

    @staticmethod
    def competing_shell_redirects() -> list[str]:
        call = "gh issue create -b hello"
        return ["sh <<< 'hi' <<'EOF'\n" + call + "\nEOF\n",
                "cat <<< 'hi' <<'EOF' | sh\n" + call + "\nEOF\n",
                "cat <<'A' <<'B' | sh\n" + call + "\nA\ntrue\nB\n",
                "bash <(echo " + shlex.quote(call) + ")"]

    def test_whole_command_keeps_all_redirected_script_text(self) -> None:
        for index, command in enumerate(self.competing_shell_redirects()):
            with self.subTest(command=command):
                expected = [] if index == 2 else [["issue", "create", "-b", "hello"]]
                self.assertEqual(self.bash_argv(command), expected)
                self.assertBlocked(self.hook({"command": command}))
                zsh = "zsh -f -c " + shlex.quote(command)
                self.assertBlocked(self.hook({"command": zsh}))
                if shutil.which("zsh"):
                    self.assertEqual(self.bash_argv(zsh), [["issue", "create", "-b", "hello"]])

    def test_main_differential_has_no_unintended_allowances(self) -> None:
        # The exact shipped classifier is an independent safety baseline.
        baseline = self.cwd / "baseline"
        baseline.mkdir()
        for name in ("project-direction", "agentsmd_instructions.py"):
            path = baseline / name
            path.write_bytes(subprocess.check_output(
                ["git", "show", "15b1dd5:bin/" + name], cwd=ROOT))
            path.chmod(0o755)
        corpus = self.round_four_commands() + self.unknown_producer_scripts("hello") + list(self.prefixed_creates("gh issue create --body hello"))
        corpus += ["gh issue create --body hello", "gh issue create --help",
                   "gh issue create --title --help", "gh issue create # --help",
                   "gh pr create --body-file missing.md",
                   "gh -R view issue create --body hello",
                   "gh --repo search pr create --body hello",
                   "gh view gh issue create --body hello",
                   "case x in x)gh issue create --body hello;; esac",
                   "i=0; while test $i = 0; do i=1; gh issue create --body hello; done",
                   "i=0; until test $i = 1; do i=1; gh issue create --body hello; done",
                   "while gh issue create --body hello; do break; done",
                   "until gh issue create --body hello; do break; done",
                   "find . -maxdepth 0 -exec gh issue create --body hello \\;",
                   "nice gh api -X POST repos/o/r/issues -f body=hello",
                   "gh pr create --body " + shlex.quote(RECORD)]
        corpus += self.competing_shell_redirects()
        corpus += ["zsh -f -c " + shlex.quote(command) for command in self.competing_shell_redirects()]
        corpus += self.whole_command_shell_feeds()
        corpus += ["cat > f.md <<'BODY'\n" + RECORD + "BODY\ncommand -v cat > f.md; gh issue create -F f.md"]
        corpus += [command for command, _ in self.unreadable_shell_scripts("hello")]
        corpus += ['bash <<< "$(echo hello)"', "bash <<EOF\necho $(date)\nEOF\n"]
        corpus += list(self.prefixed_shell_scripts("gh issue create --body hello"))
        corpus += ["f() { gh issue create; }; f",
                   "cat <<EOF\n$(gh issue create --body hello)\nEOF\n",
                   "cat <<EOF\n`gh pr new --body hello`\nEOF\n",
                   "cat <<'EOF'\n$(gh issue create --body hello)\nEOF\n",
                   'cat <<"EOF"\n`gh pr new --body hello`\nEOF\n']
        corpus += list(self.shell_option_scripts("gh issue create --body hello"))
        corpus += ["echo $((gh issue create))", "echo $((0$(gh issue create --body hello)))",
                   "echo -n hello | sh", "grep foo file | sh"]
        # Only these exact data/corrected-record rows may stop blocking vs main.
        intended = {
            # Main truncates PR-BODY and rejects this required complete record.
            "gh pr create --body-file - <<'PR-BODY'\n" + RECORD + "PR-BODY\n",
            "echo $(( gh issue create ))",
            "echo 'gh issue create'", 'git commit -m "gh issue create"',
            "printf '%s' 'gh issue create'", "rg gh issue create",
            "grep 'gh issue create' README.md",
            "gh issue list --search 'gh issue create'",
            "gh pr list --search 'gh pr create'",
            "gh -R o/r issue list --search gh issue create",
        }
        corpus += ['gh pr create --body $(cat <<EOF\n' + RECORD + 'EOF\n)']
        corpus += ['gh pr create --body "$(cat <<EOF\nRequirements and who asked: $VAR\nDeleted: $VAR\nBottleneck: $VAR\nChecked myself: $VAR\nEOF\n)"']
        corpus += sorted(intended)
        for command in corpus:
            event = {"hook_event_name": "PreToolUse", "cwd": str(self.cwd),
                     "tool_input": {"command": command}}
            before = subprocess.run([str(baseline / "project-direction"), "hook", "--host", "claude"],
                                    input=json.dumps(event), capture_output=True, text=True, env=self.env)
            after = self.hook({"command": command})
            with self.subTest(command=command):
                self.assertIn(before.returncode, (0, 2), before.stderr)
                if before.returncode == 2 and command not in intended:
                    self.assertBlocked(after)

    def test_create_help_passes_without_a_record(self) -> None:
        for kind in ("issue", "pr"):
            for help_flag in ("--help", "-h", "--help=true", "--help=TRUE", "--help=True", "--help=1", "--help=t", "--help=T"):
                for args in (f"{kind} create {help_flag}",
                             f"{kind} create -R o/r {help_flag}",
                             f"{kind} create {help_flag} -R o/r",
                             f"{kind} create --repo o/r {help_flag}",
                             f"{kind} create {help_flag} --repo o/r",
                             f"{kind} create --repo=o/r {help_flag}",
                             f"{kind} create {help_flag} --repo=o/r"):
                    for verb in ("create", "new"):
                        command = "gh " + args.replace(" create ", " " + verb + " ")
                        with self.subTest(command=command):
                            self.assertEqual(self.bash_argv(command),
                                             [shlex.split(command)[1:]])
                            result = self.hook({"command": command})
                            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_help_does_not_exempt_another_create_in_the_command(self) -> None:
        for operator in (";", "&&", "||", "|", "|&", "&", "\n"):
            for first, second in (("issue", "pr"), ("pr", "issue")):
                for help_first in (True, False):
                    help_call = f"gh {first} create --help"
                    create = f"gh {second} create --title x --body hello"
                    calls = (help_call, create) if help_first else (create, help_call)
                    command = f" {operator} ".join(calls)
                    with self.subTest(command=command):
                        self.assertBlocked(self.hook({"command": command}))

    def test_help_text_used_as_a_value_does_not_exempt_a_create(self) -> None:
        for kind in ("issue", "pr"):
            for flag in ("-R", "--repo", "--hostname", "-a", "--assignee", "--attach",
                         "--blocked-by", "--blocking", "-B", "--base", "-b", "--body",
                         "-F", "--body-file", "-H", "--head", "-l", "--label", "-m",
                         "--milestone", "--parent", "-p", "--project", "--recover",
                         "-r", "--reviewer", "-T", "--template", "-t", "--title", "--type"):
                for value in ("--help", "-h"):
                    with self.subTest(kind=kind, flag=flag, value=value):
                        self.assertBlocked(self.hook({"command": f"gh {kind} create {flag} '{value}'"}))
            self.assertBlocked(self.hook({"command": f"gh {kind} create -- --help"}))
            for redirect in (">", "<", "2>"):
                self.assertBlocked(self.hook({"command": f"gh {kind} create --body hello {redirect} --help"}))

    def test_comments_cannot_supply_help_or_a_body(self) -> None:
        for kind in ("issue", "pr"):
            for comment in ("# --help", "# -h", "#comment --help"):
                for args in (f"--title x --body hello {comment}",
                             f"{comment} --title x --body hello"):
                    with self.subTest(kind=kind, args=args):
                        self.assertBlocked(self.hook({"command": f"gh {kind} create {args}"}))
            with self.subTest(kind=kind, comment="body"):
                self.assertBlocked(self.hook({"command": f"gh {kind} create # --body " + shlex.quote(RECORD)}))
        self.assertBlocked(self.hook({"command": "gh api repos/o/r/issues -f body=hello # -f body="
                                     + shlex.quote(RECORD)}))

    def test_hashes_in_values_are_not_comments(self) -> None:
        for kind in ("issue", "pr"):
            for title in ("x#", '"a # b"', '"#"', r"\#", r"a\ #"):
                with self.subTest(kind=kind, title=title):
                    command = f"gh {kind} create --title {title}"
                    self.assertBlocked(self.hook({"command": command + " --body hello"}))
                    self.assertBlocked(self.hook({"command": command + " --help"}))
                    self.assertEqual(self.hook({"command": command + " --body " + shlex.quote(RECORD)}).returncode, 0)
            for value in ("false", "FALSE", "False", "0", "f", "F"):
                self.assertBlocked(self.hook({"command": f"gh {kind} create --help={value}"}))

    def test_line_continuations_before_help_and_comments(self) -> None:
        continuation = "\\\n"
        for kind in ("issue", "pr"):
            create = f"gh {kind} create --title x --body hello "
            cases = (
                (create + continuation + "# --help", False),
                (create + continuation + "# -h", False),
                (create + continuation + "--help", False),
                # Removing the continuation joins a word; x# is still data.
                (f"gh {kind} create --title x" + continuation + "# --help", False),
                # An escaped hash remains data after a continuation.
                (create + continuation + r"\# --help", False),
                # A comment's trailing backslash does not continue the comment.
                (create + "--help # ignored " + continuation + "gh issue list", False),
                ("gh issue list # ignored " + continuation + create, False),
                # Backslash-CRLF escapes CR, not LF; the next line is separate.
                (create + "\\\r\n# --help", False),
            )
            for command, allowed in cases:
                with self.subTest(command=command):
                    result = self.hook({"command": command})
                    if allowed:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertBlocked(result)
        self.assertBlocked(self.hook({"command": "gh api repos/o/r/issues -f body=hello " + continuation
                                     + "# -f body=" + shlex.quote(RECORD)}))

    def test_comment_ends_at_newline_not_a_commented_separator(self) -> None:
        command = "gh issue list # ignored ; gh pr create --body hello"
        self.assertEqual(self.hook({"command": command}).returncode, 0)
        self.assertBlocked(self.hook({"command": command + "\ngh pr create --body hello"}))

    def test_help_exemption_rejects_shell_syntax_in_the_raw_command(self) -> None:
        for kind in ("issue", "pr"):
            help_call = f"gh {kind} create --help"
            for suffix in ("\n", "\r", ";", " && true", " || true", " | cat", " |& cat", " &",
                           " <<EOF\nEOF", " <<< foo", " >out", " <in", " # comment",
                           " $(true)", " <(true)", " >(true)", " `true`",
                           " --title 'a; b'", " --title 'a # b'"):
                with self.subTest(kind=kind, suffix=suffix):
                    self.assertBlocked(self.hook({"command": help_call + suffix}))
            # Even a later create with a valid record cannot exempt compound help.
            command = help_call + "; gh pr create --body " + shlex.quote(RECORD)
            self.assertBlocked(self.hook({"command": command}))
            self.assertBlocked(self.hook({"command": "env " + help_call}))
        self.assertBlocked(self.hook({"command": ["gh issue create --help",
                                                   "gh pr create --body " + shlex.quote(RECORD)]}))

    def test_here_string_does_not_swallow_a_later_create(self) -> None:
        for prefix in ("cat <<< foo", "gh issue create --help <<< foo"):
            for create in ("gh pr create --title x --body hello",
                           "gh api repos/o/r/issues -f body="):
                with self.subTest(prefix=prefix, create=create):
                    self.assertBlocked(self.hook({"command": prefix + "\n" + create}))

    def test_malformed_command_cannot_get_the_help_exemption(self) -> None:
        for suffix in (" '", ' "', " \\"):
            with self.subTest(suffix=suffix):
                self.assertBlocked(self.hook({"command": "gh issue create --help" + suffix}))

    def test_help_exemption_requires_the_raw_character_allow_list(self) -> None:
        for kind in ("issue", "pr"):
            commands = (
                f"gh {kind} create --title x --body hello\x00 --help",
                f"gh\t{kind}\tcreate\t--help",
                f'gh {kind} create --title "a b" --help',
                f"gh {kind} create --title 'a b' --help",
                f"gh {kind} create --title café --help",
                f"gh {kind} create --title {{x,y}} --help",
                f"gh {kind} create --title a\\ b --help",
            )
            for command in commands:
                with self.subTest(command=command):
                    self.assertBlocked(self.hook({"command": command}))
            # Allowed raw characters alone do not make a non-bare help call exempt.
            command = f"gh {kind} create --title Az09-_./=:,@+ --help"
            self.assertBlocked(self.hook({"command": command}))

    def test_only_bare_help_with_at_most_one_repo_selector_is_exempt(self) -> None:
        for command in ("gh pr create -dt --help -b x", "gh pr create -fb --help"):
            with self.subTest(command=command):
                self.assertBlocked(self.hook({"command": command}))
        for kind in ("issue", "pr"):
            for args in ("--title x --help", "--help --title x", "--help x", "x --help",
                         "--help --help", "-R o/r --help --repo o/r", "--help -R o/r -R o/r",
                         "--repo= --help", "--repo=--help --help", "-R --help --help",
                         "--repo host/o/r --help", "--repo o/ --help", "--repo /r --help",
                         "--help --fill", "--draft --help", "--help --body x"):
                with self.subTest(kind=kind, args=args):
                    self.assertBlocked(self.hook({"command": f"gh {kind} create {args}"}))
            for command in (f"gh -R o/r {kind} create --help", f"gh {kind} --help create"):
                with self.subTest(command=command):
                    self.assertBlocked(self.hook({"command": command}))

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

    # Regressions for #225: patch data is an edit, not a command the tool runs.
    def test_patch_payload_with_a_create_example_is_an_edit(self) -> None:
        patch = ("*** Begin Patch\n*** Update File: README.md\n@@\n-old\n"
                 "+    gh pr create --title x --body-file body.md\n"
                 " gh issue create --title y --body hi\n*** End Patch\n")
        # Codex sends apply_patch, including one nested in functions.exec, as
        # tool_input.command; an untagged envelope is still patch data.
        for tool_name in ("apply_patch", None):
            with self.subTest(tool_name=tool_name):
                extra = {"tool_name": tool_name} if tool_name else {}
                result = self.hook({"command": patch}, host="codex", **extra)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(self.hook({"command": ["apply_patch", patch]}, host="codex").returncode, 0)
        heredoc = "apply_patch <<'EOF'\n" + patch + "EOF"
        self.assertEqual(self.hook({"command": heredoc}, tool_name="Bash").returncode, 0)

    def test_shell_tool_still_runs_a_patch_shaped_command(self) -> None:
        # The tool boundary, not the text shape, decides: a shell runs every line.
        command = "*** Begin Patch\ngh pr create --title x --body hi\n*** End Patch"
        self.assertBlocked(self.hook({"command": command}, tool_name="Bash"))
        after_edit = "apply_patch <<'EOF'\n*** Begin Patch\n*** End Patch\nEOF\ngh issue create --body hi"
        self.assertBlocked(self.hook({"command": after_edit}, tool_name="Bash"))
        self.assertEqual(self.hook({"command": after_edit.replace("--body hi", "--body " + shlex.quote(RECORD))},
                                   tool_name="Bash").returncode, 0)

    # Regressions for #226: `gh api` creation faces the same record requirement.
    def test_gh_api_creation_needs_the_record(self) -> None:
        (self.cwd / "issue.json").write_text(json.dumps({"title": "x", "body": RECORD}), encoding="utf-8")
        (self.cwd / "body.md").write_text(RECORD, encoding="utf-8")
        for endpoint in ("repos/o/r/issues", "/repos/{owner}/{repo}/pulls"):
            for args, ok in ((f"-X POST {endpoint} -f title=x -f body=hi", False),
                             (f"--method POST {endpoint} -f title=x", False),
                             (f"{endpoint} -f title=x -f body=hi", False),
                             (f"{endpoint} --raw-field title=x -F body=@absent.md", False),
                             (f"{endpoint} -f title=x -f body={shlex.quote(RECORD)}", True),
                             (f"{endpoint} -F title=x -F body=@body.md", True),
                             (f"{endpoint} --input issue.json", True),
                             (f"--method=POST {endpoint} --field body=@- <<'EOF'\n{RECORD}EOF", True)):
                command = "gh api " + args
                with self.subTest(command=command):
                    result = self.hook({"command": command}, tool_name="Bash")
                    if ok:
                        self.assertEqual(result.returncode, 0, result.stderr)
                    else:
                        self.assertBlocked(result, "Deleted")
        self.assertBlocked(self.hook({"command": "gh -R o/r api -XPOST repos/o/r/issues -f title=x"}))

    def test_gh_api_input_is_the_only_body(self) -> None:
        # Regression from the Grok roast of PR #233: with --input, gh sends the
        # file as the request body and field flags go to the query string.
        (self.cwd / "empty.json").write_text(json.dumps({"body": "nope"}), encoding="utf-8")
        (self.cwd / "good.json").write_text(json.dumps({"body": RECORD}), encoding="utf-8")
        (self.cwd / "rec.md").write_text(RECORD, encoding="utf-8")
        api = "gh api repos/o/r/issues "
        for args in ("--input empty.json -f body=" + shlex.quote(RECORD),
                     "-f body=" + shlex.quote(RECORD) + " --input empty.json",
                     "--input empty.json -F body=@rec.md",
                     "--input - -f body=" + shlex.quote(RECORD),
                     "--input - <<'EOF'\n" + json.dumps({"body": "nope"}) + "\nEOF"):
            with self.subTest(args=args):
                self.assertBlocked(self.hook({"command": api + args}, tool_name="Bash"), "Deleted")
        for args in ("--input good.json -f body=hi", "-f body=hi --input good.json",
                     "--input - <<'EOF'\n" + json.dumps({"body": RECORD}) + "\nEOF",
                     "-f body=hi --input - <<'EOF'\n" + json.dumps({"body": RECORD}) + "\nEOF"):
            with self.subTest(args=args):
                result = self.hook({"command": api + args}, tool_name="Bash")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_read_only_gh_api_and_status_posts_pass(self) -> None:
        for command in ("gh api repos/o/r/issues",
                        "gh api repos/o/r/pulls?state=open --jq '.[].title'",
                        "gh api -X GET repos/o/r/issues -f state=open",
                        "gh api repos/o/r/issues/5/comments -f body=hi",
                        "gh api -X PATCH repos/o/r/issues/5 -f body=hi",
                        "gh api repos/{owner}/{repo}/statuses/abc123 -f state=success "
                        "-f context=review/independent -f description='create ok'"):
            with self.subTest(command=command):
                self.assertEqual(self.hook({"command": command}, tool_name="Bash").returncode, 0)

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
        self.assertTrue(run("gh api repos/o/r/issues -f title=x").startswith("blocked:AgentsMD blocked"))



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
        for template in ("skills/operations/procedures/to-spec/index.md",
                         "skills/operations/procedures/to-tickets/references/ticket-decomposition.md"):
            with self.subTest(template=template):
                self.assertIn("- **Checked myself:** <what you ran or read>",
                              (ROOT / template).read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
