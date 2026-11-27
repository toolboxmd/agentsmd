#!/usr/bin/env python3
"""Node seam proof that the OpenCode plugin transports the loader payload
on both OpenCode plugin APIs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.direction_block import REMINDER

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "opencode/agentsmd-project-direction.js"
LOADER = ROOT / "bin/project-direction"
ROUTING = ROOT / "bin/operations-routing"
NODE = shutil.which("node")
LOG_PREFIX = "agentsmd-project-direction:"
# OpenCode 1.x calls `server`; OpenCode 2.x calls `setup`.
APIS = ("v1", "v2")
DRIVER = """
import { pathToFileURL } from "node:url";

const [modulePath, directory, calls, api] = process.argv.slice(2);
const module = await import(pathToFileURL(modulePath).href);
const plugin = module.default;
let system;
if (api === "v2") {
  // OpenCode 2.x: setup registers hooks; the context hook edits system parts.
  const registered = {};
  const hook = (domain) => async (name, callback) => {
    registered[`${domain}.${name}`] = callback;
    return { dispose: async () => {} };
  };
  await plugin.setup({
    location: { directory, project: { directory } },
    session: { hook: hook("session") },
    tool: { hook: hook("tool") },
  });
  const request = {
    sessionID: "ses_fixture",
    system: [{ type: "text", text: "host" }],
    messages: [],
  };
  for (let call = 0; call < Number(calls); call += 1) {
    await registered["session.context"](request);
  }
  const added = request.system.slice(1);
  if (added.some((part) => part.type !== "text" || Object.keys(part).length !== 2)) {
    throw new Error("unexpected system part shape: " + JSON.stringify(added));
  }
  system = added.map((part) => part.text);
} else {
  // OpenCode 1.x: server returns hooks; the transform edits system strings.
  const hooks = await plugin.server({ directory, worktree: directory });
  const output = { system: [] };
  for (let call = 0; call < Number(calls); call += 1) {
    await hooks["experimental.chat.system.transform"](
      { sessionID: "ses_fixture", model: { id: "fixture" } },
      output,
    );
  }
  system = output.system;
}
process.stdout.write(JSON.stringify({
  system,
  id: plugin.id,
  supported: plugin.supportedOpenCodeVersions,
  exports: Object.fromEntries(
    Object.entries(module).map(([name, value]) => [name, typeof value]),
  ),
  members: Object.fromEntries(
    Object.entries(plugin).map(([name, value]) => [name, typeof value]),
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
        source = self.base / "release/global/AGENTS.md"
        source.parent.mkdir(parents=True)
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

    def transform(self, directory: Path, module: Path = PLUGIN, calls: int = 1, api: str = "v1"):
        result = subprocess.run(
            # Bun runs OpenCode plugins; the flag only silences Node module notices.
            [NODE, "--no-warnings", str(self.driver), str(module), str(directory), str(calls), api],
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

    def routing_context(self) -> str:
        result = subprocess.run([str(ROUTING)], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_triad_repository_payload_reaches_the_system_prompt(self) -> None:
        for api in APIS:
            with self.subTest(api=api):
                self.check_triad_payload(api)

    def check_triad_payload(self, api: str) -> None:
        report, stderr = self.transform(self.repository, api=api)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(len(report["system"]), 2)
        self.assertEqual(report["system"][0], self.loaded_context(self.repository))
        self.assertEqual(report["system"][1], self.routing_context())
        self.assertIn("operations/SKILL.md", report["system"][1])
        payload = json.loads(report["system"][0].splitlines()[1])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["repository_root"], str(self.repository))
        self.assertIn("Make agent work purposeful.", report["system"][0])
        # The conversation reminder (#201) closes the loader context once.
        self.assertTrue(report["system"][0].endswith("\n\n" + REMINDER))
        self.assertEqual(report["system"][0].count(REMINDER), 1)

    def test_directory_outside_a_repository_carries_the_loader_verdict(self) -> None:
        for api in APIS:
            with self.subTest(api=api):
                self.check_outside(api)

    def check_outside(self, api: str) -> None:
        report, stderr = self.transform(self.outside, api=api)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(len(report["system"]), 2)
        self.assertEqual(report["system"][0], self.loaded_context(self.outside))
        self.assertEqual(report["system"][1], self.routing_context())
        payload = json.loads(report["system"][0].splitlines()[1])
        self.assertEqual(payload["status"], "not_in_repository")
        self.assertNotIn("files", payload)
        self.assertNotIn("Make agent work purposeful.", report["system"][0])

    def test_default_export_serves_both_plugin_apis(self) -> None:
        # OpenCode 2.x requires a default object with `id` and `setup`, and
        # rejects a function default; OpenCode 1.x loads `{id, server}` from the
        # default export alone. Any other export would be a second 1.x plugin.
        report, stderr = self.transform(self.repository, calls=0)
        self.assertNotIn(LOG_PREFIX, stderr)
        self.assertEqual(report["system"], [])
        self.assertEqual(report["exports"], {"default": "object"})
        self.assertEqual(report["id"], "agentsmd-project-direction")
        self.assertEqual(report["members"]["server"], "function")
        self.assertEqual(report["members"]["setup"], "function")
        self.assertNotIn("tui", report["members"])
        self.assertIn("1.18.32", report["supported"])
        self.assertIn("2.3.2", report["supported"])

    def test_installed_link_resolves_the_canonical_loader(self) -> None:
        plugins = self.base / "opencode/plugins"
        plugins.mkdir()
        link = plugins / PLUGIN.name
        link.symlink_to(PLUGIN)
        for api in APIS:
            with self.subTest(api=api):
                report, stderr = self.transform(self.repository, module=link, api=api)
                self.assertNotIn(LOG_PREFIX, stderr)
                self.assertEqual(
                    report["system"],
                    [self.loaded_context(self.repository), self.routing_context()],
                )

    def test_setup_without_session_and_tool_hooks_registers_nothing(self) -> None:
        # OpenCode 1.x also calls `setup`, with a context lacking session and
        # tool hooks; `server` covers 1.x, so setup must be a silent no-op.
        driver = self.base / "reduced.mjs"
        driver.write_text(
            "import { pathToFileURL } from 'node:url';\n"
            "const plugin = (await import(pathToFileURL(process.argv[2]).href)).default;\n"
            "const result = await plugin.setup({ options: {}, agent: {}, skill: {} });\n"
            "process.stdout.write(String(result));\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [NODE, "--no-warnings", str(driver), str(PLUGIN)],
            capture_output=True, text=True, env=self.environment, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "undefined")
        self.assertEqual(result.stderr, "")

    def test_unreachable_loader_leaves_the_system_prompt_unchanged(self) -> None:
        detached = self.base / "detached/agentsmd-project-direction.js"
        detached.parent.mkdir()
        shutil.copyfile(PLUGIN, detached)
        for api in APIS:
            with self.subTest(api=api):
                report, stderr = self.transform(self.repository, module=detached, api=api)
                self.assertEqual(report["system"], [])
                self.assertIn(LOG_PREFIX, stderr)

    def test_failing_loader_leaves_the_system_prompt_unchanged_and_logs_once(self) -> None:
        clone = self.base / "clone"
        (clone / "bin").mkdir(parents=True)
        (clone / "opencode").mkdir()
        loader = clone / "bin/project-direction"
        # Drain spawnSync's JSON input before exiting so the status is observable.
        loader.write_text("#!/bin/sh\ncat >/dev/null || exit 1\nexit 3\n", encoding="utf-8")
        loader.chmod(0o755)
        module = clone / "opencode/agentsmd-project-direction.js"
        shutil.copyfile(PLUGIN, module)
        for api in APIS:
            with self.subTest(api=api):
                report, stderr = self.transform(self.repository, module=module, calls=2, api=api)
                self.assertEqual(report["system"], [])
                # One line for Project Direction and one for the missing routing command.
                lines = stderr.splitlines()
                self.assertEqual(len(lines), 2, stderr)
                self.assertIn("status 3", lines[0])
                self.assertIn("operations pointer was not loaded", lines[1])


if __name__ == "__main__":
    unittest.main()
