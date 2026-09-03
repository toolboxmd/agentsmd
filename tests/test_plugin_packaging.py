#!/usr/bin/env python3
"""Public packaging contract for the installable AgentsMD plugin."""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

ACTIVE_SKILLS = {
    "algorithm",
    "domain-modeling",
    "grill-with-docs",
    "grilling",
    "project-direction",
    "prototype",
    "research",
    "to-spec",
    "to-tickets",
    "use-grok",
    "version-control",
    "wayfinder",
    "writing-for-agents",
}

PROJECT_RECORD_SKILLS = [
    f"skills/{name}/SKILL.md" for name in sorted(ACTIVE_SKILLS)
]

MATT_ADAPTATIONS = {
    "domain-modeling",
    "grill-with-docs",
    "grilling",
    "prototype",
    "research",
    "to-spec",
    "to-tickets",
    "wayfinder",
    "writing-for-agents",
}

INACTIVE_SKILLS = {
    "ask-matt",
    "grill-me",
    "setup-matt-pocock-skills",
    "teach",
    "triage",
    "wait-what",
}

MATT_LOCK = json.loads(
    (ROOT / "provenance/mattpocock-skills.lock.json").read_text(encoding="utf-8")
)
MATT_SKILLS = {
    name
    for names in MATT_LOCK["categories"].values()
    for name in names
}

USE_GROK_SHA256 = {
    "SKILL.md": "a07708fabb34d92b1c3f5f3efeaa03d383bc0f1cb4aa09f7f838c3c570f41a8c",
    "agents/openai.yaml": "4a754f952f42112b48a02a007805e56e1c05a11104d08eba6df3d339469ff0d5",
    "references/grok-cli.md": "9c63d9467c9f1c09caee145f8c927f5e0ae101e4f1cd431286fab7efb6018010",
}


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def frontmatter(relative: str) -> str:
    text = read_text(relative)
    if not text.startswith("---\n"):
        return ""
    return text.split("---\n", 2)[1]


class PluginPackagingTests(unittest.TestCase):
    def test_project_record_is_minimal_and_points_to_released_fact_owners(
        self,
    ) -> None:
        record = json.loads((ROOT / ".toolboxmd/project.json").read_text())
        self.assertEqual(
            list(record),
            ["$schema", "id", "kind", "outcome", "factSources"],
        )
        self.assertEqual(
            record["$schema"],
            "https://raw.githubusercontent.com/toolboxmd/marketplace/"
            "v0.3.0/schemas/project-record-v1.schema.json",
        )
        self.assertEqual(record["id"], "agentsmd")
        self.assertEqual(record["kind"], "agent-module")
        self.assertTrue(record["outcome"].strip())

        sources = record["factSources"]
        self.assertEqual(
            sources,
            {
                "version": "VERSION",
                "delivery": {
                    "codex": ".codex-plugin/plugin.json",
                    "claude-code": ".claude-plugin/plugin.json",
                    "grok-build": ".grok-plugin/plugin.json",
                },
                "skills": PROJECT_RECORD_SKILLS,
                "documentation": [
                    "README.md",
                    "SKILL_CATALOGUE.md",
                    "docs/adr/0001-persistent-host-automation.md",
                ],
                "requirements": ["AGENTS.md", ".version-policy.json"],
                "proof": [
                    "tests/delivery_continuation_validator.py",
                    "tests/fixtures/delivery_continuation_cases.json",
                    "tests/fixtures/persistent_host_automation_cases.json",
                    "tests/fixtures/specify_workflow_cases.json",
                    "tests/fixtures/workspace_isolation_cases.json",
                    "tests/persistent_host_automation_validator.py",
                    "tests/test_delivery_continuation_contract.py",
                    "tests/test_global_instructions.py",
                    "tests/test_persistent_host_automation_contract.py",
                    "tests/test_plugin_packaging.py",
                    "tests/test_project_direction_loader.py",
                    "tests/test_skill_contracts.py",
                ],
            },
        )
        referenced = [sources["version"], *sources["delivery"].values()]
        for field in ("skills", "documentation", "requirements", "proof"):
            referenced.extend(sources[field])
        self.assertEqual(len(referenced), len(set(referenced)))
        for relative in referenced:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_project_direction_hooks_cover_supported_reload_boundaries(self) -> None:
        hook_config = json.loads((ROOT / "hooks/hooks.json").read_text())
        hooks = hook_config["hooks"]
        self.assertEqual(
            hooks["SessionStart"][0]["matcher"],
            "^(startup|resume|clear|compact)$",
        )
        self.assertNotIn("matcher", hooks["UserPromptSubmit"][0])
        self.assertNotIn("matcher", hooks["SubagentStart"][0])
        for event in ("SessionStart", "UserPromptSubmit", "SubagentStart"):
            with self.subTest(event=event):
                handler = hooks[event][0]["hooks"][0]
                self.assertEqual(handler["type"], "command")
                self.assertEqual(
                    handler["command"],
                    '"${CLAUDE_PLUGIN_ROOT}/bin/project-direction" hook',
                )
                self.assertEqual(handler["additionalContextLimit"], 6000)

    def test_three_host_identity(self) -> None:
        manifests = {
            "codex": json.loads((ROOT / ".codex-plugin/plugin.json").read_text()),
            "claude": json.loads((ROOT / ".claude-plugin/plugin.json").read_text()),
            "grok": json.loads((ROOT / ".grok-plugin/plugin.json").read_text()),
        }
        for label, manifest in manifests.items():
            self.assertEqual(manifest["name"], "agentsmd", label)
            self.assertEqual(manifest["version"], VERSION, label)
            self.assertIn("workflow", manifest["description"].lower(), label)

    def test_codex_install_surface_uses_descriptions_without_starter_prompts(
        self,
    ) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        interface = manifest["interface"]
        self.assertNotIn("defaultPrompt", interface)
        for field in ("shortDescription", "longDescription"):
            with self.subTest(field=field):
                description = interface[field]
                self.assertIsInstance(description, str)
                self.assertTrue(description.strip())

    def test_not_a_local_marketplace(self) -> None:
        for rel in (
            ".claude-plugin/marketplace.json",
            ".grok-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
        ):
            path = ROOT / rel
            if not path.is_file():
                continue
            name = json.loads(path.read_text()).get("name")
            self.assertNotIn(name, {"agentsmd-local", "toolboxmd"})

    def test_active_skill_inventory_is_exact(self) -> None:
        discovered = {
            path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(discovered, ACTIVE_SKILLS)
        self.assertTrue(INACTIVE_SKILLS.isdisjoint(discovered))

    def test_every_active_skill_has_host_metadata(self) -> None:
        for name in ACTIVE_SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((ROOT / "skills" / name / "agents/openai.yaml").is_file())

    def test_complete_supporting_resources_are_packaged(self) -> None:
        expected = {
            "tests/delivery_continuation_validator.py",
            "tests/fixtures/delivery_continuation_cases.json",
            "tests/test_delivery_continuation_contract.py",
            "tests/fixtures/specify_workflow_cases.json",
            "skills/algorithm/evals/trigger-evals.json",
            "skills/algorithm/references/marketplace-project-record-regression.md",
            "skills/project-direction/references/file-contracts.md",
            "skills/project-direction/templates/MISSION.md",
            "skills/project-direction/templates/OBJECTIVE.md",
            "skills/project-direction/templates/VISION.md",
            "skills/prototype/LOGIC.md",
            "skills/prototype/UI.md",
            "skills/domain-modeling/ADR-FORMAT.md",
            "skills/domain-modeling/GLOSSARY-FORMAT.md",
            "skills/use-grok/references/grok-cli.md",
            "skills/version-control/references/bump-rules.md",
            "skills/version-control/references/project-policy.md",
            "skills/writing-for-agents/SKILL-MECHANICS.md",
        }
        missing = [relative for relative in expected if not (ROOT / relative).is_file()]
        self.assertEqual(missing, [])

    def test_runtime_files_are_packaged_and_executable(self) -> None:
        for relative in (
            "bin/agentsmd-global-instructions",
            "bin/project-direction",
            "hooks/hooks.json",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        for relative in (
            "bin/agentsmd-global-instructions",
            "bin/project-direction",
        ):
            with self.subTest(executable=relative):
                self.assertTrue(os.access(ROOT / relative, os.X_OK))

    def test_packaged_project_direction_guard_has_matching_contracts(self) -> None:
        loader = read_text("bin/project-direction")
        agents = read_text("AGENTS.md")
        skill = read_text("skills/project-direction/SKILL.md")

        for required in (
            "potentially_stale",
            "configured upstream",
            "ahead/behind",
        ):
            with self.subTest(required=required):
                self.assertIn(required, loader)
                self.assertIn(required, agents)
                self.assertIn(required, skill)

    def test_matt_adaptations_declare_origin_and_licence(self) -> None:
        for name in MATT_ADAPTATIONS:
            metadata = frontmatter(f"skills/{name}/SKILL.md")
            with self.subTest(skill=name):
                self.assertIn("license: MIT", metadata)
                self.assertIn("owner: toolboxmd", metadata)
                self.assertIn("origin: mattpocock/skills", metadata)
                self.assertIn(
                    "source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76",
                    metadata,
                )

    def test_use_grok_is_the_exact_approved_source(self) -> None:
        for relative, expected in USE_GROK_SHA256.items():
            payload = (ROOT / "skills/use-grok" / relative).read_bytes()
            actual = hashlib.sha256(payload).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_third_party_licences_are_packaged(self) -> None:
        matt = read_text("LICENSES/mattpocock-skills-MIT.txt")
        grok = read_text("LICENSES/use-grok-Apache-2.0.txt")
        self.assertIn("Copyright (c) 2026 Matt Pocock", matt)
        self.assertIn("Apache License", grok)
        self.assertIn("Copyright 2026 lukaszmaj", grok)

    def test_catalogue_covers_every_lifecycle(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        for name in ACTIVE_SKILLS | INACTIVE_SKILLS | MATT_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(f"`{name}`", catalogue)
        for lifecycle in ("Active", "Deferred", "Retired", "Upstream reference"):
            self.assertIn(lifecycle, catalogue)
        self.assertIn("6654f6b60cd9d5be8b54c6fafe44346dabeb3b76", catalogue)
        self.assertIn("a8ae6ab3c862de836ca576276a221610e3fe274c", catalogue)

    def test_catalogue_owns_project_direction_as_native_active_skill(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        row = next(
            line
            for line in catalogue.splitlines()
            if line.startswith("| `project-direction`")
        )
        self.assertIn("AgentsMD-native; this release commit", row)
        self.assertIn("Active", row)
        self.assertIn("MIT", row)
        self.assertIn("Vision, Mission, and Objective", row)

    def test_catalogue_owns_algorithm_as_native_active_skill(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        row = next(
            line
            for line in catalogue.splitlines()
            if line.startswith("| `algorithm`")
        )
        self.assertIn("AgentsMD-native; this release commit", row)
        self.assertIn("Active", row)
        self.assertIn("MIT", row)
        self.assertIn("five-step Algorithm", row)

    def test_every_catalogue_row_resolves_an_exact_source_revision(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        rows = {
            line.split("`", 2)[1]: line
            for line in catalogue.splitlines()
            if line.startswith("| `")
        }
        for name in ACTIVE_SKILLS | MATT_SKILLS:
            with self.subTest(skill=name):
                row = rows[name]
                if name in {"algorithm", "project-direction", "version-control"}:
                    self.assertIn("this release commit", row)
                elif name == "use-grok":
                    self.assertIn("use-grok pin", row)
                else:
                    self.assertIn("Matt pin", row)

    def test_legacy_glossary_references_are_read_only(self) -> None:
        for path in (ROOT / "skills").glob("**/*.md"):
            text = path.read_text(encoding="utf-8")
            if "`CONTEXT.md`" not in text and "`CONTEXT-MAP.md`" not in text:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue("read-only" in text or "read only" in text)
                self.assertNotIn("create `CONTEXT", text)
                self.assertNotIn("update `CONTEXT", text)
                self.assertNotIn("write to `CONTEXT", text)

    def test_root_glossary_owns_agentsmd_language(self) -> None:
        glossary = read_text("GLOSSARY.md")
        for term in (
            "AgentsMD",
            "ContextMD",
            "World Model",
            "Parent Spec only",
            "Skill Catalogue",
            "Product Registry",
            "Plugin Registry",
        ):
            with self.subTest(term=term):
                self.assertIn(f"**{term}**", glossary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
