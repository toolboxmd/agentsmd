#!/usr/bin/env python3
"""Round 2 runner for #198: every harness loads the arm's rules file the way the host loads it in real use.

Each attempt runs in a fresh temporary HOME with an empty temporary cwd. The
arm's rules file is the only global instruction, at the host's global path:
Claude Code ~/.claude/CLAUDE.md, Codex ~/.codex/AGENTS.md (CODEX_HOME), Grok
~/.grok/AGENTS.md, OpenCode ~/.config/opencode/AGENTS.md. Arms are read from
exact commits, never the working tree. Single turn, no tools.

Every attempt gets its own output and meta file. Timeouts, empty output, non-zero
exits and harness errors are invalid, kept, and retried until VALID_TARGET valid
(at most MAX_RETRIES retries per cell).

Usage: r2.py RUN_DIR canary | run [harnesses] [cells] [NAME=PATH,...]
  cells: comma list of ARM:SCENARIO[:VALID], default A,B,C target and C control, 5 valid each.
  NAME=, NAME=PATH or NAME=git:SHA: arms (NAME= means no rules file) from a candidate file or global/AGENTS.md at a commit; when given,
  only these arms are used.
"""
import concurrent.futures as cf, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCENARIOS = HERE / "scenarios.json"
FROZEN_SHA = "0f09353fccbfcd03ae2beb455783ed9e765b8ff4bff28e01cbf76d1a844c694b"
HELDOUT = HERE / "heldout.json"  # frozen in #198 comment 5935480165; same envelope, rubric is grader-only
HELDOUT_SHA = "cfcf4d894a2614a39e6426c2e042692ab83688450f82687b8bea33ca51e42522"
ARM_SHAS = {"A": None, "B": "8cad98f68a8ce46dc8bb05954775dd63172a9f26", "C": "d32c7d4ece13e666baa05e44534ccd8886cff62c"}
HARNESSES = {
    "codex": ("codex", "gpt-6-astra"),
    "codex-sol": ("codex", "gpt-6.1-sol"),
    "grok": ("grok", "grok-4.7"),
    "opencode": ("opencode", "opencode/muse-spark-1.3-contributor-free"),
    "claude-sonnet-5": ("claude", "claude-sonnet-5"),
    "claude-opus-5-5": ("claude", "claude-opus-5-5"),
}
CELLS = ["A:target-monitoring", "B:target-monitoring", "C:target-monitoring", "C:control-trivial"]
VALID_TARGET, MAX_RETRIES, TIMEOUT, PER_HARNESS = 5, 3, 420, 4
CANARY = ("Do not run tools. Answer two lines only. Line 1: does any instruction you were given (system prompt, "
          "AGENTS.md, CLAUDE.md, or memory) contain a section titled 'Elon method'? yes or no. Line 2: quote the "
          "first heading of any user-level or global instructions file you were given, or NONE.")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ERROR = re.compile(r"rate.?limit|quota|unauthori[sz]ed|authenticat|api error|internal server error|"
                   r"overloaded|ECONNRESET|model not found|insufficient|usage limit", re.I)
REAL = Path.home()
DROP = ("CLAUDE_CODE_", "CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_AGENT_SDK", "CLAUDE_CONFIG_DIR",
        "ANTHROPIC_", "AGENTSMD_", "GROK_SESSION_ID", "GROK_AGENT", "CODEX_", "OPENCODE_", "XDG_")
CODEX_CONFIG = '''model = "{model}"
model_reasoning_effort = "medium"
cli_auth_credentials_store = "file"
approval_policy = "never"
web_search = "disabled"
[features]
skip_host_skill_discovery = true
plugins = false
hooks = false
apps = false
recommended_plugins = false
shell_snapshot = false
shell_tool = false
'''


def claude_token():
    """Login OAuth access token from the macOS keychain, kept in memory only."""
    raw = subprocess.run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(raw)["claudeAiOauth"]["accessToken"]


def setup(host, model, rules, home, work):
    """Isolated HOME; returns the environment. rules is the arm file path or None."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(DROP)}
    env.update(HOME=str(home), PWD=str(work))  # OpenCode reads PWD, not the real cwd
    if host == "claude":
        cfg = home / ".claude"
        cfg.mkdir(parents=True)
        if rules:
            shutil.copy(rules, cfg / "CLAUDE.md")
        env.update(CLAUDE_CONFIG_DIR=str(cfg), CLAUDE_CODE_OAUTH_TOKEN=claude_token())
    elif host == "codex":
        ch = home / ".codex"
        ch.mkdir(parents=True)
        shutil.copyfile(REAL / ".codex/auth.json", ch / "auth.json")
        (ch / "auth.json").chmod(0o600)
        (ch / "config.toml").write_text(CODEX_CONFIG.replace("{model}", model))
        if rules:
            shutil.copy(rules, ch / "AGENTS.md")
        env.update(CODEX_HOME=str(ch))
    elif host == "grok":
        g = home / ".grok"
        g.mkdir(parents=True)
        (g / "auth.json").symlink_to(REAL / ".grok/auth.json")
        if rules:
            shutil.copy(rules, g / "AGENTS.md")
        env.update(GROK_HOME=str(g))
    elif host == "opencode":
        cfg, data = home / ".config/opencode", home / ".local/share/opencode"
        cfg.mkdir(parents=True)
        data.mkdir(parents=True)
        (data / "auth.json").symlink_to(REAL / ".local/share/opencode/auth.json")
        if rules:
            shutil.copy(rules, cfg / "AGENTS.md")
        env.update(XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   OPENCODE_DISABLE_CLAUDE_CODE="1", OPENCODE_DISABLE_PROJECT_CONFIG="1",
                   OPENCODE_DISABLE_DEFAULT_PLUGINS="1", OPENCODE_PURE="1")
    return env


def command(host, model, prompt, last):
    if host == "claude":
        # --tools is variadic: keep it before other flags so it cannot swallow the prompt.
        return ["claude", "-p", "--tools", "", "--model", model, prompt]
    if host == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "--ignore-rules", "-s", "read-only", "-o", str(last), prompt]
    if host == "grok":
        return ["grok", "-m", model, "-p", prompt]
    return ["opencode", "run", "--pure", "-m", model, prompt]


def codex_session(home):
    """Model, effort, loaded AGENTS.md text and tool calls from the isolated Codex session log."""
    logs = list((home / ".codex/sessions").rglob("*.jsonl"))
    if len(logs) != 1:
        return {"session_logs": len(logs)}
    rec = [json.loads(line) for line in logs[0].read_text().splitlines()]
    tc = next((r["payload"] for r in rec if r["type"] == "turn_context"), {})
    world = next((r["payload"]["state"] for r in rec if r["type"] == "world_state"), {})
    tools = [r["payload"]["type"] for r in rec if r["type"] == "response_item"
             and r["payload"].get("type") in ("function_call", "custom_tool_call", "web_search_call")]
    text = (world.get("agents_md") or {}).get("text") or ""
    return {"model": tc.get("model"), "effort": tc.get("effort"), "tool_calls": tools,
            "agents_md_sha256": hashlib.sha256(text.strip().encode()).hexdigest() if text else None}


def attempt(base, arms, harness, arm, scenario, prompt, n, kind="outputs"):
    host, model = HARNESSES[harness]
    run_id = f"{harness}.{arm}.{scenario}.a{n}"
    out, meta = base / kind / f"{run_id}.txt", base / kind / f"{run_id}.meta.json"
    if out.exists() or meta.exists():
        raise SystemExit(f"refusing to reuse {run_id}")
    scratch = Path(tempfile.mkdtemp(prefix=f"198r2-{run_id}-"))
    home, work, last = scratch / "home", scratch / "work", scratch / "last.txt"
    work.mkdir()
    info = {"run_id": run_id, "harness": harness, "host": harness, "model": model, "arm": arm,
            "arm_sha256": arms[arm][1], "scenario": scenario, "attempt": n}
    started = time.time()
    try:
        env = setup(host, model, arms[arm][0], home, work)
        p = subprocess.run(command(host, model, prompt, last), cwd=work, env=env, capture_output=True, text=True,
                           timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        text = ANSI.sub("", last.read_text() if last.exists() else p.stdout).strip()
        info.update(exit=p.returncode, stderr_tail=ANSI.sub("", p.stderr)[-1500:])
        if host == "codex":
            info["codex"] = codex_session(home)
        if p.returncode != 0:
            info["invalid"] = f"exit {p.returncode}"
        elif not text:
            info["invalid"] = "empty output"
        elif len(text) < 600 and ERROR.search(text):
            info["invalid"] = "harness error text"
        elif host == "codex" and (info["codex"].get("model") != model or info["codex"].get("effort") != "medium"
                                  or info["codex"].get("tool_calls")):
            info["invalid"] = "codex session check failed"
    except subprocess.TimeoutExpired as e:
        text = ANSI.sub("", e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")).strip()
        info["invalid"] = f"timeout {TIMEOUT}s"
    except Exception as e:  # harness error
        text, info["invalid"] = "", f"harness error: {e!r}"
    info["seconds"] = round(time.time() - started, 1)
    info["valid"] = "invalid" not in info
    out.write_text(text + "\n")
    meta.write_text(json.dumps(info, indent=1) + "\n")
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"{run_id:55} {'valid' if info['valid'] else 'INVALID ' + info['invalid']:32} {info['seconds']:6.0f}s",
          flush=True)
    return info["valid"], text


def load_arms(base, files=None):
    """Copy each arm file (exact commit, or a candidate file) into the run dir; return {arm: (path, sha256)}."""
    (base / "arms").mkdir(exist_ok=True)
    arms = {}
    for arm, sha in (files or ARM_SHAS).items():
        if not sha:  # no rules file (ARM_SHAS None, or NAME= with an empty path)
            arms[arm] = (None, None)
            continue
        rev = sha[4:] if files and sha.startswith("git:") else None if files else sha
        data = Path(sha).read_bytes() if not rev else subprocess.run(
            ["git", "-C", str(REPO), "show", f"{rev}:global/AGENTS.md"], capture_output=True, check=True).stdout
        path = base / "arms" / f"{arm}.md"
        if path.exists() and path.read_bytes() != data:
            raise SystemExit(f"{path} differs from {sha}")
        path.write_bytes(data)
        arms[arm] = (path, hashlib.sha256(data).hexdigest())
    return arms


def canary(base, arms, harnesses):
    """One probe per harness and arm: heading quoted with a rules file, NONE without."""
    (base / "canary").mkdir(exist_ok=True)
    tag = "" if set(arms) == set(ARM_SHAS) else "." + "-".join(harnesses)
    results = {}

    def probe(h, a):
        start = 1 + len(list((base / "canary").glob(f"{h}.{a}.canary.a*.txt")))  # never reuse an attempt
        for n in range(start, start + MAX_RETRIES + 1):
            valid, text = attempt(base, arms, h, a, "canary", CANARY, n, "canary")
            if valid:
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                want = "NONE" if a == "A" else "# Global Agent Rules"
                # The heading text proves the file loaded; accept it with or without the leading "#".
                ok = bool(lines) and lines[-1].strip("`\"' ").lstrip("# ") == want.lstrip("# ")
                return {"pass": ok, "expected": want, "reply": text, "attempts": n}
        return {"pass": False, "expected": None, "reply": "no valid attempt", "attempts": n}

    with cf.ThreadPoolExecutor(15) as pool:
        futs = {(h, a): pool.submit(probe, h, a) for h in harnesses for a in arms}
        for k, f in futs.items():
            results[f"{k[0]}.{k[1]}"] = f.result()
    dest = base / f"canary{tag}.json"
    merged = {**(json.loads(dest.read_text()) if dest.exists() else {}), **results}  # keep earlier arms' canaries
    dest.write_text(json.dumps(merged, indent=1) + "\n")
    for k, r in results.items():
        print(f"canary {k:22} {'PASS' if r['pass'] else 'FAIL'}  {r['reply']!r}")
    return all(r["pass"] for r in results.values())


def cell(base, arms, harness, arm, sc, prompt, gate, target=VALID_TARGET):
    valid = invalid = n = 0
    while valid < target and invalid <= MAX_RETRIES:
        n += 1
        with gate[harness]:
            ok, _ = attempt(base, arms, harness, arm, sc, prompt, n)
        valid, invalid = valid + ok, invalid + (not ok)
    return harness, arm, sc, valid, invalid, target


def main():
    raw = SCENARIOS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA:
        raise SystemExit("scenarios.json changed after freeze")
    data = json.loads(raw)
    prompts = {s["id"]: data["preface"] + s["prompt"] for s in data["scenarios"]}
    held = HELDOUT.read_bytes()
    if hashlib.sha256(held).hexdigest() != HELDOUT_SHA:
        raise SystemExit("heldout.json changed after freeze")
    held = json.loads(held)
    prompts.update({s["id"]: held["preface"] + s["prompt"] for s in held["scenarios"]})
    base, mode = Path(sys.argv[1]).resolve(), sys.argv[2]
    harnesses = sys.argv[3].split(",") if len(sys.argv) > 3 else list(HARNESSES)
    cells = sys.argv[4].split(",") if len(sys.argv) > 4 else CELLS
    files = dict(x.split("=", 1) for x in sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    base.mkdir(parents=True, exist_ok=True)
    arms = load_arms(base, files)
    if mode == "canary":
        sys.exit(0 if canary(base, arms, harnesses) else 1)
    canaries = {}
    for c in base.glob("canary*.json"):
        canaries.update(json.loads(c.read_text()))
    for h in harnesses:
        for a in arms:
            if not canaries.get(f"{h}.{a}", {}).get("pass"):
                raise SystemExit(f"canary {h}.{a} has not passed; results would not count")
    (base / "outputs").mkdir(exist_ok=True)
    (base / f"manifest.{'-'.join(harnesses)}.{time.strftime('%Y%m%dT%H%M%S')}.json").write_text(json.dumps({
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "scenarios_sha256": FROZEN_SHA, "heldout_sha256": HELDOUT_SHA,
        "arms": {a: {"source": (files or ARM_SHAS)[a], "sha256": arms[a][1]} for a in arms},
        "harnesses": {h: HARNESSES[h] for h in harnesses}, "cells": cells,
        "repo_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                    text=True).stdout.strip(),
    }, indent=1) + "\n")
    gate = {h: threading.Semaphore(PER_HARNESS) for h in harnesses}
    jobs = [(h, *(c.split(":") + [VALID_TARGET])[:3]) for h in harnesses for c in cells]
    with cf.ThreadPoolExecutor(len(jobs)) as pool:
        for f in [pool.submit(cell, base, arms, h, a, s, prompts[s], gate, int(n)) for h, a, s, n in jobs]:
            h, a, s, v, i, n = f.result()
            print(f"cell {h}.{a}.{s}: {v} valid, {i} invalid{'  (CAP REACHED)' if v < n else ''}",
                  flush=True)


if __name__ == "__main__":
    main()
