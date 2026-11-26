"""Read and record Codex trust for the AgentsMD plugin hooks.

Codex 0.172 stores two hashes per hook under `[hooks.state."<key>"]`:
`trusted_hash` for the hook definition and `trusted_content_hash` for the
plugin content. It silently skips a hook when either no longer matches, as after
every plugin update. `codex app-server` reports each hook's `currentHash` as
`<definition hash>/<content hash>` and its `trustStatus`.
"""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path
from typing import Any

PLUGIN_ID = "agentsmd@toolboxmd"
# `managed` hooks are trusted by an administrator's requirements.
RUNNABLE = {"trusted", "managed"}
TIMEOUT_SECONDS = 30
TRUST_COMMAND = "agentsmd-codex-hooks trust"


class CodexUnavailable(Exception):
    """The Codex app server could not be started or did not answer as expected."""


class CodexAbsent(CodexUnavailable):
    """No `codex` executable exists, so Codex is not in use here."""


def app_server(requests: list[tuple[str, dict[str, Any]]], codex: str = "codex") -> list[Any]:
    """Send JSON-RPC requests to one `codex app-server` and return their results."""
    lines = [{"id": 0, "method": "initialize",
              "params": {"clientInfo": {"name": "agentsmd", "version": "1"}}},
             {"method": "initialized"}]
    lines += [{"id": index, "method": method, "params": params}
              for index, (method, params) in enumerate(requests, start=1)]
    try:
        process = subprocess.Popen([codex, "app-server"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, cwd=Path.home())
    except FileNotFoundError as error:
        raise CodexAbsent(f"no {codex} executable: {error}") from error
    except OSError as error:
        raise CodexUnavailable(f"cannot run {codex} app-server: {error}") from error
    results: list[Any] = []
    # A server that never answers must not hang inspect; killing it ends readline.
    watchdog = threading.Timer(TIMEOUT_SECONDS, process.kill)
    watchdog.start()
    try:
        assert process.stdin is not None and process.stdout is not None
        # Answers must arrive in order: a write must finish before the next list.
        for message in lines:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            if "id" not in message:
                continue
            while True:
                line = process.stdout.readline()
                if not line:
                    raise CodexUnavailable(f"{codex} app-server exited before answering {message['method']}")
                reply = json.loads(line)
                if reply.get("id") == message["id"]:
                    break
            if "error" in reply:
                raise CodexUnavailable(f"{message['method']} failed: {reply['error']}")
            if message["id"]:
                results.append(reply.get("result"))
    except (OSError, ValueError, AttributeError) as error:
        raise CodexUnavailable(f"{codex} app-server: {error}") from error
    finally:
        watchdog.cancel()
        process.kill()
        process.wait(timeout=TIMEOUT_SECONDS)
    return results


LIST = ("hooks/list", {"cwds": [str(Path.home())]})


def agentsmd_hooks(listing: Any) -> list[dict[str, Any]]:
    """Parse a hooks/list result; a changed shape must not read as no hooks."""
    try:
        hooks = [hook for entry in listing["data"] for hook in entry["hooks"]]
        ours = [hook for hook in hooks if hook.get("pluginId") == PLUGIN_ID]
        if all(isinstance(hook.get(field), str)
               for hook in ours for field in ("key", "trustStatus", "currentHash")):
            return ours
    except (TypeError, KeyError, AttributeError):
        pass
    raise CodexUnavailable("unexpected hooks/list reply from codex app-server")


def report(listing: dict[str, Any]) -> dict[str, Any]:
    hooks = agentsmd_hooks(listing)
    # One hook can appear once per inspected cwd; report each key once.
    states = {hook["key"]: hook["trustStatus"] for hook in hooks}
    untrusted = sorted(key for key, status in states.items() if status not in RUNNABLE)
    result: dict[str, Any] = {
        "healthy": not untrusted,
        "hooks": [{"key": key, "trustStatus": status} for key, status in sorted(states.items())],
    }
    if not states:
        result["status"] = "none-listed"
    elif untrusted:
        result.update(status="untrusted", untrusted=untrusted, action=(
            "Codex skips these AgentsMD hooks, so no Project Direction or rules reach "
            f"its sessions. Run `{TRUST_COMMAND}` from the AgentsMD clone's bin, "
            "then rerun inspect."))
    else:
        result["status"] = "trusted"
    return result


def inspect(codex: str = "codex") -> dict[str, Any]:
    try:
        [listing] = app_server([LIST], codex)
        return report(listing)
    except CodexAbsent as error:
        return {"healthy": False, "status": "codex-absent", "detail": str(error)}
    except CodexUnavailable as error:
        return {"healthy": False, "status": "codex-unavailable", "detail": str(error), "action": (
            "Codex is installed but did not report its hooks, so they may be skipped "
            "and trust is unverified. Fix what `codex app-server` reports, then rerun inspect.")}


def trust_values(listing: dict[str, Any]) -> dict[str, dict[str, str]]:
    values: dict[str, dict[str, str]] = {}
    for hook in agentsmd_hooks(listing):
        if hook["trustStatus"] in RUNNABLE:
            continue
        definition, _, content = hook["currentHash"].partition("/")
        values[hook["key"]] = {"trusted_hash": definition}
        if content:
            values[hook["key"]]["trusted_content_hash"] = content
    return values


def trust(codex: str = "codex") -> dict[str, Any]:
    """Record both hashes of every AgentsMD hook Codex does not trust."""
    [listing] = app_server([LIST], codex)
    values = trust_values(listing)
    if not values:
        return {**report(listing), "trusted_now": []}
    # Codex writes its own config, preserving every other table and comment.
    _, after = app_server([("config/value/write", {
        "keyPath": "hooks.state", "mergeStrategy": "upsert", "value": values}), LIST], codex)
    return {**report(after), "trusted_now": sorted(values)}
