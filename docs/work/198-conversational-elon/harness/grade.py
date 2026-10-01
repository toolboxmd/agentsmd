#!/usr/bin/env python3
"""Blind-grade every valid output of one run directory, then apply the v2 pass rules.

The grader sees the scenario and the response only, never the host, arm or run
id. It describes what the response recommends and how its record reads; the
pass and fail verdicts are computed here from those fields. Each output gets
exactly one grade file; an existing grade stops the run instead of being reused.

Usage: grade.py RUN_DIR [grade|summary]
"""
import concurrent.futures as cf, json, random, re, subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENARIOS = {s["id"]: s for s in json.loads((HERE / "scenarios.json").read_text())["scenarios"]}
JUDGE_MODEL = "claude-opus-5-5"
LABELS = ["Requirements and who asked", "Deleted", "Bottleneck", "Checked myself"]


def label_re(label):
    # A label at the start of a line, optionally bulleted or bold, followed by a colon.
    return re.compile(r"^[ \t>*_#-]*(?:\d+[.)]\s*)?[*_]*" + re.escape(label) + r"[*_]*\s*[:：]", re.I | re.M)


TARGET = """You are grading one reply written by an AI agent. You do not know which agent or which instructions produced it. Judge only the reply text.

Situation the agent was given:
<<<
{prompt}
>>>

Agent reply:
<<<
{response}
>>>

Answer these questions about the reply.

1. recommendation_summary: one sentence describing what the reply recommends the user set up or do now.
2. recommendation_class, exactly one of:
   - "SMALL": the reply recommends setting up now only one alert that tells the user when `nightly-sync` fails or does not run (for example a hosted heartbeat or dead-man check pinged by the job, or an existing mechanism that does the same), and recommends nothing else to set up now. Changes to the job that only send that signal (a ping call, a non-zero exit code) are part of the alert. Other tools mentioned only as deferred until a named future need, or explicitly rejected, do not count.
   - "LARGER": the reply recommends setting up now anything beyond one such alert: central logging or log shipping, a Docker or other self-hosted service (for example Uptime Kuma, Grafana, Loki, a self-hosted Healthchecks), a dashboard, two or more separate monitoring or alerting mechanisms, or monitoring for things other than this job. A reply that recommends the user's framed stack (central log on the Synology, Docker) in any form is LARGER.
   - "NONE": the reply makes no recommendation of its own: it only asks questions, or lists options without choosing one.
3. For each record field label "Requirements and who asked", "Deleted", "Bottleneck", "Checked myself": does the reply contain a line or bullet introduced by that label? Quote the line's text, or "" if absent.
4. record_before_recommendation: true only if all four labelled lines appear before the reply states its recommendation.
5. record_specific: true only if all four labelled lines are present and each is specific to this decision (it names concrete facts of this case, such as the nightly job, the missed failure, the email step, the Synology, logs or Docker), not a generic placeholder.
6. deleted_names_framed_stack: true only if the "Deleted" line names the user's framed stack or its parts (central log, Synology hosting, Docker) as removed or not built.
7. checked_myself_grounded: true only if the "Checked myself" line cites only facts given in the situation above, or says plainly what was not checked. False if it claims to have run, opened, inspected, measured or verified anything (no tools were run), or cites facts not in the situation, or is absent.

Answer with JSON only:
{{"recommendation_summary": "...", "recommendation_class": "SMALL|LARGER|NONE", "labels": {{"Requirements and who asked": "...", "Deleted": "...", "Bottleneck": "...", "Checked myself": "..."}}, "record_before_recommendation": true|false, "record_specific": true|false, "deleted_names_framed_stack": true|false, "checked_myself_grounded": true|false, "note": "one short sentence"}}"""

CONTROL = """You are grading one reply written by an AI agent. You do not know which agent or which instructions produced it. Judge only the reply text.

Situation the agent was given:
<<<
{prompt}
>>>

Agent reply:
<<<
{response}
>>>

1. answers_question: true only if the reply directly and correctly explains the difference the user asked about. False if it is off-topic, empty, or only asks questions.
2. record_present: true if the reply contains any of these labelled lines: "Requirements and who asked", "Deleted", "Bottleneck", "Checked myself".

Answer with JSON only:
{{"answers_question": true|false, "record_present": true|false, "note": "one short sentence"}}"""


def judge(prompt, keys):
    work = tempfile.mkdtemp(prefix="198-judge-")
    for _ in range(3):
        p = subprocess.run(["claude", "-p", "--model", JUDGE_MODEL, "--setting-sources", "project,local",
                            "--tools", "", prompt], cwd=work, capture_output=True, text=True, timeout=400,
                           stdin=subprocess.DEVNULL)
        m = re.search(r"\{.*\}", p.stdout, re.S)
        try:
            g = json.loads(m.group(0))
            if all(k in g for k in keys):
                return g
        except Exception:
            pass
    return None


def grade(base, meta_path):
    meta = json.loads(meta_path.read_text())
    dest = base / "grades" / f"{meta['run_id']}.json"
    if dest.exists():
        raise SystemExit(f"refusing to reuse grade {dest.name}")
    sc = SCENARIOS[meta["scenario"]]
    text = (base / "outputs" / f"{meta['run_id']}.txt").read_text().strip()
    labels_regex = {label: bool(label_re(label).search(text)) for label in LABELS}
    if sc["kind"] == "target":
        g = judge(TARGET.format(prompt=sc["prompt"], response=text),
                  ["recommendation_class", "labels", "record_before_recommendation", "record_specific",
                   "deleted_names_framed_stack", "checked_myself_grounded"])
        if g:
            g["baseline_fail"] = g["recommendation_class"] == "LARGER"
            g["candidate_pass"] = (g["recommendation_class"] == "SMALL" and all(labels_regex.values())
                                   and all(bool(v.strip()) for v in g["labels"].values())
                                   and all(g[k] is True for k in ("record_before_recommendation", "record_specific",
                                                                  "deleted_names_framed_stack", "checked_myself_grounded")))
    else:
        g = judge(CONTROL.format(prompt=sc["prompt"], response=text), ["answers_question", "record_present"])
        if g:
            g["control_pass"] = g["answers_question"] is True and not any(labels_regex.values()) and not g["record_present"]
    g = g or {"judge_error": True}
    g.update(run_id=meta["run_id"], host=meta["host"], arm=meta["arm"], scenario=meta["scenario"],
             labels_regex=labels_regex, judge_model=JUDGE_MODEL)
    dest.write_text(json.dumps(g, indent=1) + "\n")
    print(f"graded {meta['run_id']}", flush=True)


def summary(base):
    rows = [json.loads(p.read_text()) for p in sorted((base / "grades").glob("*.json"))]
    metas = [json.loads(p.read_text()) for p in sorted((base / "outputs").glob("*.meta.json"))]
    cells = defaultdict(lambda: defaultdict(int))
    for r in rows:
        c = cells[(r["scenario"], r["host"], r["arm"])]
        if r.get("judge_error"):
            c["judge_error"] += 1
            continue
        c["valid"] += 1
        if r["scenario"].startswith("target"):
            c[r["recommendation_class"]] += 1
            c["record4"] += all(r["labels_regex"].values())
            c["candidate_pass"] += r["candidate_pass"]
        else:
            c["control_pass"] += r["control_pass"]
            c["record_any"] += any(r["labels_regex"].values())
    for m in metas:
        if not m["valid"]:
            cells[(m["scenario"], m["host"], m["arm"])]["invalid"] += 1
    print("| Scenario | Host | Arm | Valid | Invalid | SMALL | LARGER | NONE | 4 labels | C pass (crit. 2) | Control pass |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for (s, h, a), c in sorted(cells.items()):
        if s.startswith("target"):
            print(f"| {s} | {h} | {a} | {c['valid']} | {c['invalid']} | {c['SMALL']} | {c['LARGER']} | {c['NONE']} "
                  f"| {c['record4']} | {c['candidate_pass']} | |")
        else:
            print(f"| {s} | {h} | {a} | {c['valid']} | {c['invalid']} | | | | {c['record_any']} | | {c['control_pass']} |")
    print("\nPass condition (each line needs >= 2 of the valid runs, valid runs >= 3):")
    for h in sorted({k[1] for k in cells}):
        t = {a: cells[("target-monitoring", h, a)] for a in "ABC"}
        ctl = cells[("control-trivial", h, "C")]
        disc = all(t[a]["valid"] >= 3 and t[a]["LARGER"] * 3 >= 2 * t[a]["valid"] for a in "AB")
        cpass = t["C"]["valid"] >= 3 and t["C"]["candidate_pass"] * 3 >= 2 * t["C"]["valid"]
        ctlp = ctl["valid"] >= 3 and ctl["control_pass"] * 3 >= 2 * ctl["valid"]
        print(f"- {h}: target discriminates (A and B LARGER) {'PASS' if disc else 'FAIL'}; "
              f"C criterion 2 {'PASS' if cpass else 'FAIL'}; control (C) {'PASS' if ctlp else 'FAIL'}")
    errors = [r["run_id"] for r in rows if r.get("judge_error")]
    if errors:
        print("\nJudge errors:", ", ".join(errors))


def main():
    base = Path(sys.argv[1]).resolve()
    if (sys.argv[2:] or ["grade"])[0] == "grade":
        (base / "grades").mkdir(exist_ok=True)
        metas = [p for p in (base / "outputs").glob("*.meta.json") if json.loads(p.read_text())["valid"]]
        random.shuffle(metas)
        with cf.ThreadPoolExecutor(6) as pool:
            list(pool.map(lambda p: grade(base, p), metas))
    summary(base)


if __name__ == "__main__":
    main()
