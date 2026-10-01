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


def summary(base):
    rows = [json.loads(p.read_text()) for p in sorted((base / "grades").glob("*.json"))]
    metas = [json.loads(p.read_text()) for p in sorted((base / "outputs").glob("*.meta.json"))]
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
    for h in HARNESSES:
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
            list(pool.map(lambda p: g1.grade(base, p), metas))
    summary(base)


if __name__ == "__main__":
    main()
