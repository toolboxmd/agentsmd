"""Pinned adaptation coverage and real installed reference resolution.

These checks prove package structure, not agent behavior or historical reading.
The same suite can run from an extracted release archive without upstream access.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b42effe0aa50f59c693d7e2924714e015e00bf7c"
NEW_SKILLS = {
    "software-design", "diagnosis", "code-review", "project-verification",
    "reflection", "technical-writing",
}


def relative_links(document: Path) -> list[str]:
    # Fenced examples describe generated artifacts and are not package links.
    prose = re.sub(r"^(`{3,}|~{3,}).*?^\1[^\n]*$", "",
                   document.read_text(), flags=re.MULTILINE | re.DOTALL)
    links = re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", prose)
    links += re.findall(r"^\[[^]]+\]:\s+(\S+)", prose, flags=re.MULTILINE)
    result = []
    for link in links:
        parsed = urlsplit(link.strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        result.append(unquote(parsed.path))
    return result


class PstackPackagingTests(unittest.TestCase):
    def setUp(self):
        self.lock = json.loads((ROOT / "provenance/pstack.lock.json").read_text())

    def test_pin_inventory_and_license_identity(self):
        self.assertEqual(self.lock["source"]["revision"], REVISION)
        self.assertEqual(self.lock["source"]["version"], "0.15.3")
        inventory = self.lock["inventory"]
        paths = [item["path"] for item in inventory]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(len(paths), 158)
        for item in inventory:
            self.assertRegex(item["gitBlob"], r"^[0-9a-f]{40}$")
            self.assertRegex(item["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreaterEqual(item["bytes"], 0)
            self.assertIn(item["encoding"], {"utf-8", "binary"})
            self.assertFalse(Path(item["path"]).is_absolute())
            self.assertNotIn("..", Path(item["path"]).parts)
        license_record = self.lock["license"]
        payload = (ROOT / license_record["destination"]).read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(digest, license_record["sha256"])
        self.assertEqual(digest, next(x["sha256"] for x in inventory
                                     if x["path"] == license_record["source"]))
        self.assertIn(b"Copyright (c) 2026 Lauren Tan", payload)

    def test_every_source_skill_and_playbook_has_one_decision(self):
        paths = {item["path"] for item in self.lock["inventory"]}
        skills = {p for p in paths if p.endswith("/SKILL.md")}
        playbooks = {p for p in paths if p.startswith("skills/poteto-mode/playbooks/")}
        self.assertEqual(len(skills), 50)
        self.assertEqual(len(playbooks), 23)
        decisions = self.lock["decisions"]
        self.assertEqual(len(decisions), len({d["source"] for d in decisions}))
        self.assertEqual({d["source"] for d in decisions if d["kind"] == "skill"}, skills)
        self.assertEqual({d["source"] for d in decisions if d["kind"] == "playbook"}, playbooks)
        for decision in decisions:
            self.assertTrue(decision["disposition"].strip())
            self.assertTrue(decision["rationale"].strip())
            self.assertTrue(decision["destinations"])
        for decision in [*decisions, *self.lock["supportingDecisions"]]:
            for destination in decision["destinations"]:
                target = (ROOT / destination).resolve(strict=True)
                self.assertTrue(target.is_relative_to(ROOT))
                self.assertTrue(target.is_file())
        for group in self.lock["supportingDecisions"]:
            self.assertTrue(any(p.startswith(group["sourcePrefix"]) for p in paths))

    def test_report_pinned_links_resolve_in_source_inventory(self):
        report = (ROOT / self.lock["report"]).read_text()
        prefix = f"https://github.com/cursor/plugins/blob/{REVISION}/pstack/"
        sources = re.findall(re.escape(prefix) + r"([^\s)#]+)", report)
        paths = {item["path"] for item in self.lock["inventory"]}
        self.assertTrue(sources)
        self.assertEqual(set(sources) - paths, set())
        self.assertTrue({d["source"] for d in self.lock["decisions"]} <= set(sources))

    def test_procedures_keep_provenance_without_discovery_entries(self):
        record = json.loads((ROOT / ".toolboxmd/project.json").read_text())
        discovered = {p.relative_to(ROOT).as_posix() for p in (ROOT / "skills").rglob("SKILL.md")}
        self.assertEqual(discovered, {"skills/operations/SKILL.md"})
        self.assertEqual(set(record["factSources"]["skills"]), discovered)
        catalogue = (ROOT / "SKILL_CATALOGUE.md").read_text()
        for name in NEW_SKILLS:
            folder = ROOT / "skills/operations/workflows" / name
            metadata = (folder / "index.md").read_text().split("---\n", 2)[1]
            self.assertIn(f"source-revision: {REVISION}", metadata)
            self.assertIn("license: MIT", metadata)
            self.assertIn(f"| `{name}` |", catalogue)
            self.assertFalse((folder / "SKILL.md").exists())
            self.assertFalse((folder / "agents").exists())

    def test_all_skill_reference_graphs_survive_package_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            # Copy only the role-kit unit, not the package. No external docs may rescue links.
            bundle = (Path(temporary) / "isolated-kit/skills/operations").resolve()
            shutil.copytree(ROOT / "skills/operations", bundle)
            decoy = Path(temporary) / "unrelated-project/skills/operations/references"
            decoy.mkdir(parents=True)
            (decoy / "verification.md").write_text("wrong source")
            pending = [bundle / "SKILL.md"]
            visited = set()
            while pending:
                document = pending.pop().resolve()
                if document in visited:
                    continue
                visited.add(document)
                for link in relative_links(document):
                    target = (document.parent / link).resolve()
                    self.assertTrue(target.is_relative_to(bundle), (document, link))
                    self.assertTrue(target.exists(), (document, link))
                    if target.is_file() and target.suffix == ".md":
                        pending.append(target)
            for reference in bundle.rglob("*.md"):
                self.assertIn(reference.resolve(), visited, reference)


if __name__ == "__main__":
    unittest.main()
