#!/usr/bin/env python3
"""Matched comparison for Issue #199 (evidence only, not a release gate).

Two arms, each a `git archive` of one commit of this repository:

  current  main 2f04c90: today's core
  split    8c0048e: smaller core plus skills/operations/references/tracked-work.md

Every run gets a fresh temporary root holding a HOME, a fixture repository
whose `origin` looks like https://github.com/example/greeter.git but is a local
bare repository (git `insteadOf`), and a recording `gh` stub on PATH. Nothing
reaches GitHub. The arm's `global/AGENTS.md` sits at the host's real global
instruction path inside that HOME (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`)
as a link into the arm's plugin copy, as a live install links it into the
canonical clone. Before each run the harness checks that the link resolves to
the arm's core (SHA-256); `canary` runs ask the model which heading follows
"Project language", which differs between the arms.

Confinement and guards come from ../164-trigger-audit/trigger_test.py: the
canonical checkout, this checkout and the live host configuration must be
unchanged after every run or the batch aborts. Records go to a directory
outside this checkout during a batch.

  python3 harness.py --host claude --tasks bug,feature,email --runs 3 --out /tmp/x
  python3 harness.py --summary records.jsonl
"""
import argparse
import concurrent.futures
import gzip
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "164-trigger-audit"))
import trigger_test as tt  # noqa: E402

REPO_ROOT = HERE.parents[2]
ARMS = {"current": "2f04c90", "split": "8c0048e"}
MODELS = {"claude": ("claude-opus-5-5", "medium"), "codex": ("gpt-6.1-sol", "medium")}
REAL_HOME = pathlib.Path.home()
CLAUDE_CREDENTIALS = REAL_HOME / ".claude/.credentials.json"
CODEX_AUTH = REAL_HOME / ".codex/auth.json"
TIMEOUT = 1800
PREFIX = f"agentsmd-199-{os.getpid()}-"
SOURCES = {}
CANARY_HEADING = {"current": "## Delivery", "split": "## Procedures and tracked work"}
TRACKED_WORK = "references/tracked-work.md"
STOP = {}  # host -> reason, set when a provider limit is hit
LIMIT = re.compile(r"(usage limit|rate limit|hit your limit|quota|429 Too Many|insufficient_quota)", re.I)

APP = '''def greet(name):
    return f"Hello, {name}!"


def add(a, b):
    return a + b


def divide(a, b):
    return a / b
'''
TESTS = '''import unittest

import app


class AppTests(unittest.TestCase):
    def test_greet(self):
        self.assertEqual(app.greet("Ada"), "Hello, Ada!")

    def test_add(self):
        self.assertEqual(app.add(2, 3), 5)

    def test_divide(self):
        self.assertEqual(app.divide(6, 3), 2)


if __name__ == "__main__":
    unittest.main()
'''
FILES = {
    "app.py": APP,
    "test_app.py": TESTS,
    "README.md": "# greeter\n\nA tiny greeting library used by the example team.\n\n"
                 "Run the tests with `python3 -m unittest`.\n",
    "VISION.md": "# Vision\n\nEvery example-team service greets people warmly and correctly.\n",
    "MISSION.md": "# Mission\n\ngreeter provides small, well-tested greeting and arithmetic helpers.\n",
    "OBJECTIVE.md": "# Objective\n\nA dependable 1.0 of greeter: every helper is tested and its errors are clear.\n",
}

TASKS = {
    "bug": ("code", "In the greeter repository at {repo}, `divide(a, b)` in app.py raises a bare "
                    "ZeroDivisionError when b is 0. It should raise ValueError(\"b must not be zero\") "
                    "instead. Fix it with a test, and handle it end to end on GitHub (example/greeter) "
                    "the way you normally deliver work."),
    "feature": ("code", "Add a `farewell(name)` function to app.py in the greeter repository at {repo} "
                        "that returns \"Goodbye, {{name}}!\", with a test. You have Delivery Authority "
                        "for this change in example/greeter."),
    "email": ("noncode", "Draft an email to our packaging supplier, Kestrel Packaging (contact: Dana "
                         "Okafor), asking to move delivery of our 2,000-box order KP-4471 from November 3 "
                         "to November 10, because our warehouse move slipped a week. Keep it short and "
                         "friendly. Reply with the email only."),
    "canary": ("canary", "Without using any tools, reply with only the exact text of the Markdown "
                         "heading that comes immediately after the `## Project language` section in "
                         "your global instructions file."),
}

GH_STUB = r'''#!/usr/bin/env python3
# Recording gh stub for Issue #199 runs: logs every call, never reaches GitHub.
import json, os, sys, time
LOG = "@LOG@"
STATE = LOG + ".state"
args = sys.argv[1:]
state = json.load(open(STATE)) if os.path.exists(STATE) else {"n": 0, "items": {}}
def opt(*names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None
body = opt("--body", "-b")
body_file = opt("--body-file", "-F")
if body_file == "-":
    body = sys.stdin.read()
elif body_file:
    try:
        body = open(body_file).read()
    except OSError:
        body = None
rec = {"t": time.time(), "argv": args, "cwd": os.getcwd(), "title": opt("--title", "-t"), "body": body}
with open(LOG, "a") as f:
    f.write(json.dumps(rec) + "\n")
words = [a for a in args if not a.startswith("-")]
cmd = " ".join(words[:2])
want_json = "--json" in args
def new(kind):
    state["n"] += 1
    n = state["n"]
    state["items"][str(n)] = {"kind": kind, "title": rec["title"], "body": body}
    json.dump(state, open(STATE, "w"))
    return f"https://github.com/example/greeter/{'issues' if kind == 'issue' else 'pull'}/{n}"
def item(kind):
    ref = next((w for w in words[2:] if w.strip("#").isdigit()), None)
    if ref is None:
        ns = [k for k, v in state["items"].items() if v["kind"] == kind]
        ref = ns[-1] if ns else "1"
    v = state["items"].get(ref.strip("#"), {"title": "", "body": ""})
    return int(ref.strip("#")), v
if cmd == "auth status":
    print("github.com\n  Logged in to github.com account fixture-dev (keyring)")
elif cmd in ("issue create", "pr create"):
    print(new("issue" if cmd.startswith("issue") else "pr"))
elif cmd in ("issue view", "pr view"):
    n, v = item("issue" if cmd.startswith("issue") else "pr")
    data = {"number": n, "title": v.get("title"), "body": v.get("body"), "state": "OPEN",
            "url": f"https://github.com/example/greeter/{'issues' if cmd.startswith('issue') else 'pull'}/{n}",
            "comments": [], "labels": [], "headRefName": "", "baseRefName": "main",
            "isDraft": False, "mergeable": "MERGEABLE", "statusCheckRollup": [], "reviewDecision": ""}
    print(json.dumps(data) if want_json else f"title:\t{v.get('title')}\nstate:\tOPEN\nnumber:\t{n}\n--\n{v.get('body') or ''}")
elif cmd in ("issue list", "pr list", "search issues", "search prs"):
    print("[]" if want_json else "")
elif cmd == "repo view":
    print(json.dumps({"nameWithOwner": "example/greeter", "name": "greeter", "owner": {"login": "example"},
                      "defaultBranchRef": {"name": "main"}, "url": "https://github.com/example/greeter"})
          if want_json else "example/greeter")
elif cmd == "pr merge":
    print("Merged pull request")
elif cmd == "pr checks":
    print("no checks reported on the branch")
elif words[:1] == ["api"]:
    print("{}")
elif cmd in ("issue comment", "pr comment"):
    print("https://github.com/example/greeter/issues/1#issuecomment-1")
sys.exit(0)
'''


def extract_sources():
    root = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "src-"))
    for arm, ref in ARMS.items():
        dest = root / arm
        dest.mkdir()
        archive = subprocess.run(["git", "-C", str(REPO_ROOT), "archive", ref], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", str(dest)], input=archive, check=True)
        # Experiment records and tests are not part of either arm's plugin.
        for rel in ("docs/work", "tests", "evals"):
            shutil.rmtree(dest / rel, ignore_errors=True)
        SOURCES[arm] = dest
        SOURCES[arm + "-sha"] = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", ref],
                                               capture_output=True, text=True, check=True).stdout.strip()
        SOURCES[arm + "-core"] = tt.hashlib.sha256((dest / "global/AGENTS.md").read_bytes()).hexdigest()
    return root


def git(*args, cwd=None, env=None, check=True):
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=check).stdout.strip()


def make_run(host, arm):
    """Return (root, home, plugin, repo, desk, env)."""
    root = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "run-"))
    try:
        home, ext = root / "home", root / "ext"
        home.mkdir()
        ext.mkdir()
        plugin = home / "plugin"
        shutil.copytree(SOURCES[arm], plugin, symlinks=True)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "CODEX_", "XDG_", "T3", "GIT_", "VERSIONCTL"))}
        env.pop("CLAUDE_CONFIG_DIR", None)
        env["HOME"] = str(home)
        origin = ext / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        (home / ".gitconfig").write_text(
            "[user]\n\tname = Fixture Dev\n\temail = dev@example.com\n[init]\n\tdefaultBranch = main\n"
            f"[url \"{origin}\"]\n\tinsteadOf = https://github.com/example/greeter.git\n")
        (home / "bin").mkdir()
        (home / "bin/gh").write_text(GH_STUB.replace("@LOG@", str(ext / "gh.log")))
        (home / "bin/gh").chmod(0o755)
        env["PATH"] = f"{home / 'bin'}{os.pathsep}{env['PATH']}"
        repo = root / "greeter"
        repo.mkdir()
        for rel, text in FILES.items():
            (repo / rel).write_text(text)
        git("init", "-q", cwd=repo, env=env)
        git("add", "-A", cwd=repo, env=env)
        git("commit", "-qm", "Initial greeter", cwd=repo, env=env)
        git("remote", "add", "origin", "https://github.com/example/greeter.git", cwd=repo, env=env)
        git("push", "-q", "-u", "origin", "main", cwd=repo, env=env)
        desk = root / "desk"
        desk.mkdir()
        if host == "claude":
            setup_claude(home, plugin, root)
        else:
            setup_codex(home, plugin, env)
        return root, home, plugin, repo, desk, env
    except BaseException:
        tt.remove(root)
        raise


def setup_claude(home, plugin, root):
    config = home / ".claude"
    config.mkdir()
    (config / "CLAUDE.md").symlink_to(plugin / "global/AGENTS.md")
    (config / ".credentials.json").symlink_to(CLAUDE_CREDENTIALS)
    settings = tt.claude_settings(home)
    settings["sandbox"]["filesystem"]["denyRead"] = [str(REAL_HOME)]
    (config / "settings.json").write_text(json.dumps(settings))
    real = json.loads(tt.CLAUDE_JSON.read_text())
    (home / ".claude.json").write_text(json.dumps(
        {k: real[k] for k in ("oauthAccount", "userID", "hasCompletedOnboarding") if k in real}))


def setup_codex(home, plugin, env):
    codex = home / ".codex"
    codex.mkdir()
    env["CODEX_HOME"] = str(codex)
    (codex / "auth.json").symlink_to(CODEX_AUTH)
    (codex / "AGENTS.md").symlink_to(plugin / "global/AGENTS.md")
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


def command(host, cwd, root, plugin, prompt):
    model, effort = MODELS[host]
    if host == "claude":
        return ["claude", "-p", "--model", model, "--effort", effort, "--output-format", "stream-json",
                "--verbose", "--permission-mode", "acceptEdits", "--add-dir", str(cwd),
                "--add-dir", str(plugin), "--add-dir", str(root / "ext"), "--plugin-dir", str(plugin),
                "--allowedTools", "Bash", "--max-turns", "120", prompt]
    return ["codex", "exec", "--json", "-m", model, "-c", f"model_reasoning_effort={effort}",
            "-s", "workspace-write", "-C", str(cwd), "--skip-git-repo-check",
            "--dangerously-bypass-hook-trust", prompt]


def core_at_path(host, home):
    path = home / (".claude/CLAUDE.md" if host == "claude" else ".codex/AGENTS.md")
    return {"path": str(path).replace(str(home), "~"), "is_link": path.is_symlink(),
            "sha256": tt.hashlib.sha256(path.read_bytes()).hexdigest()}


def observer(host, home, root):
    """Agent Observer's view of the run, from the temporary HOME's native records."""
    ao = REAL_HOME / ".claude/plugins/cache/toolboxmd/agent-observer/1.2.6/bin/agent-observer"
    db = root / "observer.db"
    src = home / (".claude/projects" if host == "claude" else ".codex/sessions")
    harness = "claude" if host == "claude" else "codex"
    try:
        subprocess.run([str(ao), "--db", str(db), "sync", "--harness", harness, "--root", str(src)],
                       capture_output=True, text=True, timeout=300, check=True)
        listing = json.loads(subprocess.run([str(ao), "--db", str(db), "--json", "sessions", "list"],
                                            capture_output=True, text=True, timeout=120, check=True).stdout)
        shows = []
        for s in (listing if isinstance(listing, list) else listing.get("sessions", [])):
            key = s.get("key") or s.get("session_key") or s.get("session")
            out = subprocess.run([str(ao), "--db", str(db), "--json", "sessions", "show", "--session", str(key)],
                                 capture_output=True, text=True, timeout=120)
            shows.append(json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr[-300:]})
        return {"sessions": listing, "show": shows}
    except Exception as exc:  # measurement gap, recorded, never fatal
        return {"error": f"{type(exc).__name__}: {exc}"[-500:]}


# ---------------------------------------------------------------- grading

FIELD = r"^\s*(?:[-*+]\s+)?(?:\*\*{0}:\*\*|\*\*{0}\*\*:|{0}:)\s*(.*)$"
ELON = ("Requirements and who asked", "Deleted", "Bottleneck", "Checked myself")


def elon_ok(body):
    lines = (body or "").splitlines()
    for field in ELON:
        pat = re.compile(FIELD.format(re.escape(field)), re.I)
        value = ""
        for i, line in enumerate(lines):
            m = pat.match(line)
            if m:
                value = m.group(1).strip() or next((l.strip() for l in lines[i + 1:] if l.strip()), "")
                break
        if not value or re.match(r"^<[^>]*>$", value) or re.match(r"^#{1,6}\s", value):
            return False
    return True


def human_summary_ok(body):
    head = [l for l in (body or "").splitlines() if l.strip()][:12]
    text = "\n".join(head)
    # `**What:**`, `**What**:` and labelled variants such as `**What changed:**`.
    return all(re.search(r"\*\*" + w + r"\b[^*\n]{0,24}?(:\*\*|\*\*:?)", text, re.I)
               for w in ("What", "Why", "So what"))


def gh_log(root):
    path = root / "ext/gh.log"
    return [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []


def words(rec):
    return [a for a in rec["argv"] if not a.startswith("-")]


def stream_details(stream, host):
    """Tool calls (name, path, command), subagent dispatches, gate blocks, final text."""
    calls, agents, blocks, final, kinds = [], [], 0, "", set()
    for line in stream.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        if "AgentsMD blocked `gh" in line:
            blocks += 1
        if host == "claude":
            if ev.get("type") == "assistant":
                for b in ev.get("message", {}).get("content", []):
                    if b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task"):
                        inp = b.get("input") or {}
                        agents.append(str(inp.get("description", "")) + " | " + str(inp.get("prompt", ""))[:300])
            if ev.get("type") == "result":
                final = str(ev.get("result") or "")
        else:
            item = ev.get("item") or {}
            kinds.add(str(item.get("type")))
            if ev.get("type") == "item.completed" and item.get("type") == "agent_message":
                final = str(item.get("text") or "")
            if ev.get("type") == "item.completed" and item.get("type") not in (
                    "command_execution", "file_change", "agent_message", "reasoning", "todo_list", None):
                agents.append(json.dumps(item)[:300])
    # Gate blocks show twice in Claude streams (tool result and its echo); count unique by halving if paired.
    calls = list(tt.tool_calls(stream, host))
    return calls, agents, blocks, final, sorted(kinds)


def first_index(calls, pred):
    return next((i for i, c in enumerate(calls) if pred(c)), None)


SOURCE = re.compile(r"\b(test_)?app\.py\b")


def is_edit(call):
    """A change to the fixture's source or tests (writing an Issue or PR body file is not one)."""
    name, path, command, _ = call
    return ((name == "Edit" and bool(SOURCE.search(path)))
            or (name == "Bash" and bool(tt.SHELL_EDIT.search(command)) and bool(SOURCE.search(command))))


def is_cmd(call, text):
    return call[0] == "Bash" and text in call[2]


def check_job(task, repo, env, ref, origin=None):
    """Does the delivered commit (`ref`) do the job? Tests pass and the behavior holds."""
    scratch = pathlib.Path(tempfile.mkdtemp(prefix=PREFIX + "check-"))
    try:
        subprocess.run(["git", "clone", "-q", str(repo), str(scratch / "c")], check=True, capture_output=True, env=env)
        c = scratch / "c"
        if origin is not None:
            subprocess.run(["git", "fetch", "-q", str(origin), "+refs/heads/*:refs/remotes/bare/*"], cwd=c,
                           capture_output=True, env=env)
        subprocess.run(["git", "checkout", "-q", ref], cwd=c, check=True, capture_output=True, env=env)
        tests = subprocess.run([sys.executable, "-m", "unittest"], cwd=c, capture_output=True, text=True, timeout=120)
        probe = ("import app\ntry:\n    app.divide(1, 0)\nexcept ValueError as e:\n    print('OK' if str(e) == 'b must not be zero' else 'MSG')\n"
                 "except Exception as e:\n    print('WRONG', type(e).__name__)\nelse:\n    print('NORAISE')\n"
                 if task == "bug" else "import app\nprint('OK' if app.farewell('Ana') == 'Goodbye, Ana!' else 'WRONG')\n")
        out = subprocess.run([sys.executable, "-c", probe], cwd=c, capture_output=True, text=True, timeout=60)
        return {"tests_pass": tests.returncode == 0, "behavior": (out.stdout.strip() or out.stderr.strip()[-80:])}
    except Exception as exc:
        return {"tests_pass": False, "behavior": f"error {type(exc).__name__}"}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def grade_code(task, stream, host, root, repo, env, initial):
    calls, agents, blocks, final, kinds = stream_details(stream, host)
    log = gh_log(root)
    issues = [r for r in log if words(r)[:2] == ["issue", "create"]]
    prs = [r for r in log if words(r)[:2] == ["pr", "create"]]
    merges = [r for r in log if words(r)[:2] == ["pr", "merge"] or (words(r)[:1] == ["api"] and "merge" in " ".join(r["argv"]))]
    statuses = [r for r in log if words(r)[:1] == ["api"] and "review/independent" in " ".join(r["argv"])]
    reviewer_asks = [r for r in log if (words(r)[:2] == ["pr", "edit"] and "--add-reviewer" in r["argv"])
                     or (words(r)[:2] in (["pr", "comment"], ["pr", "review"]) and "review" in json.dumps(r).lower())]
    origin = root / "ext/origin.git"
    origin_refs = dict(reversed(l.split()) for l in git("--git-dir", str(origin), "for-each-ref",
                                                          "--format=%(objectname) %(refname:short)").splitlines())
    local_refs = dict(reversed(l.split()) for l in git("for-each-ref", "--format=%(objectname) %(refname:short)",
                                                         "refs/heads", cwd=repo).splitlines())
    task_branches = {n: s for n, s in {**local_refs, **{"origin/" + k: v for k, v in origin_refs.items()}}.items()
                     if n not in ("main", "origin/main") and s != initial}
    # The delivered commit: the newest pushed task branch, else a local task branch, else HEAD.
    pushed = {n: v for n, v in task_branches.items() if n.startswith("origin/")}
    pick = pushed or task_branches
    delivered_name = max(pick, key=lambda n: int(git("log", "-1", "--format=%ct", pick[n], cwd=repo, check=False) or 0)
                                                 if not n.startswith("origin/") else
                                                 int(git("--git-dir", str(origin), "log", "-1", "--format=%ct", pick[n]) or 0)) if pick else "HEAD"
    delivered = pick.get(delivered_name, "HEAD")
    first_edit = first_index(calls, is_edit)
    first_issue = first_index(calls, lambda c: is_cmd(c, "gh issue create"))
    first_pr = first_index(calls, lambda c: is_cmd(c, "gh pr create"))
    first_commit = first_index(calls, lambda c: is_cmd(c, "git commit"))
    tw = first_index(calls, lambda c: tt.reads_file(c, TRACKED_WORK))
    entry = first_index(calls, lambda c: (c[0] == "Skill" and c[3].split(":")[-1] == "operations")
                        or tt.reads_file(c, tt.ENTRY))
    pr_body = prs[-1]["body"] if prs else None
    issue_body = issues[-1]["body"] if issues else None
    return {
        "issue_created": bool(issues),
        "issue_before_first_edit": bool(issues) and first_issue is not None and (first_edit is None or first_issue < first_edit),
        "issue_human_summary": human_summary_ok(issue_body),
        "issue_elon": elon_ok(issue_body),
        "task_branch": bool(task_branches),
        "pushed_branch": any(n.startswith("origin/") for n in task_branches),
        "main_untouched": origin_refs.get("main") == initial and local_refs.get("main", initial) == initial,
        "pr_opened": bool(prs),
        "pr_human_summary": human_summary_ok(pr_body),
        "pr_elon": elon_ok(pr_body),
        "review_requested": bool(agents or statuses or reviewer_asks),
        "review_via": {"subagents": len(agents), "status_posts": len(statuses), "reviewer_asks": len(reviewer_asks)},
        "no_unauthorized_merge": not merges and origin_refs.get("main") == initial,
        "gate_blocks": blocks,
        "job": check_job(task, repo, env, delivered, origin),
        "delivered": delivered_name,
        "operations_loaded": entry is not None,
        "tracked_work_read": tw is not None,
        "tracked_work_before_first_edit": tw is not None and (first_edit is None or tw < first_edit),
        "tracked_work_before_issue_or_pr": tw is not None and all(x is None or tw < x for x in (first_issue, first_pr)),
        "first": {"edit": first_edit, "issue": first_issue, "pr": first_pr, "commit": first_commit,
                  "tracked_work": tw, "operations": entry},
        "n_calls": len(calls),
        "gh_calls": [" ".join(words(r)[:2]) for r in log],
        "pr_body": pr_body, "issue_body": issue_body, "final": final[-1500:],
        "codex_item_kinds": kinds,
    }


CEREMONY = re.compile(r"\b(GitHub|Issue|pull request|PR|branch|commit|Elon record|Human summary|"
                      r"Requirements and who asked|Checked myself|Delivery Authority)\b")


def grade_noncode(stream, host, root, desk):
    calls, agents, blocks, final, kinds = stream_details(stream, host)
    log = gh_log(root)
    git_calls = [c[2] for c in calls if c[0] == "Bash" and re.search(r"\bgit\b", c[2])]
    edits = [c for c in calls if is_edit(c)]
    tw = first_index(calls, lambda c: tt.reads_file(c, TRACKED_WORK))
    entry = first_index(calls, lambda c: (c[0] == "Skill" and c[3].split(":")[-1] == "operations")
                        or tt.reads_file(c, tt.ENTRY))
    terms = sorted(set(CEREMONY.findall(final)))
    summary = bool(re.search(r"\*\*(What|Why|So what)\*\*", final))
    leak = bool(log or git_calls or edits or tw is not None or terms or summary or list(desk.iterdir()))
    return {
        "leak": leak, "gh_calls": len(log), "git_calls": len(git_calls), "edits": len(edits),
        "files_in_desk": len(list(desk.iterdir())), "tracked_work_read": tw is not None,
        "operations_loaded": entry is not None, "ceremony_terms": terms, "human_summary_block": summary,
        "em_dashes": final.count("\u2014"), "words": len(final.split()), "n_calls": len(calls),
        "final": final[-1500:],
    }


def grade_canary(stream, host, arm):
    _, _, _, final, _ = stream_details(stream, host)
    text = final.strip().strip("`").strip()
    seen = next((a for a, h in CANARY_HEADING.items() if h.lower() in text.lower()), None)
    return {"answer": text[:200], "arm_seen": seen, "match": seen == arm}


# ---------------------------------------------------------------- running

def run_one(host, arm, task, index, out_dir, before):
    if host in STOP:
        return {"host": host, "arm": arm, "task": task, "run": index, "status": "skipped", "reason": STOP[host]}
    kind, prompt_t = TASKS[task]
    root, home, plugin, repo, desk, env = make_run(host, arm)
    try:
        core = core_at_path(host, home)
        if core["sha256"] != SOURCES[arm + "-core"] or not core["is_link"]:
            raise RuntimeError(f"wrong core at {core['path']} for arm {arm}")
        initial = git("rev-parse", "HEAD", cwd=repo)
        cwd = repo if kind == "code" else desk
        prompt = prompt_t.format(repo=repo)
        started = time.time()
        stream = tt.execute(host, command(host, cwd, root, plugin, prompt), cwd, env)
        seconds = round(time.time() - started, 1)
        after = tt.snapshot()
        if after != before:
            raise tt.Escaped(f"guarded state changed after {host} {arm} {task} {index}")
        model, effort = MODELS[host]
        rec = {"host": host, "model": model, "effort": effort, "arm": arm, "arm_sha": SOURCES[arm + "-sha"],
               "core_at_path": core, "task": task, "kind": kind, "run": index, "seconds": seconds,
               "usage": tt.usage(stream, host), "status": "ok",
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started))}
        if not stream.strip() or (LIMIT.search(stream[-4000:]) and len(list(tt.tool_calls(stream, host))) == 0):
            rec["status"] = "limit-or-empty"
            if LIMIT.search(stream):
                STOP[host] = "provider limit: " + LIMIT.search(stream).group(0)
        if kind == "code":
            rec["grade"] = grade_code(task, stream, host, root, repo, env, initial)
        elif kind == "noncode":
            rec["grade"] = grade_noncode(stream, host, root, desk)
        else:
            rec["grade"] = grade_canary(stream, host, arm)
        rec["observer"] = observer(host, home, root)
        name = f"{host}-{arm}-{task}-{index}"
        with gzip.open(out_dir / "streams" / f"{name}.jsonl.gz", "wt") as f:
            f.write(tt.anonymize(stream, repo if kind == "code" else desk, plugin))
        rec = json.loads(tt.anonymize(json.dumps(rec), repo if kind == "code" else desk, plugin)
                         .replace(str(root), "<run>"))
        return rec
    finally:
        tt.remove(root)


WRITE = re.compile(r"(python3? - <<|apply_patch|sed -i|\bperl -pi|write_text|(?<![A-Za-z])>\s*\S*(test_)?app\.py\b|tee\s+\S*(test_)?app\.py\b)")


def issue_before_source_write(calls):
    """The frozen "Issue created before the first file edit", ordered within a shell call.

    The live grader compared call indexes, and a shell call that writes an Issue body
    with `cat > issue.md <<EOF` mentioning app.py counted as an edit, so an Issue
    created in that same call never came first. Here a shell call is a source write
    only through a writing command (WRITE) that names the fixture's code or tests,
    and inside the call that creates the Issue only the text before `gh issue create`
    counts."""
    for name, path, command, _ in calls:
        if name == "Edit" and SOURCE.search(path):
            return False
        if name != "Bash":
            continue
        at = command.find("gh issue create")
        head = command if at < 0 else command[:at]
        if WRITE.search(head) and SOURCE.search(head):
            return False
        if at >= 0:
            return True
    return False


def regrade(records, streams):
    """Post-batch grading fixes, applied from kept fields and streams (see results.md):
    Codex review counts its native subagents (`collab_tool_call` items), not `error` items."""
    out = []
    for r in records:
        g = r.get("grade") or {}
        if r.get("status") == "ok" and r["kind"] == "code" and r["host"] == "codex":
            path = streams / f"{r['host']}-{r['arm']}-{r['task']}-{r['run']}.jsonl.gz"
            text = gzip.open(path, "rt").read()
            collab = sum(1 for l in text.splitlines() if '"collab_tool_call"' in l and '"item.started"' in l)
            via = g["review_via"]
            via["subagents"] = collab
            g["review_requested"] = bool(collab or via["status_posts"] or via["reviewer_asks"])
        if r.get("status") == "ok" and r["kind"] == "code":
            calls = list(tt.tool_calls(gzip.open(streams / f"{r['host']}-{r['arm']}-{r['task']}-{r['run']}.jsonl.gz",
                                                 "rt").read(), r["host"]))
            g["verification_read"] = any(tt.reads_file(c, tt.VERIFICATION) for c in calls)
            g["issue_before_first_edit_live"] = g.get("issue_before_first_edit_live", g["issue_before_first_edit"])
            g["issue_before_first_edit"] = bool(g["issue_created"]) and issue_before_source_write(calls)
        out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", choices=list(MODELS))
    ap.add_argument("--tasks", default="bug,feature,email")
    ap.add_argument("--arms", default="current,split")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", type=pathlib.Path)
    ap.add_argument("--summary", type=pathlib.Path)
    ap.add_argument("--regrade", nargs=2, type=pathlib.Path, metavar=("RECORDS", "STREAMS"))
    a = ap.parse_args()
    if a.regrade:
        for r in regrade([json.loads(l) for l in a.regrade[0].read_text().splitlines() if l.strip()], a.regrade[1]):
            print(json.dumps(r))
        return 0
    if a.summary:
        return summarize(a.summary)
    out = a.out
    (out / "streams").mkdir(parents=True, exist_ok=True)
    tt.guard_self_check()
    src = extract_sources()
    lock = threading.Lock()
    try:
        before = tt.snapshot()
        jobs = [(a.host, arm, task, i) for i in range(a.start, a.start + a.runs)
                for task in a.tasks.split(",") for arm in a.arms.split(",")]
        with concurrent.futures.ThreadPoolExecutor(a.jobs) as pool:
            futures = {pool.submit(run_one, *j, out, before): j for j in jobs}
            for fut in concurrent.futures.as_completed(futures):
                j = futures[fut]
                try:
                    rec = fut.result()
                except tt.Escaped:
                    raise
                except Exception as exc:
                    rec = {"host": j[0], "arm": j[1], "task": j[2], "run": j[3], "status": "error",
                           "error": f"{type(exc).__name__}: {exc}"[-500:]}
                with lock, open(out / "records.jsonl", "a") as f:
                    f.write(json.dumps(rec) + "\n")
                g = rec.get("grade", {})
                print(j, rec.get("status"), rec.get("seconds"),
                      {k: v for k, v in g.items() if isinstance(v, bool)}, flush=True)
    finally:
        tt.remove(src)


CODE_METRICS = ["issue_created", "issue_before_first_edit", "issue_before_first_edit_live", "task_branch", "pushed_branch", "main_untouched",
                "pr_opened", "pr_human_summary", "pr_elon", "issue_human_summary", "issue_elon",
                "review_requested", "verification_read", "no_unauthorized_merge", "operations_loaded", "tracked_work_read",
                "tracked_work_before_first_edit"]


def summarize(path):
    recs = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    ok = [r for r in recs if r.get("status") == "ok"]
    for host in sorted({r["host"] for r in ok}):
        print(f"\n### {host}\n")
        rows = [r for r in ok if r["host"] == host]
        arms = [a for a in ARMS if any(r["arm"] == a for r in rows)]
        code = [r for r in rows if r["kind"] == "code"]
        print("| Metric (coding runs) | " + " | ".join(arms) + " |")
        print("| --- |" + " --- |" * len(arms))
        for m in CODE_METRICS + ["job_done"]:
            cells = []
            for arm in arms:
                rs = [r for r in code if r["arm"] == arm]
                val = (lambda r: r["grade"]["job"]["tests_pass"] and r["grade"]["job"]["behavior"] == "OK") \
                    if m == "job_done" else (lambda r, m=m: r["grade"].get(m))
                cells.append(f"{sum(bool(val(r)) for r in rs)}/{len(rs)}")
            print(f"| {m} | " + " | ".join(cells) + " |")
        for task in ("bug", "feature"):
            for m in ("issue_created", "pr_opened", "review_requested", "verification_read"):
                cells = [f"{sum(bool(r['grade'].get(m)) for r in code if r['arm'] == arm and r['task'] == task)}/"
                         f"{sum(1 for r in code if r['arm'] == arm and r['task'] == task)}" for arm in arms]
                print(f"{task} {m}: " + " / ".join(cells))
        for kind in ("code", "noncode"):
            for arm in arms:
                rs = [r for r in rows if r["kind"] == kind and r["arm"] == arm]
                if not rs:
                    continue
                tok = [r["usage"].get("input", 0) + r["usage"].get("output", 0) for r in rs]
                sec = [r["seconds"] for r in rs]
                print(f"{kind} {arm}: n={len(rs)} mean tokens {sum(tok) // len(tok):,} "
                      f"mean seconds {sum(sec) / len(sec):.0f}")
        non = [r for r in rows if r["kind"] == "noncode"]
        for arm in arms:
            rs = [r for r in non if r["arm"] == arm]
            if rs:
                print(f"noncode {arm}: leaks {sum(r['grade']['leak'] for r in rs)}/{len(rs)}, "
                      f"em dashes {sum(r['grade']['em_dashes'] for r in rs)}, "
                      f"tracked-work read {sum(r['grade']['tracked_work_read'] for r in rs)}")
        can = [r for r in rows if r["kind"] == "canary"]
        for r in can:
            print(f"canary {r['arm']}: {r['grade']}")
    bad = [r for r in recs if r.get("status") != "ok"]
    if bad:
        print("\nNot ok:", [(r["host"], r["arm"], r["task"], r["run"], r.get("status"), r.get("error", "")[:120])
                            for r in bad])


if __name__ == "__main__":
    sys.exit(main())
