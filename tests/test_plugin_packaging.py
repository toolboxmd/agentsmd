#!/usr/bin/env python3
"""agentsmd is a three-host plugin in marketplace toolboxmd, not agentsmd-local."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


class PluginPackagingTests(unittest.TestCase):
    def test_three_host_identity(self) -> None:
        manifests = {
            "codex": json.loads((ROOT / ".codex-plugin/plugin.json").read_text()),
            "claude": json.loads((ROOT / ".claude-plugin/plugin.json").read_text()),
            "grok": json.loads((ROOT / ".grok-plugin/plugin.json").read_text()),
        }
        for label, manifest in manifests.items():
            self.assertEqual(manifest["name"], "agentsmd", label)
            self.assertEqual(manifest["version"], VERSION, label)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
