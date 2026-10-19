"""Muse native package and real wrapper contracts, without the Muse CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tests.direction_block import REMINDER, parse_block

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import agentsmd_instructions as instructions

EVENTS = {"session-start": "SessionStart", "user-prompt-submit": "UserPromptSubmit",
          "subagent-start": "SubagentStart", "pre-tool-use": "PreToolUse",
          "operations-routing": "SessionStart"}


class MuseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if key not in {"AGENTSMD_HOST", "CODEX_HOME", "GROK_HOME",
                                   "GROK_HOOK_NAME", "CLAUDE_CONFIG_DIR", "OPENCODE_CONFIG_DIR",
                                   "MUSE_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT", "PLUGIN_DATA",
                                   "CLAUDE_PLUGIN_DATA", "GROK_PLUGIN_DATA"}}
        self.env.update(HOME=str(self.home), XDG_CONFIG_HOME="",
                        AGENTSMD_PROJECT_DIRECTION_DATA=str(self.base / "cache"))
        self.source = self.base / "stable/global/AGENTS.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("# Shared contract\n")
        target = self.home / ".config/muse/AGENTS.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.source)
        self.repository = self.base / "project"
        self.repository.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.repository)], check=True)
        for name in ("VISION", "MISSION", "OBJECTIVE"):
            (self.repository / f"{name}.md").write_text(f"# {name.title()}\n\nPurpose.\n")

    def call(self, wrapper, payload=None, raw=None, root=ROOT, env=None):
        if raw is None:
            payload = {"cwd": str(self.repository), "session_id": "same-session",
                       "hook_event_name": EVENTS[wrapper], **(payload or {})}
            raw = json.dumps(payload)
        return subprocess.run([sys.executable, str(root / f"hooks/muse/{wrapper}.py")],
                              input=raw, text=True, capture_output=True, cwd=self.repository,
                              env=env or self.env)

    def context(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return parse_block(json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def assert_reminder_only(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit", "additionalContext": REMINDER}})

    def test_manifest_exposes_one_skill_and_distinct_event_sources(self):
        manifest = json.loads((ROOT / ".muse-plugin/plugin.json").read_text())
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["compat"], {"source": "native", "manifestDir": ".muse-plugin"})
        self.assertEqual(manifest["version"], (ROOT / "VERSION").read_text().strip())
        capabilities = manifest["capabilities"]
        self.assertEqual(capabilities["skills"], [{"id": "operations", "path": "skills/operations/SKILL.md",
                                                  "enabledDefault": True}])
        for family in ("commands", "mcpServers", "reminders"):
            self.assertEqual(capabilities[family], [])
        hooks = capabilities["hooks"]
        self.assertEqual({h["id"]: h["event"] for h in hooks}, EVENTS)
        sources = [h["command"][1] for h in hooks]
        self.assertEqual(len(sources), len(set(sources)))
        for hook in hooks:
            self.assertEqual(hook["command"], ["python3", f'hooks/muse/{hook["id"]}.py'])
            self.assertTrue((ROOT / hook["command"][1]).is_file())
            self.assertEqual(hook["timeoutMs"], 15000)
            self.assertNotIn("matcher", hook)
            self.assertNotIn("additionalContextLimit", hook)
        mirrors = json.loads((ROOT / ".version-policy.json").read_text())["mirrors"]
        self.assertIn({"path": ".muse-plugin/plugin.json", "pointer": "/version"}, mirrors)
        # A plugin is the only registered route, with no shared-directory links.
        self.assertEqual(list((ROOT / "skills").glob("*/SKILL.md")), [ROOT / "skills/operations/SKILL.md"])

    def test_native_target_xdg_set_unset_empty_and_relative(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            os.environ["XDG_CONFIG_HOME"] = str(self.base / "custom-config")
            self.assertEqual(instructions.default_target("muse"), self.base / "custom-config/muse/AGENTS.md")
            for value in (None, ""):
                if value is None:
                    os.environ.pop("XDG_CONFIG_HOME", None)
                else:
                    os.environ["XDG_CONFIG_HOME"] = value
                self.assertEqual(instructions.default_target("muse"), self.home / ".config/muse/AGENTS.md")
            os.environ["XDG_CONFIG_HOME"] = "relative"
            with self.assertRaisesRegex(ValueError, "XDG_CONFIG_HOME must be absolute"):
                instructions.default_target("muse")

    def manage(self, action, source=None, env=None, target=None):
        return subprocess.run([str(ROOT / "bin/agentsmd-global-instructions"), action,
                               "--host", "muse", "--source", str(source or self.source),
                               *(["--target", str(target)] if target else [])],
                              env=env or self.env, text=True, capture_output=True)

    def test_global_link_install_preserves_foreign_files_and_preferences(self):
        target = self.home / ".config/muse/AGENTS.md"
        target.unlink()
        (self.source.parent.parent / "PREFERENCES.example.md").write_text("# Defaults\n")
        private = self.source.parent.parent / "PREFERENCES.md"
        installed = self.manage("install")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertEqual(json.loads(installed.stdout)["preferences"]["action"], "created")
        private.write_text("# Private defaults\n")
        self.assertEqual(self.manage("install").returncode, 0)
        self.assertEqual(private.read_text(), "# Private defaults\n")
        self.assertEqual(self.manage("inspect").returncode, 0)
        target.unlink()
        target.write_text("user-owned")
        for action in ("install", "inspect"):
            result = self.manage(action)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), "user-owned")
        self.assertEqual(private.read_text(), "# Private defaults\n")

    def test_global_link_rejects_cache_bound_sources_and_targets(self):
        cached = self.base / "plugins/cache/agentsmd/global/AGENTS.md"
        cached.parent.mkdir(parents=True)
        cached.write_text("# Cached\n")
        result = self.manage("install", source=cached)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["error"], "cache-bound-source")
        for action in ("install", "inspect"):
            result = self.manage(action, target=self.base / "plugins/cache/config/muse/AGENTS.md")
            self.assertEqual(result.returncode, 2)
            self.assertIn("cache-bound-target", result.stdout)
        self.assertFalse((self.base / "plugins/cache/config").exists())

    def test_custom_xdg_install_rejected_without_writes_but_inspect_works(self):
        example = self.source.parent.parent / "PREFERENCES.example.md"
        example.write_text("# Defaults\n")
        for xdg in (str(self.base / "custom-config"), "relative"):
            with self.subTest(xdg=xdg):
                env = dict(self.env, XDG_CONFIG_HOME=xdg)
                before = sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*"))
                result = self.manage("install", env=env)
                self.assertEqual(result.returncode, 2, result.stdout)
                report = json.loads(result.stdout)
                self.assertEqual(report["error"], "unsupported-muse-xdg-config-home")
                self.assertIn("XDG_CONFIG_HOME", report["message"])
                self.assertIn("unsupported", report["message"])
                self.assertEqual(sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*")), before)
                self.assertFalse((self.source.parent.parent / "PREFERENCES.md").exists())
        custom = self.base / "custom-config"
        env = dict(self.env, XDG_CONFIG_HOME=str(custom))
        result = self.manage("inspect", env=env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["target"], str(custom / "muse/AGENTS.md"))
        target = custom / "muse/AGENTS.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(self.source)
        self.assertEqual(self.manage("inspect", env=env).returncode, 0)
        for xdg in (None, ""):
            env = dict(self.env)
            if xdg is None:
                env.pop("XDG_CONFIG_HOME", None)
            else:
                env["XDG_CONFIG_HOME"] = xdg
            self.assertEqual(self.manage("install", env=env).returncode, 0)

    def test_unknown_events_reach_loader_diagnostic(self):
        for wrapper in ("session-start", "user-prompt-submit", "subagent-start", "pre-tool-use"):
            for event in ("PostCompact", "not_an_event"):
                with self.subTest(wrapper=wrapper, event=event):
                    result = self.call(wrapper, {"hook_event_name": event})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    message = json.loads(result.stdout)["systemMessage"]
                    self.assertIn("malformed hook input", message)
                    self.assertIn("hook_event_name must be", message)

    def test_session_start_source_is_ignored(self):
        for source in ("startup", "resume", "clear", "compact", "unknown"):
            result = self.call("session-start", {"source": source})
            self.assertEqual(self.context(result)["status"], "ready")

    def test_lifecycle_delivery_and_original_session_hash(self):
        first = self.context(self.call("session-start"))
        self.assertEqual(first["status"], "ready")
        self.assertIn("unchanged", first["instructions"]["action"])
        self.assert_reminder_only(self.call("user-prompt-submit"))
        self.assertEqual(self.context(self.call("subagent-start"))["status"], "ready")
        self.source.write_text("# Changed contract\n")
        changed = self.context(self.call("user-prompt-submit"))
        self.assertIn("changed since", changed["instructions"]["action"])
        self.assert_reminder_only(self.call("user-prompt-submit"))
        self.assertIn("unchanged", self.context(self.call("session-start"))["instructions"]["action"])

    def test_pretooluse_gate_blocks_and_allows_without_direction(self):
        for kind in ("issue", "pr"):
            for valid in (False, True):
                body = "\n".join(f"{field}: evidence" for field in
                                 ("Requirements and who asked", "Deleted", "Bottleneck", "Checked myself")) if valid else "missing record"
                command = f"gh {kind} create --title x --body {shlex.quote(body)}"
                for tool_input in ({"command": command}, {"cmd": command}, {"command": None, "cmd": command}):
                    with self.subTest(kind=kind, valid=valid, tool_input=tool_input):
                        result = self.call("pre-tool-use", {"tool_name": "bash", "tool_input": tool_input})
                        self.assertEqual(result.returncode, 0 if valid else 2, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(bool(result.stderr), not valid)
                        if not valid:
                            self.assertIn(f"blocked `gh {kind} create`", result.stderr)
        self.assertFalse((self.base / "cache").exists())

    def test_event_variants_and_tool_input_shapes_keep_gate_block_and_allow(self):
        fields = ("Requirements and who asked", "Deleted", "Bottleneck", "Checked myself")
        for valid in (False, True):
            body = "\n".join(f"{field}: proof" for field in fields) if valid else "missing"
            argv = ["gh", "issue", "create", "--title", "x", "--body", body]
            command = shlex.join(argv)
            shapes = ({"command": argv}, json.dumps({"command": command}),
                      json.dumps({"command": argv}), json.dumps({"cmd": command}))
            for event in ("pre_tool_use", "preToolUse", "PRETOOLUSE", "pre-tool-use"):
                for tool_input in shapes:
                    with self.subTest(valid=valid, event=event, tool_input=tool_input):
                        result = self.call("pre-tool-use", {"hook_event_name": event, "tool_input": tool_input})
                        self.assertEqual(result.returncode, 0 if valid else 2, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(bool(result.stderr), not valid)
        for event in ("sessionstart", "session_start", "SESSION-START"):
            result = self.call("session-start", {"hook_event_name": event})
            self.assertIn("hookSpecificOutput", json.loads(result.stdout))
            self.assertEqual(self.context(result)["status"], "ready")

    def test_quoted_context_falls_back_for_muse_encoded_stdout_only(self):
        dense = '\"\\\n' * 1160
        (self.repository / "VISION.md").write_text("# Vision\n" + dense)
        (self.source.parent.parent / "PREFERENCES.md").write_text("# Preferences\n" + dense)
        for args in (["add", "."], ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--quiet", "-m", "fixture"]):
            subprocess.run(["git", "-C", str(self.repository), *args], check=True)
        # Claude receives the identical full payload with the same native source.
        target = self.home / ".claude/CLAUDE.md"
        target.parent.mkdir()
        target.symlink_to(self.source)
        payload = {"cwd": str(self.repository), "hook_event_name": "SessionStart", "session_id": "same-session"}
        full = subprocess.run([str(ROOT / "bin/project-direction"), "hook", "--host", "claude"],
                              input=json.dumps(payload), text=True, capture_output=True, env=self.env)
        context = json.loads(full.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertLess(len(context.encode()), 10000)
        self.assertGreater(len(full.stdout.encode()), 16384)
        result = self.call("session-start")
        report = self.context(result)
        self.assertEqual(report["status"], "read_required")
        self.assertEqual(report["preferences"]["status"], "read_required")
        self.assertTrue(all("content" not in item for item in report["files"]))
        self.assertLessEqual(len(result.stdout.encode()), 16384)

    def test_malformed_input_matches_loader_policy(self):
        for raw in ("{invalid", "[]", '{"tool_input":{"command":"gh pr create"}}'):
            result = self.call("pre-tool-use", raw=raw)
            direct = subprocess.run([sys.executable, str(ROOT / "bin/project-direction"), "hook", "--host", "muse"],
                                    input=raw, text=True, capture_output=True, env=self.env)
            self.assertEqual((result.returncode, result.stdout, result.stderr),
                             (direct.returncode, direct.stdout, direct.stderr))

    def test_host_cache_isolation(self):
        self.context(self.call("session-start"))
        env = dict(self.env, CODEX_HOME=str(self.base / "codex"))
        target = self.base / "codex/AGENTS.md"
        target.parent.mkdir()
        target.symlink_to(self.source)
        raw = json.dumps({"cwd": str(self.repository), "session_id": "same-session",
                          "hook_event_name": "UserPromptSubmit"})
        result = subprocess.run([sys.executable, str(ROOT / "bin/project-direction"), "hook", "--host", "codex"],
                                input=raw, text=True, capture_output=True, env=env)
        self.assertIn("unverified", self.context(result)["instructions"]["action"])
        self.assert_reminder_only(self.call("user-prompt-submit"))

    def test_pointer_runs_actual_sibling(self):
        result = self.call("operations-routing")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        self.assertIn(str(ROOT / "skills/operations/SKILL.md"), output["additionalContext"])

    def test_transport_preserves_payload_streams_exit_and_resolved_root(self):
        package = self.base / "package with spaces"
        shutil.copytree(ROOT / "hooks/muse", package / "hooks/muse")
        (package / "bin").mkdir()
        stub = 'import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({"argv":sys.argv[1:],"input":p}))\nprint("reason",file=sys.stderr)\nsys.exit(2)\n'
        for name in ("project-direction", "operations-routing"):
            (package / "bin" / name).write_text(stub)
        alias = self.base / "alias"
        alias.symlink_to(package, target_is_directory=True)
        for wrapper, event in EVENTS.items():
            for explicit in (False, True):
                payload = {"cwd": str(self.repository), "session_id": "id",
                           "tool_name": "bash", "tool_input": {"command": "echo hello"}}
                if explicit:
                    payload["hook_event_name"] = event
                result = self.call(wrapper, raw=json.dumps(payload), root=alias,
                                   env=dict(self.env, MUSE_PLUGIN_ROOT="/unusable"))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "reason\n")
                observed = json.loads(result.stdout)
                self.assertEqual(observed["input"], {**payload, "hook_event_name": event})
                self.assertEqual(observed["argv"], [] if wrapper == "operations-routing" else ["hook", "--host", "muse"])
        for tool_input in ("not JSON", '{"command":', "[]", {"command": ["gh", 3]}):
            result = self.call("pre-tool-use", {"tool_input": tool_input}, root=package)
            self.assertEqual(json.loads(result.stdout)["input"]["tool_input"], tool_input)
        # A detached wrapper can resolve the packaged loader through either env.
        detached = self.base / "detached"
        shutil.copytree(ROOT / "hooks/muse", detached / "hooks/muse")
        for variable in ("MUSE_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
            result = self.call("session-start", root=detached, env=dict(self.env, **{variable: str(package)}))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["argv"], ["hook", "--host", "muse"])


if __name__ == "__main__":
    unittest.main()
