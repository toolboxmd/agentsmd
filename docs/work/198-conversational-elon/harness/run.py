#!/usr/bin/env python3
"""Run the #198 scenarios on every host in arms A (no rules), B (origin/main core), C (candidate core).

Every attempt gets its own output file and is never reused. Timeouts, empty
output, non-zero exits and harness errors are recorded as invalid and do not
count toward the valid-run target.

Usage: run.py RUN_DIR [hosts] [arms] [scenario ids]
"""
import concurrent.futures as cf, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCENARIOS = HERE / "scenarios.json"
FROZEN_SHA = "0f09353fccbfcd03ae2beb455783ed9e765b8ff4bff28e01cbf76d1a844c694b"
ARMS = {"A": None, "B": HERE / "arms/B.md", "C": REPO / "global/AGENTS.md"}
HOSTS = ["codex", "grok", "opencode", "claude"]
VALID_TARGET, MAX_ATTEMPTS, TIMEOUT = 3, 6, 420
PER_HOST = {"codex": 3, "grok": 3, "opencode": 3, "claude": 3}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
ERROR = re.compile(r"rate.?limit|quota|unauthori[sz]ed|authenticat|api error|internal server error|"
                   r"overloaded|ECONNRESET|model not found|insufficient|usage limit", re.I)
HOME = Path.home()


def setup(host, arm, root):
    """Isolated home per host and arm; the arm's rules file is the only global instruction."""
    src = ARMS[arm]
    if host == "codex":
        root.mkdir(parents=True, exist_ok=True)
        (root / "auth.json").symlink_to(HOME / ".codex/auth.json")
        (root / "config.toml").write_text('model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n')
        if src:
            shutil.copy(src, root / "AGENTS.md")
        return {"CODEX_HOME": str(root)}
    if host == "grok":
        g = root / ".grok"
        g.mkdir(parents=True, exist_ok=True)
        (g / "auth.json").symlink_to(HOME / ".grok/auth.json")
        if src:
            shutil.copy(src, g / "AGENTS.md")
        return {"HOME": str(root), "GROK_HOME": str(g)}
    if host == "opencode":
        c = root / "opencode"
        c.mkdir(parents=True, exist_ok=True)
        if src:
            shutil.copy(src, c / "AGENTS.md")
        return {"XDG_CONFIG_HOME": str(root), "OPENCODE_DISABLE_CLAUDE_CODE": "1"}
    return {}


def command(host, arm, prompt, last):
    if host == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-o", str(last), prompt]
    if host == "grok":
        return ["grok", "-p", prompt]
    if host == "opencode":
        return ["opencode", "run", "-m", "opencode/muse-spark-1.3-contributor-free", prompt]
    rules = ["--append-system-prompt-file", str(ARMS[arm])] if ARMS[arm] else []
    return ["claude", "-p", "--model", "claude-sonnet-5", "--setting-sources", "project,local",
            "--tools", "", *rules, prompt]


def attempt(base, host, arm, sc, n, preface):
    run_id = f"{host}.{arm}.{sc['id']}.a{n}"
    out, meta = base / "outputs" / f"{run_id}.txt", base / "outputs" / f"{run_id}.meta.json"
    if out.exists() or meta.exists():
        raise SystemExit(f"refusing to reuse {run_id}")
    scratch = Path(tempfile.mkdtemp(prefix=f"198-{run_id}-"))
    work, last = scratch / "work", scratch / "last.txt"
    work.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "AGENTSMD_"))}
    env.update(setup(host, arm, scratch / "home"))
    started, info = time.time(), {"run_id": run_id, "host": host, "arm": arm, "scenario": sc["id"], "attempt": n}
    try:
        p = subprocess.run(command(host, arm, preface + sc["prompt"], last), cwd=work, env=env,
                           capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        text = last.read_text() if last.exists() else p.stdout
        text = ANSI.sub("", text).strip()
        info.update(exit=p.returncode, stderr_tail=ANSI.sub("", p.stderr)[-1500:])
        if p.returncode != 0:
            info["invalid"] = f"exit {p.returncode}"
        elif not text:
            info["invalid"] = "empty output"
        elif len(text) < 600 and ERROR.search(text):
            info["invalid"] = "harness error text"
    except subprocess.TimeoutExpired as e:
        text = ANSI.sub("", (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        info["invalid"] = f"timeout {TIMEOUT}s"
    except Exception as e:  # harness error
        text, info["invalid"] = "", f"harness error: {e!r}"
    info["seconds"] = round(time.time() - started, 1)
    info["valid"] = "invalid" not in info
    out.write_text(text + "\n")
    meta.write_text(json.dumps(info, indent=1) + "\n")
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"{run_id:45} {'valid' if info['valid'] else 'INVALID ' + info['invalid']:30} {info['seconds']:6.0f}s", flush=True)
    return info["valid"]


def cell(base, host, arm, sc, preface, gate):
    valid = 0
    for n in range(1, MAX_ATTEMPTS + 1):
        if valid >= VALID_TARGET:
            break
        with gate[host]:
            valid += attempt(base, host, arm, sc, n, preface)


def main():
    raw = SCENARIOS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA:
        raise SystemExit("scenarios.json changed after freeze")
    data = json.loads(raw)
    base = Path(sys.argv[1]).resolve()
    if base.exists():
        raise SystemExit(f"{base} exists; every run gets a new directory")
    hosts = sys.argv[2].split(",") if len(sys.argv) > 2 else HOSTS
    arms = sys.argv[3].split(",") if len(sys.argv) > 3 else list(ARMS)
    ids = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    (base / "outputs").mkdir(parents=True)
    (base / "manifest.json").write_text(json.dumps({
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scenarios_sha256": FROZEN_SHA,
        "arms_sha256": {a: hashlib.sha256(p.read_bytes()).hexdigest() if p else None for a, p in ARMS.items()},
        "repo_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "hosts": hosts, "arms": arms,
    }, indent=1) + "\n")
    gate = {h: threading.Semaphore(PER_HOST[h]) for h in hosts}
    jobs = [(h, a, sc) for sc in data["scenarios"] if not ids or sc["id"] in ids for h in hosts for a in arms]
    with cf.ThreadPoolExecutor(len(jobs)) as pool:
        for f in [pool.submit(cell, base, h, a, sc, data["preface"], gate) for h, a, sc in jobs]:
            f.result()


if __name__ == "__main__":
    main()
