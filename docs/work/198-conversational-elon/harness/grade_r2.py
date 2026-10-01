#!/usr/bin/env python3
"""Blind-grade round 2 with the grade.py judge, then apply the frozen round 2 pass condition.

The judge prompts, label regex and verdict rules are grade.py's, unchanged. Only
the summary differs: round 2 needs 5/5 valid runs per harness for arm C on the
target (criterion 2) and the control.

Usage: grade_r2.py RUN_DIR [grade|summary]
"""
import concurrent.futures as cf, json, random, sys
from collections import defaultdict
from pathlib import Path

import grade as g1

HARNESSES = ["codex", "grok", "opencode", "claude-sonnet-5", "claude-opus-5-5"]
HELD = json.loads((g1.HERE / "heldout.json").read_text())
# Grader-facing rubric fields, verbatim from the frozen comment. candidate_pass, baseline_fail and
# run_policy are computed by the harness or are operator policy, so the judge does not see them.
HELD_RUBRIC = {k: v for k, v in HELD["rubric"].items() if k not in ("candidate_pass", "baseline_fail", "run_policy")}
HELD_TARGET = """You are grading one reply written by an AI agent. You do not know which agent or which instructions produced it. Judge only the reply text.

Situation the agent was given:
<<<
{prompt}
>>>

Agent reply:
<<<
{response}
>>>

Answer each field below using its definition in this rubric:
<<<
{rubric}
>>>

recommendation_class is exactly one of "SMALL", "LARGER", "NONE". The four predicates are booleans.

Answer with JSON only:
{{"recommendation_summary": "...", "recommendation_class": "SMALL|LARGER|NONE", "labels": {{"Requirements and who asked": "...", "Deleted": "...", "Bottleneck": "...", "Checked myself": "..."}}, "record_before_recommendation": true|false, "record_specific": true|false, "deleted_names_framed_stack": true|false, "checked_myself_grounded": true|false, "note": "one short sentence"}}"""
KEYS = ["recommendation_class", "labels", "record_before_recommendation", "record_specific",
        "deleted_names_framed_stack", "checked_myself_grounded"]


def grade_heldout(base, meta_path):
    """grade.py's grade() with the frozen held-out rubric; same result schema and candidate_pass conjunction."""
    meta = json.loads(meta_path.read_text())
    dest = base / "grades" / f"{meta['run_id']}.json"
    if dest.exists():
        raise SystemExit(f"refusing to reuse grade {dest.name}")
    sc = next(s for s in HELD["scenarios"] if s["id"] == meta["scenario"])
    text = (base / "outputs" / f"{meta['run_id']}.txt").read_text().strip()
    labels_regex = {label: bool(g1.label_re(label).search(text)) for label in g1.LABELS}
    g = g1.judge(HELD_TARGET.format(prompt=sc["prompt"], response=text, rubric=json.dumps(HELD_RUBRIC, indent=1)), KEYS)
    if g:
        g["baseline_fail"] = g["recommendation_class"] == "LARGER"
        g["candidate_pass"] = (g["recommendation_class"] == "SMALL" and all(labels_regex.values())
                               and all(bool(v.strip()) for v in g["labels"].values())
                               and all(g[k] is True for k in KEYS[2:]))
    g = g or {"judge_error": True}
    g.update(run_id=meta["run_id"], host=meta["host"], arm=meta["arm"], scenario=meta["scenario"],
             labels_regex=labels_regex, judge_model=g1.JUDGE_MODEL)
    dest.write_text(json.dumps(g, indent=1) + "\n")
    print(f"graded {meta['run_id']}", flush=True)


def heldout_summary(base, rows, metas):
    cells = defaultdict(lambda: defaultdict(int))
    for r in rows:
        c = cells[(r["host"], r["arm"])]
        if r.get("judge_error"):
            c["judge_error"] += 1
            continue
        c["valid"] += 1
        c[r["recommendation_class"]] += 1
        c["record4"] += all(r["labels_regex"].values())
        c["pass"] += r["candidate_pass"]
    for m in metas:
        if not m["valid"]:
            cells[(m["host"], m["arm"])]["invalid"] += 1
    print("| Harness | A LARGER | B LARGER | C criterion 2 | C four labels | Invalid | Judge errors |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for h in sorted({k[0] for k in cells}):
        a, b, c = (cells[(h, x)] for x in "ABC")
        inv = sum(cells[(h, x)]["invalid"] for x in "ABC")
        je = sum(cells[(h, x)]["judge_error"] for x in "ABC")
        print(f"| {h} | {a['LARGER']}/{a['valid']} | {b['LARGER']}/{b['valid']} | {c['pass']}/{c['valid']} "
              f"| {c['record4']}/{c['valid']} | {inv} | {je} |")
    print("\nFailing arm C runs:")
    for r in rows:
        if r["arm"] == "C" and not r.get("judge_error") and not r["candidate_pass"]:
            print(f"- {r['run_id']}: {r['recommendation_class']} {r.get('note', '')}")


def summary(base):
    rows = [json.loads(p.read_text()) for p in sorted((base / "grades").glob("*.json"))]
    metas = [json.loads(p.read_text()) for p in sorted((base / "outputs").glob("*.meta.json"))]
    if rows and all(r["scenario"].startswith("heldout") for r in rows):
        return heldout_summary(base, rows, metas)
    cells = defaultdict(lambda: defaultdict(int))
    for r in rows:
        c = cells[(r["host"], r["arm"], r["scenario"])]
        if r.get("judge_error"):
            c["judge_error"] += 1
            continue
        c["valid"] += 1
        if r["scenario"] == "target-monitoring":
            c[r["recommendation_class"]] += 1
            c["record4"] += all(r["labels_regex"].values())
            c["pass"] += r["candidate_pass"]
        else:
            c["pass"] += r["control_pass"]
    for m in metas:
        if not m["valid"]:
            cells[(m["host"], m["arm"], m["scenario"])]["invalid"] += 1
    if not any(k[1] in "ABC" for k in cells):  # diagnostic pilot: candidate-file arms only
        print("| Harness | Variant | Criterion 2 | All four labels | Classes | Invalid |")
        print("| --- | --- | --- | --- | --- | --- |")
        for (h, v, s), c in sorted(cells.items()):
            print(f"| {h} | {v} {s} | {c['pass']}/{c['valid']} | {c['record4']}/{c['valid']} "
                  f"| SMALL {c['SMALL']}, LARGER {c['LARGER']}, NONE {c['NONE']} | {c['invalid']} |")
        print("\nFailing runs:")
        for r in rows:
            if not r.get("judge_error") and not r.get("candidate_pass", r.get("control_pass")):
                print(f"- {r['run_id']}: {r.get('recommendation_class', '')} {r.get('note', '')}")
        return
    print("| Harness | A LARGER | B LARGER | C criterion 2 | C control | Invalid | Verdict |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for h in [x for x in HARNESSES + sorted({k[0] for k in cells} - set(HARNESSES)) if any(k[0] == x for k in cells)]:
        a, b, c = (cells[(h, x, "target-monitoring")] for x in "ABC")
        ctl = cells[(h, "C", "control-trivial")]
        inv = sum(cells[k]["invalid"] for k in cells if k[0] == h)
        ok = c["valid"] == 5 and c["pass"] == 5 and ctl["valid"] == 5 and ctl["pass"] == 5
        print(f"| {h} | {a['LARGER']}/{a['valid']} | {b['LARGER']}/{b['valid']} | {c['pass']}/{c['valid']} "
              f"| {ctl['pass']}/{ctl['valid']} | {inv} | {'PASS' if ok else 'FAIL'} |")
    errors = [r["run_id"] for r in rows if r.get("judge_error")]
    if errors:
        print("\nJudge errors:", ", ".join(errors))
    print("\nFailing arm C runs:")
    for r in rows:
        if r["arm"] == "C" and not r.get("judge_error") and not r.get("candidate_pass", r.get("control_pass")):
            print(f"- {r['run_id']}: {r.get('recommendation_class', '')} {r.get('note', '')}")


def main():
    base = Path(sys.argv[1]).resolve()
    if (sys.argv[2:] or ["grade"])[0] == "grade":
        (base / "grades").mkdir(exist_ok=True)
        metas = [p for p in (base / "outputs").glob("*.meta.json") if json.loads(p.read_text())["valid"]
                 and not (base / "grades" / p.name.replace(".meta.json", ".json")).exists()]  # grade new runs only
        random.shuffle(metas)
        with cf.ThreadPoolExecutor(6) as pool:
            list(pool.map(lambda p: (grade_heldout if "heldout" in p.name else g1.grade)(base, p), metas))
    summary(base)


if __name__ == "__main__":
    main()
