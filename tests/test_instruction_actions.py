"""The loader's instructions.action for every reportable state on every host."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
import agentsmd_instructions as instructions  # noqa: E402

VERIFIED = ("Verified: the global rules in context match this canonical global/AGENTS.md "
            "path and SHA-256. No comparison or reread is needed.")
REREAD = ("The global rules in context are unverified. Read the current canonical "
          "global/AGENTS.md in full before acting and report this status.")


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
        for name in ("CODEX_HOME", "GROK_HOME", "CLAUDE_CONFIG_DIR",
                     "OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME"):
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
            with self.subTest(host=host, state="healthy"):
                report = self.action(host)
                self.assertTrue(report["healthy"])
                self.assertEqual(report["action"], VERIFIED)

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


if __name__ == "__main__":
    unittest.main()
