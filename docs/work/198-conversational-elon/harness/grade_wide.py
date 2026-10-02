#!/usr/bin/env python3
"""Blind-grade the frozen wider set (#198 comment 5938481653) with each scenario's own rubric, routed by kind.

The judge sees the situation, the reply and the rubric's classification and predicate
definitions (rubric[scenario.id] without candidate_pass, baseline_fail and run_policy, which
the harness applies). Two kinds need one extra judge boolean because their candidate_pass
has a substantive condition the harness cannot compute:
- target-larger: larger_capabilities_met (the chosen option has every capability its LARGER
  definition names).
- control: answers_correctly (the relevant correct answer its rubric names).

Verdicts, computed here:
- target: SMALL, four labels detected and nonempty, and the four record predicates true.
- target-larger: LARGER with larger_capabilities_met, plus the same record conditions.
- control: answers_correctly and no record label anywhere (regex or judge quote).
A and B wrong decision: target LARGER; target-larger SMALL or LARGER lacking capabilities.

Usage: grade_wide.py RUN_DIR [grade|summary] [AB_DIR:HARNESS,...]
  AB_DIR:HARNESS,...: take arms A and B for those harnesses from an earlier run dir (unchanged arms).
"""
import concurrent.futures as cf, json, random, sys
from collections import defaultdict
from pathlib import Path

import grade as g1

WIDE = json.loads((g1.HERE / "wide.json").read_text())
SCEN = {s["id"]: s for s in WIDE["scenarios"]}
HIDDEN = ("candidate_pass", "baseline_fail", "run_policy")
BAR = {"opencode": 4}  # frozen: 5/5 per cell, OpenCode at least 4/5
EXTRA = {
    "target": "",
    "target-larger": ', "larger_capabilities_met": true|false',
    "control": ', "answers_correctly": true|false',
}
EXTRA_TEXT = {
    "target": "",
    "target-larger": "\nlarger_capabilities_met: true only if the option the reply chooses has every necessary capability "
                     "named in the rubric's LARGER definition.",
    "control": "\nanswers_correctly: true only if the reply gives the relevant correct answer the rubric names.",
}
JUDGE = """You are grading one reply written by an AI agent. You do not know which agent or which instructions produced it. Judge only the reply text.

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

recommendation_class is exactly one of "SMALL", "LARGER", "NONE". The four predicates are booleans.{extra_text}

Answer with JSON only:
{{"recommendation_summary": "...", "recommendation_class": "SMALL|LARGER|NONE", "labels": {{"Requirements and who asked": "...", "Deleted": "...", "Bottleneck": "...", "Checked myself": "..."}}, "record_before_recommendation": true|false, "record_specific": true|false, "deleted_names_framed_stack": true|false, "checked_myself_grounded": true|false{extra}, "note": "one short sentence"}}"""
PRED = ["record_before_recommendation", "record_specific", "deleted_names_framed_stack", "checked_myself_grounded"]


def grade(base, meta_path):
    meta = json.loads(meta_path.read_text())
    dest = base / "grades" / f"{meta['run_id']}.json"
    if dest.exists():
        raise SystemExit(f"refusing to reuse grade {dest.name}")
    sc = SCEN[meta["scenario"]]
    kind = sc["kind"]
    rubric = {k: v for k, v in WIDE["rubric"][sc["id"]].items() if k not in HIDDEN}
    text = (base / "outputs" / f"{meta['run_id']}.txt").read_text().strip()
    labels_regex = {label: bool(g1.label_re(label).search(text)) for label in g1.LABELS}
    keys = ["recommendation_class", "labels", *PRED] + {"target": [], "target-larger": ["larger_capabilities_met"],
                                                         "control": ["answers_correctly"]}[kind]
    g = g1.judge(JUDGE.format(prompt=sc["prompt"], response=text, rubric=json.dumps(rubric, indent=1),
                              extra=EXTRA[kind], extra_text=EXTRA_TEXT[kind]), keys)
    if g:
        record = (all(labels_regex.values()) and all(bool(str(v).strip()) for v in g["labels"].values())
                  and all(g[k] is True for k in PRED))
        cls = g["recommendation_class"]
        if kind == "target":
            g["wrong_decision"] = cls == "LARGER"
            g["candidate_pass"] = cls == "SMALL" and record
        elif kind == "target-larger":
            ok = cls == "LARGER" and g["larger_capabilities_met"] is True
            g["wrong_decision"] = cls == "SMALL" or (cls == "LARGER" and not ok)
            g["candidate_pass"] = ok and record
        else:
            g["candidate_pass"] = (g["answers_correctly"] is True and not any(labels_regex.values())
                                   and not any(str(v).strip() for v in g["labels"].values()))
    g = g or {"judge_error": True}
    g.update(run_id=meta["run_id"], host=meta["host"], arm=meta["arm"], scenario=meta["scenario"], kind=kind,
             labels_regex=labels_regex, judge_model=g1.JUDGE_MODEL)
    dest.write_text(json.dumps(g, indent=1) + "\n")
    print(f"graded {meta['run_id']}", flush=True)


def summary(base, reuse=None):
    rows = [json.loads(p.read_text()) for p in sorted((base / "grades").glob("*.json"))]
    metas = [json.loads(p.read_text()) for p in sorted((base / "outputs").glob("*.meta.json"))]
    reused = set()
    if reuse:
        ab_dir, hosts = reuse.split(":", 1)
        reused = set(hosts.split(","))
        pick = lambda x: x["arm"] in "AB" and x["host"] in reused
        rows = [r for r in rows if not pick(r)] + [json.loads(p.read_text()) for p in
                sorted((Path(ab_dir) / "grades").glob("*.json")) if pick(json.loads(p.read_text()))]
        metas = [m for m in metas if not pick(m)] + [json.loads(p.read_text()) for p in
                 sorted((Path(ab_dir) / "outputs").glob("*.meta.json")) if pick(json.loads(p.read_text()))]
    cells = defaultdict(lambda: defaultdict(int))
    for r in rows:
        c = cells[(r["scenario"], r["host"], r["arm"])]
        if r.get("judge_error"):
            c["judge_error"] += 1
            continue
        c["valid"] += 1
        c["pass"] += r["candidate_pass"]
        c["wrong"] += r.get("wrong_decision", False)
        c["NONE"] += r["recommendation_class"] == "NONE"
    for m in metas:
        if not m["valid"]:
            cells[(m["scenario"], m["host"], m["arm"])]["invalid"] += 1
    hosts = sorted({k[1] for k in cells})
    print("| Scenario | Kind | Harness | C pass | A wrong | B wrong | Invalid | Cell |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    failing, total = [], 0
    for s in WIDE["scenarios"]:
        for h in hosts:
            a, b, c = (cells[(s["id"], h, x)] for x in "ABC")
            if not (a["valid"] or b["valid"] or c["valid"] or c["invalid"]):
                continue
            inv = a["invalid"] + b["invalid"] + c["invalid"]
            ok = c["valid"] == 5 and c["pass"] >= BAR.get(h, 5)
            total += 1
            if not ok:
                failing.append((s["id"], h))
            tag = " (reused)" if h in reused else ""
            ab = (lambda x: f"{x['wrong']}/{x['valid']}" + (f" ({x['NONE']} NONE)" if x["NONE"] else "") + tag) \
                if s["kind"] != "control" else (lambda x: "n/a")
            print(f"| {s['id']} | {s['kind']} | {h} | {c['pass']}/{c['valid']} | {ab(a)} | {ab(b)} | {inv} "
                  f"| {'PASS' if ok else 'FAIL'} |")
    print(f"\nCells passing: {total - len(failing)}/{total}")
    errors = [r["run_id"] for r in rows if r.get("judge_error")]
    if errors:
        print("Judge errors:", ", ".join(errors))
    print("\nFailing arm C runs:")
    for r in rows:
        if r["arm"] == "C" and not r.get("judge_error") and not r["candidate_pass"]:
            print(f"- {r['run_id']}: {r['recommendation_class']} {r.get('note', '')}")


def main():
    base = Path(sys.argv[1]).resolve()
    if (sys.argv[2:] or ["grade"])[0] == "grade":
        (base / "grades").mkdir(exist_ok=True)
        metas = [p for p in (base / "outputs").glob("*.meta.json") if json.loads(p.read_text())["valid"]
                 and not (base / "grades" / p.name.replace(".meta.json", ".json")).exists()]  # grade new runs only
        random.shuffle(metas)
        with cf.ThreadPoolExecutor(10) as pool:
            list(pool.map(lambda p: grade(base, p), metas))
    summary(base, sys.argv[3] if len(sys.argv) > 3 else None)


if __name__ == "__main__":
    main()
