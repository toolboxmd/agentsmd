"""OpenCode ownership and adapter proof in isolated homes, without model calls."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "bin/agentsmd-opencode"


class OpenCodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.config = self.root / "xdg"
        self.target = self.config / "opencode/AGENTS.md"
        self.target.parent.mkdir(parents=True)
        self.source = self.root / "release/AGENTS.md"
        self.source.parent.mkdir()
        self.source.write_text("canonical contract\n")
        self.env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config),
                    "XDG_DATA_HOME": str(self.root / "data"), "XDG_CACHE_HOME": str(self.root / "cache"),
                    "XDG_STATE_HOME": str(self.root / "state")}
        self.preserved = [self.target.parent / "opencode.json", self.target.parent / "opencode.jsonc",
                          self.root / "data/opencode/auth.json", self.home / ".agents/skills/user/SKILL.md"]
        for path in self.preserved:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("user-owned fixture " + path.name)
        self.hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.preserved}

    def tearDown(self):
        self.assertEqual(self.hashes, {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.preserved})

    def call(self, *args, env=None):
        result = subprocess.run([str(COMMAND), *map(str, args)], env=env or self.env,
                                capture_output=True, text=True, cwd=ROOT)
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def manage(self, name, *args):
        return self.call(name, "--source", self.source, *args)

    def test_install_status_idempotent_update_and_uninstall(self):
        self.assertEqual(self.manage("status")[1]["status"], "missing")
        code, report = self.manage("install")
        self.assertEqual(code, 0)
        self.assertEqual(report["after"]["target_sha256"], report["after"]["source_sha256"])
        self.assertEqual(self.manage("install")[1]["action"], "unchanged")
        self.assertEqual(self.manage("status")[1]["status"], "owned-link")
        newer = self.root / "new-release/AGENTS.md"
        newer.parent.mkdir()
        newer.write_text("new canonical contract")
        self.assertEqual(self.call("update", "--source", newer)[0], 2)
        self.assertEqual(self.call("update", "--source", newer, "--previous-source", self.source)[0], 0)
        self.assertEqual(self.target.resolve(), newer)
        self.assertEqual(self.manage("uninstall")[0], 2)
        self.assertEqual(self.call("uninstall", "--source", newer)[0], 0)
        self.assertFalse(os.path.lexists(self.target))

    def test_regular_divergent_and_broken_user_paths_preserved(self):
        other = self.root / "other/AGENTS.md"
        other.parent.mkdir()
        for kind in ("regular-file", "divergent-link", "broken-link", "other-path"):
            with self.subTest(kind=kind):
                if kind == "regular-file":
                    self.target.write_text("user instructions")
                elif kind == "other-path":
                    self.target.mkdir()
                else:
                    if kind == "divergent-link":
                        other.write_text("unrelated instructions")
                    elif other.exists():
                        other.unlink()
                    self.target.symlink_to(other)
                self.assertEqual(self.manage("status")[1]["status"], kind)
                for action in ("install", "update", "uninstall"):
                    self.assertEqual(self.manage(action)[0], 2)
                if self.target.is_symlink():
                    self.assertEqual(os.readlink(self.target), str(other))
                    self.target.unlink()
                elif self.target.is_dir():
                    self.target.rmdir()
                else:
                    self.assertEqual(self.target.read_text(), "user instructions")
                    self.target.unlink()

    def test_broken_owned_link_can_be_removed_or_explicitly_updated(self):
        self.manage("install")
        self.source.unlink()
        code, report = self.manage("status")
        self.assertEqual(code, 2)
        self.assertTrue(report["owned"])
        self.assertEqual(report["status"], "broken-link")
        self.assertEqual(self.manage("uninstall")[0], 0)

    def test_fallback_home_and_relative_xdg_rejection(self):
        env = dict(self.env)
        del env["XDG_CONFIG_HOME"]
        code, report = self.call("install", "--source", self.source, env=env)
        self.assertEqual(code, 0)
        self.assertEqual(report["after"]["target"], str(self.home / ".config/opencode/AGENTS.md"))
        env["XDG_CONFIG_HOME"] = "relative"
        self.assertEqual(self.call("install", "--source", self.source, env=env)[0], 2)

    def test_cache_and_symlink_source_rejected(self):
        cached = self.root / "plugins/cache/release/AGENTS.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("cached")
        self.assertEqual(self.call("install", "--source", cached)[0], 2)
        alias = self.root / "alias"
        alias.symlink_to(cached.parent, target_is_directory=True)
        self.assertEqual(self.call("install", "--source", alias / "AGENTS.md")[0], 2)
        self.assertFalse(os.path.lexists(self.target))

    def test_status_and_uninstall_reject_source_alias_into_cache(self):
        cached = self.root / "plugins/cache/release/AGENTS.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("cached")
        alias = self.root / "alias/AGENTS.md"
        alias.parent.mkdir()
        alias.symlink_to(cached)
        self.target.symlink_to(alias)
        for action in ("status", "uninstall"):
            self.assertEqual(self.call(action, "--source", alias)[0], 2)
            self.assertEqual(os.readlink(self.target), str(alias))
        self.assertEqual(cached.read_text(), "cached")

    def test_update_exact_broken_previous_release(self):
        previous = self.root / "removed/AGENTS.md"
        self.target.symlink_to(previous)
        code, report = self.manage("update", "--previous-source", previous)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["before"]["status"], "broken-link")
        self.assertEqual(self.target.resolve(), self.source)

    def test_existing_directory_link_is_not_broken(self):
        directory = self.root / "user-directory"
        directory.mkdir()
        self.target.symlink_to(directory, target_is_directory=True)
        code, report = self.manage("status")
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "other-path")
        self.assertFalse(report["owned"])
        for action in ("install", "update", "uninstall"):
            self.assertEqual(self.manage(action)[0], 2)
        self.assertEqual(os.readlink(self.target), str(directory))
        self.assertTrue(directory.is_dir())

    def prepare_run(self, mode="success", help_stream="stdout"):
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "commit", "--allow-empty", "-qm", "fixture"], check=True)
        head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.prompt = self.root / "prompt.txt"
        self.prompt.write_text("--dangerous-looking literal prompt $(touch never) `echo no`\nReturn a handoff.")
        fake = self.root / "opencode"
        fake.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
if sys.argv[1:] == ['--version']:
    print('1.18.29'); sys.exit()
if sys.argv[1:] == ['run', '--help']:
    print('--model --dir --format --auto', file=sys.''' + help_stream + '''); sys.exit()
pathlib.Path('invocation.json').write_text(json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}))
mode = ''' + repr(mode) + '''
if mode == 'timeout': time.sleep(30)
if mode == 'failure': sys.exit(7)
if mode == 'invalid': print('not json'); sys.exit()
print(json.dumps({'type': 'text', 'sessionID': 'ses_fixture', 'part': {'text': '   ' if mode == 'blank' else 'Candidate only'}}))
if mode == 'error': print(json.dumps({'type': 'error', 'sessionID': 'ses_fixture'}))
if mode == 'missing-git': pathlib.Path('.git').rename('.git-hidden')
''')
        fake.chmod(0o755)
        self.output = self.root / "receipt"
        self.run_args = ["run", "--cwd", self.repo, "--issue", "https://github.com/toolboxmd/agentsmd/issues/78",
                         "--base", head, "--head", head, "--model", "provider/exact-model", "--permissions", "configured",
                         "--prompt-file", self.prompt, "--output", self.output, "--executable", fake]
        return head

    def test_run_binds_exact_invocation_and_does_not_infer_approval(self):
        head = self.prepare_run()
        code, report = self.call(*self.run_args)
        self.assertEqual(code, 0, report)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["head_before"], head)
        self.assertEqual(receipt["head_after"], head)
        self.assertEqual(receipt["base"], head)
        self.assertEqual(receipt["session_ids"], ["ses_fixture"])
        self.assertEqual(receipt["model"], "provider/exact-model")
        self.assertEqual(receipt["exit_status"], 0)
        self.assertFalse(receipt["approval"])
        self.assertFalse(receipt["live_verified"])
        invocation = json.loads((self.repo / "invocation.json").read_text())
        self.assertNotIn("--auto", invocation["argv"])
        self.assertEqual(invocation["argv"][-2], "--")
        self.assertIn(self.prompt.read_text(), invocation["argv"][-1])
        self.assertEqual(invocation["cwd"], str(self.repo))
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_auto_requires_explicit_selection(self):
        self.prepare_run()
        self.run_args[self.run_args.index("configured")] = "auto"
        self.assertEqual(self.call(*self.run_args)[0], 0)
        self.assertIn("--auto", json.loads((self.repo / "invocation.json").read_text())["argv"])

    def test_run_accepts_supported_help_on_stderr(self):
        self.prepare_run(help_stream="stderr")
        code, report = self.call(*self.run_args)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["result"], "candidate")

    def test_stale_head_refuses_dispatch(self):
        self.prepare_run()
        self.run_args[self.run_args.index("--head") + 1] = "0" * 40
        self.assertEqual(self.call(*self.run_args)[0], 2)
        self.assertFalse((self.repo / "invocation.json").exists())

    def test_failure_receipt(self):
        self.prepare_run("failure")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["exit_status"], 7)

    def test_malformed_event_refuses_candidate(self):
        self.prepare_run("invalid")
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_error_event_refuses_candidate(self):
        self.prepare_run("error")
        self.assertEqual(self.call(*self.run_args)[0], 2)

    def test_blank_result_refuses_candidate(self):
        self.prepare_run("blank")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        self.assertEqual(json.loads((self.output / "receipt.json").read_text())["result"], "failed")

    def test_unavailable_after_state_refuses_candidate(self):
        self.prepare_run("missing-git")
        self.assertEqual(self.call(*self.run_args)[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "failed")
        self.assertEqual(receipt["exit_status"], 0)
        self.assertIsNone(receipt["head_after"])
        self.assertEqual(receipt["after_state_error"], "git-state-unavailable")

    def test_timeout_preserves_receipt(self):
        self.prepare_run("timeout")
        self.assertEqual(self.call(*self.run_args, "--timeout", "1")[0], 2)
        receipt = json.loads((self.output / "receipt.json").read_text())
        self.assertEqual(receipt["result"], "timeout")
        self.assertEqual(receipt["exit_status"], 124)


if __name__ == "__main__":
    unittest.main()
