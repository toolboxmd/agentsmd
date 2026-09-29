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
