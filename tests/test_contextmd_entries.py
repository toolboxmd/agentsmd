#!/usr/bin/env python3
"""ContextMD entries in contextmd/ are pointer rules to procedures that exist (#215)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "contextmd"
# ContextMD rejects larger entries; its deny must fit a harness preview.
MAX_ENTRY_BYTES = 1800


def front_matter(path: Path) -> tuple[dict[str, list[str]], str]:
    match = re.match(r"---\n(.*?)\n---\n(.*)", path.read_text(encoding="utf-8"), re.S)
    if not match:
        raise AssertionError(f"{path}: no front matter")
    fields: dict[str, list[str]] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), []).append(value.strip())
    return fields, match.group(2).strip()


class ContextmdEntries(unittest.TestCase):
    def entries(self) -> list[Path]:
        return [p for p in sorted(STORE.glob("*.md")) if p.name.lower() != "readme.md"]

    def test_the_store_has_entries_with_unique_ids(self):
        ids = [front_matter(p)[0].get("id", [p.stem])[0] for p in self.entries()]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_entry_is_a_pointer_rule_to_a_procedure_in_this_repository(self):
        for path in self.entries():
            fields, body = front_matter(path)
            with self.subTest(entry=path.name):
                self.assertEqual(fields.get("must-know-before"), ["true"])
                self.assertTrue(fields.get("command"))
                self.assertEqual(len(fields.get("target", [])), 1)
                target = fields["target"][0]
                self.assertFalse(target.startswith(("/", "~")), "a relative target resolves in every clone")
                resolved = (path.parent / target).resolve()
                self.assertTrue(resolved.is_relative_to((ROOT / "skills").resolve()))
                self.assertTrue(resolved.is_file(), f"{target} does not exist")
                self.assertTrue(body)
                self.assertLessEqual(len(path.read_bytes()), MAX_ENTRY_BYTES)


if __name__ == "__main__":
    unittest.main()
