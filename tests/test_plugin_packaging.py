#!/usr/bin/env python3
"""Public packaging contract for the installable AgentsMD plugin."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

ACTIVE_SKILLS = {"operations"}

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
                    "docs/work/119-pstack-integration/analysis.md",
                    "docs/adr/0001-persistent-host-automation.md",
                    "docs/opencode.md",
                    "skills/operations/references/scoped-proof.md",
                    "skills/operations/workflows/project-direction/references/context.md",
                ],
                "requirements": [
                    "global/AGENTS.md",
                    ".version-policy.json",
                    ".toolboxmd/delivery.json",
                    "schemas/delivery-v1.schema.json",
                    "skills/operations/references/delivery.md",
                    "skills/operations/references/finalization.md",
                    "skills/operations/references/implementation.md",
                    "skills/operations/references/orchestration.md",
                    "skills/operations/references/reconciliation.md",
                    "skills/operations/references/repository-setup.md",
                    "skills/operations/references/verification.md",

                ],
                "proof": [
                    "tests/delivery_continuation_validator.py",
                    "tests/fixtures/delivery_continuation_cases.json",
                    "tests/fixtures/delivery_finalization_cases.json",
                    "tests/fixtures/persistent_host_automation_cases.json",
                    "tests/fixtures/repository_reconciliation_approval.json",
                    "tests/fixtures/repository_reconciliation_cases.json",
                    "tests/fixtures/review_ready_stack_cases.json",
                    "tests/fixtures/specify_workflow_cases.json",
                    "tests/fixtures/workspace_isolation_cases.json",
                    "tests/persistent_host_automation_validator.py",
                    "tests/repository_reconciliation_validator.py",
                    "tests/test_delivery_continuation_contract.py",
                    "tests/test_delivery_profile.py",
                    "tests/test_delivery_system_contract.py",
                    "tests/test_global_instructions.py",
                    "tests/test_opencode.py",
                    "tests/test_persistent_host_automation_contract.py",
                    "tests/test_plugin_packaging.py",
                    "tests/test_project_direction_loader.py",
                    "tests/test_release_dispatch_contract.py",
                    "tests/test_repository_reconciliation_contract.py",
                    "tests/test_skill_contracts.py",
                    "tests/test_scoped_proof.py",
                    "tests/test_operations_contract.py",
                    "tests/test_pstack_packaging.py",
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
        # PreToolUse carries no matcher so Grok delivers on the first tool of any kind.
        self.assertNotIn("matcher", hooks["PreToolUse"][0])
        for event in (
            "SessionStart",
            "UserPromptSubmit",
            "SubagentStart",
            "PreToolUse",
        ):
            with self.subTest(event=event):
                handler = hooks[event][0]["hooks"][0]
                self.assertEqual(handler["type"], "command")
                self.assertEqual(
                    handler["command"],
                    '"${CLAUDE_PLUGIN_ROOT}/bin/project-direction" hook',
                )
                self.assertTrue(handler["statusMessage"])
                if event == "PreToolUse":
                    self.assertNotIn("additionalContextLimit", handler)
                else:
                    self.assertEqual(handler["additionalContextLimit"], 16000)
        for event, count in hooks.items():
            with self.subTest(event=event):
                self.assertEqual(len(count), 1)
                self.assertEqual(len(count[0]["hooks"]), 1)

    # Per-hook output limits (#175). Claude Code keeps 10,000 characters of
    # additionalContext and silently replaces the rest with a file path and a
    # preview (anthropics/claude-code#94358). Codex spills a hook message past
    # about 2,500 tokens, counted as UTF-8 bytes / 4 (developers.openai.com/codex/hooks;
    # codex-rs/utils/string/src/truncate.rs). Grok clips hook context at 10,000
    # characters (measured in #108). OpenCode documents no cap for its system
    # transform (opencode.ai/docs/plugins), so the shared floor applies.
    HOOK_LIMITS = {
        "claude": ("characters", 10000),
        "codex": ("tokens", 2500),
        "grok": ("characters", 10000),
        "opencode": ("characters", 10000),
    }

    def test_project_direction_output_at_its_caps_leaves_headroom_per_host(self) -> None:
        prose = "Agents keep direction short so every host sees all of it.\n"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            source = base / "agentsmd/global/AGENTS.md"
            source.parent.mkdir(parents=True)
            source.write_text("# Shared contract\n")
            preferences = "# Personal preferences\n\n" + prose * 80
            (base / "agentsmd/PREFERENCES.md").write_text(preferences[:3999] + "\n")
            repository = base / "project"
            repository.mkdir()
            for name, size in (("VISION.md", 400), ("MISSION.md", 500), ("OBJECTIVE.md", 600)):
                text = f"# {name[:-3].title()}\n\n" + prose * 12
                (repository / name).write_text(text[: size - 1] + "\n")
            for command in (
                ["init", "--quiet"],
                ["add", "."],
                ["-c", "user.name=t", "-c", "user.email=t@example.invalid",
                 "commit", "--quiet", "-m", "direction"],
            ):
                subprocess.run(["git", "-C", str(repository), *command], check=True)
            homes = {
                "codex": ("CODEX_HOME", "AGENTS.md"),
                "claude": ("CLAUDE_CONFIG_DIR", "CLAUDE.md"),
                "grok": ("GROK_HOME", "AGENTS.md"),
                "opencode": ("OPENCODE_CONFIG_DIR", "AGENTS.md"),
            }
            environment = {
                key: value for key, value in os.environ.items()
                if key not in {"AGENTSMD_HOST", "GROK_HOOK_NAME", "XDG_CONFIG_HOME"}
            }
            for host, (variable, name) in homes.items():
                home = base / f"{host}-home"
                home.mkdir()
                (home / name).symlink_to(source)
                environment[variable] = str(home)
            for host, (unit, limit) in self.HOOK_LIMITS.items():
                with self.subTest(host=host):
                    grok = host == "grok"
                    event = {
                        "cwd": str(repository),
                        "session_id": f"{host}-session",
                        "hook_event_name": "PreToolUse" if grok else "SessionStart",
                        "tool_name": "read_file",
                        "tool_input": {},
                    }
                    host_environment = dict(
                        environment,
                        AGENTSMD_PROJECT_DIRECTION_DATA=str(base / f"{host}-cache"),
                    )
                    if grok:
                        host_environment["GROK_HOOK_NAME"] = "agentsmd"
                    result = subprocess.run(
                        [str(ROOT / "bin/project-direction"), "hook", "--host", host],
                        input=json.dumps(event), text=True, capture_output=True,
                        env=host_environment, check=True,
                    )
                    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                    header = json.loads(context.splitlines()[1])
                    # Both files sit at their caps and still arrive in full.
                    self.assertEqual(header["status"], "ready")
                    self.assertEqual(header["budgets"]["direction"]["characters"], 1500)
                    self.assertEqual(header["budgets"]["preferences"]["characters"], 4000)
                    self.assertIn(prose.strip(), context)
                    size = (
                        -(-len(context.encode("utf-8")) // 4)
                        if unit == "tokens"
                        else len(context)
                    )
                    # At least 10% of the host limit stays free for other hooks.
                    self.assertLessEqual(size, limit * 0.9, f"{size} {unit}")

    def test_operations_pointer_hook_is_registered_for_claude_code_only(self) -> None:
        # Codex and Grok load the operations Skill themselves; Claude Code and
        # OpenCode get the pointer (#174).
        claude = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(claude["hooks"], "./hooks/claude.json")
        for manifest in (".codex-plugin/plugin.json", ".grok-plugin/plugin.json"):
            with self.subTest(manifest=manifest):
                self.assertNotIn("hooks", json.loads((ROOT / manifest).read_text()))
        self.assertNotIn("operations-routing", (ROOT / "hooks/hooks.json").read_text())
        hooks = json.loads((ROOT / "hooks/claude.json").read_text())["hooks"]
        self.assertEqual(list(hooks), ["SessionStart"])
        self.assertEqual(len(hooks["SessionStart"]), 1)
        entry = hooks["SessionStart"][0]
        self.assertEqual(entry["matcher"], "^(startup|resume|clear|compact)$")
        self.assertEqual(
            [handler["command"] for handler in entry["hooks"]],
            ['"${CLAUDE_PLUGIN_ROOT}/bin/operations-routing"'],
        )
        plugin = (ROOT / "opencode/agentsmd-project-direction.js").read_text()
        self.assertIn('const ROUTING = ["bin", "operations-routing"];', plugin)

    def test_operations_pointer_fits_the_headroom_left_for_other_hooks(self) -> None:
        result = subprocess.run(
            [str(ROOT / "bin/operations-routing")],
            capture_output=True,
            text=True,
            check=True,
        )
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        skill = (ROOT / "skills/operations/SKILL.md").resolve()
        self.assertIn(f"use the `operations` Skill (or read {skill})", context)
        for moment in ("start of every task", "researching", "an experiment", "reproducing a defect",
                       "first file edit", "commit", "GitHub Issue", "pull request"):
            self.assertIn(moment, context)
        # The Project Direction hook keeps 10% of each host limit free for
        # other hooks; the pointer must fit there, so on OpenCode, where both
        # reach one system prompt, the combined output stays under the limit.
        for host, (unit, limit) in self.HOOK_LIMITS.items():
            with self.subTest(host=host):
                size = (
                    -(-len(context.encode("utf-8")) // 4)
                    if unit == "tokens"
                    else len(context)
                )
                self.assertLessEqual(size, limit * 0.1, f"{size} {unit}")

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
            path.parent.name for path in (ROOT / "skills").rglob("SKILL.md")
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
            "tests/fixtures/delivery_profiles/valid-minimal.json",
            "tests/fixtures/delivery_profiles/invalid-artifact.json",
            "tests/fixtures/delivery_profiles/invalid-canonical-truth.json",
            "tests/fixtures/delivery_profiles/invalid-command.json",
            "tests/fixtures/delivery_profiles/invalid-empty.json",
            "tests/fixtures/delivery_continuation_cases.json",
            "tests/fixtures/delivery_finalization_cases.json",
            "tests/fixtures/repository_reconciliation_approval.json",
            "tests/fixtures/repository_reconciliation_cases.json",
            "tests/repository_reconciliation_validator.py",
            "tests/test_delivery_continuation_contract.py",
            "tests/test_repository_reconciliation_contract.py",
            "tests/fixtures/specify_workflow_cases.json",

            "skills/operations/workflows/elon-method/evals/procedure-selection.json",
            "skills/operations/workflows/elon-method/references/first-principles.md",
            "skills/operations/workflows/elon-method/references/idiot-index.md",
            "skills/operations/workflows/elon-method/references/current-constraint.md",
            "skills/operations/workflows/elon-method/references/algorithm.md",
            "skills/operations/workflows/elon-method/references/marketplace-project-record-regression.md",

            ".toolboxmd/delivery.json",
            "schemas/delivery-v1.schema.json",
            "skills/operations/workflows/project-direction/references/file-contracts.md",
            "skills/operations/workflows/project-direction/templates/MISSION.md",
            "skills/operations/workflows/project-direction/templates/OBJECTIVE.md",
            "skills/operations/workflows/project-direction/templates/VISION.md",
            "skills/operations/workflows/prototype/LOGIC.md",
            "skills/operations/workflows/prototype/UI.md",
            "skills/operations/workflows/domain-modeling/ADR-FORMAT.md",
            "skills/operations/workflows/domain-modeling/GLOSSARY-FORMAT.md",
            "skills/operations/workflows/version-control/references/bump-rules.md",
            "skills/operations/workflows/version-control/references/project-policy.md",
            "skills/operations/workflows/writing-for-agents/SKILL-MECHANICS.md",
        }
        missing = [relative for relative in expected if not (ROOT / relative).is_file()]
        self.assertEqual(missing, [])

    def test_retirement_contract_and_proof_ship_together(self) -> None:
        agents = " ".join(read_text("skills/operations/references/finalization.md").split())
        glossary = read_text("GLOSSARY.md")
        cases = json.loads(read_text("tests/fixtures/delivery_finalization_cases.json"))
        self.assertIn("Check every temporary checkout for removal", agents)
        self.assertIn("**Temporary checkout**:", glossary)
        self.assertIn("required-deployment-pending", {c["id"] for c in cases["terminal-cases"]})
        self.assertTrue({"required-evidence-durable", "dependency-resolved", "process-resolved"}
                        <= {c["id"] for c in cases["resource-cases"]})

    def test_runtime_files_are_packaged_and_executable(self) -> None:
        for relative in (
            "bin/agentsmd-global-instructions",
            "bin/agentsmd-opencode",
            "bin/delivery-profile",
            "bin/project-direction",
            "hooks/hooks.json",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())
        for relative in (
            "bin/agentsmd-global-instructions",
            "bin/agentsmd-opencode",
            "bin/delivery-profile",
            "bin/project-direction",
        ):
            with self.subTest(executable=relative):
                self.assertTrue(os.access(ROOT / relative, os.X_OK))

    def test_packaged_project_direction_guard_has_matching_contracts(self) -> None:
        loader = read_text("bin/project-direction")
        agents = read_text("skills/operations/workflows/project-direction/references/context.md")
        skill = read_text("skills/operations/workflows/project-direction/index.md")

        for required in (
            "potentially_stale",
            'upstream',
            "ahead/behind",
        ):
            with self.subTest(required=required):
                self.assertIn(required, loader)
                self.assertIn(required, agents)
        self.assertIn('[context](references/context.md)', skill)

    def test_ticket_entrypoints_resolve_one_owner_after_install_relocation(self) -> None:
        # Exercise the real published relative links with an unrelated install root.
        # Existing workflow metadata and transition fixtures cover invocation/gates.
        owner = Path("skills/operations/workflows/to-tickets/references/ticket-decomposition.md")
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "plugins/cache/agentsmd/version"
            shutil.copytree(ROOT / "skills", installed / "skills")
            resolved = []
            for name in ("to-spec", "to-tickets"):
                entry = installed / "skills/operations/workflows" / name / "index.md"
                links = re.findall(r"\[ticket decomposition\]\(([^)]+)\)", entry.read_text())
                self.assertEqual(len(links), 1, name)
                target = (entry.parent / links[0]).resolve(strict=True)
                self.assertEqual(target, (installed / owner).resolve(strict=True))
                self.assertEqual(target.read_bytes(), (ROOT / owner).read_bytes())
                resolved.append(target)
            self.assertEqual(resolved[0], resolved[1])
            # The owner is guidance, not another independently invoked Skill.
            self.assertFalse(resolved[0].read_text().startswith("---\n"))

    def test_matt_adaptations_declare_origin_and_licence(self) -> None:
        for name in MATT_ADAPTATIONS:
            metadata = frontmatter(f"skills/operations/workflows/{name}/index.md")
            with self.subTest(skill=name):
                self.assertIn("license: MIT", metadata)
                self.assertIn("owner: toolboxmd", metadata)
                self.assertIn("origin: mattpocock/skills", metadata)
                self.assertIn(
                    "source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76",
                    metadata,
                )

    def test_third_party_licences_are_packaged(self) -> None:
        matt = read_text("LICENSES/mattpocock-skills-MIT.txt")
        self.assertIn("Copyright (c) 2026 Matt Pocock", matt)

    def test_catalogue_covers_every_lifecycle(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        for name in ACTIVE_SKILLS | INACTIVE_SKILLS | MATT_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(f"`{name}`", catalogue)
        for lifecycle in ("Active", "Deferred", "Retired", "Upstream reference"):
            self.assertIn(lifecycle, catalogue)
        self.assertIn("6654f6b60cd9d5be8b54c6fafe44346dabeb3b76", catalogue)

    def test_catalogue_owns_project_direction_as_native_active_skill(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        row = next(
            line
            for line in catalogue.splitlines()
            if line.startswith("| `project-direction`")
        )
        self.assertIn("AgentsMD-native; this release commit", row)
        self.assertIn("Procedure", row)
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
        self.assertIn("Retired", row)
        self.assertIn("MIT", row)
        self.assertIn("five-step Algorithm", row)

    def test_catalogue_owns_delivery_profile_as_native_active_skill(self) -> None:
        catalogue = read_text("SKILL_CATALOGUE.md")
        row = next(
            line
            for line in catalogue.splitlines()
            if line.startswith("| `delivery-profile`")
        )
        self.assertIn("AgentsMD-native; this release commit", row)
        self.assertIn("Procedure", row)
        self.assertIn("MIT", row)
        self.assertIn("Delivery System", row)

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
                if name in {
                    "algorithm",
                    "delivery-profile",
                    "elon-method",
                    "operations",
                    "project-direction",
                    "version-control",
                }:
                    self.assertIn("this release commit", row)
                elif name in {"software-design", "diagnosis", "code-review",
                              "project-verification", "reflection", "technical-writing"}:
                    self.assertIn("pstack pin", row)
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
            "Delivery System",
            "Delivery Profile",
            "Merge Unit",
            "Implementation Slice",
            "Elon method",
            "Algorithm",
            "Current constraint",
            "Idiot index",
        ):
            with self.subTest(term=term):
                self.assertIn(f"**{term}**", glossary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
