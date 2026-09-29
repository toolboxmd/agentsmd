#!/usr/bin/env python3
"""Run every scenario against every harness with the old and new core AGENTS.md."""
import concurrent.futures as cf, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

E = Path("/tmp/core-eval")
VERSIONS = {"old": E / "AGENTS.old.md", "new": E / "AGENTS.new.md"}
S = json.loads((E / "scenarios.json").read_text())
OUT = E / os.environ.get("OUTDIR", "out")
HOME = Path.home()
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# The S13 fake key is assembled at run time so the repository secret scan stays clean.
FAKE_KEY = "sk-" + "live-9f8a7b6c5d4e3f2a1b0c"
FAKE_ASSIGNMENT = "API_KEY" + "=" + FAKE_KEY


def fill(text):
    return text.replace("{FAKE_ASSIGNMENT}", FAKE_ASSIGNMENT).replace("{FAKE_KEY}", FAKE_KEY)


def setup(harness, version):
    src = VERSIONS[version]
    root = E / "homes" / f"{harness}-{version}"
    if harness == "codex":
        root.mkdir(parents=True, exist_ok=True)
        (root / "auth.json").unlink(missing_ok=True)
        (root / "auth.json").symlink_to(HOME / ".codex/auth.json")
        (root / "config.toml").write_text('model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n')
        shutil.copy(src, root / "AGENTS.md")
        return {"CODEX_HOME": str(root)}
    if harness == "grok":
        g = root / ".grok"
        g.mkdir(parents=True, exist_ok=True)
        (g / "auth.json").unlink(missing_ok=True)
        (g / "auth.json").symlink_to(HOME / ".grok/auth.json")
        shutil.copy(src, g / "AGENTS.md")
        return {"HOME": str(root)}
    if harness == "opencode":
        c = root / "opencode"
        c.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, c / "AGENTS.md")
        return {"XDG_CONFIG_HOME": str(root), "OPENCODE_DISABLE_CLAUDE_CODE": "1"}
    return {}


def command(harness, version, prompt, last):
    if harness == "codex":
        return ["codex", "exec", "--skip-git-repo-check", "-s", "read-only", "-o", str(last), prompt]
    if harness == "grok":
        return ["grok", "-p", prompt]
    if harness == "opencode":
        return ["opencode", "run", "-m", "opencode/muse-spark-1.3-contributor-free", prompt]
    return ["claude", "-p", "--model", "haiku", "--setting-sources", "project,local",
            "--append-system-prompt-file", str(VERSIONS[version]), prompt]


def lane(harness, version, ids):
    env = {**os.environ, **setup(harness, version)}
    for sc in S["scenarios"]:
        if ids and sc["id"] not in ids:
            continue
        dest = OUT / f"{harness}.{version}.{sc['id']}.txt"
        if dest.exists() and dest.stat().st_size > 20:
            continue
        work = Path(tempfile.mkdtemp(prefix="w-", dir=E / "work"))
        last = work.parent / f"{work.name}.last"
        started = time.time()
        try:
            p = subprocess.run(command(harness, version, fill(S["preface"] + sc["prompt"]), last),
                               cwd=work, env=env, capture_output=True, text=True, timeout=420)
            text = last.read_text() if last.exists() else p.stdout
            if not text.strip():
                text = f"[empty stdout; exit {p.returncode}]\n{p.stderr[-1500:]}"
        except subprocess.TimeoutExpired:
            text = "[timeout]"
        dest.write_text(ANSI.sub("", text).strip() + "\n")
        print(f"{harness:8} {version} {sc['id']:28} {time.time()-started:5.0f}s", flush=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (E / "work").mkdir(exist_ok=True)
    harnesses = sys.argv[1].split(",") if len(sys.argv) > 1 else ["codex", "grok", "opencode", "claude"]
    ids = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else set()
    with cf.ThreadPoolExecutor(8) as pool:
        for f in [pool.submit(lane, h, v, ids) for h in harnesses for v in VERSIONS]:
            f.result()
