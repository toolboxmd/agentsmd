#!/usr/bin/env python3
"""Behavioral contracts for the AgentsMD-owned workflow Skills."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class SkillContractTests(unittest.TestCase):
    def test_global_contract_uses_new_glossary_names(self) -> None:
        agents = read_text("AGENTS.md")
        self.assertIn("`GLOSSARY.md`", agents)
        self.assertIn("`GLOSSARY-MAP.md`", agents)
        self.assertIn("read-only", agents)
        self.assertNotIn("create a root `CONTEXT.md`", agents)
        self.assertNotIn("update the appropriate `CONTEXT.md`", agents)
        self.assertNotIn("ASD-STE100-style", agents)
        self.assertIn("AgentsMD workflow Skills", agents)

    def test_global_contract_defines_independent_partnership(self) -> None:
        agents = read_text("AGENTS.md")
        for required in (
            "Align on ends. Think independently about means.",
            "Optimize for mission and valuable outcome",
            "Form and state an independent view",
            "Dissent when it can materially change",
            "Use initiative within authority",
            "lead with it",
        ):
            self.assertIn(required, agents)

    def test_domain_modeling_owns_lazy_glossary_behavior(self) -> None:
        skill = read_text("skills/domain-modeling/SKILL.md")
        self.assertIn("`GLOSSARY.md`", skill)
        self.assertIn("`GLOSSARY-MAP.md`", skill)
        self.assertIn("read-only fallback", skill)
        self.assertIn("create files lazily", skill.lower())
        self.assertNotIn("[CONTEXT-FORMAT.md]", skill)
        self.assertFalse((ROOT / "skills/domain-modeling/CONTEXT-FORMAT.md").exists())

    def test_grill_with_docs_does_not_precreate_documents(self) -> None:
        skill = read_text("skills/grill-with-docs/SKILL.md")
        self.assertIn("grilling", skill)
        self.assertIn("domain-modeling", skill)
        self.assertIn("lazily", skill)
        self.assertNotIn("setup-matt-pocock-skills", skill)

    def test_to_spec_publishes_a_ready_github_parent_issue(self) -> None:
        skill = read_text("skills/to-spec/SKILL.md")
        for required in (
            "GitHub parent Issue",
            "## Outcome",
            "## Acceptance criteria",
            "## Non-goals",
            "## Blockers",
            "## Required proof",
        ):
            self.assertIn(required, skill)
        for forbidden in (
            "setup-matt-pocock-skills",
            "ready-for-agent",
            "local file",
            "configured tracker",
        ):
            self.assertNotIn(forbidden, skill)

    def test_to_tickets_publishes_github_issues_and_native_edges(self) -> None:
        skill = read_text("skills/to-tickets/SKILL.md")
        for required in (
            "GitHub Issues",
            "native sub-Issue",
            "native blocking",
            "fresh context",
            "## Non-goals",
            "## Required proof",
            "user approves",
        ):
            self.assertIn(required, skill)
        for forbidden in (
            "setup-matt-pocock-skills",
            "ready-for-agent",
            "Local files",
            ".scratch/",
            "configured tracker",
        ):
            self.assertNotIn(forbidden, skill)

    def test_wayfinder_maps_only_the_visible_github_frontier(self) -> None:
        skill = read_text("skills/wayfinder/SKILL.md")
        for required in (
            "owning GitHub repository",
            "visible decision frontier",
            "native blocking",
            "stop when the route is clear",
        ):
            self.assertIn(required, skill)
        for forbidden in (
            "setup-matt-pocock-skills",
            "local-markdown",
            "Fire the research subagents",
        ):
            self.assertNotIn(forbidden, skill)

    def test_grilling_keeps_the_exhaustive_frontier(self) -> None:
        skill = read_text("skills/grilling/SKILL.md")
        self.assertIn("Interview the user relentlessly", skill)
        self.assertIn("Ask the whole frontier in one round", skill)
        self.assertIn("frontier is empty", skill)
        self.assertNotIn("question limit", skill)

    def test_readme_explains_package_and_registry_boundaries(self) -> None:
        readme = read_text("README.md")
        for required in (
            "Skill Catalogue",
            "Product Registry",
            "Plugin Registry",
            "fresh session",
            "duplicate",
        ):
            self.assertIn(required, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
