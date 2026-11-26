#!/usr/bin/env python3
"""Codex skips AgentsMD hooks whose recorded hashes went stale (#288)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTION = ROOT / "bin/project-direction"
TRUST = ROOT / "bin/agentsmd-codex-hooks"
KEY = "agentsmd@toolboxmd:hooks/hooks.json:{}:0:0"
DEFINITION = "sha256:" + "d" * 64
OLD_CONTENT = "sha256:" + "0" * 64
NEW_CONTENT = "sha256:" + "c" * 64

# Stands in for `codex app-server`: answers hooks/list from the listing file
# and applies config/value/write the way Codex 0.172 judges trust.
FAKE_CODEX = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    state = os.environ["FAKE_CODEX_STATE"]
    assert sys.argv[1:] == ["app-server"], sys.argv
    methods = []
    for line in sys.stdin:
        message = json.loads(line)
        methods.append(message["method"])
        # Codex refuses requests before the initialize handshake completes.
        assert methods[:2] == ["initialize", "initialized"][:len(methods)], methods
        if "id" not in message:
            continue
        data = json.load(open(state))
        result = {}
        if message["method"] == "hooks/list":
            assert message["params"] == {"cwds": [os.environ["HOME"]]}, message
            result = data.get("raw") or {"data": [{"cwd": os.environ["HOME"], "errors": [],
                                                   "warnings": [], "hooks": data["hooks"]}]}
        elif message["method"] == "config/value/write":
            params = message["params"]
            data["writes"].append(params)
            for hook in data["hooks"]:
                value = params["value"].get(hook["key"])
                if value is None:
                    continue
                recorded = value["trusted_hash"] + "/" + value.get("trusted_content_hash", "")
                hook["trustStatus"] = "trusted" if recorded == hook["currentHash"] else "modified"
            json.dump(data, open(state, "w"))
        print(json.dumps({"id": message["id"], "result": result}), flush=True)
""")


def hook(event: str, status: str, plugin: str = "agentsmd@toolboxmd") -> dict[str, object]:
    return {"key": KEY.format(event).replace("agentsmd@toolboxmd", plugin), "pluginId": plugin,
            "eventName": event, "source": "plugin", "trustStatus": status,
            "currentHash": f"{DEFINITION}/{NEW_CONTENT}"}


class CodexHookTrustTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        source = self.root / "agentsmd/global/AGENTS.md"
        source.parent.mkdir(parents=True)
        source.write_text("# AgentsMD contract\n")
        target = self.root / "codex/AGENTS.md"
        target.parent.mkdir()
        target.symlink_to(source)
        fake = self.root / "fake-bin/codex"
        fake.parent.mkdir()
        fake.write_text(FAKE_CODEX)
        fake.chmod(0o755)
        self.state = self.root / "state.json"
        self.env = {**os.environ, "CODEX_HOME": str(target.parent), "HOME": str(self.root),
                    "FAKE_CODEX_STATE": str(self.state),
                    "PATH": f"{fake.parent}{os.pathsep}{os.environ['PATH']}"}

    def listing(self, *hooks: dict[str, object]) -> None:
        self.state.write_text(json.dumps({"hooks": list(hooks), "writes": []}))

    def run_tool(self, *command: str) -> tuple[int, dict[str, object]]:
        result = subprocess.run(command, env=self.env, cwd=self.root, text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)

    def test_inspect_fails_and_names_a_modified_hook(self) -> None:
        self.listing(hook("session_start", "modified"), hook("pre_tool_use", "trusted"))
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual(code, 2)
        self.assertEqual(payload["codex_hooks"]["status"], "untrusted")
        self.assertEqual(payload["codex_hooks"]["untrusted"], [KEY.format("session_start")])
        self.assertIn("agentsmd-codex-hooks trust", payload["codex_hooks"]["action"])

    def test_inspect_fails_on_an_untrusted_hook(self) -> None:
        self.listing(hook("user_prompt_submit", "untrusted"))
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual(code, 2)
        self.assertEqual(payload["codex_hooks"]["untrusted"], [KEY.format("user_prompt_submit")])

    def test_inspect_passes_when_every_agentsmd_hook_is_trusted(self) -> None:
        # Another plugin's untrusted hook is not AgentsMD's to judge.
        self.listing(hook("session_start", "trusted"), hook("session_start", "modified", "other@toolboxmd"))
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual(code, 0)
        self.assertEqual(payload["codex_hooks"]["status"], "trusted")

    def test_other_harnesses_do_not_consult_codex(self) -> None:
        self.listing(hook("session_start", "modified"))
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root / "claude")
        (self.root / "claude").mkdir()
        (self.root / "claude/CLAUDE.md").symlink_to(self.root / "agentsmd/global/AGENTS.md")
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "claude")
        self.assertEqual(code, 0)
        self.assertNotIn("codex_hooks", payload)

    def test_trust_records_both_hashes_of_only_the_stale_hooks(self) -> None:
        self.listing(hook("session_start", "modified"), hook("pre_tool_use", "trusted"),
                     hook("session_start", "modified", "other@toolboxmd"))
        code, result = self.run_tool(str(TRUST), "trust")
        self.assertEqual(code, 0)
        self.assertEqual(result["trusted_now"], [KEY.format("session_start")])
        self.assertEqual(result["status"], "trusted")
        [write] = json.loads(self.state.read_text())["writes"]
        self.assertEqual(write, {"keyPath": "hooks.state", "mergeStrategy": "upsert", "value": {
            KEY.format("session_start"): {"trusted_hash": DEFINITION, "trusted_content_hash": NEW_CONTENT}}})
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual((code, payload["codex_hooks"]["status"]), (0, "trusted"))

    def test_inspect_fails_when_installed_codex_does_not_answer(self) -> None:
        # The fake exits on its missing state file before answering.
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual(code, 2)
        self.assertEqual(payload["codex_hooks"]["status"], "codex-unavailable")
        self.assertIn("unverified", payload["codex_hooks"]["action"])

    def test_inspect_fails_on_an_unexpected_hooks_list_shape(self) -> None:
        # A renamed field must not read as "no AgentsMD hooks".
        self.state.write_text(json.dumps({"raw": {"entries": []}, "hooks": [], "writes": []}))
        code, payload = self.run_tool(str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual((code, payload["codex_hooks"]["status"]), (2, "codex-unavailable"))
        self.listing({**hook("session_start", "modified"), "currentHash": None})
        code, result = self.run_tool(str(TRUST), "trust")
        self.assertEqual((code, result["status"]), (2, "codex-unavailable"))
        self.assertEqual(json.loads(self.state.read_text())["writes"], [])

    def test_inspect_passes_without_a_codex_executable(self) -> None:
        empty = self.root / "empty-bin"
        empty.mkdir()
        self.env["PATH"] = str(empty)
        code, payload = self.run_tool(sys.executable, str(DIRECTION), "inspect", "--harness", "codex")
        self.assertEqual((code, payload["codex_hooks"]["status"]), (0, "codex-absent"))

    def test_trust_is_a_no_op_when_everything_is_trusted(self) -> None:
        self.listing(hook("session_start", "trusted"))
        code, result = self.run_tool(str(TRUST), "trust")
        self.assertEqual((code, result["trusted_now"]), (0, []))
        self.assertEqual(json.loads(self.state.read_text())["writes"], [])

    def test_trust_fails_when_the_plugin_lists_no_hooks(self) -> None:
        self.listing()
        code, result = self.run_tool(str(TRUST), "trust")
        self.assertEqual((code, result["status"]), (2, "none-listed"))


if __name__ == "__main__":
    unittest.main()
