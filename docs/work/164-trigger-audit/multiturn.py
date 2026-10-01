#!/usr/bin/env python3
"""Multi-turn routing test for Issue #164 (evidence only, not a release gate).

The single-prompt harness (trigger_test.py) gives each run a fresh session, so the
session-start pointer is always the latest thing the model saw. Real failures
happen later: a long conversation where each new user turn starts a new kind of
action (session 86d43ea9, 2026-10-01). Here one session gets five user turns in
order, and each routed action is scored against the reads made before it in the
whole session.

Hosts, arms, confinement, plugin loading and scoring reuse trigger_test.py. Turns
continue one session the way each host continues it:

  claude    one `claude -p --input-format stream-json` process; each turn is a new
            user message on stdin, sent after the previous turn's result event
            (SessionStart fires once, as in an interactive or T3 session)
  codex     `codex exec`, then `codex exec resume --last` per turn
  grok      `grok -p`, then `grok -p --continue` per turn
  opencode  `opencode run`, then `opencode run --continue` per turn

Arm `none` is the no-guidance control: the host with its login only, no global
rules file and no plugin.

  python3 multiturn.py canary --host claude --arms main,branch,none
  python3 multiturn.py run --host claude --model claude-opus-5-5 --effort medium \\
      --arms main=<ref>,branch=<ref>,none --runs 5 --record multiturn.jsonl
  python3 multiturn.py --summary multiturn.jsonl
"""
import argparse
import concurrent.futures
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True  # no __pycache__ in the checkout the guard watches
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import trigger_test as tt  # noqa: E402

VC, DELIVERY, ORCH = "version-control/index.md", "references/delivery.md", "references/orchestration.md"
RESEARCH, IMPL, VERIF = "research/index.md", "references/implementation.md", "references/verification.md"
REWORDED = [VC, DELIVERY, ORCH]
DELEGATE = r"tool:(?i:Agent|Task|spawn_agent|spawn_subagent|spawn_thread|subagent|delegate|task)"
SPAWN_SHELL = r"bash:\b(codex\s+exec|claude\s+-p|opencode\s+run|grok\s+(-p|--prompt))\b"

# (turn id, prompt, moment, required files scored at that moment). A required file
# counts when it was read before the moment, anywhere earlier in the session.
TURNS = [
    ("question", "What does divide() in {repo}/src/app.py do when b is 0? Answer from the code only.",
     ("end",), []),
    ("research", "We want to hear about errors like that from people who use this library. Research the "
                 "options for error reporting in a small Python library and recommend one. Do not change "
                 "anything yet.", ("end",), [RESEARCH]),
    ("commit", "Start small: make divide() raise ValueError with a clear message when b is 0, then commit "
               "the change.", ("edit", r"bash:\bgit\b[^|;&]*\bcommit\b"), [IMPL, VC]),
    ("pr", "Now open a pull request for it with gh pr create. There is no remote; the gh on PATH handles it.",
     (r"bash:\bgh\s+pr\s+create\b",), [VERIF, DELIVERY]),
    ("delegate", "Before I merge, have a separate agent review the change independently and report back to me.",
     (DELEGATE, SPAWN_SHELL), [ORCH]),
]
CANARY = ("Do not run any tools. Answer in exactly three lines. Line 1: quote the first heading of your "
          "user-level global instructions file (CLAUDE.md or AGENTS.md), or NONE. Line 2: is a Skill named "
          "operations available to you? yes or no. Line 3: does your context contain a note that begins "
          "'AgentsMD: at the start of every task'? yes or no.")
TURN_TIMEOUT = 1200


def make_home(host, arm):
    if arm != "none":
        return tt.make_home(host, arm)
    home = pathlib.Path(tempfile.mkdtemp(prefix=tt.PREFIX + "home-"))
    try:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "CODEX_", "GROK_", "OPENCODE_", "XDG_"))}
        env.pop("CLAUDE_CONFIG_DIR", None)
        env["HOME"] = str(home)
        (home / "bin").mkdir()
        (home / "bin/gh").write_text(tt.GH_STUB)
        (home / "bin/gh").chmod(0o755)
        if host != "grok":
            (home / "bin/grok").write_text(tt.GROK_STUB)
            (home / "bin/grok").chmod(0o755)
        env["PATH"] = f"{home / 'bin'}{os.pathsep}{env['PATH']}"
        plugin = home / "plugin"  # empty: nothing to load
        plugin.mkdir()
        if host == "claude":
            config = home / ".claude"
            config.mkdir()
            (config / "settings.json").write_text(json.dumps(tt.claude_settings(home)))
            if tt.KEYCHAINS.is_dir():
                (home / "Library").mkdir()
                (home / "Library/Keychains").symlink_to(tt.KEYCHAINS)
            real = json.loads(tt.CLAUDE_JSON.read_text())
            (home / ".claude.json").write_text(json.dumps({k: real[k] for k in ("oauthAccount", "userID") if k in real}))
        elif host == "codex":
            env["CODEX_HOME"] = str(home / "codex")
            tt.link_login(home / "codex/auth.json", tt.LOGIN["codex"])
        elif host == "grok":
            env["GROK_HOME"] = str(home / "grok")
            tt.link_login(home / "grok/auth.json", tt.LOGIN["grok"])
        else:
            config = home / "opencode"
            env.update(OPENCODE_CONFIG_DIR=str(config), XDG_DATA_HOME=str(home / "data"),
                       XDG_CACHE_HOME=str(home / "cache"), XDG_CONFIG_HOME=str(home / "config"))
            tt.link_login(home / "data/opencode/auth.json", tt.LOGIN["opencode"])
            config.mkdir()
            (config / "opencode.json").write_text(json.dumps({
                "$schema": "https://opencode.ai/config.json",
                "permission": {"edit": "allow", "bash": "allow", "webfetch": "deny",
                               "external_directory": {"*": "deny"}}}))
        return home, plugin, env
    except BaseException:
        tt.remove(home)
        raise


def turn_command(host, model, effort, repo, plugin, prompt, first, arm):
    """Command for one turn on codex, grok or opencode (claude runs in one process)."""
    cmd = tt.command(host, model, effort, repo, plugin, prompt)
    if host == "codex":
        cmd.remove("--ephemeral")
        # workspace-write keeps .git read-only, so a commit would fail; the live setup runs
        # danger-full-access. Only the run's own .git is added.
        cmd[2:2] = ["-c", f'sandbox_workspace_write.writable_roots=["{repo.resolve()}/.git"]']
        if not first:
            # `exec resume` takes no -s or -C: the sandbox goes through config, cwd is the repo.
            i = cmd.index("-s")
            del cmd[i:i + 2]
            i = cmd.index("-C")
            del cmd[i:i + 2]
            cmd[1:2] = ["exec", "resume", "--last"]
            cmd[4:4] = ["-c", 'sandbox_mode="workspace-write"']
            cmd = [c for c in cmd if c != prompt] + [prompt]
    elif host == "grok" and not first:
        cmd.append("--continue")
    elif host == "opencode" and not first:
        cmd.insert(-1, "--continue")
    if arm == "none" and host == "claude":
        i = cmd.index("--plugin-dir")
        del cmd[i:i + 2]
    return cmd


def claude_session(cmd, cwd, env, prompts):
    """Run every prompt as a user message in one stream-json session; return (stream, turn starts by line)."""
    cmd = [c for c in cmd[:-1] if c != "--no-session-persistence"]
    cmd[cmd.index("-p") + 1:cmd.index("-p") + 1] = ["--input-format", "stream-json"]
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    lines, starts, results, complete = [], [], [], []
    done = threading.Event()

    def reader():
        for line in proc.stdout:
            lines.append(line)
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                results.append(not event.get("is_error"))
                done.set()
        done.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        for prompt in prompts:
            starts.append(len(lines))
            done.clear()
            count = len(results)
            proc.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n")
            proc.stdin.flush()
            deadline = time.monotonic() + TURN_TIMEOUT
            while len(results) == count and proc.poll() is None and time.monotonic() < deadline:
                done.wait(5)
            if len(results) == count:
                break
            complete.append(results[-1])
        proc.stdin.close()
        proc.wait(60)
    except (BrokenPipeError, subprocess.TimeoutExpired):
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        thread.join(5)
    return lines, starts, complete + [False] * (len(prompts) - len(complete))


def execute(host, cmd, cwd, env):
    """trigger_test.execute, plus whether the process ended on its own with exit code 0."""
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    lines, last = [], [time.monotonic()]

    def reader():
        for line in proc.stdout:
            lines.append(line)
            last[0] = time.monotonic()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    start, silence, killed = time.monotonic(), tt.SILENCE.get(host, tt.TIMEOUT), False
    try:
        while proc.poll() is None:
            now = time.monotonic()
            if now - start > tt.TIMEOUT or now - last[0] > silence:
                killed = True
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
    return "".join(lines), not killed and proc.returncode == 0


def turn_done(text, host):
    """The host's end-of-turn event is in the stream: Codex turn.completed, OpenCode step_finish, Grok a
    result event whose is_error is false (Claude's result events are checked in claude_session)."""
    events = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if host == "grok":
        results = [e for e in events if e.get("type") == "result"]
        return bool(results) and results[-1].get("is_error") is False
    return any(e.get("type") == {"codex": "turn.completed", "opencode": "step_finish"}[host] for e in events)


def session(host, model, effort, arm, repo, plugin, env, prompts):
    """Return (stream text, call indexes where each turn starts, whether each turn completed).

    A turn completed when the host finished it on its own: Claude's result event without an error;
    elsewhere exit code 0 before the watchdog, with the host's end-of-turn event (Grok's result
    event must not be an error)."""
    if host == "claude":
        cmd = turn_command(host, model, effort, repo, plugin, "PROMPT", True, arm)
        lines, starts, complete = claude_session(cmd, repo, env, prompts)
        stream = "".join(lines)
        bounds = [sum(1 for _ in tool_calls("".join(lines[:s]), host)) for s in starts]
        return stream, bounds, complete
    stream, bounds, complete = "", [], []
    for n, prompt in enumerate(prompts):
        bounds.append(sum(1 for _ in tool_calls(stream, host)))
        text, ok = execute(host, turn_command(host, model, effort, repo, plugin, prompt, n == 0, arm), repo, env)
        ok = ok and turn_done(text, host)
        stream += text
        complete.append(ok)
    return stream, bounds, complete


def tool_calls(stream, host):
    return [entry[0] for entry in parse(stream, host)]


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(c.get("text", c.get("content", ""))) if isinstance(c, dict) else str(c) for c in content)
    return "" if content is None else json.dumps(content)


def parse(stream, host):
    """[(call, output, called_at, returned_at)]: trigger_test's calls in order (plus Codex's non-shell tool
    items by name), each with the text its tool returned ("" when none was recorded), the stream event at
    which it was invoked and the event at which its output arrived (infinity when none did). OpenCode
    reports a tool part once, when it has finished, so both positions are that event."""
    never = float("inf")
    events = []
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            events.append(event)
    if host == "codex":
        items, order, thread, started, completed = {}, [], 0, {}, {}
        for pos, event in enumerate(events):
            if event.get("type") == "thread.started":
                thread += 1  # each resumed `codex exec` numbers its items from item_0 again
            item = event.get("item") or {}
            if event.get("type") not in ("item.started", "item.completed"):
                continue
            key = (thread, item.get("id"))
            if key not in items:
                order.append(key)
                started[key] = pos
            if event.get("type") == "item.completed":
                completed.setdefault(key, pos)
            items[key] = item
        result = []
        for key in order:
            item = items[key]
            kind = item.get("type")
            if kind == "command_execution":
                done = item.get("status") == "completed" and item.get("exit_code") is not None
                result.append((("Bash", "", str(item.get("command", "")), ""),
                               str(item.get("aggregated_output") or "") if done else "",
                               started[key], completed.get(key, never) if done else never))
            elif kind == "file_change":
                for change in item.get("changes") or [{}]:
                    result.append((("Edit", str(change.get("path", "")), "", ""), "", started[key], never))
            elif kind and kind not in ("agent_message", "reasoning", "todo_list", "error", "web_search"):
                result.append(((str(item.get("tool") or item.get("name") or kind), "", "", ""), "", started[key],
                               never))
        return result
    calls = list(tt.tool_calls(stream, host))
    if host == "opencode":
        outputs, order, at = {}, [], {}
        for pos, event in enumerate(events):
            part = event.get("part") or {}
            if event.get("type") == "tool_use":
                if part.get("callID") not in outputs:
                    order.append(part.get("callID"))
                    at[part.get("callID")] = pos
                state = part.get("state") or {}
                outputs[part.get("callID")] = _text(state.get("output")) if state.get("status") == "completed" else ""
        found = [(outputs[k], at[k], at[k] if outputs[k] else never) for k in order]
        return [(c, *x) for c, x in zip(calls, found + [("", never, never)] * (len(calls) - len(found)))]
    ids, outputs, called, returned = [], {}, {}, {}
    for pos, event in enumerate(events):
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None  # some events carry a string
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use" and block.get("id") not in ids:
                ids.append(block.get("id"))
                called[block.get("id")] = pos
            elif (event.get("type") == "user" and block.get("type") == "tool_result" and not block.get("is_error")
                  and block.get("tool_use_id") not in outputs):
                outputs[block.get("tool_use_id")] = _text(block.get("content"))
                returned[block.get("tool_use_id")] = pos
    found = [(outputs.get(i, ""), called[i], returned.get(i, never)) for i in ids]
    return [(c, *x) for c, x in zip(calls, found + [("", never, never)] * (len(calls) - len(found)))]


def heading(plugin, f):
    """First Markdown heading of a procedure in a plugin copy, or None when it has none."""
    for path in sorted((pathlib.Path(plugin) / "skills/operations").rglob(pathlib.Path(f).name)):
        if str(path).endswith(f):
            return next((l.strip() for l in path.read_text().splitlines() if l.startswith("# ")), None)
    return None


def first_hit(calls, spec, start, end):
    """Index of the first call in [start, end) matching any alternative of spec; "end" means end."""
    hits = []
    for alternative in spec:
        if alternative == "end":
            hits.append(end)
            continue
        for i in range(start, end):
            name, path, command, _ = calls[i]
            if alternative == "edit":
                hit = (name == "Edit" and "/.claude/" not in path) or (
                    name == "Bash" and tt.SHELL_EDIT.search(command) is not None)
            elif alternative.startswith("tool:"):
                hit = re.fullmatch(alternative[5:], name) is not None
            else:
                hit = name == "Bash" and re.search(alternative[5:], command) is not None
            if hit:
                hits.append(i)
                break
    return min(hits) if hits else None


def score_session(stream, bounds, host, headings):
    """A read counts when the call names the file and its returned text contains the file's first
    heading: a failed, refused or merely echoed read does not. It counts before an action only when its
    output arrived before the action was invoked. `reads` reports the index of the call whose output
    arrived first."""
    parsed = parse(stream, host)
    calls = [entry[0] for entry in parsed]
    called = [entry[2] for entry in parsed] + [float("inf")]  # called[len(calls)]: after the last call
    files = sorted({f for *_, req in TURNS for f in req} | set(REWORDED))
    returned = {f: min(((ret, i) for i, (c, out, _, ret) in enumerate(parsed)
                        if headings.get(f) and tt.reads_file(c, f) and headings[f] in out),
                       default=(float("inf"), None)) for f in files}
    reads = {f: returned[f][1] for f in files}

    def before(f, index):
        """The file's content had arrived before call `index` was invoked (or before the session ended)."""
        return returned[f][0] < called[index]

    entry = next((i for i, (name, _, _, skill) in enumerate(calls)
                  if (name == "Skill" and skill.split(":")[-1] == "operations") or tt.reads_file(calls[i], tt.ENTRY)),
                 None)
    turns = {}
    for n, (turn, _, moment, required) in enumerate(TURNS):
        if n >= len(bounds):
            turns[turn] = {"status": "not-run"}
            continue
        start, end = bounds[n], bounds[n + 1] if n + 1 < len(bounds) else len(calls)
        at = first_hit(calls, moment, start, end)
        verdict = {}
        for f in required:
            # Required files are scored against the moment the action first happens in this turn; "edit" is
            # the implementation file's moment, the rest use the turn's other alternatives.
            spec = ("edit",) if f == IMPL else tuple(a for a in moment if a != "edit") or moment
            hit = first_hit(calls, spec, start, end)
            if hit is None:
                verdict[f] = "read-noaction" if before(f, end) else "noaction"
            else:
                verdict[f] = "fired" if before(f, hit) else "skip"
        turns[turn] = {"start": start, "moment_at": at, "verdict": verdict}
    # Over-trigger check: a reworded file opened during the question or research turns.
    early_end = bounds[2] if len(bounds) > 2 else len(calls)
    opened_early = sorted(f for f in REWORDED if before(f, early_end))
    return {"calls": len(calls), "entry_loaded_at": entry, "reads": reads, "turns": turns,
            "reworded_opened_in_turns_1_2": opened_early,
            "call_list": [[c[0], c[1] or " ".join(c[2].split())[:300] or c[3]] for c in calls]}


def run_one(host, model, effort, arm, index, before):
    repo = home = None
    try:
        repo = tt.make_repo()
        home, plugin, env = make_home(host, arm)
        prompts = [p.format(repo=repo.resolve()) for _, p, _, _ in TURNS]
        started = time.time()
        stream, bounds, complete = session(host, model, effort, arm, repo, plugin, env, prompts)
        files = sorted({f for *_, req in TURNS for f in req} | set(REWORDED))
        # The control loads no plugin, so its reads are scored against a real arm's procedures.
        source = plugin if arm != "none" else next(
            v for k, v in tt.SOURCES.items() if not k.endswith("-sha"))
        headings = {f: heading(source, f) for f in files}
        if not all(headings.values()):
            raise RuntimeError(f"no heading for {[f for f, h in headings.items() if not h]}")
        after = tt.snapshot()
        if after != before:
            changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
            raise tt.Escaped(f"{changed} changed during {host} {arm} run {index}")
        item = {"host": tt.HOST_LABEL.get(host, host), "model": model, "effort": effort or None, "arm": arm,
                "source": tt.SOURCES.get(arm + "-sha", "")[:7] or None, "run": index,
                "seconds": round(time.time() - started), "turns_started": len(bounds),
                "turns_completed": complete, "usage": tt.usage(stream, host),
                **score_session(stream, bounds, host, headings)}
        item["call_list"] = [[n, tt.anonymize(t, repo, plugin)] for n, t in item["call_list"]]
        item["valid"] = len(complete) == len(TURNS) and all(complete) and item["calls"] > 0
        return item
    finally:
        tt.remove(repo)
        tt.remove(home)


def canary(host, model, effort, arm):
    repo = home = None
    try:
        repo = tt.make_repo()
        home, plugin, env = make_home(host, arm)
        cmd = turn_command(host, model, effort, repo, plugin, CANARY, True, arm)
        if host == "codex":
            cmd.append("--ephemeral")
        stream = tt.execute(host, cmd, repo, env)
        text = reply_text(stream, host)
        lines = [l.strip().strip("`*\"' ") for l in text.strip().splitlines() if l.strip()]
        pointer = host in ("claude", "opencode") and arm != "none"
        want = (["NONE", "no", "no"] if arm == "none" else
                ["# Global Agent Rules", "yes", "yes" if pointer else None])
        ok = len(lines) >= 3 and all(
            w is None or lines[i].lower().lstrip("# ").endswith(w.lower().lstrip("# ")) for i, w in enumerate(want))
        return {"host": host, "model": model, "arm": arm, "reply": text.strip()[-400:], "want": want, "pass": ok}
    finally:
        tt.remove(repo)
        tt.remove(home)


def reply_text(stream, host):
    """Final assistant text of a single-turn run."""
    text = ""
    for line in stream.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if host in ("claude", "grok") and event.get("type") == "result":
            text = event.get("result") or text
        elif host == "codex" and (event.get("item") or {}).get("type") == "agent_message":
            text = event["item"].get("text") or text
        elif host == "opencode" and event.get("type") == "text":
            text += (event.get("part") or {}).get("text", "")
    return text


def summary(path):
    records = [json.loads(l) for l in open(path)]
    cells = {}
    for r in records:
        if not r.get("valid"):
            continue
        key = (r["host"], r["model"], r["arm"])
        c = cells.setdefault(key, {"runs": 0, "early": 0, "entry": 0, "files": {}})
        c["runs"] += 1
        c["early"] += bool(r["reworded_opened_in_turns_1_2"])
        c["entry"] += r["entry_loaded_at"] is not None
        for turn, t in r["turns"].items():
            for f, v in t.get("verdict", {}).items():
                c["files"].setdefault(f"{turn}: {f}", []).append(v)
    for (host, model, arm), c in sorted(cells.items()):
        print(f"\n### {host}, `{model}`, arm {arm}: {c['runs']} valid runs\n")
        print(f"- operations loaded at some point: {c['entry']}/{c['runs']}")
        print(f"- reworded file opened in the question or research turn: {c['early']}/{c['runs']}\n")
        print("| Turn: required file | fired before the action | detail |\n| --- | --- | --- |")
        for f, vs in c["files"].items():
            acted = [v for v in vs if v in ("fired", "skip")]
            detail = ", ".join(f"{v} {vs.count(v)}" for v in sorted(set(vs)))
            print(f"| {f} | {vs.count('fired')}/{len(acted)} | {detail} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", nargs="?", choices=["run", "canary"])
    parser.add_argument("--host", choices=sorted(tt.SETUP), default="claude")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="")
    parser.add_argument("--arms", default="main,branch,none")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--record")
    parser.add_argument("--summary")
    args = parser.parse_args()
    if args.summary:
        summary(args.summary)
        return 0
    arms = [a.partition("=")[0] for a in args.arms.split(",")]
    git_arms = {a: r or tt.DEFAULT_REFS[a] for a, r in (x.partition("=")[::2] for x in args.arms.split(","))
                if a != "none"}
    # The control is scored against main's procedures, so a control-only batch still extracts main.
    sources = tt.extract_sources(git_arms or {"main": tt.DEFAULT_REFS["main"]})
    try:
        tt.guard_self_check()
        before = tt.snapshot()
        if args.mode == "canary":
            results = [canary(args.host, args.model, args.effort, arm) for arm in arms]
            for r in results:
                print(json.dumps(r))
            if args.record:
                with open(args.record, "a") as out:
                    for r in results:
                        out.write(json.dumps(r) + "\n")
            return 0 if all(r["pass"] for r in results) else 1
        jobs = [(arm, i) for i in range(1, args.runs + 1) for arm in arms]  # arms interleaved
        lock = threading.Lock()
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            futures = {pool.submit(run_one, args.host, args.model, args.effort, arm, i, before): (arm, i)
                       for arm, i in jobs}
            for future in concurrent.futures.as_completed(futures):
                arm, i = futures[future]
                item = future.result()
                with lock:
                    verdicts = {k: v.get("verdict") for k, v in item["turns"].items()}
                    print(f"{args.host} {arm} run {i}: valid={item['valid']} calls={item['calls']} "
                          f"{json.dumps(verdicts)}", flush=True)
                    if args.record:
                        # The record file lives outside the guarded checkouts while runs are active.
                        with open(args.record, "a") as out:
                            out.write(json.dumps(item) + "\n")
        return 0
    finally:
        if sources:
            tt.remove(sources)


if __name__ == "__main__":
    sys.exit(main())
