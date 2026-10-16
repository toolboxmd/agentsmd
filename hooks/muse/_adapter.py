"""Transport Muse hook input to the existing AgentsMD executables."""
from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
import subprocess
import sys


def run(event: str, executable: str = "project-direction") -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        # Preserve the loader's malformed-input diagnostic and exit policy.
        pass
    else:
        if isinstance(payload, dict):
            payload.setdefault("hook_event_name", event)
            supplied = payload["hook_event_name"]
            if isinstance(supplied, str):
                key = supplied.replace("_", "").replace("-", "").lower()
                for canonical in ("SessionStart", "UserPromptSubmit", "SubagentStart", "PreToolUse"):
                    if key == canonical.lower():
                        payload["hook_event_name"] = canonical
                        break
            tool_input = payload.get("tool_input")
            if isinstance(tool_input, str):
                try:
                    parsed = json.loads(tool_input)
                except ValueError:
                    pass
                else:
                    if isinstance(parsed, dict):
                        tool_input = payload["tool_input"] = parsed
            if isinstance(tool_input, dict):
                command = tool_input.get("command")
                if isinstance(command, list) and all(isinstance(word, str) for word in command):
                    tool_input["command"] = shlex.join(command)
            if (isinstance(tool_input, dict)
                    and not isinstance(tool_input.get("command"), str)
                    and isinstance(tool_input.get("cmd"), str)):
                tool_input["command"] = tool_input["cmd"]
            # Keep unknown events visible to the loader's input diagnostic.
            raw = json.dumps(payload).encode("utf-8")
    root = Path(__file__).resolve().parents[2]
    target = root / "bin" / executable
    if not target.is_file():
        for variable in ("MUSE_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"):
            fallback = os.environ.get(variable)
            if fallback and (Path(fallback) / "bin" / executable).is_file():
                target = Path(fallback) / "bin" / executable
                break
    arguments = [sys.executable, str(target)]
    if executable == "project-direction":
        arguments += ["hook", "--host", "muse"]
    # Inherit both output streams; in particular exit 2 must retain stderr
    # because Muse uses that reason to block the tool call.
    return subprocess.run(arguments, input=raw, check=False).returncode
