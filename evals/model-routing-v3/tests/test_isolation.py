"""Tests for the v3 trusted local candidate boundary."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "isolation.py"
SPEC = importlib.util.spec_from_file_location("routing_v3_isolation", MODULE_PATH)
assert SPEC and SPEC.loader
isolation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = isolation
SPEC.loader.exec_module(isolation)


class IsolationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.command_bin = self.root / "pinned-tools"
        self.command_bin.mkdir()
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.tmpdir = self.candidate / ".runner-tmp"
        self.paths = isolation.CodexPaths(
            candidate_root=self.candidate,
            home=self.root / "isolated-home",
            codex_home=self.root / "isolated-codex-home",
            codex_sqlite_home=self.root / "isolated-codex-sqlite",
            tmpdir=self.tmpdir,
            auth_target=self.root / "controller" / "auth.json",
            controller_root=self.root / "controller",
            memory_root=self.root / "operator-memory",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_candidate_profile_is_canonical_and_strict(self) -> None:
        first = isolation.permission_profile_toml(self.paths)
        second = isolation.permission_profile_toml(self.paths)
        self.assertEqual(first, second)
        config = tomllib.loads(first.decode("utf-8"))
        self.assertEqual(config["default_permissions"], isolation.PROFILE_CANDIDATE)
        self.assertEqual(config["permissions"][isolation.PROFILE_CANDIDATE]["filesystem"][":root"], "deny")
        self.assertEqual(config["permissions"][isolation.PROFILE_CANDIDATE]["filesystem"][":slash_tmp"], "deny")
        self.assertFalse(config["permissions"][isolation.PROFILE_CANDIDATE]["network"]["enabled"])
        self.assertFalse(config["features"]["apps"])
        self.assertFalse(config["features"]["multi_agent"])
        self.assertEqual(config["model_reasoning_effort"], "high")
        self.assertEqual(config["shell_environment_policy"]["inherit"], "none")
        self.assertEqual(len(config["skills"]["config"]), 5)
        self.assertTrue(all(not item["enabled"] for item in config["skills"]["config"]))
        self.assertNotIn("sandbox_mode", first.decode("utf-8"))
        self.assertEqual(len(isolation.config_sha256(first)), 64)

    def test_reviewer_profile_writes_only_ephemeral_runner_temp(self) -> None:
        config = tomllib.loads(isolation.permission_profile_toml(self.paths, reviewer=True).decode("utf-8"))
        filesystem = config["permissions"][isolation.PROFILE_REVIEWER]["filesystem"][":workspace_roots"]
        self.assertEqual(filesystem, {".": "read", ".runner-tmp": "write"})
        with self.assertRaises(isolation.IsolationError):
            isolation.permission_profile_toml(
                self.paths, reviewer=True, writable_paths=("daemon/src/acp.ts",)
            )

    def test_candidate_can_receive_exact_write_paths(self) -> None:
        config = tomllib.loads(
            isolation.permission_profile_toml(
                self.paths, writable_paths=("daemon/src/acp.ts", ".runner-tmp")
            ).decode("utf-8")
        )
        filesystem = config["permissions"][isolation.PROFILE_CANDIDATE]["filesystem"][":workspace_roots"]
        self.assertEqual(filesystem["."], "read")
        self.assertEqual(filesystem["daemon/src/acp.ts"], "write")
        with self.assertRaises(isolation.IsolationError):
            isolation.permission_profile_toml(self.paths, writable_paths=("../controller",))

    def test_invalid_path_topology_fails_closed(self) -> None:
        unsafe = isolation.CodexPaths(
            candidate_root=self.candidate,
            home=self.candidate / "home",
            codex_home=self.candidate / "codex-home",
            codex_sqlite_home=self.candidate / "sqlite",
            tmpdir=self.tmpdir,
            auth_target=self.candidate / "auth.json",
            controller_root=self.candidate / "controller",
            memory_root=self.candidate / "memory",
        )
        with self.assertRaises(isolation.IsolationError):
            unsafe.normalized()
        outside_tmp = isolation.CodexPaths(
            candidate_root=self.candidate,
            home=Path(self.temporary.name) / "isolated-home",
            codex_home=Path(self.temporary.name) / "home",
            codex_sqlite_home=Path(self.temporary.name) / "sqlite",
            tmpdir=Path(self.temporary.name) / "tmp",
            auth_target=Path(self.temporary.name) / "auth",
            controller_root=Path(self.temporary.name) / "controller",
            memory_root=Path(self.temporary.name) / "memory",
        )
        with self.assertRaises(isolation.IsolationError):
            outside_tmp.normalized()

    def test_symlinked_controller_location_cannot_hide_inside_candidate(self) -> None:
        controller_link = self.candidate / "controller-link"
        controller_link.symlink_to(self.candidate / "real-controller")
        unsafe = isolation.CodexPaths(
            candidate_root=self.candidate,
            home=Path(self.temporary.name) / "isolated-home",
            codex_home=Path(self.temporary.name) / "home",
            codex_sqlite_home=Path(self.temporary.name) / "sqlite",
            tmpdir=self.tmpdir,
            auth_target=Path(self.temporary.name) / "auth",
            controller_root=controller_link,
            memory_root=Path(self.temporary.name) / "memory",
        )
        with self.assertRaises(isolation.IsolationError):
            unsafe.normalized()

    def test_clean_environment_has_no_parent_leaks(self) -> None:
        environment = isolation.build_clean_environment(
            self.paths, command_path=(self.command_bin,)
        )
        self.assertEqual(environment["HOME"], str(self.paths.home.resolve()))
        self.assertEqual(environment["CODEX_SQLITE_HOME"], str(self.paths.codex_sqlite_home.resolve()))
        self.assertNotIn("USER", environment)
        self.assertNotIn("SSH_AUTH_SOCK", environment)
        self.assertEqual(environment["TSX_DISABLE_CACHE"], "1")
        self.assertTrue(environment["PATH"].startswith(str(self.command_bin.resolve())))
        with self.assertRaises(isolation.IsolationError):
            isolation.build_clean_environment(self.paths, extra={"USER": "leak"})
        with self.assertRaises(isolation.IsolationError):
            isolation.build_clean_environment(self.paths, extra={"HOME": "/escaped"})
        environment = isolation.build_clean_environment(
            self.paths,
            extra={
                "ROUTING_CANDIDATE_ACP": str(self.candidate / "daemon/src/acp.ts"),
                "ROUTING_RUN_MARKER": "routing-v3-0123456789abcdef",
            },
        )
        self.assertTrue(environment["ROUTING_CANDIDATE_ACP"].endswith("daemon/src/acp.ts"))
        self.assertEqual(environment["ROUTING_RUN_MARKER"], "routing-v3-0123456789abcdef")
        with self.assertRaises(isolation.IsolationError):
            isolation.build_clean_environment(
                self.paths,
                extra={"ROUTING_CANDIDATE_ACP": str(self.paths.controller_root / "acp.ts")},
            )
        with self.assertRaises(isolation.IsolationError):
            isolation.build_clean_environment(
                self.paths, extra={"ROUTING_RUN_MARKER": "short"}
            )
        with self.assertRaises(isolation.IsolationError):
            isolation.build_clean_environment(self.paths, command_path=("/opt/codex-bin",))

    def test_command_path_checks_executables_not_parent_directory_name(self) -> None:
        safe = self.root / ".codex" / "runtime" / "bin"
        safe.mkdir(parents=True)
        (safe / "node").write_text("node\n", encoding="utf-8")
        self.assertEqual(isolation._command_path((safe,)), [str(safe.resolve())])
        forbidden = self.root / "runtime-with-codex"
        forbidden.mkdir()
        (forbidden / "codex").write_text("codex\n", encoding="utf-8")
        with self.assertRaises(isolation.IsolationError):
            isolation._command_path((forbidden,))

    def test_profile_can_grant_exact_readonly_runtime_roots(self) -> None:
        runtime = Path(self.temporary.name) / "pinned-runtime"
        config = tomllib.loads(
            isolation.permission_profile_toml(
                self.paths, runtime_roots=(runtime,), command_path=(self.command_bin,)
            ).decode("utf-8")
        )
        roots = config["permissions"][isolation.PROFILE_CANDIDATE]["filesystem"]
        self.assertEqual(roots[str(runtime.resolve())], "read")
        self.assertTrue(
            config["shell_environment_policy"]["set"]["PATH"].startswith(
                str(self.command_bin.resolve())
            )
        )
        with self.assertRaises(isolation.IsolationError):
            isolation.permission_profile_toml(self.paths, runtime_roots=(self.paths.controller_root / "node",))
        with self.assertRaises(isolation.IsolationError):
            isolation.permission_profile_toml(
                self.paths, runtime_roots=(Path(self.temporary.name),)
            )

    def test_command_pins_the_required_form(self) -> None:
        schema = Path(self.temporary.name) / "schema.json"
        command = isolation.build_codex_command(
            codex_executable="/opt/pinned/codex",
            paths=self.paths,
            model="gpt-5.6-terra",
            output_schema=schema,
            last_message_path=self.paths.controller_root / "last-message.json",
        )
        self.assertIn("--strict-config", command)
        self.assertIn("--ignore-rules", command)
        self.assertIn("--skip-git-repo-check", command)
        self.assertIn("--json", command)
        self.assertIn("--output-schema", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("-C", command)
        self.assertIn("-m", command)
        self.assertNotIn("-P", command)
        self.assertEqual(command[-1], "-")
        self.assertNotIn("--sandbox", command)
        self.assertNotIn("--ignore-user-config", command)
        self.assertNotIn("--ephemeral", command)
        with self.assertRaises(isolation.IsolationError):
            isolation.build_codex_command(
                codex_executable="/opt/pinned/codex",
                paths=self.paths,
                model="gpt-5.6-terra",
                output_schema=schema,
                last_message_path=self.candidate / "leak.json",
            )

    def test_probe_contract_covers_every_required_boundary(self) -> None:
        contracts = isolation.build_sandbox_probe_contracts(
            probe_executable="/bin/echo",
            paths=self.paths,
            allowed_read=self.candidate / "TASK.md",
            allowed_write=self.candidate / ".runner-tmp" / "probe.txt",
            symlink_escape=self.candidate / "escape",
        )
        names = {contract.name for contract in contracts}
        self.assertEqual(
            names,
            {
                "allowed-read", "allowed-write", "denied-controller", "denied-auth", "denied-memory",
                "environment-leakage", "denied-external-network", "denied-loopback-network",
                "denied-unix-socket", "denied-symlink-escape", "timeout-breakaway",
            },
        )
        self.assertTrue(next(item for item in contracts if item.name == "allowed-read").expect_success)
        self.assertFalse(next(item for item in contracts if item.name == "denied-auth").expect_success)

    def test_probe_runner_records_success_denial_and_timeout(self) -> None:
        fake = self._fake_probe()
        environment = isolation.build_clean_environment(self.paths)
        probes = (
            isolation.ProbeSpec("allowed", (str(fake), "allowed"), True),
            isolation.ProbeSpec("denied", (str(fake), "denied"), False),
            isolation.ProbeSpec("hang", (str(fake), "hang"), False, timeout_seconds=0.1),
        )
        report = isolation.run_sandbox_probes(probes, environment=environment, cwd=self.candidate)
        self.assertTrue(report.passed)
        self.assertTrue(next(result for result in report.results if result.name == "hang").timed_out)
        report.require_passed()

    def test_probe_report_fails_closed_on_wrong_outcome(self) -> None:
        fake = self._fake_probe()
        report = isolation.run_sandbox_probes(
            (isolation.ProbeSpec("unexpected", (str(fake), "allowed"), False),),
            environment=isolation.build_clean_environment(self.paths),
            cwd=self.candidate,
        )
        self.assertFalse(report.passed)
        with self.assertRaises(isolation.IsolationError):
            report.require_passed()

    def _fake_probe(self) -> Path:
        path = Path(self.temporary.name) / "fake-probe.py"
        path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import subprocess
                import sys
                import time
                if sys.argv[1] == "allowed":
                    raise SystemExit(0)
                if sys.argv[1] == "denied":
                    raise SystemExit(1)
                if sys.argv[1] == "hang":
                    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
                    time.sleep(30)
                raise SystemExit(2)
                """
            )
        )
        path.chmod(0o755)
        return path


if __name__ == "__main__":
    unittest.main()
