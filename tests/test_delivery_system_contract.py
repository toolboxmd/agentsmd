#!/usr/bin/env python3
"""Regression checks for the portable Delivery System v1 instruction contract."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeliverySystemContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        cls.agents_words = " ".join(cls.agents.split())
        cls.skill = (ROOT / "skills/delivery-profile/SKILL.md").read_text(
            encoding="utf-8"
        )

    def test_lifecycle_states_are_reported_separately(self) -> None:
        for state in (
            "qualified",
            "implemented",
            "proved",
            "reviewed",
            "merged",
            "released",
            "distributed",
            "deployed",
            "installed",
            "activated",
            "loaded",
            "Live Verified",
            "website-current",
        ):
            with self.subTest(state=state):
                self.assertIn(state, self.agents)

    def test_parallel_review_version_and_runner_contract_is_present(self) -> None:
        required = (
            "Sequential direct work",
            "Independent worktree pull requests",
            "Dependent stacked pull requests",
            "Tightly coupled single-writer integration",
            "Codex Luna",
            "maximum reasoning",
            "exact SHA",
            "generated-scope validation",
            "earliest owning layer",
            "highest semantic impact",
            "GitHub-hosted runners",
            "Rocky",
            "Cavallo",
            "Bigbrain",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.agents_words)

    def test_proof_artifact_and_website_contract_is_present(self) -> None:
        required = (
            "changed-scope",
            "complete merge gate",
            "complete release gate",
            "built once",
            "immutable digest",
            "promoted unchanged",
            "none, generated, narrative, or runtime",
            "major version",
            "complete website review",
            "SEO impact",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.agents_words)

    def test_legacy_ledgers_have_no_active_tracker_role(self) -> None:
        self.assertIn("legacy input ledgers", self.agents)
        self.assertNotIn("`TODO.md` is immediate local action", self.agents)
        self.assertNotIn("`ISSUES.md`, when intentionally present", self.agents)
        self.assertNotIn("`IDEAS.md` is optional future work", self.agents)
        self.assertNotIn("`STATUS.md` is an optional current snapshot", self.agents)

    def test_skill_is_a_narrow_profile_loader_not_an_orchestrator(self) -> None:
        self.assertIn("bin/delivery-profile", self.skill)
        self.assertIn("Project-specific deltas", self.skill)
        self.assertIn("AGENTS.md", self.skill)
        self.assertNotIn("orchestration engine", self.skill)


if __name__ == "__main__":
    unittest.main(verbosity=2)
