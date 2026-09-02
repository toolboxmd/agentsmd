from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from execution import ExecutionError, run_bounded_process  # noqa: E402


class ExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.marker = "unused-routing-marker-0123456789abcdef"
        self.environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_script(
        self,
        source: str,
        *,
        seconds: float = 2.0,
        stdin: bytes = b"input",
        grace_seconds: float = 0.1,
    ):
        return run_bounded_process(
            (sys.executable, "-c", source),
            cwd=self.root,
            environment=self.environment,
            stdin_bytes=stdin,
            stdout_path=self.root / "stdout",
            stderr_path=self.root / "stderr",
            deadline_monotonic=time.monotonic() + seconds,
            run_marker=self.marker,
            grace_seconds=grace_seconds,
        )

    def test_success_binds_launchd_coalitions_and_exact_outputs_without_marker(self) -> None:
        receipt = self.run_script(
            "import os,sys; print(sys.stdin.read()); print('err', file=sys.stderr); "
            "print('marker=' + str('ROUTING_RUN_MARKER' in os.environ))"
        )
        self.assertEqual(receipt.returncode, 0)
        self.assertFalse(receipt.timed_out)
        self.assertFalse(receipt.marker_identity_used)
        self.assertTrue(receipt.coalition_binding_verified)
        self.assertTrue(receipt.terminal_process_state)
        self.assertTrue(receipt.service_registration_absent)
        self.assertTrue(receipt.resource_coalition_reaped)
        self.assertTrue(receipt.jetsam_coalition_absent)
        self.assertEqual(receipt.terminal_member_pids, ())
        self.assertEqual(receipt.survivor_pids, ())
        self.assertFalse(receipt.broker_usage_observed)
        self.assertTrue(receipt.observed_executable_paths)
        self.assertEqual((self.root / "stdout").read_text(), "input\nmarker=False\n")
        self.assertEqual((self.root / "stderr").read_text(), "err\n")
        self.assertEqual(
            receipt.stdout_sha256,
            hashlib.sha256((self.root / "stdout").read_bytes()).hexdigest(),
        )
        self.assertEqual(len(receipt.runner_handshake_sha256), 64)
        self.assertEqual(len(receipt.runner_result_sha256 or ""), 64)
        self.assertIn("outside the threat model", receipt.containment_scope)

    def test_timeout_reaps_sigterm_ignoring_setsid_process(self) -> None:
        receipt = self.run_script(
            "import os,signal,time; os.setsid(); "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); os.environ.clear(); "
            "time.sleep(30)",
            seconds=0.15,
        )
        self.assertTrue(receipt.timed_out)
        self.assertIsNone(receipt.returncode)
        self.assertTrue(receipt.terminal_process_state)
        self.assertTrue(receipt.terminated_member_pids)
        self.assertEqual(receipt.terminal_member_pids, ())

    def test_environment_cleared_setsid_double_fork_survivor_is_reaped(self) -> None:
        receipt = run_bounded_process(
            (str(ROOT / "boundary_probe.py"), "coalition-breakaway"),
            cwd=self.root,
            environment=self.environment,
            stdin_bytes=b"",
            stdout_path=self.root / "stdout",
            stderr_path=self.root / "stderr",
            deadline_monotonic=time.monotonic() + 2.0,
            run_marker=self.marker,
            grace_seconds=0.1,
        )
        self.assertEqual(receipt.returncode, 0)
        self.assertFalse(receipt.timed_out)
        self.assertTrue(receipt.survivor_pids)
        self.assertTrue(receipt.terminal_process_state)
        self.assertEqual(receipt.terminal_member_pids, ())
        self.assertTrue(set(receipt.survivor_pids) <= set(receipt.terminated_member_pids))

    def test_known_broker_usage_is_auditable_without_claiming_complete_prevention(self) -> None:
        receipt = run_bounded_process(
            ("/bin/launchctl", "print-disabled", f"gui/{os.getuid()}"),
            cwd=self.root,
            environment=self.environment,
            stdin_bytes=b"",
            stdout_path=self.root / "stdout",
            stderr_path=self.root / "stderr",
            deadline_monotonic=time.monotonic() + 3.0,
            run_marker=self.marker,
            grace_seconds=0.1,
        )
        self.assertEqual(receipt.returncode, 0)
        self.assertTrue(receipt.broker_usage_observed)
        self.assertIn("/bin/launchctl", receipt.broker_executables)
        self.assertTrue(receipt.launch_observation_complete)
        self.assertTrue(receipt.terminal_process_state)

    def test_rejects_elapsed_deadline_and_existing_output_before_launch(self) -> None:
        with self.assertRaises(ExecutionError):
            run_bounded_process(
                (sys.executable, "-c", "pass"),
                cwd=self.root,
                environment=self.environment,
                stdin_bytes=b"",
                stdout_path=self.root / "a",
                stderr_path=self.root / "b",
                deadline_monotonic=time.monotonic(),
                run_marker=self.marker,
            )
        existing = self.root / "existing"
        existing.write_bytes(b"owned")
        with self.assertRaises(ExecutionError):
            run_bounded_process(
                (sys.executable, "-c", "pass"),
                cwd=self.root,
                environment=self.environment,
                stdin_bytes=b"",
                stdout_path=existing,
                stderr_path=self.root / "absent",
                deadline_monotonic=time.monotonic() + 1,
                run_marker=self.marker,
            )
        self.assertEqual(existing.read_bytes(), b"owned")


if __name__ == "__main__":
    unittest.main()
