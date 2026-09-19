#!/usr/bin/env python3
"""Node seam proof that the OpenCode plugin transports the loader payload."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "opencode/agentsmd-project-direction.js"
LOADER = ROOT / "bin/project-direction"
NODE = shutil.which("node")
LOG_PREFIX = "agentsmd-project-direction:"
DRIVER = """
import { pathToFileURL } from "node:url";

const [modulePath, directory, calls] = process.argv.slice(2);
const module = await import(pathToFileURL(modulePath).href);
const hooks = await module.default({ directory, worktree: directory });
const output = { system: [] };
for (let call = 0; call < Number(calls); call += 1) {
  await hooks["experimental.chat.system.transform"](
    { sessionID: "ses_fixture", model: { id: "fixture" } },
    output,
  );
}
process.stdout.write(JSON.stringify({
  system: output.system,
  supported: module.default.supportedOpenCodeVersion,
  exports: Object.fromEntries(
    Object.entries(module).map(([name, value]) => [name, typeof value]),
  ),
}));
"""


@unittest.skipIf(NODE is None, "node is not on PATH; the OpenCode plugin seam needs it")
class OpenCodePluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.driver = self.base / "driver.mjs"
        self.driver.write_text(DRIVER, encoding="utf-8")
        self.outside = self.base / "outside"
        self.outside.mkdir()
        self.repository = self.base / "repository"
        self.repository.mkdir()
        for name, content in (
            ("VISION.md", "# Vision\n\nMake agent work purposeful.\n"),
            ("MISSION.md", "# Mission\n\nTurn direction into delivery.\n"),
            ("OBJECTIVE.md", "# Objective\n\nShip Project Direction now.\n"),
        ):
            (self.repository / name).write_text(content, encoding="utf-8")
        self.git("init", "--quiet", ".")
        self.git("config", "user.name", "AgentsMD Tests")
        self.git("config", "user.email", "agentsmd-tests@example.invalid")
        self.git("add", "VISION.md", "MISSION.md", "OBJECTIVE.md")
        self.git("commit", "--quiet", "-m", "Add Project Direction")
        config = self.base / "opencode"
        config.mkdir()
        source = self.base / "release/AGENTS.md"
        source.parent.mkdir()
        source.write_text("# Agents\n\nCanonical contract fixture.\n", encoding="utf-8")
        (config / "AGENTS.md").symlink_to(source)
        self.environment = {
            **os.environ,
            "HOME": str(self.base / "home"),
            "XDG_CONFIG_HOME": str(self.base / "xdg"),
            "OPENCODE_CONFIG_DIR": str(config),
            "AGENTSMD_PROJECT_DIRECTION_DATA": str(self.base / "plugin-data"),
        }
        (self.base / "home").mkdir()

    def git(self, *arguments: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )

    def transform(self, directory: Path, module: Path = PLUGIN, calls: int = 1):
        result = subprocess.run(
            # Bun runs OpenCode plugins; the flag only silences Node module notices.
            [NODE, "--no-warnings", str(self.driver), str(module), str(directory), str(calls)],
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result.stderr

    def loaded_context(self, directory: Path) -> str:
        result = subprocess.run(
            [str(LOADER), "hook", "--host", "opencode"],
            input=json.dumps(
                {
                    "hook_event_name": "SessionStart",
                    "cwd": str(directory),
                    "session_id": "ses_fixture",
                }
            ),
            capture_output=True,
            text=True,
            env=self.environment,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_triad_repository_payload_reaches_the_system_prompt(self) -> None:
        report, stderr = self.transform(self.repository)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(report["supported"], "1.18.29")
        self.assertEqual(len(report["system"]), 1)
        self.assertEqual(report["system"][0], self.loaded_context(self.repository))
        payload = json.loads(report["system"][0].splitlines()[1])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["repository_root"], str(self.repository))
        self.assertIn("Make agent work purposeful.", report["system"][0])

    def test_directory_outside_a_repository_carries_the_loader_verdict(self) -> None:
        report, stderr = self.transform(self.outside)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(len(report["system"]), 1)
        self.assertEqual(report["system"][0], self.loaded_context(self.outside))
        payload = json.loads(report["system"][0].splitlines()[1])
        self.assertEqual(payload["status"], "not_in_repository")
        self.assertNotIn("files", payload)
        self.assertNotIn("Make agent work purposeful.", report["system"][0])

    def test_every_module_export_is_a_plugin_function(self) -> None:
        # OpenCode calls every export of a plugin module, so a value export fails to load.
        report, stderr = self.transform(self.repository, calls=0)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(report["system"], [])
        self.assertTrue(report["exports"])
        self.assertEqual(
            sorted(set(report["exports"].values())),
            ["function"],
            report["exports"],
        )

    def test_installed_link_resolves_the_canonical_loader(self) -> None:
        plugins = self.base / "opencode/plugins"
        plugins.mkdir()
        link = plugins / PLUGIN.name
        link.symlink_to(PLUGIN)
        report, stderr = self.transform(self.repository, module=link)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(report["system"], [self.loaded_context(self.repository)])

    def test_unreachable_loader_leaves_the_system_prompt_unchanged(self) -> None:
        detached = self.base / "detached/agentsmd-project-direction.js"
        detached.parent.mkdir()
        shutil.copyfile(PLUGIN, detached)
        report, stderr = self.transform(self.repository, module=detached)
        self.assertEqual(report["system"], [])
        self.assertIn(LOG_PREFIX, stderr)

    def test_failing_loader_leaves_the_system_prompt_unchanged_and_logs_once(self) -> None:
        clone = self.base / "clone"
        (clone / "bin").mkdir(parents=True)
        (clone / "opencode").mkdir()
        loader = clone / "bin/project-direction"
        loader.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
        loader.chmod(0o755)
        module = clone / "opencode/agentsmd-project-direction.js"
        shutil.copyfile(PLUGIN, module)
        report, stderr = self.transform(self.repository, module=module, calls=2)
        self.assertEqual(report["system"], [])
        self.assertEqual(len(stderr.splitlines()), 1)
        self.assertIn("status 3", stderr)


if __name__ == "__main__":
    unittest.main()
