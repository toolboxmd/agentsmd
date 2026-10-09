#!/usr/bin/env python3
"""Measure how often AgentsMD operations procedures are read when their trigger fires.

Issue #164. Reads native transcripts read-only:
  Claude Code  ~/.claude/projects/**/*.jsonl (subagent files included, flagged)
  Codex        ~/.codex/sessions/**/*.jsonl
  Grok Build   ~/.grok/sessions/*/*/chat_history.jsonl
  OpenCode     ~/.local/share/opencode/opencode.db (opened read-only)

A row "fires" in a session when a read of one of its required files happens at
or before the step of the first triggering call. Row definitions live in ROWS;
docs/work/164-trigger-audit/triggers.md explains each one.

With --ledger, reads the Agent Observer ledger instead (see load_ledger).

Usage: measure.py [--since YYYY-MM-DD] [--until ISO] [--ledger [DB]] [--exclude SESSION_ID ...] [--json]
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict

HOME = os.path.expanduser("~")

# ---------------------------------------------------------------- patterns

AGENT_INSTR = re.compile(
    r"(^|/)(SKILL\.md|AGENTS(\.override)?\.md|CLAUDE\.md|GEMINI\.md)$"
    r"|/skills/.+\.md$|/\.claude/(agents|commands|packets)/.+\.md$")
SKILL_MD = re.compile(r"(^|/)SKILL\.md$")
TECH_DOC = re.compile(r"(^|/)(README|CHANGELOG|CONTRIBUTING)\.md$|/docs/(?!work/|adr/).+\.mdx?$")
TRIAD = re.compile(r"(^|/)(VISION|MISSION|OBJECTIVE)\.md$")
GLOSSARY = re.compile(r"(^|/)(GLOSSARY(-MAP)?|CONTEXT(-MAP)?)\.md$")
ADR = re.compile(r"/docs/adr/[^/]+\.md$")
ARTIFACT = re.compile(r"/docs/work/|/(research|reviews|prototypes?|reflections?)/")
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__)/|(_test|\.test|\.spec)\.[a-z]+$|/test_[^/]+\.py$")
VERSION_FILE = re.compile(r"(^|/)VERSION$")
PROJ_VERIF = re.compile(r"verif[^/]*/SKILL\.md$|(^|/)VERIFY(ING)?\.md$|/docs/verification/")
SCRATCH = re.compile(r"^/(private/)?tmp/|/\.claude/(projects|plans|packets)/|/scratchpad/|/\.local/state/")

GIT_COMMIT = re.compile(r"\bgit\b[^\n;|&]*\scommit\b")
GH_ISSUE_CREATE = re.compile(r"\bgh\s+issue\s+create\b")
GH_PR_READY = re.compile(r"\bgh\s+pr\s+(create|ready)\b")
GH_PR_MERGE = re.compile(r"\bgh\s+pr\s+merge\b")
DELIVERY = re.compile(r"\bgh\s+pr\s+(create|merge)\b|\bgh\s+release\s+create\b"
                      r"|\bgit\s+push\b[^\n]*--tags|\bgit\s+tag\s+-a\b|\bnpm\s+publish\b")
FINAL = re.compile(r"\bgh\s+issue\s+close\b|\bgit\b[^\n;|&]*\sworktree\s+remove\b"
                   r"|\bgit\b[^\n;|&]*\sbranch\s+-[dD]\b")
REPO_SETUP = re.compile(r"\bgh\s+repo\s+edit\b|\bgh\s+label\s+create\b|\bgh\s+ruleset\b"
                        r"|\bgh\s+api\b[^\n]*(-X|--method)\s*(PUT|PATCH|POST|DELETE)[^\n]*"
                        r"(rulesets|protection|actions/permissions|/labels\b)")
TESTS = re.compile(r"\b(pytest|python3?\s+-m\s+(pytest|unittest)|(npm|pnpm|bun|yarn)\s+(run\s+)?test"
                   r"|vitest|jest|go\s+test|cargo\s+test|make\s+(test|check)|swift\s+test)\b")
VERSIONCTL_BUMP = re.compile(r"\bversionctl\s+bump\b")
DELIVERY_JSON = re.compile(r"\.toolboxmd/delivery\.json")
SPAWN_CMD = re.compile(r"\bopencode\s+run\b|\bcodex\s+exec\b|\bclaude\s+(-p|--print)\b")

P_GRILL = re.compile(r"\bgrill", re.I)
P_WAYFIND = re.compile(r"\bwayfind", re.I)
P_SPEC = re.compile(r"\b(to-spec|to-tickets|specification|PRD|write (a|the) spec)\b", re.I)
P_REVIEW = re.compile(r"\b(code[- ]review|review (this|the|my|that) (pr|pull request|diff|change|branch|code))\b", re.I)
P_REFLECT = re.compile(r"\b(reflect|reflection|retrospective|retro|lessons learned|post-?mortem)\b", re.I)
MEMORY_DIR = re.compile(r"/\.claude/projects/[^/]+/memory/")

READER = re.compile(r"(^|[\s;&|(`\"'])(cat|sed|head|tail|nl|less|more|bat|awk|view)\b|\bgit\s+show\b"
                    r"|read_text|open\(|Get-Content|tools\.read")

SPAWN_TOOLS = {"Agent", "Task", "mcp__t3-code__spawn_thread", "mcp__t3-code__prism_submit",
               "collaboration.spawn_agent", "spawn_agent", "task",
               "t3-code_spawn_thread", "t3-code_prism_submit"}
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "edit", "write", "patch",
              "search_replace", "write_file", "edit_file", "create_file", "apply_patch"}
READ_TOOLS = {"Read", "read", "read_file", "view_file"}
CMD_TOOLS = {"Bash", "bash", "run_terminal_command", "exec_command", "shell", "local_shell",
             "shell_command"}
PATH_KEYS = ("file_path", "filePath", "target_file", "path", "filename", "notebook_path")


# ---------------------------------------------------------------- actions

INJECTED = ("<", "# AGENTS.md", "This session is being continued", "[Request interrupted",
            "Caveat:", "Base directory for this skill", "[Subagent ", ">>>")
EVAL_CWD = re.compile(r"^/(private/)?(tmp|var/folders)/")


SLASH = re.compile(r"<command-name>/?(?:[\w-]+:)?([\w-]+)</command-name>|(?:^|\s)/agentsmd:([\w-]+)"
                   r"|\[\$(?:[\w-]+:)?([\w-]+)\]\(")
HUMAN_PROMPT_MAX = 1200  # longer prompts are nearly always dispatched worker packets


def prompt_actions(step, texts):
    """User-typed text only: drop host-injected reminders, rules and summaries.

    A slash command naming a skill counts as a skill load (the host injects its body).
    """
    out = []
    for t in texts:
        if not isinstance(t, str) or not t.strip():
            continue
        for m in SLASH.finditer(t):
            out.append(Action(step, "skill", "slash", json.dumps({"skill": m.group(1) or m.group(2) or m.group(3)})))
        if not t.lstrip().startswith(INJECTED):
            out.append(Action(step, "user", "prompt", t))
    return out


class Action:
    __slots__ = ("step", "kind", "name", "text", "paths")

    def __init__(self, step, kind, name, text="", paths=()):
        self.step, self.kind, self.name, self.text, self.paths = step, kind, name, text, list(paths)


def is_edit(a, rx):
    return a.kind == "edit" and any(rx.search(p) for p in a.paths)


def is_cmd(a, rx):
    return a.kind == "cmd" and rx.search(a.text) is not None


def is_prompt(a, rx, limit=HUMAN_PROMPT_MAX):
    """limit=None also counts long dispatched packets (a review request is a real trigger)."""
    return (a.kind == "user" and (limit is None or len(a.text) <= limit)
            and rx.search(a.text) is not None)


def is_work_edit(a):
    return a.kind == "edit" and any(not SCRATCH.search(p) for p in a.paths)


def _aliases(suffix):
    """Current path plus its pre-#120 standalone-skill path (layout changed 2026-09-23).

    Returns (tail, needs_operations_context) pairs. `references/...` tails are
    generic names, so they count only when "operations" appears in the call.
    """
    if suffix == "operations/SKILL.md":
        return [("operations/SKILL.md", False)]
    tail = suffix[len("operations/"):] if suffix.startswith("operations/") else suffix
    out = [(tail, not tail.startswith("workflows/"))]
    m = re.match(r"workflows/([^/]+)/(.+)$", tail)
    if m:
        name, rest = m.groups()
        out.append((f"skills/{name}/" + ("SKILL.md" if rest == "index.md" else rest), False))
        if name == "elon-method" and rest in ("index.md", "references/algorithm.md"):
            out.append(("skills/algorithm/SKILL.md", False))
    return out


def _skill_name(a):
    try:
        args = json.loads(a.text)
    except ValueError:
        return ""
    name = args.get("skill") or args.get("name") or "" if isinstance(args, dict) else ""
    return str(name).split(":")[-1]


def reads_file(a, suffix):
    """True when the action opens a procedure file whose path ends with suffix."""
    if a.kind == "skill":
        name = _skill_name(a)
        if suffix == "operations/SKILL.md":
            return name == "operations"
        m = re.match(r"workflows/([^/]+)/index\.md$", suffix)
        return bool(m and (name == m.group(1) or (m.group(1) == "elon-method" and name == "algorithm")))
    for tail, needs_ops in _aliases(suffix):
        rx = re.compile(r"(^|[/\s\"'`:=])" + re.escape(tail) + r"\b")
        if a.kind == "read" and any(rx.search(p) and (not needs_ops or "operations/" in p) for p in a.paths):
            return True
        if (a.kind == "cmd" and rx.search(a.text) and READER.search(a.text)
                and (not needs_ops or "operations" in a.text)):
            return True
    return False


# ---------------------------------------------------------------- rows

def first(actions, pred):
    for a in actions:
        if pred(a):
            return a
    return None


def nth(actions, pred, n):
    hits = [a for a in actions if pred(a)]
    return hits[n - 1] if len(hits) >= n else None


def parallel_spawn(actions):
    by_step = defaultdict(int)
    for a in actions:
        if a.kind == "spawn":
            by_step[a.step] += 1
            if by_step[a.step] >= 2:
                return a
    return None


def test_after_edit(actions):
    edited = False
    for a in actions:
        if is_work_edit(a):
            edited = True
        elif edited and is_cmd(a, TESTS):
            return a
    return None


def entry_trigger(a):
    return (is_work_edit(a) or is_cmd(a, GH_ISSUE_CREATE) or is_cmd(a, GH_PR_READY)
            or is_cmd(a, GIT_COMMIT))


W = "workflows/"
R = "operations/references/"
ROWS = [
    # id, label, trigger (actions -> first triggering Action or None), required files (any)
    ("entry", "Operations entry point", lambda s: first(s, entry_trigger),
     ["operations/SKILL.md"]),
    ("elon", "Elon method (material work)", lambda s: first(s, lambda a: is_cmd(a, GH_ISSUE_CREATE)),
     [W + "elon-method/index.md", W + "elon-method/references/algorithm.md"]),
    ("elon>algorithm", "Elon method -> algorithm.md", lambda s: first(s, lambda a: is_cmd(a, GH_ISSUE_CREATE)),
     [W + "elon-method/references/algorithm.md"]),
    ("pd", "Repair or change Project Direction", lambda s: first(s, lambda a: is_edit(a, TRIAD) and not any("/templates/" in p for p in a.paths)),
     [W + "project-direction/index.md"]),
    ("pd>contracts", "Project Direction -> file-contracts.md", lambda s: first(s, lambda a: is_edit(a, TRIAD) and not any("/templates/" in p for p in a.paths)),
     [W + "project-direction/references/file-contracts.md"]),
    ("grilling", "Grilling (explicit request)", lambda s: first(s, lambda a: is_prompt(a, P_GRILL)),
     [W + "grilling/index.md", W + "grill-with-docs/index.md"]),
    ("domain", "Domain modeling", lambda s: first(s, lambda a: is_edit(a, GLOSSARY) or is_edit(a, ADR)),
     [W + "domain-modeling/index.md"]),
    ("domain>glossary", "Domain modeling -> GLOSSARY-FORMAT.md", lambda s: first(s, lambda a: is_edit(a, GLOSSARY)),
     [W + "domain-modeling/GLOSSARY-FORMAT.md"]),
    ("domain>adr", "Domain modeling -> ADR-FORMAT.md", lambda s: first(s, lambda a: is_edit(a, ADR)),
     [W + "domain-modeling/ADR-FORMAT.md"]),
    ("wayfinder", "Wayfinder (explicit request)", lambda s: first(s, lambda a: is_prompt(a, P_WAYFIND)),
     [W + "wayfinder/index.md"]),
    ("spec", "Specify or tickets (explicit request)", lambda s: first(s, lambda a: is_prompt(a, P_SPEC)),
     [W + "to-spec/index.md", W + "to-tickets/index.md"]),
    ("tickets>decomp", "Tickets -> ticket-decomposition.md (2+ Issues created)", lambda s: nth(s, lambda a: is_cmd(a, GH_ISSUE_CREATE), 2),
     [W + "to-tickets/references/ticket-decomposition.md"]),
    ("impl", "Implementation", lambda s: first(s, is_work_edit),
     [R + "implementation.md"]),
    ("impl>verif", "Implementation -> verification.md (tests after edit)", test_after_edit,
     [R + "verification.md"]),
    ("test-design", "Test design (test file edited)", lambda s: first(s, lambda a: is_edit(a, TEST_FILE)),
     [R + "test-design.md"]),
    ("orch", "Orchestration (delegation)", lambda s: first(s, lambda a: a.kind == "spawn"),
     [R + "orchestration.md"]),
    ("orch>bounded", "Orchestration -> bounded-delegation.md (parallel spawn)", parallel_spawn,
     [R + "bounded-delegation.md"]),
    ("verif", "Verification (readiness claim: gh pr create/ready)", lambda s: first(s, lambda a: is_cmd(a, GH_PR_READY)),
     [R + "verification.md"]),
    ("review", "Code review (review request, incl. dispatched packets)", lambda s: first(s, lambda a: is_prompt(a, P_REVIEW, None)),
     [W + "code-review/index.md"]),
    ("review>method", "Code review -> review-method.md", lambda s: first(s, lambda a: is_prompt(a, P_REVIEW, None)),
     [W + "code-review/references/review-method.md"]),
    ("proj-verif", "Project verification", lambda s: first(s, lambda a: is_edit(a, PROJ_VERIF)),
     [W + "project-verification/index.md"]),
    ("artifacts", "Artifact placement", lambda s: first(s, lambda a: a.name in ("Write", "write", "create_file", "write_file") and is_edit(a, ARTIFACT)),
     [R + "artifacts.md"]),
    ("wfa", "Writing for agents", lambda s: first(s, lambda a: is_edit(a, AGENT_INSTR) and not is_edit(a, MEMORY_DIR)),
     [W + "writing-for-agents/index.md"]),
    ("wfa>mechanics", "Writing for agents -> SKILL-MECHANICS.md (SKILL.md edited)", lambda s: first(s, lambda a: is_edit(a, SKILL_MD)),
     [W + "writing-for-agents/SKILL-MECHANICS.md"]),
    ("wfa>prose", "Writing for agents -> prose.md", lambda s: first(s, lambda a: is_edit(a, AGENT_INSTR) and not is_edit(a, MEMORY_DIR)),
     [W + "technical-writing/references/prose.md"]),
    ("tw", "Technical writing", lambda s: first(s, lambda a: is_edit(a, TECH_DOC) and not is_edit(a, AGENT_INSTR)),
     [W + "technical-writing/index.md"]),
    ("tw>prose", "Technical writing -> prose.md", lambda s: first(s, lambda a: is_edit(a, TECH_DOC) and not is_edit(a, AGENT_INSTR)),
     [W + "technical-writing/references/prose.md"]),
    ("reflection", "Reflection (request; memory write as proxy)", lambda s: first(s, lambda a: is_prompt(a, P_REFLECT) or is_edit(a, MEMORY_DIR)),
     [W + "reflection/index.md"]),
    ("vc", "Version control (git commit)", lambda s: first(s, lambda a: is_cmd(a, GIT_COMMIT)),
     [W + "version-control/index.md"]),
    ("vc>bump", "Version control -> bump-rules.md (version change)", lambda s: first(s, lambda a: is_edit(a, VERSION_FILE) or is_cmd(a, VERSIONCTL_BUMP)),
     [W + "version-control/references/bump-rules.md"]),
    ("delivery-profile", "Delivery profile", lambda s: first(s, lambda a: DELIVERY_JSON.search(a.text + " " + " ".join(a.paths)) and a.kind in ("cmd", "read", "edit")),
     [W + "delivery-profile/index.md"]),
    ("delivery", "Delivery (PR, merge, release)", lambda s: first(s, lambda a: is_cmd(a, DELIVERY)),
     [R + "delivery.md"]),
    ("delivery>final", "Delivery -> finalization.md (gh pr merge)", lambda s: first(s, lambda a: is_cmd(a, GH_PR_MERGE)),
     [R + "finalization.md"]),
    ("final", "Finalization (close Issue, retire worktree/branch)", lambda s: first(s, lambda a: is_cmd(a, FINAL)),
     [R + "finalization.md"]),
    ("repo-setup", "Repository setup (settings mutation)", lambda s: first(s, lambda a: is_cmd(a, REPO_SETUP)),
     [R + "repository-setup.md"]),
]


# ---------------------------------------------------------------- loaders

def _paths_from(args):
    out = []
    if isinstance(args, dict):
        for k in PATH_KEYS:
            v = args.get(k)
            if isinstance(v, str):
                out.append(v)
    return out


def _cmd_from(args):
    if isinstance(args, dict):
        for k in ("command", "cmd"):
            v = args.get(k)
            if isinstance(v, list):
                return " ".join(map(str, v))
            if isinstance(v, str):
                return v
    return ""


# A heredoc written to a file is content, not a command (the ledger omits it too)
# (an interpreter heredoc such as `python3 - <<PY` is the program and stays)
WRITE_HEREDOC = re.compile(r"^((?=[^\n]*(?:>|\btee\b))(?![^\n]*\b(?:python3?|node|bash|sh|ruby|perl)\s+-\s)"
                           r"[^\n]*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n).*?^(\s*\2)$", re.S | re.M)


def classify(step, name, args):
    """Map one generic tool call to Actions."""
    text = json.dumps(args) if not isinstance(args, str) else args
    if name in SPAWN_TOOLS:
        return [Action(step, "spawn", name, text)]
    if name == "Skill" or name == "skill":
        return [Action(step, "skill", name, text)]
    if name in EDIT_TOOLS:
        paths = _paths_from(args)
        if name == "apply_patch" or not paths:
            paths += re.findall(r"\*\*\* (?:Update|Add) File: ([^\n\\]+)", text)
        return [Action(step, "edit", name, json.dumps(paths), paths)]  # written content is not a command
    if name in READ_TOOLS:
        return [Action(step, "read", name, text, _paths_from(args))]
    if name in CMD_TOOLS:
        cmd = WRITE_HEREDOC.sub(r"\1[content omitted]\n\3", _cmd_from(args) or text)
        acts = [Action(step, "cmd", name, cmd)]
        acts += [Action(step, "edit", name, cmd, [p]) for p in bash_writes(cmd)]
        if SPAWN_CMD.search(cmd):
            acts.append(Action(step, "spawn", name, cmd))
        return acts
    return [Action(step, "other", name, text)]


def bash_writes(cmd):
    return re.findall(r"(?:\bcat\s*>>?|\btee\s+(?:-a\s+)?)\s*['\"]?([~/\w.\-]+/[\w.\-/]+)", cmd)


PATCH_BODY = re.compile(r"\*\*\* Begin Patch.*?(\*\*\* End Patch|$)", re.S)


def codex_exec(step, blob):
    """Split a Codex code-mode exec blob into commands and patch edits."""
    acts = []
    for p in re.findall(r"\*\*\* (?:Update|Add) File: ([^\n\\]+)", blob):
        acts.append(Action(step, "edit", "apply_patch", blob[:2000], [p.strip()]))
    cmds = re.findall(r"cmd\s*:\s*(\"(?:[^\"\\]|\\.)*\"|`(?:[^`\\]|\\.)*`)", blob)
    rest = PATCH_BODY.sub("", blob)
    for raw in cmds:
        try:
            c = json.loads(raw) if raw.startswith('"') else raw[1:-1]
        except ValueError:
            c = raw[1:-1]
        acts += classify(step, "exec_command", {"cmd": c})
        rest = rest.replace(raw, json.dumps(WRITE_HEREDOC.sub(r"\1[content omitted]\n\3", c)))
    if "spawn_agent" in blob:
        acts.append(Action(step, "spawn", "spawn_agent", blob[:500]))
    if not acts:
        acts.append(Action(step, "cmd", "exec", blob))
    # blob-level fallback so reads with workdir-relative paths still count;
    # patch and file-writing heredoc bodies are content, not commands
    acts.append(Action(step, "cmd", "exec", rest))
    return acts


def load_claude(since_ts):
    seen = set()  # a symlinked project directory lists the same files twice
    for f in sorted(glob.glob(os.path.join(HOME, ".claude/projects/**/*.jsonl"), recursive=True)):
        real = os.path.realpath(f)
        if real in seen or os.path.getmtime(f) < since_ts:
            continue
        seen.add(real)
        acts, start, step, cwd = [], None, 0, ""
        sub = "/subagents/" in f
        try:
            lines = open(f, encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ts = r.get("timestamp")
            if ts and start is None:
                start = _iso(ts)
            cwd = r.get("cwd") or cwd
            msg = r.get("message") or {}
            content = msg.get("content")
            if r.get("type") == "user" and not r.get("isMeta"):
                if isinstance(content, str):
                    acts += prompt_actions(step, [content])
                elif isinstance(content, list):
                    acts += prompt_actions(step, [c.get("text", "") for c in content
                                                  if isinstance(c, dict) and c.get("type") == "text"])
            elif r.get("type") == "assistant" and isinstance(content, list):
                step += 1
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        acts += classify(step, c.get("name", ""), c.get("input") or {})
        if start is None or start < since_ts:
            continue
        sid = os.path.basename(f)[:-6]
        yield dict(host="claude", id=sid, start=start, cwd=cwd, sub=sub, path=f, actions=acts)


def load_codex(since_ts):
    for f in glob.glob(os.path.join(HOME, ".codex/sessions/**/*.jsonl"), recursive=True):
        if os.path.getmtime(f) < since_ts:
            continue
        acts, start, step, cwd, sub, sid = [], None, 0, "", False, os.path.basename(f)
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if start is None and r.get("timestamp"):
                start = _iso(r["timestamp"])
            p = r.get("payload") or {}
            t, pt = r.get("type"), p.get("type")
            if t == "session_meta":
                cwd = p.get("cwd", "")
                sid = p.get("id", sid)
                src = json.dumps(p.get("source", ""))
                sub = "subagent" in src or "spawn" in src
            elif t == "response_item" and pt == "message" and p.get("role") == "user":
                acts += prompt_actions(step, [c.get("text", "") for c in p.get("content") or []
                                              if isinstance(c, dict)])
            elif t == "response_item" and pt in ("function_call", "custom_tool_call", "local_shell_call"):
                step += 1
                name = p.get("name") or pt
                if p.get("namespace"):
                    name = p["namespace"] + "." + name
                raw = p.get("input") if pt == "custom_tool_call" else p.get("arguments", p.get("action", {}))
                if name == "exec" and isinstance(raw, str):
                    acts += codex_exec(step, raw)
                    continue
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except ValueError:
                        pass
                acts += classify(step, name, raw)
        if start is None or start < since_ts:
            continue
        yield dict(host="codex", id=sid, start=start, cwd=cwd, sub=sub, path=f, actions=acts)


def load_grok(since_ts):
    for f in glob.glob(os.path.join(HOME, ".grok/sessions/*/*/chat_history.jsonl")):
        d = os.path.dirname(f)
        start = _grok_start(d)
        if start is None or start < since_ts:
            continue
        acts, step = [], 0
        for line in open(f, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") == "user":
                c = r.get("content")
                items = [c] if isinstance(c, str) else [x.get("text", "") for x in c or [] if isinstance(x, dict)]
                acts += prompt_actions(step, items)
            elif r.get("type") == "assistant":
                step += 1
                for tc in r.get("tool_calls") or []:
                    args = tc.get("arguments", {})
                    try:
                        args = json.loads(args) if isinstance(args, str) else args
                    except ValueError:
                        pass
                    acts += classify(step, tc.get("name", ""), args)
        cwd = _unquote(os.path.basename(os.path.dirname(d)))
        yield dict(host="grok", id=os.path.basename(d), start=start, cwd=cwd, sub=False, actions=acts)


def _grok_start(d):
    ev = os.path.join(d, "events.jsonl")
    try:
        with open(ev, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                ts = json.loads(line).get("ts")
                if ts:
                    return _iso(ts)
    except (OSError, ValueError):
        pass
    try:
        return os.path.getmtime(os.path.join(d, "chat_history.jsonl"))
    except OSError:
        return None


def load_opencode(since_ts):
    db = os.path.join(HOME, ".local/share/opencode/opencode.db")
    if not os.path.exists(db):
        return
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    sessions = con.execute(
        "select id, directory, parent_id, time_created from session where time_created >= ?",
        (int(since_ts * 1000),)).fetchall()
    for sid, cwd, parent, created in sessions:
        rows = con.execute(
            "select p.data, m.data, m.id from part p join message m on m.id = p.message_id "
            "where p.session_id = ? order by p.time_created, p.id", (sid,)).fetchall()
        acts, step, last_msg = [], 0, None
        for pdata, mdata, mid in rows:
            try:
                part, msg = json.loads(pdata), json.loads(mdata)
            except ValueError:
                continue
            role = msg.get("role")
            if part.get("type") == "text" and role == "user":
                acts += prompt_actions(step, [part.get("text", "")])
            elif part.get("type") == "tool":
                if mid != last_msg:
                    step += 1
                    last_msg = mid
                args = (part.get("state") or {}).get("input") or {}
                acts += classify(step, part.get("tool", ""), args)
        yield dict(host="opencode", id=sid, start=created / 1000, cwd=cwd, sub=bool(parent), actions=acts)
    con.close()


LEDGER = os.path.join(HOME, ".local/state/agent-observer/observer.db")
LEDGER_SUB_SOURCES = ("subagent",)


def _ledger_args(harness, name, target):
    """Rebuild the argument shape classify() expects from an Agent Observer target."""
    if name in READ_TOOLS or (name in EDIT_TOOLS and name != "apply_patch"):
        return {"file_path": target}
    if name in CMD_TOOLS:
        return {"command": target}
    if name in ("Skill", "skill"):
        return {"skill": target}
    return target


def load_ledger(since_ts, db=LEDGER):
    """Agent Observer ledger (0.6.0+, privacy version 6), opened read-only.

    One unit per session, and per source file for Codex: Agent Observer files a
    Codex child-thread rollout that carries its parent's id under the parent
    session, but each thread has its own context, and the native loader reads it
    as its own unit. Claude copies (a symlinked project directory) count once,
    as in load_claude. Tool calls come from
    `tool_call` events with full targets; OpenCode Skill calls from
    `skill_invoke`. Prompts are only the 300-character excerpt of genuine
    main-session submissions, so prompt-triggered rows do not port.
    Steps (assistant messages): time order. Claude Code writes each tool_use
    block as its own record (0 of 22,594 records since 2026-09-15 hold two), so
    each Claude call is its own step here as in load_claude. Grok calls in one
    message share a timestamp. OpenCode numbers every part and a message's tool parts sit between
    its step-start and step-finish parts, so consecutive ordinals share a step.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    sessions = con.execute(
        "select session_key, harness, native_id, started_at, project_dir,"
        " parent_session_key is not null or role = 'subagent' from sessions"
        " where harness in ('claude', 'codex', 'grok', 'opencode') and started_at >= ?",
        (since_ts,)).fetchall()
    for key, harness, native_id, start, cwd, sub in sessions:
        rows = con.execute(
            "select 'e', family, name, target, ts, ordinal_num, id, source_id from events"
            " where session_key = ? and (family = 'tool_call' or"
            " (family = 'skill_invoke' and session_key like 'opencode:%'))"
            " union all select 's', kind, '', text_excerpt, ts, ordinal_num, rowid, source_id"
            " from submissions where session_key = ? and is_genuine = 1"
            " order by 5, 6, 7", (key, key)).fetchall()
        by_source = defaultdict(list)
        for r in rows:  # Claude copies of one file split their rows across sources
            by_source[r[7] if harness == "codex" else None].append(r)
        if not by_source:
            by_source[None] = []
        if harness == "claude" and ":agent:" in native_id:  # native file name is agent-<id>.jsonl
            native_id = "agent-" + native_id.rsplit(":", 1)[1]
        for source_id, src_rows in by_source.items():
            thread = con.execute("select thread_source, path from sources where id = ?",
                                 (source_id,)).fetchone() if source_id else None
            thread = thread or (None, None)
            acts, step, last = [], 0, None
            for kind, family, name, target, ts, ordinal, _i, _s in src_rows:
                if kind == "s":
                    acts += prompt_actions(step, [target])
                    continue
                if harness == "grok":
                    same = ts == last
                    last = ts
                elif harness == "opencode":
                    same = last is not None and ordinal is not None and ordinal - last in (0, 1)
                    last = ordinal
                else:
                    same = False
                step += not same
                if family == "skill_invoke":
                    acts.append(Action(step, "skill", "skill", json.dumps({"skill": target or ""})))
                elif harness == "codex" and name == "exec" and target:
                    acts += codex_exec(step, target)
                else:
                    acts += classify(step, name or "", _ledger_args(harness, name, target or ""))
            first_ts = min((r[4] for r in src_rows if r[4] is not None), default=start)
            yield dict(host=harness, id=native_id, start=min(start, first_ts) if len(by_source) == 1 else first_ts,
                       cwd=cwd or "", sub=bool(sub) or thread[0] in LEDGER_SUB_SOURCES,
                       path=thread[1], actions=acts)
    con.close()


def _iso(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def _unquote(s):
    from urllib.parse import unquote
    return unquote(s)


# ---------------------------------------------------------------- measure

def measure(sessions):
    stats = {rid: dict(trigger=0, fired=0, sub=0, hosts=defaultdict(lambda: [0, 0])) for rid, *_ in ROWS}
    for s in sessions:
        acts = s["actions"]
        for rid, _label, trig, files in ROWS:
            t = trig(acts)
            if t is None:
                continue
            fired = any(a.step <= t.step and any(reads_file(a, f) for f in files) for a in acts)
            st = stats[rid]
            st["trigger"] += 1
            st["fired"] += fired
            st["sub"] += bool(s["sub"])
            st["hosts"][s["host"]][0] += 1
            st["hosts"][s["host"]][1] += fired
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_since = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    ap.add_argument("--since", default=default_since, help="session start date, YYYY-MM-DD (default: 14 days ago)")
    ap.add_argument("--exclude", nargs="*", default=[], help="session ids to leave out")
    ap.add_argument("--top-level", action="store_true", help="leave out subagent/child sessions")
    ap.add_argument("--include-tmp", action="store_true",
                    help="keep sessions whose cwd is under /tmp or /var/folders (eval and probe runs)")
    ap.add_argument("--until", help="leave out sessions started at or after this ISO time (UTC unless offset given)")
    ap.add_argument("--ledger", nargs="?", const=LEDGER, metavar="DB",
                    help="read the Agent Observer ledger instead of native records (default path: %(const)s)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", metavar="ROW", help="print each triggering session and call for one row")
    a = ap.parse_args()
    since_ts = dt.datetime.fromisoformat(a.since).replace(tzinfo=dt.timezone.utc).timestamp()

    coverage, sessions, dropped = defaultdict(lambda: [0, 0]), [], defaultdict(int)
    until_ts = None
    if a.until:
        until = dt.datetime.fromisoformat(a.until)
        until_ts = (until if until.tzinfo else until.replace(tzinfo=dt.timezone.utc)).timestamp()
    loaders = [lambda t: load_ledger(t, a.ledger)] if a.ledger else [load_claude, load_codex, load_grok, load_opencode]
    for loader in loaders:
        for s in loader(since_ts):
            if until_ts is not None and s["start"] >= until_ts:
                continue
            if s["id"] in a.exclude or (a.top_level and s["sub"]):
                continue
            if not a.include_tmp and EVAL_CWD.search(s["cwd"] or ""):
                dropped[s["host"]] += 1
                continue
            coverage[s["host"]][0] += 1
            coverage[s["host"]][1] += bool(s["sub"])
            sessions.append(s)
    stats = measure(sessions)

    if a.show:
        row = next(r for r in ROWS if r[0] == a.show)
        for s in sessions:
            t = row[2](s["actions"])
            if t is not None:
                fired = any(x.step <= t.step and any(reads_file(x, f) for f in row[3]) for x in s["actions"])
                snippet = re.sub(r"\s+", " ", t.text + " " + " ".join(t.paths))[:160]
                print(f"{s['host']}\t{s['id']}\t{'fired' if fired else 'SKIP'}\t{s['cwd']}\t{snippet}")
        return

    if a.json:
        json.dump(dict(since=a.since, coverage={h: dict(sessions=v[0], subagent=v[1], dropped_tmp=dropped[h])
                                                for h, v in coverage.items()},
                       rows={rid: dict(st, hosts={h: dict(trigger=v[0], fired=v[1]) for h, v in st["hosts"].items()})
                             for rid, st in stats.items()}), sys.stdout, indent=2)
        print()
        return

    print(f"since {a.since}; sessions per host (subagent/child in parentheses; tmp/eval cwd dropped):")
    for h in ("claude", "codex", "grok", "opencode"):
        n, sub = coverage.get(h, [0, 0])
        print(f"  {h}: {n} ({sub}); dropped {dropped[h]}")
    print()
    print("| Row | Procedure | Trigger sessions | Fired | Skip rate | Subagent share | By host (fired/trigger) |")
    print("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    for rid, label, _t, _f in ROWS:
        st = stats[rid]
        n, fz = st["trigger"], st["fired"]
        skip = f"{(n - fz) / n:.0%}" if n else "n/a"
        subs = f"{st['sub']}/{n}" if n else "-"
        hosts = ", ".join(f"{h} {v[1]}/{v[0]}" for h, v in sorted(st["hosts"].items())) or "-"
        print(f"| `{rid}` | {label} | {n} | {fz} | {skip} | {subs} | {hosts} |")


if __name__ == "__main__":
    main()
