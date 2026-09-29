#!/usr/bin/env python3
"""Before-and-after trigger test for Issue #164 (evidence only, not a release gate).

Each case runs `claude -p --model haiku` in a fresh throwaway git repository
under the system temp directory, once per arm:

  main    a copy of the newest installed AgentsMD plugin
  branch  a copy of this checkout

A positive case fires when the required file is read before the first file
edit. A negative case passes when the file is never read. Scores go to stdout;
with --record, one compact line per run (tool calls up to the first edit,
paths anonymized, no prompts or file contents) is appended to a JSONL file.
Raw streams are never kept: they may hold private context.

Confinement (added after a run escaped into the canonical checkout on
2026-09-29): each run gets a temporary HOME whose `.claude` (CLAUDE_CONFIG_DIR
left unset, so it resolves there) holds only the global contract, and a copy of
the plugin under test loaded with --plugin-dir. It runs with
`--permission-mode acceptEdits --add-dir <temp repo>` instead of skipping
permissions, and names files by absolute in-repo path. After every run the
canonical checkout and this checkout must show the same `git status
--porcelain --ignored --untracked-files=all` and HEAD as before the batch, or
the batch aborts; every batch first proves that the guard sees a new ignored
file and that a setup failure leaves nothing behind (--self-check runs only
those). New files, including ignored ones, are
caught; content edits to an already-ignored file are not.

Login: the temporary HOME gets the account metadata from ~/.claude.json (no
token) and a symlink to ~/Library/Keychains so Claude reads the existing login
itself. No credential is copied. The link, the temporary HOME and the temporary
repository exist only for the run's lifetime: they are removed in a `finally`,
also on failure, timeout or abort.

  python3 trigger_test.py --runs 5 --jobs 8 --record records.jsonl > results.tsv
  python3 trigger_test.py --runs 5 --jobs 8 --entry --record records.jsonl > results-entry.tsv
  python3 trigger_test.py --score results.tsv
  python3 trigger_test.py --record-from results.tsv plain-unconfined > records.jsonl

--entry prefixes each prompt with `/agentsmd:operations`, so the entry point is
loaded and only the routing and procedure wording is under test.
"""
import argparse
import concurrent.futures
import glob
import json
import pathlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

BRANCH = pathlib.Path(__file__).resolve().parents[3]
CANONICAL = pathlib.Path.home() / "dev/toolboxmd/agentsmd"
INSTALLED = pathlib.Path.home() / ".claude/plugins/cache/toolboxmd/agentsmd"
GUARDED = [CANONICAL, BRANCH]
CLAUDE_JSON = pathlib.Path.home() / ".claude.json"

PROSE = "technical-writing/references/prose.md"
MECHANICS = "writing-for-agents/SKILL-MECHANICS.md"
TEST_DESIGN = "references/test-design.md"
GLOSSARY_FORMAT = "domain-modeling/GLOSSARY-FORMAT.md"

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

READERS = re.compile(r"\b(cat|sed|head|tail|nl|less|awk|bat|grep)\b")
SHELL_EDIT = re.compile(r"(sed -i|\bcat\s*>|\btee\b|>\s*[\w./-]+\.(py|md)\b|python3? -\s*<<)")


def make_repo():
    root = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-164-"))
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


def tool_calls(stream):
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                yield block.get("name", ""), block.get("input", {})


def score(stream, required):
    """Return (index of first edit or None, {file: index of first read or None})."""
    first_edit, reads = None, {f: None for f in required}
    for i, (name, args) in enumerate(tool_calls(stream)):
        path = str(args.get("file_path", ""))
        command = str(args.get("command", ""))
        for f in required:
            if reads[f] is None and (
                (name == "Read" and path.endswith(f))
                or (name == "Bash" and f in command and READERS.search(command))
            ):
                reads[f] = i
        if first_edit is None and (
            (name in ("Edit", "Write", "MultiEdit") and "/.claude/" not in path)
            or (name == "Bash" and SHELL_EDIT.search(command))
        ):
            first_edit = i
    return first_edit, reads


class Escaped(Exception):
    pass


def snapshot(roots=None):
    """Status (including ignored files) and HEAD of every checkout a run must not touch."""
    state = {}
    for root in GUARDED if roots is None else roots:
        if (root / ".git").exists():
            git = ["git", "-C", str(root)]
            state[str(root)] = (
                subprocess.run(git + ["status", "--porcelain", "--ignored", "--untracked-files=all"],
                               capture_output=True, text=True, check=True).stdout,
                subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True).stdout,
            )
    return state


def guard_self_check():
    """Prove that the guard sees a new ignored file; raise if it does not."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-164-guard-"))
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


def plugin_source(arm):
    if arm == "branch":
        return BRANCH
    return max(INSTALLED.iterdir(), key=lambda p: [int(x) for x in p.name.split(".")])


def cleanup_self_check():
    """Prove that a setup failure leaves no temporary repository, HOME or keychain link.

    `claude` is replaced by a stub on PATH so no model can run; repository setup
    fails after its directory exists, and HOME setup fails after the keychain link
    exists (unreadable account file)."""
    global CLAUDE_JSON, FILES
    stub = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-164-stub-"))
    saved = CLAUDE_JSON, FILES, os.environ["PATH"]
    pattern = os.path.join(tempfile.gettempdir(), "agentsmd-164-*")
    try:
        (stub / "claude").write_text("#!/bin/sh\nexit 99\n")
        (stub / "claude").chmod(0o755)
        os.environ["PATH"] = f"{stub}{os.pathsep}{os.environ['PATH']}"
        existing = set(glob.glob(pattern))
        CLAUDE_JSON = stub / "missing.json"
        for label in ("home", "repo"):
            if label == "repo":
                CLAUDE_JSON, FILES = saved[0], dict(saved[1], **{"README.md/blocked": ""})
            try:
                run("branch", CASES[0], 0)
            except (OSError, ValueError):
                pass
            else:
                raise RuntimeError(f"cleanup self-check: {label} setup did not fail")
            left = set(glob.glob(pattern)) - existing - {str(stub)}
            if left:
                raise RuntimeError(f"cleanup self-check: {label} setup failure left {sorted(left)}")
        keychains = pathlib.Path.home() / "Library/Keychains"
        if keychains.is_symlink():
            raise RuntimeError("cleanup self-check: the real keychain directory became a link")
    finally:
        CLAUDE_JSON, FILES, os.environ["PATH"] = saved
        shutil.rmtree(stub, ignore_errors=True)


def make_home(arm):
    """Temporary HOME whose Claude config holds only the plugin under test."""
    home = pathlib.Path(tempfile.mkdtemp(prefix="agentsmd-164-home-"))
    try:
        return home, populate_home(home, arm)
    except BaseException:
        remove(home)
        raise


def populate_home(home, arm):
    config = home / ".claude"
    config.mkdir()
    plugin = home / "plugin"
    source = plugin_source(arm)
    if (source / ".git").exists():
        files = subprocess.run(["git", "-C", str(source), "ls-files", "-co", "--exclude-standard"],
                               capture_output=True, text=True, check=True).stdout.split()
        for rel in files:
            if (source / rel).is_file():
                (plugin / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / rel, plugin / rel)
    else:
        shutil.copytree(source, plugin)
    shutil.copy2(plugin / "global/AGENTS.md", config / "CLAUDE.md")
    (config / "settings.json").write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}))
    # Login: account metadata only (no token), plus a link to the macOS keychain
    # directory so Claude reads the existing login itself. No credential is copied.
    # Without both a fresh HOME reports "Not logged in".
    keychains = pathlib.Path.home() / "Library/Keychains"
    if keychains.is_dir():
        (home / "Library").mkdir()
        (home / "Library/Keychains").symlink_to(keychains)
    real = json.loads(CLAUDE_JSON.read_text())
    (home / ".claude.json").write_text(json.dumps(
        {k: real[k] for k in ("oauthAccount", "userID") if k in real}))
    return plugin


def anonymize(text, repo, plugin):
    for real, label in ((repo, "<repo>"), (plugin, "<plugin>"), (plugin.parent, "<home>"),
                        (pathlib.Path.home(), "~")):
        for form in sorted({str(real), str(real.resolve()), "/private" + str(real)}, key=len, reverse=True):
            text = text.replace(form, label)
    return text


def record(stream, condition, arm, target, kind, index, required, verdicts, repo, plugin):
    """Compact, anonymized per-run record: tool calls up to and including the first edit."""
    first_edit, reads = score(stream, required)
    calls = []
    for i, (name, args) in enumerate(tool_calls(stream)):
        if first_edit is not None and i > first_edit:
            break
        if name in ("Read", "Edit", "Write", "MultiEdit"):
            calls.append([name, anonymize(str(args.get("file_path", "")), repo, plugin)])
        elif name == "Bash":
            calls.append([name, anonymize(" ".join(str(args.get("command", "")).split())[:200], repo, plugin)])
        else:
            calls.append([name])
    return {"condition": condition, "host": "claude-code", "model": "haiku", "arm": arm,
            "target": target, "kind": kind, "run": index, "first_edit": first_edit,
            "required_read_at": {f.split("/")[-1]: reads[f] for f in required},
            "verdict": {f.split("/")[-1]: v for f, v in verdicts.items()}, "calls": calls}


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
    link = path / "Library/Keychains"
    if link.is_symlink():
        link.unlink()
    shutil.rmtree(path, ignore_errors=True)


def run(arm, case, index, entry=False, before=None, condition=None):
    repo = home = None
    try:
        repo = make_repo()
        home, plugin = make_home(arm)
        return run_in(arm, case, index, entry, before, condition, repo, home, plugin)
    finally:
        remove(repo)
        remove(home)


def run_in(arm, case, index, entry, before, condition, repo, home, plugin):
    target, kind, required, prompt = case
    prompt = prompt.format(repo=repo.resolve())
    cmd = ["claude", "-p", "--model", "haiku", "--output-format", "stream-json", "--verbose",
           "--permission-mode", "acceptEdits", "--add-dir", str(repo), "--plugin-dir", str(plugin),
           "--no-session-persistence", "--max-turns", "40"]
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE"))}
    # CLAUDE_CONFIG_DIR stays unset so it resolves to the temporary HOME/.claude
    # while macOS keeps finding the login under its default keychain entry name.
    env.pop("CLAUDE_CONFIG_DIR", None)
    env["HOME"] = str(home)
    try:
        if entry:
            prompt = "/agentsmd:operations " + prompt
        result = subprocess.run(cmd + [prompt], cwd=repo, env=env, capture_output=True, text=True,
                                timeout=900)
        stream = result.stdout
    except subprocess.TimeoutExpired as error:
        stream = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
    if before is not None and snapshot() != before:
        raise Escaped(f"guarded checkout changed during {arm} {target} {kind} run {index}")
    loaded = next((p.get("path") for line in stream.splitlines()[:20] if '"init"' in line
                   for p in json.loads(line).get("plugins", []) if p.get("name") == "agentsmd"), "?")
    first_edit, reads = score(stream, required)
    verdicts = verdicts_for(kind, required, first_edit, reads)
    rows = ["\t".join([arm, target, kind, f, str(index), verdicts[f], str(first_edit), str(reads[f]),
                       anonymize(loaded, repo, plugin), "<repo>"]) for f in required]
    condition = condition or ("entry" if entry else "plain") + "-confined"
    return rows, record(stream, condition, arm, target, kind, index, required, verdicts, repo, plugin)


def records_from(tsv, condition, discard=()):
    """Records for runs whose streams are still on disk (runs made before --record existed)."""
    cases = {(c[0], c[1]): c for c in CASES}
    seen = set()
    for line in open(tsv):
        arm, target, kind, _, index, _, _, _, loaded, repo = line.rstrip("\n").split("\t")
        if (repo, arm) in seen:
            continue
        seen.add((repo, arm))
        required = cases[(target, kind)][2]
        stream = (pathlib.Path(repo) / ".stream.jsonl").read_text()
        first_edit, reads = score(stream, required)
        item = record(stream, condition, arm, target, kind, int(index), required,
                      verdicts_for(kind, required, first_edit, reads),
                      pathlib.Path(repo), pathlib.Path(loaded))
        if target in discard:
            item["discarded"] = "escaped its repository; rerun confined"
        yield item


def summarize(path):
    counts = {}
    for line in open(path):
        arm, target, kind, f, _, verdict, *_ = line.rstrip("\n").split("\t")
        key = (target, kind, f, arm)
        good = verdict == ("fired" if kind == "positive" else "clean")
        hits, total = counts.get(key, (0, 0))
        counts[key] = (hits + good, total + 1)
    print("| Target | Prompt | File | main (installed) | branch |")
    print("| --- | --- | --- | --- | --- |")
    for target, kind, f in sorted({k[:3] for k in counts}, key=lambda k: (k[0], k[1] != "positive", k[2])):
        cells = []
        for arm in ("main", "branch"):
            hits, total = counts.get((target, kind, f, arm), (0, 0))
            cells.append(f"{hits}/{total}")
        label = "naive: read before first edit" if kind == "positive" else "negative: never opened"
        print(f"| {target} | {label} | `{f.split('/')[-1]}` | {cells[0]} | {cells[1]} |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--arms", default="main,branch")
    parser.add_argument("--targets", help="comma-separated targets to run (default: all)")
    parser.add_argument("--score")
    parser.add_argument("--record", help="append one JSON line per run to this file")
    parser.add_argument("--record-from", nargs=2, metavar=("TSV", "CONDITION"),
                        help="print records for a batch whose streams are still on disk")
    parser.add_argument("--discard", default="", help="with --record-from: targets to mark discarded")
    parser.add_argument("--self-check", action="store_true", help="only prove the guard sees ignored files")
    parser.add_argument("--entry", action="store_true",
                        help="prefix each prompt with /agentsmd:operations to load the entry point")
    args = parser.parse_args()
    if args.score:
        summarize(args.score)
        return
    if args.record_from:
        for item in records_from(*args.record_from, discard=args.discard.split(",")):
            print(json.dumps(item))
        return
    cases = [c for c in CASES if not args.targets or c[0] in args.targets.split(",")]
    jobs = [(arm, case, i) for arm in args.arms.split(",") for case in cases for i in range(args.runs)]
    guard_self_check()
    cleanup_self_check()
    if args.self_check:
        print("guard and cleanup self-checks OK")
        return
    before = snapshot()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        futures = [pool.submit(run, *job, entry=args.entry, before=before) for job in jobs]
        try:
            for future in futures:
                rows, item = future.result()
                for row in rows:
                    print(row, flush=True)
                if args.record:
                    with open(args.record, "a") as out:
                        out.write(json.dumps(item) + "\n")
        except Escaped as error:
            for pending in futures:
                pending.cancel()
            print(f"ABORT: {error}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
