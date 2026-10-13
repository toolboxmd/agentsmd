#!/usr/bin/env python3
"""ContextMD entries in contextmd/ are pointer rules to procedures that exist (#215)."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "contextmd"
# ContextMD's loaders skip an entry with any other field, so its gate would vanish.
FIELDS = {"id", "command", "path", "error", "must-know-before", "target"}
# ContextMD rejects larger entries; its deny must fit a harness preview.
MAX_ENTRY_BYTES = 1800


def problems(path: Path, skills: Path = ROOT / "skills") -> list[str]:
    """Why ContextMD would skip this entry or its deny could never lift; empty when valid."""
    match = re.match(r"---\n(.*?)\n---\n(.*)", path.read_text(encoding="utf-8"), re.S)
    if not match:
        return ["no front matter"]
    fields: dict[str, list[str]] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), []).append(value.strip())
    found = []
    found += [f"unknown field {k!r}" for k in sorted(set(fields) - FIELDS)]
    if fields.get("must-know-before") != ["true"]:
        found.append("not must-know-before")
    commands = fields.get("command", [])
    if not commands or not all(c.split() for c in commands):
        found.append("missing or empty command")
    targets = fields.get("target", [])
    if len(targets) != 1 or not targets[0]:
        found.append("needs one target")
    elif targets[0].startswith(("/", "~")):
        found.append("target must be relative to resolve in every clone")
    else:
        resolved = (path.parent / targets[0]).resolve()
        if not resolved.is_relative_to(skills.resolve()) or not resolved.is_file():
            found.append(f"target {targets[0]} is not a file under skills/")
    if not match.group(2).strip():
        found.append("empty body")
    if len(path.read_bytes()) > MAX_ENTRY_BYTES:
        found.append("over the size limit")
    return found


def entries(store: Path = STORE) -> list[Path]:
    return [p for p in sorted(store.glob("*.md")) if p.name.lower() != "readme.md"]


class ContextmdEntries(unittest.TestCase):
    def test_the_store_has_entries_with_unique_ids(self):
        ids = []
        for path in entries():
            found = re.search(r"^id:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
            ids.append(found.group(1) if found else path.stem)
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_entry_is_a_pointer_rule_to_a_procedure_in_this_repository(self):
        for path in entries():
            with self.subTest(entry=path.name):
                self.assertEqual(problems(path), [])

    def test_entries_the_loaders_would_skip_are_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skills").mkdir()
            (root / "skills/proc.md").write_text("x")
            store = root / "contextmd"
            store.mkdir()
            good = "id: x\ncommand: git commit\nmust-know-before: true\ntarget: ../skills/proc.md"
            cases = {
                "good": (good, []),
                "empty-command": (good.replace("command: git commit", "command:"),
                                  ["missing or empty command"]),
                "unknown-field": (good + "\nunknown: value", ["unknown field 'unknown'"]),
                "absolute-target": (good.replace("../skills/proc.md", "/skills/proc.md"),
                                    ["target must be relative to resolve in every clone"]),
                "missing-target": (good.replace("proc.md", "gone.md"),
                                   ["target ../skills/gone.md is not a file under skills/"]),
                "not-must-know": (good.replace("true", "false"), ["not must-know-before"]),
            }
            for name, (front, expected) in cases.items():
                path = store / f"{name}.md"
                path.write_text(f"---\n{front}\n---\nRule.\n")
                with self.subTest(case=name):
                    self.assertEqual(problems(path, root / "skills"), expected)


if __name__ == "__main__":
    unittest.main()
