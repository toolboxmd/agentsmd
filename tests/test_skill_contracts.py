#!/usr/bin/env python3
"""Behavioral contracts for the AgentsMD-owned workflow Skills."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class SkillContractTests(unittest.TestCase):
    def test_project_direction_skill_owns_all_repair_and_review_triggers(self) -> None:
        skill = read_text("skills/project-direction/SKILL.md")
        metadata = skill.split("---\n", 2)[1]
        normalized_metadata = " ".join(metadata.split())
        for required in (
            "missing",
            "blank",
            "unreadable",
            "oversized",
            "unresolved placeholders",
            "contradict",
            "stale",
            "achieved",
            "invalidated",
            "abandoned",
            "reprioritized",
            "define, review, or update",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized_metadata)
        self.assertNotIn("disable-model-invocation", metadata)
        self.assertIn("Do not invoke merely to reread", normalized_metadata)

    def test_project_direction_skill_preserves_user_owned_strategy(self) -> None:
        skill = read_text("skills/project-direction/SKILL.md")
        normalized = " ".join(skill.split())
        for required in (
            "coherent unit",
            "unsupported strategic claims unknown",
            "Ask only for unresolved strategic decisions",
            "explicit user confirmation before writing",
            "Do not require repeated confirmation",
            "modify only the files whose meaning changed",
            "reread all three files in full",
            "deliberate detour",
            "advance the current Objective",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_objective_is_milestone_level_across_public_contract(self) -> None:
        for relative in (
            "AGENTS.md",
            "GLOSSARY.md",
            "README.md",
            "skills/project-direction/SKILL.md",
            "skills/project-direction/references/file-contracts.md",
        ):
            normalized = " ".join(read_text(relative).split())
            with self.subTest(relative=relative):
                self.assertIn("milestone-level", normalized)
                self.assertIn("narrower than the Mission", normalized)
                self.assertIn(
                    "broader than an individual request, task, Issue, commit, or PR",
                    normalized,
                )

        template = " ".join(
            read_text("skills/project-direction/templates/OBJECTIVE.md").split()
        )
        self.assertIn("milestone-level outcome", template)
        self.assertIn("not one task's delivery state", template)

    def test_project_direction_evals_cover_task_to_objective_regression(self) -> None:
        payload = json.loads(
            read_text("skills/project-direction/evals/evals.json")
        )
        cases = " ".join(
            f"{case['prompt']} {case['expected_output']}"
            for case in payload["evals"]
        )
        for required in (
            "active task as evidence",
            "broader milestone",
            "several contributing Issues",
            "task-level Objective",
            "genuinely off-Objective",
        ):
            with self.subTest(required=required):
                self.assertIn(required, cases)

    def test_vision_and_mission_have_distinct_directional_roles(self) -> None:
        for relative in (
            "AGENTS.md",
            "GLOSSARY.md",
            "README.md",
            "skills/project-direction/SKILL.md",
            "skills/project-direction/references/file-contracts.md",
        ):
            normalized = " ".join(read_text(relative).split())
            with self.subTest(relative=relative):
                self.assertIn("grand and visionary", normalized)
                self.assertIn("strategic", normalized)
                self.assertIn("grounded in what the project does now", normalized)

        vision_template = " ".join(
            read_text("skills/project-direction/templates/VISION.md").split()
        )
        mission_template = " ".join(
            read_text("skills/project-direction/templates/MISSION.md").split()
        )
        self.assertIn("grand and visionary future", vision_template)
        self.assertIn("strategic present purpose", mission_template)
        self.assertIn("grounded in what the project does now", mission_template)

    def test_project_direction_evals_cover_vision_and_mission_quality(
        self,
    ) -> None:
        payload = json.loads(
            read_text("skills/project-direction/evals/evals.json")
        )
        cases = " ".join(
            f"{case['prompt']} {case['expected_output']}"
            for case in payload["evals"]
        )
        self.assertIn("tactical Vision", cases)
        self.assertIn("ungrounded Mission", cases)

    def test_global_contract_requires_complete_current_project_direction(self) -> None:
        agents = read_text("AGENTS.md")
        normalized = " ".join(agents.split())
        for required in (
            "Project Direction",
            "`VISION.md`, `MISSION.md`, and `OBJECTIVE.md`",
            "at every task start, resume, clear, handoff, post-compaction continuation, and subagent start",
            "locate and read all three files in full before any other work",
            "Only the repository and tracker inspection required by that Skill may proceed",
            "reported as oversized",
            "Treat the current request as the immediate instruction",
            "Surface material drift before proceeding",
            "Every proposed Spec and Issue must state how its outcome advances the current Objective",
            "Other Skills follow their own trigger and approval contracts",
            "own current Project Direction",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_root_direction_files_are_present_and_bounded(self) -> None:
        expected_headings = {
            "VISION.md": "# Vision\n",
            "MISSION.md": "# Mission\n",
            "OBJECTIVE.md": "# Objective\n",
        }
        total = 0
        for relative, heading in expected_headings.items():
            payload = (ROOT / relative).read_bytes()
            total += len(payload)
            self.assertTrue(payload.decode("utf-8").startswith(heading), relative)
            self.assertLessEqual(len(payload), 8192, relative)
        self.assertLessEqual(total, 16384)

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

    def test_global_contract_runs_the_algorithm_in_order(self) -> None:
        agents = read_text("AGENTS.md")
        normalized = " ".join(agents.split())
        stages = (
            "Question every requirement.",
            "Delete the unnecessary part or process.",
            "Simplify or optimize only what survives deletion.",
            "Accelerate cycle time through the active constraint.",
            "Automate last.",
        )
        positions = [normalized.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        for required in (
            "The fixed order is binding",
            "Addback maps the boundary; it is not a quota.",
            "Run the Algorithm inside a closed evidence loop.",
            "the fastest check that can falsify the current assumption",
            "feedback, not final Proof",
        ):
            self.assertIn(required, normalized)

    def test_domain_modeling_owns_lazy_glossary_behavior(self) -> None:
        skill = read_text("skills/domain-modeling/SKILL.md")
        for required in (
            "`GLOSSARY.md`",
            "`GLOSSARY-MAP.md`",
            "read-only fallback",
            "Create files lazily",
            "|-- GLOSSARY.md",
            "|-- GLOSSARY-MAP.md",
            "system-wide decisions",
            "domain-specific decisions",
        ):
            self.assertIn(required, skill)
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
        normalized = " ".join(skill.split())
        for required in (
            "GitHub parent Issue",
            "current state of the codebase",
            "Prefer an existing testing seam",
            "highest public seam",
            "ideally one",
            "Confirm the proposed seam",
            "## Outcome",
            "## Acceptance criteria",
            "## Non-goals",
            "## Blockers",
            "## Required proof",
            "technical clarifications",
            "schema or API contracts",
            "external behavior",
        ):
            self.assertIn(required, normalized)
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
        normalized = " ".join(skill.split())
        for required in (
            "owning GitHub repository",
            "persistent decision fog",
            "regardless of predicted session length",
            "## Plan, don't do",
            "## Refer by name",
            "## Question",
            "## Type",
            "## Decision Issue types",
            "Research (AFK)",
            "Prototype (HITL)",
            "Grilling (HITL)",
            "Task (HITL or AFK)",
            "Invoke the bundled `research` Skill",
            "Invoke the bundled `prototype` Skill",
            "without asking the human to select a workflow",
            "breadth-first",
            "visible decision frontier",
            "native blocking",
            "assigning it",
            "agent never stands in for the human",
            "close it",
            "stop when the route is clear",
        ):
            self.assertIn(required, normalized)
        for forbidden in (
            "setup-matt-pocock-skills",
            "local-markdown",
            "Fire the research subagents",
            "100K",
            "more than one agent session can hold",
        ):
            self.assertNotIn(forbidden, skill)

        agents = read_text("AGENTS.md")
        normalized_agents = " ".join(agents.split())
        self.assertIn(
            "unresolved dependent decisions prevent a reliable spec",
            normalized_agents,
        )
        self.assertNotIn(
            "use `wayfinder` only when a large effort still has an unclear",
            normalized_agents,
        )

    def test_prototype_answers_a_typed_decision_issue(self) -> None:
        skill = " ".join(read_text("skills/prototype/SKILL.md").split())
        for required in (
            "Prototype Decision Issue",
            "without asking the human to select it",
            "[LOGIC.md](LOGIC.md)",
            "[UI.md](UI.md)",
            "runnable smoke check",
            "human verdict",
            "owning GitHub Issue",
            "throwaway branch",
        ):
            self.assertIn(required, skill)

    def test_research_answers_a_typed_decision_issue(self) -> None:
        skill = " ".join(read_text("skills/research/SKILL.md").split())
        for required in (
            "Research Decision Issue",
            "without asking the human to select it",
            "primary sources",
            "facts from inference",
            "single Markdown file",
            "owning GitHub Issue",
            "background agent",
        ):
            self.assertIn(required, skill)

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

    def test_readme_explains_project_direction_runtime_and_limits(self) -> None:
        readme = read_text("README.md")
        normalized = " ".join(readme.split())
        self.assertNotIn("The workflow Skills are human-controlled.", readme)
        for required in (
            "VISION.md`, `MISSION.md`, and `OBJECTIVE.md",
            "human-controlled planning workflows",
            "`project-direction` is model-invoked",
            "SessionStart",
            "UserPromptSubmit",
            "SubagentStart",
            "8,192 bytes per file",
            "16,384 bytes combined",
            "does not prove reinjection after a subagent's private compaction",
            "review and trust",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
