"""Regression for accepting a delegated negative result (toolboxmd/agentsmd#226)."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "negative-result-gate.json"
DELEGATION = ROOT / "skills/operations/references/bounded-delegation.md"
ORCHESTRATION = ROOT / "skills/operations/references/orchestration.md"
OWNER_FIXTURE = ROOT / "evals" / "issue-owner.json"


def words(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def leaves_with_owner(case: dict) -> bool:
    """A filed or found Issue leaves the turn with an owner only when one of these holds."""
    running = case["running_worker_started"] and case["within_authority"]
    accepted = case["handoff_sent"] and case["handoff_acknowledged"]
    return (running or accepted) and case["report_names_owner"]


def negative_may_reach_user_or_issue(case: dict, primary_sources: set[str]) -> bool:
    """The acceptance gate. A negative reaches the user or an Issue only when it survives."""
    if case["polarity"] != "negative":
        raise AssertionError("this gate does not grade positive findings")
    listed = case["attempts_listed"] and primary_sources <= set(case["primary_sources"])
    challenged = case["coordinator_tried"] or case["challenger_assigned"]
    return listed and challenged and case["attempt_failed"]


class NegativeResultGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_incident_fixture_grades_every_case(self) -> None:
        self.assertEqual(self.fixture["fixture_kind"], "negative-result-gate")
        self.assertIn("226", self.fixture["issue"])
        primary = set(self.fixture["primary_sources"])
        self.assertEqual(primary, {"docs", "readme", "help", "env", "config"})
        cases = self.fixture["cases"]
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        incident = [case["id"] for case in cases if case["incident"]]
        self.assertEqual(
            incident,
            [
                "grok-cannot-strip-relayed",
                "opencode-no-recipe-filed",
                "grok-disproved-by-own-readme",
                "opencode-disproved-by-auth-list",
            ],
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["polarity"], "negative")
                self.assertEqual(
                    negative_may_reach_user_or_issue(case, primary),
                    case["reaches_user_or_issue"],
                )

    def test_delegation_reference_owns_the_acceptance_gate(self) -> None:
        text = words(DELEGATION)
        for clause in (
            "A negative result says the work cannot be done: not possible, cannot remove, blocked, no recipe, or failed.",
            "Accept a negative result only when it lists what was tried and which primary sources were checked: the tool's own docs and bundled README, its `--help`, its environment variables, and its config keys.",
            "Before you relay that result to the user or file anything from it, try the work once yourself or assign one challenger whose only job is to make the work succeed.",
            "Report only a negative result that survives that attempt, and include the attempts.",
            "An ordinary failed slice, one that does not say the work cannot be done, is still recorded at once.",
            "Validate at safe boundaries and before reporting.",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, text)
        self.assertEqual(text.count("Validate at safe boundaries and before reporting."), 1)
        self.assertNotIn("try harder", text.lower())

    def test_worker_brief_requires_attempts_and_primary_sources(self) -> None:
        text = words(ORCHESTRATION)
        self.assertIn(
            "The report shape for a negative result (not possible, cannot remove, blocked, no recipe, or failed) "
            "lists what was tried and which primary sources were checked: the tool's own docs and bundled README, "
            "its `--help`, its environment variables, and its config keys.",
            text,
        )
        self.assertIn(
            "Before you relay a negative result or file anything from it, read [bounded delegation](bounded-delegation.md) "
            "in full and apply its negative-result gate.",
            text,
        )
        self.assertIn(
            "When you file or find an Issue for work the user wants done,",
            text,
        )
        self.assertIn(
            "leave that turn with a real owner: "
            "a running worker you started within your authority, or a named agent that has accepted the handoff, "
            "message sent and acknowledged.",
            text,
        )
        self.assertIn('"X will pick it up", with no handoff, is not an owner.', text)
        self.assertIn("Name the owner in the report to the user.", text)
        self.assertNotIn("Pursue necessary in-scope work", text)


class IssueOwnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(OWNER_FIXTURE.read_text(encoding="utf-8"))

    def test_incident_fixture_grades_every_case(self) -> None:
        self.assertEqual(self.fixture["fixture_kind"], "issue-owner")
        self.assertIn("226", self.fixture["issue"])
        cases = self.fixture["cases"]
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        incident = [case["id"] for case in cases if case["incident"]]
        self.assertEqual(incident, ["agent-observer-85-86-unstaffed"])
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(leaves_with_owner(case), case["leaves_with_owner"])


if __name__ == "__main__":
    unittest.main()
