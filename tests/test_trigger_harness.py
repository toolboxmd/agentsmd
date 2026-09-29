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
