"""Operating module ownership, routing and real package path resolution."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/operations/SKILL.md"
MODULES = {
    "implementation", "orchestration", "verification", "delivery",
    "finalization", "repository-setup", "reconciliation",
}


def words(path):
    return " ".join(path.read_text().split())


def links(path):
    return re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text())


class OperationsContractTests(unittest.TestCase):
    def test_one_model_invoked_entry_routes_every_module(self):
        text = SKILL.read_text()
        self.assertIn("name: operations", text)
        self.assertNotIn("disable-model-invocation: true", text)
        self.assertIn("allow_implicit_invocation: true", (SKILL.parent / "agents/openai.yaml").read_text())
        destinations = set(links(SKILL))
        self.assertEqual(destinations, {f"references/{name}.md" for name in MODULES})
        for row in text.splitlines():
            if "references/" in row:
                self.assertGreater(len(row.split("|")[1].strip()), 10)
        self.assertIn("load only its applicable linked reference", words(ROOT / "AGENTS.md"))
        self.assertIn("Reuse unchanged reference contents already in context", words(SKILL))
        self.assertIn("blocks only the dependent action", words(SKILL))

    def test_installed_package_links_resolve_from_an_arbitrary_project_cwd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "installed/agentsmd"
            shutil.copytree(ROOT / "skills/operations", package / "skills/operations")
            shutil.copytree(ROOT / "docs", package / "docs")
            cwd = root / "unrelated-project"
            cwd.mkdir()
            # Same pathname in the project must never become a module source.
            (cwd / "skills/operations/references").mkdir(parents=True)
            (cwd / "skills/operations/references/verification.md").write_text("wrong source")
            entry = package / "skills/operations/SKILL.md"
            for document in [entry, *entry.parent.glob("references/*.md")]:
                for link in links(document):
                    destination = (document.parent / link).resolve()
                    self.assertTrue(destination.is_file(), (document, link))
                    self.assertTrue(destination.is_relative_to(package.resolve()))
            result = subprocess.run(
                ["python3", "-c", "from pathlib import Path; import sys; p=Path(sys.argv[1]); print((p.parent/'references/verification.md').read_text())", str(entry)],
                cwd=cwd, text=True, capture_output=True, check=True,
            )
            self.assertIn("independent Codex review", result.stdout)
            self.assertNotIn("wrong source", result.stdout)

    def test_global_installer_resolves_canonical_modules_through_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "canonical"
            source.mkdir()
            shutil.copy2(ROOT / "AGENTS.md", source / "AGENTS.md")
            shutil.copytree(ROOT / "skills/operations", source / "skills/operations")
            target = root / "global/AGENTS.md"
            cwd = root / "unrelated-project"
            cwd.mkdir()
            result = subprocess.run(
                [str(ROOT / "bin/agentsmd-global-instructions"), "install", "--source", str(source / "AGENTS.md"), "--target", str(target)],
                cwd=cwd, text=True, capture_output=True, check=True,
            )
            report = json.loads(result.stdout)
            self.assertEqual(report["action"], "installed")
            entry = target.resolve().parent / "skills/operations/SKILL.md"
            self.assertEqual(entry.read_bytes(), SKILL.read_bytes())
            self.assertFalse((target.parent / "skills/operations/SKILL.md").exists())
            for link in links(entry):
                self.assertTrue((entry.parent / link).is_file())
            self.assertIn("same revision", words(ROOT / "AGENTS.md"))
            self.assertIn("older incompatible module", words(ROOT / "AGENTS.md"))

    def test_direct_work_boundary_keeps_cost_judgment_and_proof(self):
        core = words(ROOT / "AGENTS.md")
        for clause in (
            "Make the smallest possible change to achieve the wanted result.",
            "Delegate when it reduces total work or provides required independence.",
            "Create no Issue or worker purely for ceremony",
            "Ownership also covers shared services, databases, ports and deployment targets",
            "installed `model-routing` Skill",
            "stop only the affected dispatch",
        ):
            self.assertIn(clause, core)
        verification = words(SKILL.parent / "references/verification.md")
        self.assertIn('exact user-approved replacement, matching expected-text assertions, and required version bookkeeping', verification)
        self.assertIn("self-review and relevant checks still apply", verification)
        self.assertIn("independent Codex review of its exact SHA", verification)
        self.assertNotIn("Codex Luna", verification)
        self.assertNotIn("maximum reasoning", verification)

    def test_context_reuse_and_proof_ownership_preserve_freshness(self):
        core = words(ROOT / "AGENTS.md")
        self.assertIn('Honor scoped local opt-outs', core)
        self.assertIn("Reuse unchanged full contents on follow-ups; reload after change or context loss", core)
        context = words(ROOT / "skills/project-direction/references/context.md")
        self.assertIn("Reuse unchanged full contents", context)
        self.assertIn("current remote state matters", context)
        proof = words(SKILL.parent / "references/verification.md")
        for clause in (
            "Assign each check an owner",
            "relevant environment, and input assumptions are unchanged",
            "Ordinary changed-scope checks remain feedback",
            "Unsupported scope stops with a reason",
            "independent review and fresh external-state checks",
        ):
            self.assertIn(clause, proof)
        coordination = words(SKILL.parent / "references/orchestration.md")
        self.assertIn("one canonical durable handoff on the owning Issue, linked from PR/consumers", coordination)
        self.assertIn("coordinator independently verifies Git/GitHub state", coordination)
        self.assertNotIn("Start each unblocked implementation Issue in a fresh context", core)

    def test_final_approval_separates_internal_and_intended_base_authority(self):
        core = words(ROOT / "AGENTS.md")
        self.assertIn("Use one final approval PR per outcome; decompose through reviewed component PRs", core)
        self.assertIn("Final PR merges into the intended base require explicit human approval", core)
        orchestration = words(SKILL.parent / "references/orchestration.md")
        for clause in (
            "integration branch from the intended base",
            'target components there, stack dependencies, and retarget in merge order',
            "Small tasks use one ordinary PR",
            "local microfix exceptions remain",
            'exact-head/current-base checks and independent [review](verification.md)',
            'unreleased internal pushes/merges without release, publication, deployment, or protected impact',
            "never bypass checks",
            'cumulative diff, component map, outcome acceptance, combined proof',
            'independent exact-candidate review',
            "Component checks alone are insufficient",
            "Other Human Gates remain",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, orchestration)

    def test_component_integration_cannot_complete_delivery_or_versioning(self):
        orchestration = words(SKILL.parent / "references/orchestration.md")
        for clause in (
            'Component Issues stay open with integration evidence',
            "only the final PR carries closing linkage",
            'After authorized delivery',
            '[finalize](finalization.md)',
        ):
            self.assertIn(clause, orchestration)
        self.assertIn('Internal integration and open/review-ready PRs are not terminal', words(SKILL.parent / "references/finalization.md"))
        delivery = words(SKILL.parent / "references/delivery.md")
        self.assertIn("Components are unreleased checkpoints", delivery)
        self.assertIn("prepare the single version transition on the final approval PR", delivery)
        versioning = words(ROOT / "skills/version-control/SKILL.md")
        self.assertIn("Internal component checkpoint", versioning)
        self.assertIn("defer versioning to the final approval PR", versioning)

    def test_moved_procedures_have_one_owner(self):
        markers = {
            "finalization": 'Begin only after review',
            "reconciliation": "The approval record carries a canonical SHA-256",
            "repository-setup": "one complete setup bundle",
            "verification": 'exact user-approved replacement, matching expected-text assertions',
            "orchestration": "Keep a dependent Issue natively blocked",
            "delivery": "Every deployable artifact is built once",
        }
        documents = [ROOT / "AGENTS.md", *SKILL.parent.glob("references/*.md")]
        for owner, marker in markers.items():
            found = [document for document in documents if marker in words(document)]
            self.assertEqual(found, [SKILL.parent / f"references/{owner}.md"])
        record = json.loads((ROOT / ".toolboxmd/project.json").read_text())
        self.assertIn("skills/operations/SKILL.md", record["factSources"]["skills"])
        for name in MODULES:
            self.assertIn(f"skills/operations/references/{name}.md", record["factSources"]["requirements"])


if __name__ == "__main__":
    unittest.main()
