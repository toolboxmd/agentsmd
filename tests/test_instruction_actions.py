"""The loader's instructions.action for every reportable state on every host."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import agentsmd_instructions as instructions  # noqa: E402

UNCHANGED = ("The canonical global/AGENTS.md is unchanged since this session started "
             "(same SHA-256). Nothing is needed.")
CHANGED = ("The global rules changed since this session started. Read the current "
           "canonical global/AGENTS.md in full before acting.")
REREAD = ("The global rules in context are unverified. Read the current canonical "
          "global/AGENTS.md in full before acting and report this status.")
HOST_VARIABLES = ("AGENTSMD_HOST", "CODEX_HOME", "GROK_HOME", "CLAUDE_CONFIG_DIR",
                  "OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME", "PLUGIN_DATA",
                  "CLAUDE_PLUGIN_DATA", "GROK_PLUGIN_DATA", "GROK_HOOK_NAME")


class InstructionActionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / "stable/global/AGENTS.md"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("# Shared contract\n")
        self.other = self.root / "other/global/AGENTS.md"
        self.other.parent.mkdir(parents=True)
        self.other.write_text("# Different contract\n")
        home = self.root / "home"
        home.mkdir()
        patcher = mock.patch.dict(os.environ, {"HOME": str(home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        # Every host target resolves under the temporary HOME.
        for name in HOST_VARIABLES:
            os.environ.pop(name, None)

    def link(self, host, source):
        target = instructions.default_target(host)
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            target.unlink()
        target.symlink_to(source)
        return target

    def action(self, host, require_unambiguous=False):
        payload = instructions.context_payload(host, require_unambiguous)
        return payload["instructions"]

    def test_every_state_on_every_host(self):
        for host in instructions.HOSTS:
            with self.subTest(host=host, state="missing"):
                report = self.action(host)
                self.assertEqual(report["status"], "missing")
                self.assertEqual(report["action"], REREAD)

            target = self.link(host, self.source)
            with self.subTest(host=host, state="healthy-without-session"):
                report = self.action(host)
                self.assertTrue(report["healthy"])
                self.assertEqual(report["action"], REREAD)

            with self.subTest(host=host, state="ambiguous"):
                others = [self.link(other, self.other)
                          for other in instructions.HOSTS if other != host]
                report = self.action(host, require_unambiguous=True)
                self.assertEqual(report["status"], "source-ambiguous")
                self.assertTrue(report["action"].endswith(REREAD))
                for other in others:
                    other.unlink()

            with self.subTest(host=host, state="non-symlink"):
                target.unlink()
                target.write_text("# Copied contract\n")
                report = self.action(host)
                self.assertEqual(report["status"], "non-symlink")
                self.assertEqual(report["action"], REREAD)
                target.unlink()

            with self.subTest(host=host, state="broken-link"):
                target.symlink_to(self.root / "gone/global/AGENTS.md")
                report = self.action(host)
                self.assertEqual(report["status"], "broken-link")
                self.assertEqual(report["action"], REREAD)
                target.unlink()

            with self.subTest(host=host, state="unreadable"):
                target.symlink_to(self.source)
                with mock.patch.object(instructions, "digest",
                                       side_effect=PermissionError("denied")):
                    report = self.action(host)
                self.assertEqual(report["status"], "unreadable")
                self.assertEqual(report["action"], REREAD)
                target.unlink()

    def hook(self, host, event, session="session", cache=None):
        env = dict(os.environ, AGENTSMD_PROJECT_DIRECTION_DATA=str(cache or self.root / "cache"))
        if host == "grok":
            env["GROK_HOOK_NAME"] = "agentsmd"
        event_input = {"cwd": str(self.root), "hook_event_name": event}
        if session is not None:
            event_input["session_id"] = session
        if event == "PreToolUse":
            event_input.update(tool_name="Bash", tool_input={"command": "ls"})
        result = subprocess.run([str(ROOT / "bin/project-direction"), "hook", "--host", host],
                                input=json.dumps(event_input), env=env, cwd=self.root,
                                text=True, capture_output=True, check=True)
        if not result.stdout:
            return None
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        return json.loads(context.splitlines()[1])["instructions"]["action"]

    def test_session_start_sha_decides_the_action_on_every_host(self):
        for host in instructions.HOSTS:
            self.link(host, self.source)
            # Grok discards SessionStart; its first PreToolUse records the start.
            # OpenCode's plugin repeats SessionStart; only the first records.
            start, later = {"grok": ("PreToolUse", "PreToolUse"),
                            "opencode": ("SessionStart", "SessionStart")}.get(
                                host, ("SessionStart", "SubagentStart"))
            session = f"{host}-session"
            with self.subTest(host=host, state="unchanged"):
                self.assertEqual(self.hook(host, start, session), UNCHANGED)
                if host != "grok":
                    self.assertEqual(self.hook(host, later, session), UNCHANGED)
                if host in ("claude", "codex"):
                    # A real SessionStart (resume, clear, compact) reloads and re-records.
                    self.source.write_text(f"# Reloaded for {host}\n")
                    self.assertEqual(self.hook(host, "SessionStart", session), UNCHANGED)
            with self.subTest(host=host, state="changed-since-start"):
                self.source.write_text(f"# Changed for {host}\n")
                self.assertEqual(self.hook(host, later, session), CHANGED)
            with self.subTest(host=host, state="no-session-id"):
                self.assertEqual(self.hook(host, start, None), REREAD)
            with self.subTest(host=host, state="no-start-record"):
                if host in ("claude", "codex"):
                    self.assertEqual(self.hook(host, "UserPromptSubmit", f"{host}-late"), REREAD)
            with self.subTest(host=host, state="cache-unwritable"):
                blocker = self.root / "not-a-directory"
                blocker.write_text("")
                self.assertEqual(self.hook(host, start, f"{host}-blocked", cache=blocker), REREAD)
            instructions.default_target(host).unlink()


if __name__ == "__main__":
    unittest.main()
