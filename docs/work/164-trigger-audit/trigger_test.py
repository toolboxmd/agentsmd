#!/usr/bin/env python3
"""Before-and-after trigger test for Issue #164 (evidence only, not a release gate).

Each case runs one host CLI headless in a fresh throwaway git repository under
the system temp directory, once per arm:

  main    `git archive origin/main` of this repository
  branch  `git archive HEAD` of this checkout

Hosts: claude (Claude Code), codex, grok (Grok Build), opencode. A positive case
fires when the required file is read before the first file edit. A negative
case passes when the file is never read. Every run also records whether the
operations entry point was loaded (a Skill call for `operations` or a read of
`operations/SKILL.md`). Scores go to stdout; with --record, one compact line per
run (tool calls up to the first edit, paths anonymized, no prompts or file
contents) is appended to a JSONL file. Raw streams are never kept: they may
hold private context.

Confinement (added after a run escaped into the canonical checkout on
2026-09-29): each run gets a temporary HOME and a temporary host configuration
directory that hold only the arm's global contract, a copy of the arm's plugin
or Skills, and links to the host's existing login. Nothing is installed into
the live host configuration.

  claude    HOME/.claude (CLAUDE_CONFIG_DIR unset), --plugin-dir, acceptEdits,
            login through a link to ~/Library/Keychains plus account metadata
            (no token) from ~/.claude.json
  codex     CODEX_HOME=HOME/codex with a local marketplace holding the plugin
            copy, installed with `codex plugin add`; workspace-write sandbox;
            hooks run (--dangerously-bypass-hook-trust stands in for the live
            trusted hook hash); auth.json linked
  grok      GROK_HOME=HOME/grok with the plugin copy installed by `grok plugin
            install --trust` and the Project Direction hook file the live setup
            uses, pointed at the copy; --always-approve (the live setting)
            inside --sandbox workspace; auth.json linked
  opencode  OPENCODE_CONFIG_DIR=HOME/opencode with Skill and plugin links into
            the copy (as the live installer links them), external directories
            denied except the copy; XDG data, cache and config under HOME;
            auth.json linked

After every run the canonical checkout and this checkout must show the same
`git status --porcelain --ignored --untracked-files=all` and HEAD, and the live
host configuration files the same content, as before the batch, or the batch
aborts. Every batch first proves that the guard sees a new ignored file and
that a setup failure leaves nothing behind (--self-check runs only those). New
files, including ignored ones, are caught; content edits to an already-ignored
file are not. Each record's `login_files_changed` lists the linked real login
files (SHA-256 and mtime, before and after the run) that changed; it is visible
only and never blocks, and null means unknown (records made before c35c736). The run's process group is killed when it ends, and the temporary
HOME, links and repository are removed in a `finally`, also on failure,
timeout or abort.

  python3 trigger_test.py --host claude --model claude-opus-5-5 --effort medium \\
      --runs 5 --jobs 8 --record records.jsonl > results.tsv
  python3 trigger_test.py --score results.tsv
"""
import argparse
import concurrent.futures
import glob
import hashlib
import json
import pathlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

BRANCH = pathlib.Path(__file__).resolve().parents[3]
CANONICAL = pathlib.Path.home() / "dev/toolboxmd/agentsmd"
GUARDED = [CANONICAL, BRANCH]
REAL_HOME = pathlib.Path.home()
CLAUDE_JSON = REAL_HOME / ".claude.json"
# Login material linked (never copied) into the temporary host directory.
LOGIN = {
    "codex": REAL_HOME / ".codex/auth.json",
    "grok": REAL_HOME / ".grok/auth.json",
    "opencode": REAL_HOME / ".local/share/opencode/auth.json",
}
KEYCHAINS = REAL_HOME / "Library/Keychains"  # Claude Code's login, linked as a directory
# Live host configuration that a run must not change (logins excluded: a token
# refresh through the link is the host's own doing).
LIVE_CONFIG = [
    REAL_HOME / ".claude/settings.json", REAL_HOME / ".claude/CLAUDE.md",
    REAL_HOME / ".codex/config.toml", REAL_HOME / ".codex/AGENTS.md",
    REAL_HOME / ".grok/config.toml", REAL_HOME / ".grok/AGENTS.md",
    REAL_HOME / ".grok/hooks/agentsmd.json", REAL_HOME / ".grok/installed-plugins/registry.json",
    REAL_HOME / ".config/opencode/opencode.json", REAL_HOME / ".config/opencode/opencode.jsonc",
    REAL_HOME / ".config/opencode/AGENTS.md", REAL_HOME / ".config/opencode/skills",
    REAL_HOME / ".config/opencode/plugins",
]
SILENCE = {"opencode": 180}  # seconds without output before a run is killed
TIMEOUT = 1200
SOURCES = {}  # arm -> extracted archive, set per batch
# Per-process prefix, so a batch never mistakes another batch's temporary files for its own.
PREFIX = f"agentsmd-164-{os.getpid()}-"

PROSE = "technical-writing/references/prose.md"
MECHANICS = "writing-for-agents/SKILL-MECHANICS.md"
TEST_DESIGN = "references/test-design.md"
GLOSSARY_FORMAT = "domain-modeling/GLOSSARY-FORMAT.md"
ENTRY = "operations/SKILL.md"

APP = '''def greet(name):
    """Return a greeting."""
    return "Helo, " + name


def add(a, b):
    return a + b


def divide(a, b):
    return a / b
'''

FILES = {
    "README.md": """# Greeter

## Installation

In order to be able to install Greeter, it is basically necessary that you
first of all make sure that you actually have Python installed, and then, once
you have done that, you can then go ahead and simply run the command
`pip install .` which will then install it for you in your environment, which
is what you want to do in order to use it.
""",
    # Project Direction, so the global contract lets work start (without it Codex
    # stops to ask for the triad before any edit).
    "VISION.md": "# Vision\n\nPeople greet each other warmly, in any language.\n",
    "MISSION.md": "# Mission\n\nGreeter gives developers a tiny, dependable greeting library.\n",
    "OBJECTIVE.md": "# Objective\n\nShip a correct, documented and tested 1.0 of Greeter.\n",
    "src/app.py": APP,
    "tests/test_app.py": """import unittest
from src.app import add


class AppTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
""",
    "skills/greet/SKILL.md": """---
name: greet
description: Greeting stuff.
---

# Greet

Call `greet(name)` from `src/app.py` and show the result to the user.
""",
    "GLOSSARY.md": """# Glossary

**Visitor**: a person who opened the site without an account.
_Avoid_: guest
""",
}

# (target, kind, required files, prompt). Prompts never name the required file.
CASES = [
    ("technical-writing", "positive", [PROSE],
     "The Installation section of {repo}/README.md is wordy and hard to follow. Rewrite it so it is clear and short."),
    ("technical-writing", "negative", [PROSE],
     "greet() in {repo}/src/app.py returns 'Helo' instead of 'Hello'. Fix the typo."),
    ("writing-for-agents", "positive", [MECHANICS, PROSE],
     "Agents never pick the greet skill at {repo}/skills/greet/SKILL.md because its description is too vague. Improve the skill so agents select it when a user wants a greeting."),
    ("writing-for-agents", "negative", [MECHANICS, PROSE],
     "Rename add() in {repo}/src/app.py to add_numbers() and update its callers."),
    ("test-design", "positive", [TEST_DESIGN],
     "divide() in {repo}/src/app.py has no test for dividing by zero. Add one."),
    ("test-design", "negative", [TEST_DESIGN],
     "Add a one-line docstring to add() in {repo}/src/app.py."),
    ("domain-modeling", "positive", [GLOSSARY_FORMAT],
     "We agreed to call a paying user a 'member' and to stop saying 'customer'. Record that in the project glossary at {repo}/GLOSSARY.md."),
    ("domain-modeling", "negative", [GLOSSARY_FORMAT],
     "divide() in {repo}/src/app.py should raise ValueError with a clear message when b is 0. Make that change."),
]

READERS = re.compile(r"\b(cat|sed|head|tail|nl|less|awk|bat|grep|rg|python3?)\b")
SHELL_EDIT = re.compile(r"(sed -i|\bcat\s*>|\btee\b|>\s*[\w./-]+\.(py|md)\b|python3? -\s*<<|apply_patch)")
READ_TOOLS = {"Read", "read_file", "read"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "search_replace", "write_file", "edit_file", "create_file",
              "write", "edit", "multiedit", "patch", "apply_patch"}
SHELL_TOOLS = {"Bash", "bash", "run_terminal_command", "shell"}
SKILL_TOOLS = {"Skill", "skill"}


def make_repo():
    root = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX))
    try:
        populate_repo(root)
    except BaseException:
        remove(root)
        raise
    return root


def populate_repo(root):
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (root / "src/__init__.py").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
                   cwd=root, check=True)


def _path(args):
    for key in ("file_path", "target_file", "filePath", "path"):
        if args.get(key):
            return str(args[key])
    return ""


def tool_calls(stream, host="claude"):
    """Ordered (canonical name, path, command, skill) for each tool call in a host stream."""
    seen = set()
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if host == "codex":
            item = event.get("item") or {}
            if event.get("type") not in ("item.started", "item.completed") or item.get("id") in seen:
                continue
            if item.get("type") == "command_execution":
                seen.add(item.get("id"))
                yield "Bash", "", str(item.get("command", "")), ""
            elif item.get("type") == "file_change":
                seen.add(item.get("id"))
                for change in item.get("changes") or [{}]:
                    yield "Edit", str(change.get("path", "")), "", ""
            continue
        if host == "opencode":
            part = event.get("part") or {}
            if event.get("type") != "tool_use" or part.get("callID") in seen:
                continue
            seen.add(part.get("callID"))
            name, args = part.get("tool", ""), (part.get("state") or {}).get("input") or {}
        else:
            if event.get("type") != "assistant":
                continue
            blocks = [b for b in event.get("message", {}).get("content", []) if b.get("type") == "tool_use"]
            for block in blocks:
                if block.get("id") in seen:
                    continue
                seen.add(block.get("id"))
                yield canonical(block.get("name", ""), block.get("input") or {})
            continue
        yield canonical(name, args)


def canonical(name, args):
    if name in READ_TOOLS:
        return "Read", _path(args), "", ""
    if name in EDIT_TOOLS:
        return "Edit", _path(args), "", ""
    if name in SHELL_TOOLS:
        return "Bash", "", str(args.get("command", "")), ""
    if name in SKILL_TOOLS:
        return "Skill", "", "", str(args.get("skill") or args.get("name") or "")
    return name, _path(args), "", ""


BRACES = re.compile(r"([^\s{}'\"]*)\{([^{}\s]*,[^{}\s]*)\}([^\s{}'\"]*)")


def expand_braces(command):
    """Expand shell brace lists (`references/{a,b}.md`) so reads through them are seen."""
    while True:
        match = BRACES.search(command)
        if not match:
            return command
        head, body, tail = match.groups()
        words = " ".join(head + part + tail for part in body.split(","))
        command = command[:match.start()] + words + command[match.end():]


def reads_file(call, f):
    name, path, command, skill = call
    command = expand_braces(command)
    return ((name == "Read" and path.endswith(f))
            or (name == "Bash" and f in command and READERS.search(command) is not None))


def score(stream, required, host="claude"):
    """Return (index of first edit or None, {file: index of first read or None}, entry index or None)."""
    first_edit, reads, entry = None, {f: None for f in required}, None
    for i, call in enumerate(tool_calls(stream, host)):
        name, path, command, skill = call
        for f in required:
            if reads[f] is None and reads_file(call, f):
                reads[f] = i
        if entry is None and ((name == "Skill" and skill.split(":")[-1] == "operations")
                              or reads_file(call, ENTRY)):
            entry = i
        if first_edit is None and (
            (name == "Edit" and "/.claude/" not in path)
            or (name == "Bash" and SHELL_EDIT.search(command))
        ):
            first_edit = i
    return first_edit, reads, entry


class Escaped(Exception):
    pass


def live_config():
    state = {}
    for path in LIVE_CONFIG:
        if path.is_dir():
            state[str(path)] = sorted((p.name, os.readlink(p) if p.is_symlink() else "")
                                      for p in path.iterdir())
        elif path.exists():
            state[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return state


def snapshot(roots=None):
    """Status (including ignored files) and HEAD of every checkout a run must not touch,
    plus the live host configuration."""
    state = {}
    for root in GUARDED if roots is None else roots:
        if (root / ".git").exists():
            git = ["git", "-C", str(root)]
            state[str(root)] = (
                subprocess.run(git + ["status", "--porcelain", "--ignored", "--untracked-files=all"],
                               capture_output=True, text=True, check=True).stdout,
                subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout,
            )
    if roots is None:
        state["live-config"] = live_config()
    return state


def guard_self_check():
    """Prove that the guard sees a new ignored file; raise if it does not."""
    root = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "guard-"))
    try:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("ignored/\n")
        before = snapshot([root])
        (root / "ignored").mkdir()
        (root / "ignored/escape.md").write_text("x")
        if snapshot([root]) == before:
            raise RuntimeError("guard self-check failed: a new ignored file was not detected")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def extract_sources():
    """Archive origin/main and HEAD into a temporary directory; return it."""
    root = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "src-"))
    try:
        for arm, ref in (("main", "origin/main"), ("branch", "HEAD")):
            (root / arm).mkdir()
            archive = subprocess.run(["git", "-C", str(BRANCH), "archive", ref],
                                     capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", str(root / arm)], input=archive, check=True)
            SOURCES[arm] = root / arm
            SOURCES[arm + "-sha"] = subprocess.run(["git", "-C", str(BRANCH), "rev-parse", ref],
                                                   capture_output=True, text=True, check=True).stdout.strip()
    except BaseException:
        remove(root)
        raise
    return root


def cleanup_self_check(host):
    """Prove that a setup failure leaves no temporary repository, HOME or login link.

    The host binary is replaced by a stub on PATH so no model can run; repository
    setup fails after its directory exists, and HOME setup fails after the login
    link exists (missing login source)."""
    global CLAUDE_JSON, FILES
    stub = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "stub-"))
    saved = CLAUDE_JSON, FILES, os.environ["PATH"], dict(LOGIN)
    pattern = os.path.join(tempfile.gettempdir(), PREFIX + "*")
    try:
        (stub / host).write_text("#!/bin/sh\nexit 99\n")
        (stub / host).chmod(0o755)
        os.environ["PATH"] = f"{stub}{os.pathsep}{os.environ['PATH']}"
        existing = set(glob.glob(pattern))
        CLAUDE_JSON = stub / "missing.json"
        for key in LOGIN:
            LOGIN[key] = stub / "missing-auth.json"
        for label in ("home", "repo"):
            if label == "repo":
                CLAUDE_JSON = saved[0]
                LOGIN.update(saved[3])
                FILES = dict(saved[1], **{"README.md/blocked": ""})
            try:
                run(host, "stub", "", "branch", CASES[0], 0)
            except (OSError, ValueError, subprocess.CalledProcessError):
                pass
            else:
                raise RuntimeError(f"cleanup self-check: {label} setup did not fail")
            left = set(glob.glob(pattern)) - existing - {str(stub)}
            if left:
                raise RuntimeError(f"cleanup self-check: {label} setup failure left {sorted(left)}")
        for real in [REAL_HOME / "Library/Keychains", *saved[3].values()]:
            if real.is_symlink() and "agentsmd-164" in os.readlink(real):
                raise RuntimeError(f"cleanup self-check: {real} became a link")
    finally:
        CLAUDE_JSON, FILES, os.environ["PATH"] = saved[:3]
        LOGIN.clear()
        LOGIN.update(saved[3])
        shutil.rmtree(stub, ignore_errors=True)


def link_login(link, source):
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(source)
    if not source.is_file():
        raise FileNotFoundError(f"login source missing: {source}")


def copy_plugin(arm, home):
    plugin = home / "plugin"
    shutil.copytree(SOURCES[arm], plugin, symlinks=True)
    return plugin


def make_home(host, arm):
    """Temporary HOME holding only the arm's plugin copy and linked login; return (home, plugin, env)."""
    home = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "home-"))
    try:
        plugin = copy_plugin(arm, home)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "CODEX_", "GROK_", "OPENCODE_", "XDG_"))}
        env.pop("CLAUDE_CONFIG_DIR", None)
        env["HOME"] = str(home)
        SETUP[host](home, plugin, env)
        return home, plugin, env
    except BaseException:
        remove(home)
        raise


def setup_claude(home, plugin, env):
    config = home / ".claude"
    config.mkdir()
    shutil.copy2(plugin / "global/AGENTS.md", config / "CLAUDE.md")
    (config / "settings.json").write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}))
    # Login: account metadata only (no token), plus a link to the macOS keychain
    # directory so Claude reads the existing login itself. No credential is copied.
    keychains = KEYCHAINS
    if keychains.is_dir():
        (home / "Library").mkdir()
        (home / "Library/Keychains").symlink_to(keychains)
    real = json.loads(CLAUDE_JSON.read_text())
    (home / ".claude.json").write_text(json.dumps(
        {k: real[k] for k in ("oauthAccount", "userID") if k in real}))


def setup_codex(home, plugin, env):
    codex = home / "codex"
    env["CODEX_HOME"] = str(codex)
    link_login(codex / "auth.json", LOGIN["codex"])
    shutil.copy2(plugin / "global/AGENTS.md", codex / "AGENTS.md")
    market = home / "market"
    (market / ".agents/plugins").mkdir(parents=True)
    (market / "plugins").mkdir()
    (market / "plugins/agentsmd").symlink_to(plugin)
    (market / ".agents/plugins/marketplace.json").write_text(json.dumps({"name": "trigtest", "plugins": [{
        "name": "agentsmd", "source": {"source": "local", "path": "./plugins/agentsmd"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools"}]}))
    for cmd in (["codex", "plugin", "marketplace", "add", str(market)],
                ["codex", "plugin", "add", "agentsmd@trigtest"]):
        subprocess.run(cmd, env=env, cwd=home, capture_output=True, check=True, timeout=120)


def setup_grok(home, plugin, env):
    grok = home / "grok"
    env["GROK_HOME"] = str(grok)
    link_login(grok / "auth.json", LOGIN["grok"])
    shutil.copy2(plugin / "global/AGENTS.md", grok / "AGENTS.md")
    # The live setup delivers Project Direction through this global hook file
    # (Grok does not run plugin hooks); here it points at the arm's copy.
    (grok / "hooks").mkdir()
    (grok / "hooks/agentsmd.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [{
        "type": "command", "timeout": 15,
        "command": f'"{plugin}/bin/project-direction" hook'}]}]}}))
    subprocess.run(["grok", "plugin", "install", str(plugin), "--trust"], env=env, cwd=home,
                   capture_output=True, check=True, timeout=120)


def setup_opencode(home, plugin, env):
    config = home / "opencode"
    env.update(OPENCODE_CONFIG_DIR=str(config), XDG_DATA_HOME=str(home / "data"),
               XDG_CACHE_HOME=str(home / "cache"), XDG_CONFIG_HOME=str(home / "config"))
    link_login(home / "data/opencode/auth.json", LOGIN["opencode"])
    (config / "skills").mkdir(parents=True)
    (config / "plugins").mkdir()
    (config / "skills/operations").symlink_to(plugin / "skills/operations")
    (config / "plugins/agentsmd-project-direction.js").symlink_to(plugin / "opencode/agentsmd-project-direction.js")
    shutil.copy2(plugin / "global/AGENTS.md", config / "AGENTS.md")
    allowed = {f"{p}/**": "allow" for p in {str(plugin), str(plugin.resolve())}}
    (config / "opencode.json").write_text(json.dumps({
        "$schema": "https://opencode.ai/config.json",
        "permission": {"edit": "allow", "bash": "allow", "webfetch": "deny",
                       "external_directory": {"*": "deny", **allowed}}}))


SETUP = {"claude": setup_claude, "codex": setup_codex, "grok": setup_grok, "opencode": setup_opencode}


def command(host, model, effort, repo, plugin, prompt):
    if host == "claude":
        cmd = ["claude", "-p", "--model", model, "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--add-dir", str(repo), "--plugin-dir", str(plugin),
               "--no-session-persistence", "--max-turns", "40"]
        return cmd + (["--effort", effort] if effort else []) + [prompt]
    if host == "codex":
        cmd = ["codex", "exec", "--json", "-m", model, "-s", "workspace-write", "-C", str(repo),
               "--skip-git-repo-check", "--ephemeral", "--dangerously-bypass-hook-trust"]
        return cmd + (["-c", f"model_reasoning_effort={effort}"] if effort else []) + [prompt]
    if host == "grok":
        cmd = ["grok", "-p", prompt, "-m", model, "--always-approve", "--sandbox", "workspace",
               "--output-format", "streaming-messages-json", "--max-turns", "40", "--cwd", str(repo)]
        return cmd + (["--reasoning-effort", effort] if effort else [])
    cmd = ["opencode", "run", "--format", "json", "-m", model, "--dir", str(repo)]
    return cmd + (["--variant", effort] if effort else []) + [prompt]


def execute(host, cmd, cwd, env):
    """Run in its own process group with a total timeout and a silence watchdog; kill the group after."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    lines, last = [], [time.monotonic()]

    def reader():
        for line in proc.stdout:
            lines.append(line)
            last[0] = time.monotonic()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    start, silence = time.monotonic(), SILENCE.get(host, TIMEOUT)
    try:
        while proc.poll() is None:
            now = time.monotonic()
            if now - start > TIMEOUT or now - last[0] > silence:
                break
            time.sleep(1)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        thread.join(5)
        proc.stdout.close()
    return "".join(lines)


def anonymize(text, repo, plugin):
    for real, label in ((repo, "<repo>"), (plugin, "<plugin>"), (plugin.parent, "<home>"),
                        (pathlib.Path(tempfile.gettempdir()), "<tmp>"), (REAL_HOME, "~")):
        for form in sorted({str(real), str(real.resolve()), "/private" + str(real)}, key=len, reverse=True):
            text = text.replace(form, label)
    # Temporary-directory paths a model spelled differently.
    text = re.sub(r"(/private)?/var/folders/[\w.-]+/[\w.-]+", "<tmp>", text)
    # Installed plugin caches under the temporary home name the plugin copy too.
    return re.sub(r"<home>/\S*?/(agentsmd-[0-9a-f]+|plugin-[0-9a-f]+|agentsmd/\d+\.\d+\.\d+)/", "<plugin>/", text)


def record(stream, condition, host, model, effort, arm, target, kind, index, required, verdicts, repo, plugin):
    """Compact, anonymized per-run record: tool calls up to and including the first edit."""
    first_edit, reads, entry = score(stream, required, host)
    calls = []
    for i, (name, path, command_text, skill) in enumerate(tool_calls(stream, host)):
        if first_edit is not None and i > first_edit:
            break
        if path:
            calls.append([name, anonymize(path, repo, plugin)])
        elif name == "Bash":
            calls.append([name, anonymize(" ".join(command_text.split()), repo, plugin)])
        elif skill:
            calls.append([name, skill])
        else:
            calls.append([name])
    item = {"condition": condition, "host": HOST_LABEL.get(host, host), "model": model, "arm": arm,
            "target": target, "kind": kind, "run": index, "first_edit": first_edit,
            "required_read_at": {f.split("/")[-1]: reads[f] for f in required},
            "verdict": {f.split("/")[-1]: v for f, v in verdicts.items()}, "calls": calls}
    if effort:
        item["effort"] = effort
    item["entry_loaded_at"] = entry
    item["tool_calls"] = sum(1 for _ in tool_calls(stream, host))
    if arm + "-sha" in SOURCES:
        item["source"] = SOURCES[arm + "-sha"][:7]
    return item


HOST_LABEL = {"claude": "claude-code"}


def verdicts_for(kind, required, first_edit, reads):
    result = {}
    for f in required:
        read = reads[f]
        if kind == "positive":
            verdict = "fired" if read is not None and (first_edit is None or read < first_edit) else "skip"
            if first_edit is None and read is None:
                verdict = "skip-noedit"
        else:
            verdict = "opened" if read is not None else "clean"
        result[f] = verdict
    return result


def remove(path):
    if path is None:
        return
    for link in (path / "Library/Keychains", path / "codex/auth.json", path / "grok/auth.json",
                 path / "data/opencode/auth.json"):
        if link.is_symlink():
            link.unlink()
    shutil.rmtree(path, ignore_errors=True)


def run(host, model, effort, arm, case, index, before=None, condition="plain-confined"):
    repo = home = None
    try:
        repo = make_repo()
        home, plugin, env = make_home(host, arm)
        return run_in(host, model, effort, arm, case, index, before, condition, repo, home, plugin, env)
    finally:
        remove(repo)
        remove(home)


def login_sources(host):
    """The real login files or directories linked into a run's temporary home."""
    return [KEYCHAINS] if host == "claude" else [LOGIN[host]]


def fingerprint(path):
    """SHA-256 and mtime of a file, or of each top-level file of a directory; None if missing."""
    def one(f):
        return hashlib.sha256(f.read_bytes()).hexdigest(), f.stat().st_mtime_ns
    try:
        if path.is_dir():
            return sorted((f.name, *one(f)) for f in path.iterdir() if f.is_file())
        return one(path) if path.is_file() else None
    except OSError as error:  # unreadable: record that it could not be compared
        return f"unreadable: {error.__class__.__name__}"


def login_changes(before, after):
    """Labels of linked login sources whose fingerprint differs; visible only, never blocking.

    Runs share the real login files, so under --jobs > 1 a change can come from a
    concurrent run of the same host (a token refresh) rather than this one."""
    return sorted("~/" + str(path.relative_to(REAL_HOME)) if path.is_relative_to(REAL_HOME) else str(path)
                  for path in before if before[path] != after.get(path))


def run_in(host, model, effort, arm, case, index, before, condition, repo, home, plugin, env):
    target, kind, required, prompt = case
    prompt = prompt.format(repo=repo.resolve())
    logins = {path: fingerprint(path) for path in login_sources(host)}
    stream = execute(host, command(host, model, effort, repo, plugin, prompt), repo, env)
    login_changed = login_changes(logins, {path: fingerprint(path) for path in logins})
    after = snapshot() if before is not None else None
    if after != before:
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        raise Escaped(f"{changed} changed during {host} {arm} {target} {kind} run {index}")
    first_edit, reads, entry = score(stream, required, host)
    verdicts = verdicts_for(kind, required, first_edit, reads)
    if next(tool_calls(stream, host), None) is None:
        # No tool call at all: a provider error or rate limit, not a measurement.
        verdicts = {f: "no-output" for f in required}
    rows = ["\t".join([arm, target, kind, f, str(index), verdicts[f], str(first_edit), str(reads[f]),
                       str(entry), host, model]) for f in required]
    item = record(stream, condition, host, model, effort, arm, target, kind, index, required,
                  verdicts, repo, plugin)
    item["login_files_changed"] = login_changed
    return rows, item


def summarize(path):
    counts, entries = {}, {}
    for line in open(path):
        arm, target, kind, f, index, verdict, _, _, entry, *_ = line.rstrip("\n").split("\t")
        key = (target, kind, f, arm)
        if verdict == "no-output":
            continue
        good = verdict == ("fired" if kind == "positive" else "clean")
        hits, total = counts.get(key, (0, 0))
        counts[key] = (hits + good, total + 1)
        entries[(arm, target, kind, index)] = entry != "None"
    print("| Target | Prompt | File | main | branch |")
    print("| --- | --- | --- | --- | --- |")
    for target, kind, f in sorted({k[:3] for k in counts}, key=lambda k: (k[0], k[1] != "positive", k[2])):
        cells = []
        for arm in ("main", "branch"):
            hits, total = counts.get((target, kind, f, arm), (0, 0))
            cells.append(f"{hits}/{total}")
        label = "naive: read before first edit" if kind == "positive" else "negative: never opened"
        print(f"| {target} | {label} | `{f.split('/')[-1]}` | {cells[0]} | {cells[1]} |")
    for arm in ("main", "branch"):
        runs = [v for k, v in entries.items() if k[0] == arm]
        print(f"\nEntry point loaded, {arm}: {sum(runs)}/{len(runs)}", end="")
    print()


def login_status(record):
    """`unknown` when `login_files_changed` is null (runs before c35c736 did not record
    it), `unchanged` for an empty list, `changed` for a non-empty list."""
    value = record["login_files_changed"]
    if value is None:
        return "unknown"
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return "changed" if value else "unchanged"
    raise ValueError(f"login_files_changed must be null or a list of paths, not {value!r}")


def summarize_records(path, condition="plain-confined"):
    """Markdown tables per host and model from records.jsonl (runs with a `source` field)."""
    groups = {}
    for line in open(path):
        r = json.loads(line)
        login_status(r)  # validates the field; the tables do not depend on it
        if r.get("condition") == condition and "source" in r and "discarded" not in r:
            groups.setdefault((r["host"], r["model"], r.get("effort", "")), []).append(r)
    for (host, model, effort), rs in groups.items():
        valid = [r for r in rs if "no-output" not in r["verdict"].values()]
        print(f"\n### {host}, `{model}`" + (f", effort {effort}" if effort else ""))
        print(f"\n{len(valid)} of {len(rs)} runs valid (a run with no tool call is excluded).\n")
        print("| Measure | main | branch |\n| --- | --- | --- |")
        measures = [
            ("Entry point loaded, naive prompts", "positive", lambda r: r["entry_loaded_at"] is not None),
            ("Entry point loaded, negative prompts", "negative", lambda r: r["entry_loaded_at"] is not None),
            ("Target read before first edit (naive, every required file)", "positive",
             lambda r: all(v == "fired" for v in r["verdict"].values())),
            ("Negative clean (target never opened)", "negative",
             lambda r: all(v == "clean" for v in r["verdict"].values())),
        ]
        for label, kind, pred in measures:
            cells = [[pred(r) for r in valid if r["arm"] == arm and r["kind"] == kind] for arm in ("main", "branch")]
            print(f"| {label} | {sum(cells[0])}/{len(cells[0])} | {sum(cells[1])}/{len(cells[1])} |")
        files = sorted({(r["target"], f) for r in valid if r["kind"] == "positive" for f in r["verdict"]})
        for target, f in files:
            cells = [[r["verdict"][f] == "fired" for r in valid
                      if r["arm"] == arm and r["kind"] == "positive" and r["target"] == target]
                     for arm in ("main", "branch")]
            print(f"| Naive, {target} `{f}` read before first edit | {sum(cells[0])}/{len(cells[0])} "
                  f"| {sum(cells[1])}/{len(cells[1])} |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=sorted(SETUP), default="claude")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--arms", default="main,branch")
    parser.add_argument("--targets", help="comma-separated targets to run (default: all)")
    parser.add_argument("--score")
    parser.add_argument("--summary", help="print per-host tables from a records file")
    parser.add_argument("--record", help="append one JSON line per run to this file")
    parser.add_argument("--self-check", action="store_true", help="only run the guard and cleanup self-checks")
    args = parser.parse_args()
    if args.score:
        summarize(args.score)
        return
    if args.summary:
        summarize_records(args.summary)
        return
    cases = [c for c in CASES if not args.targets or c[0] in args.targets.split(",")]
    # Arms interleave, so a quota or rate limit reached mid-batch hits both alike.
    jobs = [(arm, case, i) for case in cases for i in range(args.runs) for arm in args.arms.split(",")]
    sources = extract_sources()
    try:
        guard_self_check()
        cleanup_self_check(args.host)
        if args.self_check:
            print(f"{args.host}: guard and cleanup self-checks OK")
            return
        before = snapshot()
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            futures = [pool.submit(run, args.host, args.model, args.effort, *job, before=before)
                       for job in jobs]
            items = []
            # A record file inside a guarded checkout is written after the batch; elsewhere
            # per run, so an abort keeps the completed runs.
            record = pathlib.Path(args.record).resolve() if args.record else None
            stream_records = record is not None and not any(
                record.is_relative_to(root.resolve()) for root in GUARDED)
            try:
                for future in futures:
                    rows, item = future.result()
                    for row in rows:
                        print(row, flush=True)
                    items.append(item)
                    if stream_records:
                        with open(args.record, "a") as out:
                            out.write(json.dumps(item) + "\n")
            except Escaped as error:
                for pending in futures:
                    pending.cancel()
                print(f"ABORT: {error}", file=sys.stderr)
                return 2
        # Records are written after the batch: the file may sit in a guarded checkout.
        if args.record and not stream_records:
            with open(args.record, "a") as out:
                out.writelines(json.dumps(item) + "\n" for item in items)
    finally:
        remove(sources)


if __name__ == "__main__":
    sys.exit(main())
