#!/usr/bin/env python3
"""ContextMD Cue entries in contextmd-cue/ point to procedures that exist and keep their trained texts."""

from __future__ import annotations

import hashlib
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "contextmd-cue"
EXACT_KEY_STORE = ROOT / "contextmd"
# ContextMD's Cue loader skips an entry with any other field.
FIELDS = {"id", "name", "applies", "target"}
MAX_BODY_BYTES = 1800
# The deployed Cue adapter (q4b-cloud step-64) was trained on these exact "<name>: <applies>" texts.
# Change one only together with retraining (toolboxmd/contextmd#4), then update its hash here.
TRAINED = {
    "agentsmd-grilling": "d44af593c68166aaaee69013a821fa532fc6096b3f763c8596c77d996a5b155c",
    "agentsmd-research": "e4509a1f68cd32b90860f689735c3ffaa2c4f752aa94f579c69e7a8fc8abe0cd",
    "agentsmd-prototype": "59b4720e95acc6bcac67580b0ee13381fda1ea27c9937ddfecc2b65add4a33d9",
    "agentsmd-reflection": "60866d7b0ec4afdaf60782692ca69d5227a997c68f6c805d99573a2c79f3a027",
    "agentsmd-finalization": "ca7dd7baa92af921b7e3b5733e180cd96bcea63a30be5e7dd4ef4f422b17f4f7",
    "agentsmd-specify": "502efd2f7b4d34addbb234eeca8979258f5ed80a1e507f79c611af316c3de5bf",
    "agentsmd-project-direction": "6447bc0153960f6c8f70906ec5bc9c038b437df29a6b8214c67fcae2ebe84657",
    "agentsmd-reconciliation": "dc7f8724a1713054294530de85e9ec478a33ea8ec08d461af0862de15d778bcb",
    "agentsmd-wayfinder": "cd6cb28cf198a9694f898bcbecfdfeff904c9f446c12486c03656c1064bf3fc3",
}


def parse(path: Path) -> tuple[dict[str, list[str]], str] | None:
    match = re.match(r"---\n(.*?)\n---\n(.*)", path.read_text(encoding="utf-8"), re.S)
    if not match:
        return None
    fields: dict[str, list[str]] = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), []).append(value.strip())
    return fields, match.group(2).strip()


def problems(path: Path, skills: Path = ROOT / "skills") -> list[str]:
    """Why ContextMD's Cue loader would skip this entry or its pointer would lead nowhere; empty when valid."""
    parsed = parse(path)
    if parsed is None:
        return ["no front matter"]
    fields, body = parsed
    found = [f"unknown field {k!r}" for k in sorted(set(fields) - FIELDS)]
    for key in ("id", "name", "applies", "target"):
        values = fields.get(key, [])
        if len(values) != 1 or not values[0]:
            found.append(f"needs one {key}")
    targets = fields.get("target", [])
    if len(targets) == 1 and targets[0]:
        if targets[0].startswith(("/", "~")):
            found.append("target must be relative to resolve in every clone")
        else:
            resolved = (path.parent / targets[0]).resolve()
            if not resolved.is_relative_to(skills.resolve()) or not resolved.is_file():
                found.append(f"target {targets[0]} is not a file under skills/")
    if not body:
        found.append("empty body")
    elif len(body.encode()) > MAX_BODY_BYTES:
        found.append("body over the size limit")
    return found


def entries(store: Path = STORE) -> list[Path]:
    return [p for p in sorted(store.glob("*.md")) if p.name.lower() != "readme.md"]


class ContextmdCueEntries(unittest.TestCase):
    def test_each_entry_loads_and_points_to_a_procedure_in_this_repository(self):
        self.assertTrue(entries())
        for path in entries():
            with self.subTest(entry=path.name):
                self.assertEqual(problems(path), [])

    def test_the_trained_entries_keep_their_trained_texts(self):
        texts = {}
        for path in entries():
            fields, _ = parse(path)
            texts[fields["id"][0]] = f"{fields['name'][0]}: {fields['applies'][0]}"
        self.assertEqual(len(texts), len(entries()), "ids must be unique")
        for entry_id, digest in TRAINED.items():
            with self.subTest(entry=entry_id):
                self.assertIn(entry_id, texts)
                self.assertEqual(hashlib.sha256(texts[entry_id].encode()).hexdigest(), digest)

    def test_the_cue_folder_is_not_inside_the_exact_key_store(self):
        # ContextMD's loaders read their folders recursively and reject each other's entries.
        self.assertFalse(STORE.resolve().is_relative_to(EXACT_KEY_STORE.resolve()))
        self.assertFalse(EXACT_KEY_STORE.resolve().is_relative_to(STORE.resolve()))

    def test_entries_the_loader_would_skip_are_caught(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skills").mkdir()
            (root / "skills/proc.md").write_text("x")
            store = root / "contextmd-cue"
            store.mkdir()
            good = "id: x\nname: X\napplies: When x.\ntarget: ../skills/proc.md"
            cases = {
                "good": (good, []),
                "exact-key-field": (good + "\ncommand: git commit", ["unknown field 'command'"]),
                "no-applies": (good.replace("applies: When x.", "applies:"), ["needs one applies"]),
                "absolute-target": (good.replace("../skills/proc.md", "/skills/proc.md"),
                                    ["target must be relative to resolve in every clone"]),
                "missing-target": (good.replace("proc.md", "gone.md"),
                                   ["target ../skills/gone.md is not a file under skills/"]),
            }
            for name, (front, expected) in cases.items():
                path = store / f"{name}.md"
                path.write_text(f"---\n{front}\n---\nFollow it.\n")
                with self.subTest(case=name):
                    self.assertEqual(problems(path, root / "skills"), expected)


if __name__ == "__main__":
    unittest.main()
