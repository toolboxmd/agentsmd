#!/usr/bin/env python3
"""Behavioral contracts for the AgentsMD-owned workflow Skills."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def scalar(value: str) -> str | bool | int:
    if value == "true":
        return True
    if value == "false":
        return False
    if value.isdigit():
        return int(value)
    return value.strip('"')


def frontmatter_fields(relative: str) -> dict[str, str | bool | int]:
    metadata = read_text(relative).split("---\n", 2)[1]
    fields = {}
    for line in metadata.splitlines():
        if not line or line.startswith(" ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if value.strip():
            fields[key] = scalar(value.strip())
    return fields


def frontmatter_metadata(relative: str) -> dict[str, str | bool | int]:
    metadata = read_text(relative).split("---\n", 2)[1]
    fields = {}
    in_metadata = False
    for line in metadata.splitlines():
        if line == "metadata:":
            in_metadata = True
            continue
        if in_metadata and not line.startswith("  "):
            break
        if in_metadata and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            fields[key] = scalar(value.strip())
    return fields


def nested_yaml_value(
    relative: str, section: str, key: str
) -> str | bool | int:
    in_section = False
    for line in read_text(relative).splitlines():
        if line == f"{section}:":
            in_section = True
            continue
        if in_section and not line.startswith("  "):
            break
        if in_section and line.startswith(f"  {key}:"):
            return scalar(line.split(":", 1)[1].strip())
    raise KeyError(f"{relative}: {section}.{key}")


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

    def test_project_direction_currentness_contract_is_consistent(self) -> None:
        agents = " ".join(read_text("AGENTS.md").split())
        skill = " ".join(read_text("skills/project-direction/SKILL.md").split())
        loader = read_text("bin/project-direction")

        for contract in (agents, skill):
            with self.subTest(contract=contract[:20]):
                for required in (
                    "after the complete local triad is loaded",
                    "intended base",
                    "`HEAD`",
                    "configured upstream",
                    "ahead/behind",
                    "`potentially_stale`",
                    "reread all three",
                ):
                    self.assertIn(required, contract)
        for required in (
            '"status": "potentially_stale"',
            '"branch"',
            '"head"',
            '"upstream"',
            '"divergence"',
            '"project_direction_diff"',
        ):
            with self.subTest(loader_contract=required):
                self.assertIn(required, loader)

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

    def test_global_contract_routes_material_algorithm_work(self) -> None:
        agents = read_text("AGENTS.md")
        normalized = " ".join(agents.split())
        for required in (
            "After Project Direction is loaded",
            "invoke the model-invoked `algorithm` Skill",
            "material requirement",
            "solution design",
            "process design",
            "recurring-loop automation",
            "small direct microfix",
            "stays direct",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)
        self.assertNotIn("Question every requirement.", agents)
        self.assertNotIn("Run the Algorithm inside a closed evidence loop.", agents)

    def test_algorithm_skill_preserves_order_and_completion_contract(self) -> None:
        skill = read_text("skills/algorithm/SKILL.md")
        normalized = " ".join(skill.split())
        stages = (
            "Question every requirement.",
            "Delete the unnecessary part or process.",
            "Simplify or optimize only what survives deletion.",
            "Accelerate cycle time through the active constraint.",
            "Automate last.",
        )
        positions = [normalized.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions))
        evidence_gate = normalized.index("Before step 4")
        self.assertLess(positions[2], evidence_gate)
        self.assertLess(evidence_gate, positions[3])
        for required in (
            "The fixed order is binding",
            "all five steps again for every material requirement, solution, process, and recurring loop",
            "It prevents perfect execution of the wrong requirement",
            "Requirements from experts and inherited process need scrutiny",
            "question the proposed interpretation and path",
            "Complete this step when outcome, ownership, constraints, "
            "acceptance, and proof are explicit.",
            "Test whether the requirement, scope, code, test, dependency, "
            "artifact, handoff, or ceremony should exist at all.",
            "Deletion is stronger than cleanup",
            "Make deletion risk-scaled and reversible.",
            "Use committed Git history to recover in-scope tracked work.",
            "Keep uncommitted user work, user data, credentials, legal controls",
            "Required proof and unique regression tests survive",
            "Restore work only when evidence proves it is required.",
            "Complete this step when every survivor has an evidence-linked "
            "reason to exist.",
            "Addback maps the boundary; it is not a quota.",
            "Prefer fewer states, narrower interfaces, direct paths, clear ownership",
            "Simplicity must preserve necessary behavior, error handling, proof, safety",
            "It is a design result, not a reason to hide complexity that still exists.",
            "Complete this step when the surviving path is the simplest one "
            "known to meet the requirement.",
            "Speed means faster validated learning after the right work and structure",
            "Use direct source inspection, smaller checks, fewer handoffs, cached work",
            "Keep proof and single-writer boundaries intact.",
            "Complete this step when the next unit of effort follows the "
            "shortest safe feedback path through the current constraint.",
            "Automation magnifies the process chosen before it.",
            "Automate only a necessary, stable, proven, recurring semantic loop",
            "Keep one-off or ambiguous work explicit until evidence makes it repeatable.",
            "Complete this step when automation preserves the proven semantics "
            "and exposes failures.",
            "return to the earliest affected step",
            "Resolve every earlier step before optimizing, accelerating, or automating.",
            "Run the Algorithm inside a closed evidence loop.",
            "Start from the useful outcome and inspect the exact source, work, state, or user surface.",
            "Identify the active constraint.",
            "Make the smallest meaningful reversible change or experiment",
            "the fastest check that can falsify the current assumption",
            "inspect the result, correct the model and implementation, expose bad news, and repeat",
            "Scale failure tolerance to consequence",
            "feedback, not final Proof",
            "highest practical Proof seam",
            "exact delivery state must remain explicit",
            "Human Gates",
            "Project Direction",
            "user-owned dirty work",
            "explicit user constraints",
            "current material-work artifact or evidence",
            "questioned requirement and its supporting evidence",
            "Keep a small direct microfix direct",
            "Do not narrate the Algorithm as ceremony.",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)

    def test_algorithm_is_model_invoked_with_material_branches(self) -> None:
        skill = read_text("skills/algorithm/SKILL.md")
        metadata = skill.split("---\n", 2)[1]
        normalized_metadata = " ".join(metadata.split())
        self.assertNotIn("disable-model-invocation", metadata)
        for required in (
            "material requirements",
            "solution design",
            "process design",
            "recurring-loop automation",
            "small direct microfixes direct",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized_metadata)

        host_metadata = read_text("skills/algorithm/agents/openai.yaml")
        self.assertIn("allow_implicit_invocation: true", host_metadata)

    def test_algorithm_trigger_fixture_covers_positive_and_negative_branches(
        self,
    ) -> None:
        payload = json.loads(
            read_text("skills/algorithm/evals/trigger-evals.json")
        )
        self.assertEqual(payload["skill_name"], "algorithm")
        cases = payload["queries"]
        branches = {
            case["branch"]: case["should_trigger"] for case in cases
        }
        self.assertEqual(
            branches,
            {
                "material-requirement": True,
                "solution-design": True,
                "process-design": True,
                "recurring-loop-automation": True,
                "direct-microfix": False,
                "read-only-status": False,
            },
        )

    def test_algorithm_records_real_marketplace_regression(self) -> None:
        evidence = " ".join(
            read_text(
                "skills/algorithm/references/marketplace-project-record-regression.md"
            ).split()
        )
        for required in (
            "toolboxmd/agentsmd#32",
            "toolboxmd/marketplace#6",
            "comprehensive schema",
            "accepted-record snapshot",
            "provenance lock",
            "three-release design",
            "separate snapshot",
            "separate lock",
            "registry state",
            "duplicated release and manifest facts",
            "automatic reconciliation",
            "minimal neutral index over existing released sources",
        ):
            with self.subTest(required=required):
                self.assertIn(required, evidence)

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

    def test_specify_workflow_metadata_matches_state_contract(self) -> None:
        contract = json.loads(
            read_text("tests/fixtures/specify_workflow_cases.json")
        )["contract"]
        spec = frontmatter_metadata("skills/to-spec/SKILL.md")
        tickets = frontmatter_metadata("skills/to-tickets/SKILL.md")

        self.assertEqual(spec["workflow"], contract["workflow"])
        self.assertEqual(
            spec["default-completion"], contract["default_completion"]
        )
        self.assertEqual(
            spec["parent-publication-approval"],
            contract["parent_publication_approval"],
        )
        self.assertEqual(spec["next-skill"], "to-tickets")
        self.assertEqual(spec["invocation"], contract["entry_invocation"])
        self.assertEqual(
            spec["parent-only-opt-out"], contract["parent_only_opt_out"]
        )
        self.assertEqual(
            spec["implementation-authority-source"],
            contract["implementation_authority_source"],
        )
        self.assertEqual(tickets["workflow"], contract["workflow"])
        self.assertEqual(
            tickets["default-completion"], contract["default_completion"]
        )
        self.assertEqual(
            tickets["ticket-publication-approval"],
            contract["ticket_publication_approval"],
        )
        self.assertEqual(tickets["invocation"], contract["entry_invocation"])
        self.assertEqual(
            tickets["implementation-target"], contract["implementation_target"]
        )
        self.assertEqual(
            tickets["implementation-context"],
            contract["implementation_context"],
        )
        self.assertEqual(
            tickets["implementation-authority-source"],
            contract["implementation_authority_source"],
        )
        self.assertEqual(
            tickets["missing-authority-prompt-limit"],
            contract["missing_authority_prompt_limit"],
        )

        spec_fields = frontmatter_fields("skills/to-spec/SKILL.md")
        tickets_fields = frontmatter_fields("skills/to-tickets/SKILL.md")
        self.assertEqual(spec_fields["name"], contract["entry_skill"])
        self.assertNotIn("disable-model-invocation", spec_fields)
        self.assertNotIn("disable-model-invocation", tickets_fields)
        self.assertTrue(
            nested_yaml_value(
                "skills/to-spec/agents/openai.yaml",
                "policy",
                "allow_implicit_invocation",
            )
        )
        self.assertTrue(
            nested_yaml_value(
                "skills/to-tickets/agents/openai.yaml",
                "policy",
                "allow_implicit_invocation",
            )
        )

    def test_specify_workflow_state_fixture_covers_every_decision_branch(
        self,
    ) -> None:
        payload = json.loads(
            read_text("tests/fixtures/specify_workflow_cases.json")
        )
        self.assertEqual(payload["schema"], 1)
        contract = payload["contract"]
        cases = {case["branch"]: case for case in payload["cases"]}
        self.assertEqual(
            set(cases),
            {
                "planning-only",
                "pre-authorized-implementation",
                "explicit-parent-only",
                "revised-drafts",
                "rejected-parent-draft",
                "rejected-ticket-draft",
            },
        )

        for branch, case in cases.items():
            transitions = case["transitions"]
            with self.subTest(branch=branch):
                self.assertEqual(transitions[0], "draft-parent")
                if branch == "rejected-parent-draft":
                    self.assertNotIn("publish-and-verify-parent", transitions)
                    continue
                self.assertLess(
                    transitions.index("approve-parent"),
                    transitions.index("publish-and-verify-parent"),
                )
                if case["parent_only"]:
                    self.assertNotIn("draft-tickets", transitions)
                else:
                    self.assertLess(
                        transitions.index("publish-and-verify-parent"),
                        transitions.index("draft-tickets"),
                    )
                    if branch == "rejected-ticket-draft":
                        self.assertNotIn(
                            "publish-and-verify-tickets", transitions
                        )
                        continue
                    self.assertLess(
                        transitions.index("approve-ticket-graph"),
                        transitions.index("publish-and-verify-tickets"),
                    )

        planning = cases["planning-only"]
        self.assertEqual(
            planning["implementation_authority_prompts"],
            contract["missing_authority_prompt_limit"],
        )
        self.assertTrue(planning["names_first_unblocked_issue"])
        self.assertFalse(planning["starts_implementation"])

        authorized = cases["pre-authorized-implementation"]
        self.assertTrue(authorized["implementation_authorized"])
        self.assertEqual(authorized["implementation_authority_prompts"], 0)
        self.assertTrue(authorized["starts_implementation"])
        self.assertTrue(authorized["starts_in_fresh_context"])
        for case in cases.values():
            if not case["starts_implementation"]:
                self.assertFalse(case["starts_in_fresh_context"])

        parent_only = cases["explicit-parent-only"]
        self.assertEqual(parent_only["terminal_state"], "parent-only-complete")
        self.assertEqual(parent_only["implementation_authority_prompts"], 0)

        revised = cases["revised-drafts"]["transitions"]
        for transition in (
            "revise-parent-draft",
            "revise-ticket-draft",
        ):
            self.assertIn(transition, revised)

        rejected_parent = cases["rejected-parent-draft"]
        self.assertEqual(
            rejected_parent["terminal_state"], "parent-draft-rejected"
        )
        self.assertEqual(rejected_parent["implementation_authority_prompts"], 0)

        rejected_tickets = cases["rejected-ticket-draft"]
        self.assertEqual(
            rejected_tickets["terminal_state"], "ticket-draft-rejected"
        )
        self.assertEqual(rejected_tickets["implementation_authority_prompts"], 0)

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

    def test_repository_capability_setup_is_inspected_and_authorized_once(
        self,
    ) -> None:
        agents = read_text("AGENTS.md")
        contract = " ".join(
            agents.split("## Authority and continuation", 1)[1]
            .split("\n## ", 1)[0]
            .split()
        )

        for required in (
            "inspect the exact repository read-only before relying on its delivery capabilities",
            "default branch",
            "applicable requirements",
            "native Issue dependencies and dependent work",
            "branch creation and push",
            "closing linkage",
            "authorized ready-PR merge path",
            "local and remote branch retirement",
            "Verify each capability from current evidence",
            "one complete setup bundle",
            "exact current state",
            "proposed settings",
            "expected effect, risks, and rollback path",
            "one scoped user approval",
            "without another prompt",
            "Reuse that authority while the exact settings and risk remain unchanged",
            "settings, target, or risk changes materially",
            "unsupported",
            "zero-mutation bundle",
            "no approval",
            "no repository setting changed",
        ):
            with self.subTest(required=required):
                self.assertIn(required, contract)

        states = (
            "inspection",
            "proposed setup",
            "approval",
            "settings mutation",
            "verification",
        )
        positions = [contract.index(state) for state in states]
        self.assertEqual(positions, sorted(positions))

    def test_wayfinder_maps_only_the_visible_github_frontier(self) -> None:
        skill = read_text("skills/wayfinder/SKILL.md")
        normalized = " ".join(skill.split())
        wayfinder = frontmatter_metadata("skills/wayfinder/SKILL.md")
        self.assertEqual(wayfinder["handoff-skill"], "to-spec")
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
            "intended base",
            "configured upstream",
            "ahead/behind",
            "`potentially_stale`",
            "without network access or checkout mutation",
            "does not prove reinjection after a subagent's private compaction",
            "review and trust",
        ):
            with self.subTest(required=required):
                self.assertIn(required, normalized)


if __name__ == "__main__":
    unittest.main(verbosity=2)
