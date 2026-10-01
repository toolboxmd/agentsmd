#!/usr/bin/env python3
"""Isolation probe: each host and arm reports which global instructions it sees."""
import concurrent.futures as cf, os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import run

PROBE = ("Do not run tools. Answer two lines only. Line 1: does any instruction you were given (system prompt, "
         "AGENTS.md, CLAUDE.md, or memory) contain a section titled 'Elon method'? yes or no. Line 2: quote the "
         "first heading of any user-level or global instructions file you were given, or NONE.")


def probe(host, arm):
    scratch = Path(tempfile.mkdtemp(prefix=f"198-probe-{host}-{arm}-"))
    (scratch / "work").mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE_", "CLAUDECODE", "AGENTSMD_"))}
    env.update(run.setup(host, arm, scratch / "home"), PWD=str(scratch / "work"))
    last = scratch / "last.txt"
    p = subprocess.run(run.command(host, arm, PROBE, last), cwd=scratch / "work", env=env, capture_output=True,
                       text=True, timeout=300, stdin=subprocess.DEVNULL)
    text = last.read_text() if last.exists() else p.stdout
    shutil.rmtree(scratch, ignore_errors=True)
    return f"== {host} {arm} exit {p.returncode}\n{run.ANSI.sub('', text).strip()}\n"


with cf.ThreadPoolExecutor(8) as pool:
    for out in pool.map(lambda x: probe(*x), [(h, a) for h in run.HOSTS for a in ("A", "C")]):
        print(out, flush=True)
