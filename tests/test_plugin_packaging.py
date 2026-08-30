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
    "domain-modeling",
    "grill-with-docs",
    "grilling",
    "project-direction",
    "to-spec",
    "to-tickets",
    "use-grok",
    "version-control",
    "wayfinder",
    "writing-for-agents",
}

MATT_ADAPTATIONS = {
    "domain-modeling",
    "grill-with-docs",
    "grilling",
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

    def test_codex_default_prompts_respect_host_limit(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        prompts = manifest["interface"]["defaultPrompt"]
        self.assertIsInstance(prompts, list)
        self.assertGreaterEqual(len(prompts), 1)
        self.assertLessEqual(len(prompts), 3)
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertIsInstance(prompt, str)
                self.assertLessEqual(len(prompt), 128)

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
            "skills/project-direction/references/file-contracts.md",
            "skills/project-direction/templates/MISSION.md",
            "skills/project-direction/templates/OBJECTIVE.md",
            "skills/project-direction/templates/VISION.md",
            "skills/domain-modeling/ADR-FORMAT.md",
            "skills/domain-modeling/GLOSSARY-FORMAT.md",
            "skills/use-grok/references/grok-cli.md",
            "skills/version-control/references/bump-rules.md",
            "skills/version-control/references/project-policy.md",
            "skills/writing-for-agents/SKILL-MECHANICS.md",
        }
        missing = [relative for relative in expected if not (ROOT / relative).is_file()]
        self.assertEqual(missing, [])

    def test_project_direction_runtime_files_are_packaged_and_executable(self) -> None:
        for relative in ("bin/project-direction", "hooks/hooks.json"):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        self.assertTrue(os.access(ROOT / "bin/project-direction", os.X_OK))

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
                if name in {"project-direction", "version-control"}:
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
            "Skill Catalogue",
            "Product Registry",
            "Plugin Registry",
        ):
            with self.subTest(term=term):
                self.assertIn(f"**{term}**", glossary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
