"""Deterministic checks for the #164 trigger-test harness (no model runs)."""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = ROOT / "docs/work/164-trigger-audit/trigger_test.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("trigger_test", HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LoginFilesChangedTests(unittest.TestCase):
    def setUp(self):
        self.t = load_harness()
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-164-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        # A fake login file and a minimal plugin source; no real login is read or linked.
        self.login = self.tmp / "auth.json"
        self.login.write_text('{"token": "old"}')
        source = self.tmp / "source"
        (source / "global").mkdir(parents=True)
        (source / "global/AGENTS.md").write_text("# Contract\n")
        self.t.SOURCES["branch"] = source
        self.t.LOGIN["opencode"] = self.login
        self.stub = self.tmp / "bin"
        self.stub.mkdir()
        path = os.environ["PATH"]
        self.addCleanup(os.environ.__setitem__, "PATH", path)
        os.environ["PATH"] = f"{self.stub}{os.pathsep}{path}"

    def stub_opencode(self, script):
        (self.stub / "opencode").write_text("#!/bin/sh\n" + script)
        (self.stub / "opencode").chmod(0o755)

    def run_case(self):
        rows, item = self.t.run("opencode", "stub", "", "branch", self.t.CASES[0], 0)
        json.dumps(item)  # the record stays serializable
        return item

    def test_record_names_a_login_file_the_run_changed(self):
        self.stub_opencode(f"printf '{{\"token\": \"new\"}}' > '{self.login}'\n")
        item = self.run_case()
        self.assertEqual(item["login_files_changed"], [str(self.login)])

    def test_record_is_empty_when_login_files_are_untouched(self):
        self.stub_opencode("exit 0\n")
        item = self.run_case()
        self.assertEqual(item["login_files_changed"], [])

    def test_a_change_never_blocks_the_run(self):
        self.stub_opencode(f"rm '{self.login}'\n")
        rows, item = self.t.run("opencode", "stub", "", "branch", self.t.CASES[0], 0)
        self.assertTrue(rows)
        self.assertEqual(item["login_files_changed"], [str(self.login)])

    def test_directory_fingerprint_sees_a_changed_file(self):
        folder = self.tmp / "Keychains"
        folder.mkdir()
        (folder / "login.keychain-db").write_bytes(b"a")
        before = {folder: self.t.fingerprint(folder)}
        (folder / "login.keychain-db").write_bytes(b"b")
        self.assertEqual(self.t.login_changes(before, {folder: self.t.fingerprint(folder)}), [str(folder)])

    def test_every_host_has_a_linked_login_source(self):
        for host in self.t.SETUP:
            self.assertTrue(self.t.login_sources(host), host)
        self.assertEqual(self.t.login_sources("claude"), [self.t.KEYCHAINS])


PROSE = "technical-writing/references/prose.md"


def claude_stream(*events):
    return "\n".join(json.dumps(e) for e in events)


def claude_call(call_id, name, **arguments):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": call_id, "name": name, "input": arguments}]}}


def claude_result(call_id, error):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": call_id, "is_error": error, "content": "x"}]}}


class FailedReadTests(unittest.TestCase):
    """A refused or failed read is an attempt, not a read (#174)."""

    def setUp(self):
        self.t = load_harness()
        self.read = claude_call("r1", "Read", file_path="/p/skills/operations/workflows/" + PROSE)
        self.edit = claude_call("e1", "Edit", file_path="/repo/README.md")

    def verdict(self, stream, host="claude"):
        first_edit, reads, _ = self.t.score(stream, [PROSE], host)
        return self.t.verdicts_for("positive", [PROSE], first_edit, reads)[PROSE]

    def test_a_successful_read_before_the_edit_fires(self):
        stream = claude_stream(self.read, claude_result("r1", False), self.edit)
        self.assertEqual(self.verdict(stream), "fired")

    def test_a_read_in_permission_denials_is_not_counted(self):
        stream = claude_stream(self.read, claude_result("r1", True), self.edit, {
            "type": "result", "permission_denials": [
                {"tool_name": "Read", "tool_use_id": "r1", "tool_input": {}}]})
        self.assertEqual(self.t.failed_calls(stream), {0})
        self.assertEqual(self.verdict(stream), "skip")

    def test_a_read_answered_by_an_error_is_not_counted(self):
        stream = claude_stream(self.read, claude_result("r1", True), self.edit)
        self.assertEqual(self.verdict(stream), "skip")

    def test_a_shell_read_with_a_nonzero_exit_still_counts(self):
        # `cat prose.md; ls missing` reads the file and still exits non-zero.
        shell = claude_call("b1", "Bash", command="cat /p/workflows/" + PROSE + "; ls missing")
        stream = claude_stream(shell, claude_result("b1", True), self.edit)
        self.assertEqual(self.t.failed_calls(stream), set())
        self.assertEqual(self.verdict(stream), "fired")

    def test_a_denied_shell_read_is_not_counted(self):
        shell = claude_call("b1", "Bash", command="cat /p/workflows/" + PROSE)
        stream = claude_stream(shell, claude_result("b1", True), self.edit, {
            "type": "result", "permission_denials": [
                {"tool_name": "Bash", "tool_use_id": "b1", "tool_input": {}}]})
        self.assertEqual(self.verdict(stream), "skip")

    def test_a_failed_opencode_read_is_not_counted(self):
        def part(call_id, tool, status, **arguments):
            return {"type": "tool_use", "part": {"callID": call_id, "tool": tool,
                                                 "state": {"status": status, "input": arguments}}}
        stream = claude_stream(part("c1", "read", "error", filePath="/p/" + PROSE),
                               part("c2", "edit", "completed", filePath="/repo/README.md"))
        self.assertEqual(self.verdict(stream, "opencode"), "skip")
        stream = claude_stream(part("c1", "read", "completed", filePath="/p/" + PROSE),
                               part("c2", "edit", "completed", filePath="/repo/README.md"))
        self.assertEqual(self.verdict(stream, "opencode"), "fired")


class OpenCodeReadScopeTests(unittest.TestCase):
    """OpenCode may read the Skill through its config link, as the live install can (#174)."""

    def test_config_directory_is_an_allowed_external_directory(self):
        t = load_harness()
        home = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-174-test-"))
        self.addCleanup(shutil.rmtree, home, True)
        plugin = home / "plugin"
        (plugin / "skills/operations").mkdir(parents=True)
        (plugin / "opencode").mkdir()
        (plugin / "opencode/agentsmd-project-direction.js").write_text("")
        (plugin / "global").mkdir()
        (plugin / "global/AGENTS.md").write_text("# Contract\n")
        login = home / "auth.json"
        login.write_text("{}")
        saved = dict(t.LOGIN)
        self.addCleanup(t.LOGIN.update, saved)
        t.LOGIN["opencode"] = login
        t.setup_opencode(home, plugin, {})
        config = json.loads((home / "opencode/opencode.json").read_text())
        rules = config["permission"]["external_directory"]
        self.assertEqual(rules["*"], "deny")
        self.assertEqual(rules[f"{home / 'opencode'}/**"], "allow")
        self.assertEqual(rules[f"{plugin}/**"], "allow")


class ClaudeCommandTests(unittest.TestCase):
    """Claude runs can read the plugin copy and run shell commands (#174)."""

    def test_claude_command_allows_the_plugin_copy_and_bash(self):
        t = load_harness()
        repo, plugin = pathlib.Path("/tmp/repo"), pathlib.Path("/tmp/home/plugin")
        cmd = t.command("claude", "claude-opus-5-5", "medium", repo, plugin, "prompt")
        pairs = list(zip(cmd, cmd[1:]))
        self.assertIn(("--permission-mode", "acceptEdits"), pairs)
        self.assertIn(("--add-dir", str(repo)), pairs)
        self.assertIn(("--add-dir", str(plugin)), pairs)
        self.assertIn(("--allowedTools", "Bash"), pairs)
        self.assertNotIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(cmd[-1], "prompt")


class ClaudeSandboxTests(unittest.TestCase):
    """Claude's shell commands run in its OS sandbox with no unsandboxed fallback."""

    def test_temporary_home_settings_enable_the_strict_sandbox(self):
        t = load_harness()
        home = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-174-test-"))
        self.addCleanup(shutil.rmtree, home, True)
        plugin = home / "plugin"
        (plugin / "global").mkdir(parents=True)
        (plugin / "global/AGENTS.md").write_text("# Contract\n")
        account = home / "claude.json"
        account.write_text("{}")
        saved = t.CLAUDE_JSON
        self.addCleanup(setattr, t, "CLAUDE_JSON", saved)
        t.CLAUDE_JSON = account
        t.setup_claude(home, plugin, {})
        settings = json.loads((home / ".claude/settings.json").read_text())
        self.assertEqual(settings["permissions"], {"defaultMode": "acceptEdits"})
        sandbox = settings["sandbox"]
        self.assertIs(sandbox["enabled"], True)
        self.assertIs(sandbox["allowUnsandboxedCommands"], False)
        self.assertIs(sandbox["failIfUnavailable"], True)
        # Nothing widens the default write set (working directory, --add-dir, temp).
        self.assertEqual(set(sandbox["filesystem"]), {"denyRead", "allowRead"})
        self.assertNotIn("excludedCommands", sandbox)
        # Reads: the real home and the keychain link are denied; the temporary HOME
        # (plugin copy) is re-allowed, and the repository lies outside the real home.
        self.assertEqual(sandbox["filesystem"]["denyRead"],
                         [str(t.REAL_HOME), str(home / "Library/Keychains")])
        self.assertEqual(sandbox["filesystem"]["allowRead"], [str(home)])
        self.assertFalse(home.resolve().is_relative_to(t.REAL_HOME))
        repo = t.make_repo()
        self.addCleanup(t.remove, repo)
        self.assertFalse(repo.resolve().is_relative_to(t.REAL_HOME))


class SweepMomentTests(unittest.TestCase):
    """Sweep moments and fixtures (#182)."""

    def setUp(self):
        self.t = load_harness()
        self.stream = claude_stream(
            claude_call("r1", "Read", file_path="/p/workflows/" + PROSE),
            claude_call("b1", "Bash", command="git tag v1.0.1"),
            claude_call("a1", "Agent", prompt="x"),
            claude_call("e1", "Edit", file_path="/repo/README.md"))

    def test_the_earliest_alternative_wins(self):
        m = self.t.moment_index
        self.assertEqual(m(self.stream, "claude", ("edit",)), 3)
        self.assertEqual(m(self.stream, "claude", ("edit", "bash:git (merge|tag)")), 1)
        self.assertEqual(m(self.stream, "claude", ("edit", "tool:Agent|Task")), 2)
        self.assertEqual(m(self.stream, "claude", ("end",)), 4)
        self.assertEqual(m(self.stream, "claude", "git tag"), 1)  # a plain regex is a shell moment
        self.assertIsNone(m(self.stream, "claude", ("bash:gh release",)))

    def test_a_read_before_the_end_of_an_answer_only_run_fires(self):
        first, reads, _ = self.t.score(self.stream, [PROSE], "claude")
        moment = self.t.moment_index(self.stream, "claude", ("end",))
        self.assertEqual(self.t.verdicts_for("positive", [PROSE], moment, reads)[PROSE], "fired")

    def test_extra_files_and_branches_reach_the_fixture(self):
        repo = self.t.make_repo({"TODO.md": "# TODO\n", self.t.BRANCHES: ["task/docs"]})
        self.addCleanup(self.t.remove, repo)
        self.assertEqual((repo / "TODO.md").read_text(), "# TODO\n")
        branches = __import__("subprocess").run(["git", "-C", str(repo), "branch", "--list", "task/docs"],
                                                capture_output=True, text=True).stdout
        self.assertIn("task/docs", branches)

    def test_every_sweep_row_links_an_existing_procedure(self):
        skill = ROOT / "skills/operations"
        files = [str(p.relative_to(skill)) for p in skill.rglob("*.md")]
        self.assertEqual(len(self.t.SWEEP_FILES), 21)
        for suffix in self.t.SWEEP_FILES:
            self.assertEqual(sum(f.endswith(suffix) for f in files), 1, suffix)
            self.assertIn(suffix, (skill / "SKILL.md").read_text())


class NoEditVerdictTests(unittest.TestCase):
    """A positive run that never edits is not a hit (#174)."""

    def setUp(self):
        self.t = load_harness()

    def test_a_read_without_an_edit_is_read_noedit(self):
        verdicts = self.t.verdicts_for("positive", [PROSE], None, {PROSE: 3})
        self.assertEqual(verdicts[PROSE], "read-noedit")

    def test_no_read_and_no_edit_is_skip_noedit(self):
        verdicts = self.t.verdicts_for("positive", [PROSE], None, {PROSE: None})
        self.assertEqual(verdicts[PROSE], "skip-noedit")

    def test_the_summary_does_not_count_read_noedit_as_a_hit(self):
        record = {"condition": "plain-confined", "source": "abc1234", "host": "claude-code",
                  "model": "m", "arm": "B", "target": "technical-writing", "kind": "positive",
                  "verdict": {"prose.md": "read-noedit"}, "entry_loaded_at": 0,
                  "login_files_changed": None}
        path = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-174-test-")) / "records.jsonl"
        self.addCleanup(shutil.rmtree, path.parent, True)
        path.write_text(json.dumps(record) + "\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.t.summarize_records(path)
        self.assertIn("| Target read before first edit (naive, every required file) | 0/1 |",
                      out.getvalue())


class CommittedRecordsTests(unittest.TestCase):
    """The committed records carry login_files_changed; null means unknown."""

    def setUp(self):
        self.t = load_harness()
        self.records = HARNESS.parent / "records.jsonl"

    def test_login_status_reads_null_as_unknown(self):
        status = self.t.login_status
        self.assertEqual(status({"login_files_changed": None}), "unknown")
        self.assertEqual(status({"login_files_changed": []}), "unchanged")
        self.assertEqual(status({"login_files_changed": ["~/.codex/auth.json"]}), "changed")
        with self.assertRaises(ValueError):
            status({"login_files_changed": "yes"})

    def test_every_committed_record_has_a_valid_login_field(self):
        lines = self.records.read_text().splitlines()
        self.assertEqual(len(lines), 600)
        for line in lines:
            self.assertIn(self.t.login_status(json.loads(line)), ("unknown", "unchanged", "changed"))

    def test_results_tables_regenerate_from_the_records(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.t.summarize_records(self.records)
        tables = out.getvalue().strip().replace("\n### ", "\n#### ")
        tables = tables[4:] if tables.startswith("### ") else tables
        self.assertIn("#### " + tables, (HARNESS.parent / "results.md").read_text())


if __name__ == "__main__":
    unittest.main()
