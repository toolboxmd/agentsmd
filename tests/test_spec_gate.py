#!/usr/bin/env python3
"""The Project Direction hook blocks implementation dispatch without a Spec line."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = ROOT / "bin/project-direction"

# Shortened from the two dispatches the user stopped on 2026-10-12: both used
# delegate_task with role implementation, and the second linked a tracking
# Issue that held no reviewed design.
ROUTER_BRIEF = (
    "Effort: high. Follow ~/scratch/intent-pilot/loop/SERVE-BRIEF.md exactly. "
    "Writes allowed: loop/student/serve.py and its config. Acceptance: the "
    "server answers one routing request under 200 ms."
)
CAPTURE_BRIEF = (
    "Effort: high. Build capture v1 for toolboxmd/contextmd#2 (read the Issue "
    "and its comments). Use the operations skill."
)


class SpecGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cwd = Path(self.temporary.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.cwd)], check=True)
        self.env = {k: v for k, v in os.environ.items() if k not in ("GROK_HOOK_NAME", "AGENTSMD_HOST")}

    def dispatch(self, task: str, role: str | None = "implementation", host: str = "claude",
                 tool_name: str = "mcp__t3-code__delegate_task") -> subprocess.CompletedProcess[str]:
        tool_input: dict[str, object] = {"task": task, "mode": "async"}
        if role is not None:
            tool_input["role"] = role
        event = {"hook_event_name": "PreToolUse", "cwd": str(self.cwd), "session_id": "s",
                 "tool_name": tool_name, "tool_input": tool_input}
        return subprocess.run(
            [str(LOADER), "hook", "--host", host], input=json.dumps(event),
            capture_output=True, text=True, env=self.env, check=False,
        )

    def assertBlocked(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("AgentsMD blocked this implementation dispatch", result.stderr)
        self.assertIn("Spec:", result.stderr)

    def assertAllowed(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_observed_briefs_without_spec_are_blocked(self) -> None:
        for brief in (ROUTER_BRIEF, CAPTURE_BRIEF):
            with self.subTest(brief=brief[:40]):
                self.assertBlocked(self.dispatch(brief))

    def test_spec_issue_reference_allows_dispatch(self) -> None:
        for line in ("Spec: toolboxmd/contextmd#5",
                     "**Spec:** https://github.com/toolboxmd/contextmd/issues/5",
                     "- Spec: #5 (approved parent)"):
            with self.subTest(line=line):
                self.assertAllowed(self.dispatch(CAPTURE_BRIEF + "\n" + line + "\n"))

    def test_declared_exemption_with_reason_allows_dispatch(self) -> None:
        brief = "Spec: none (microfix: correct one flag name in bin/x)\nFix the flag."
        self.assertAllowed(self.dispatch(brief))

    def test_spec_line_without_issue_or_reason_blocks(self) -> None:
        for line in ("Spec:", "Spec: none", "Spec: <link>", "Spec: TBD", "Spec: SERVE-BRIEF.md"):
            with self.subTest(line=line):
                self.assertBlocked(self.dispatch(ROUTER_BRIEF + "\n" + line))

    def test_non_implementation_dispatches_pass(self) -> None:
        for role in ("review", "research", "test", "design", "general", None):
            with self.subTest(role=role):
                self.assertAllowed(self.dispatch(ROUTER_BRIEF, role=role))

    def test_codex_tool_name_and_host_are_checked(self) -> None:
        self.assertBlocked(self.dispatch(ROUTER_BRIEF, host="codex",
                                         tool_name="mcp__t3_code__delegate_task"))

    def test_other_tools_with_role_field_pass(self) -> None:
        self.assertAllowed(self.dispatch(ROUTER_BRIEF, tool_name="mcp__other__run_task"))


if __name__ == "__main__":
    unittest.main()
