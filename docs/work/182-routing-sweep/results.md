# Routing-row sweep and the verification row on Claude Code (Issue #182)

Per-run evidence: [records.jsonl](records.jsonl), 234 runs, Claude Code 2.1.284,
Opus 5.5, effort medium, only (planner decision). Harness:
[trigger_test.py](../164-trigger-audit/trigger_test.py) with `--sweep` and
`--midtask`; Claude shell commands run in Claude Code's sandbox (#183).
Evidence only, not a release gate.

## Result

The procedure a row links is read before that row's action in every sweep row
on the shipped state (fix2). The diagnosis row is the one exception, at 8/10.
Verification before `gh pr create` went from 0/5 (#181) to 5/5.

| Row | main (v14.4.x rows) | fix2 (shipped) | notes |
| --- | --- | --- | --- |
| context | 3/3 | 3/3 |  |
| project-direction | 3/3 (1 read, no action) | 3/3 (1 read, no action) |  |
| research | 0/3 | 5/5 | fix1: 5/5 |
| software-design | 3/3 | 3/3 |  |
| prototype | 1/3 | 5/5 | fix1: 5/5 |
| diagnosis | 0/3 | 8/10 | fix1: 5/5 |
| grilling | 2/3 | 5/5 | fix1: 5/5 |
| wayfinder | 3/3 | 3/3 |  |
| to-spec | 3/3 | 3/3 |  |
| implementation | 3/3 | 3/3 |  |
| orchestration | 3/3 | 3/3 |  |
| project-verification | 3/3 | 3/3 |  |
| artifacts | 3/3 | 3/3 |  |
| reflection | 3/3 | 3/3 |  |
| preferences-pruning | 3/3 | 3/3 |  |
| delivery-profile | 3/3 | 3/3 |  |
| delivery | 3/3 (2 read, no action) | 3/3 |  |
| finalization | 3/3 (3 read, no action) | 3/3 (3 read, no action) |  |
| repository-setup | 3/3 (3 read, no action) | 3/3 (3 read, no action) |  |
| reconciliation | 3/3 (3 read, no action) | 3/3 (3 read, no action) |  |
| use-grok | 3/3 | 3/3 |  |
| verification | not run | 5/5 | row reword only: 5/5; fix1: 3/5 |
| domain-modeling | not run | 8/8 |  |
| technical-writing | not run | 3/3 |  |
| test-design | not run | 3/3 |  |
| writing-for-agents | not run | 3/3 |  |

Columns:
- **main**: the rows as released in v14.4.x, arm `9578065`.
- **fix2**: this PR, arm `4a4f7e1`.
- **Notes**: intermediate arms. "row reword only" is the verification row
  change alone (`c276fd6`). fix1 (`0da08e7`) had the first pointer wording.
- The last four rows are #174's first-edit cases, re-checked on fix2 because
  the pointer changed.

A cell counts a run when the procedure was read before the row's action (first
edit, the named shell command or tool call, or the end of the run for
answer-only rows). "Read, no action" means the procedure was read and the model
then stopped without acting. Finalization, repository setup and reconciliation
always stopped: they would delete branches or change repository settings and
the fixture offers no Issue or remote, so the procedure is read, not yet
applied.

Negatives: two shared prompts (a code question, a one-line docstring edit),
scored against all 21 row procedures (`implementation.md` excluded on the
edit). They were clean in every run on main (6/6) and fix2 (10/10); on fix1 the
question prompt opened `research/index.md` in 2/5. The #174 first-edit
negatives stayed clean on fix2 (17/17).

## What changed and why

- **Verification row** (#182's named miss): "Before opening or updating a PR,
  claiming readiness, or choosing or running proof or review". Alone it reached
  5/5.
- **The pointer, not the rows, was the gap for answer-only work.** Research,
  prototype and grilling missed because Opus never opened `operations`: the
  pointer only named the first edit, commit, Issue and PR. The pointer now
  reads "at the start of every task, and again before each new kind of action
  (researching, an experiment, reproducing a defect, the first file edit, a
  commit, a GitHub Issue or a pull request)". fix1's wording ("before its first
  tool call … for the next action") fixed those rows but dropped verification
  to 3/5 and over-triggered research on a plain question; fix2 does neither.
- **Rows reworded with a before-clause:** research, prototype, diagnosis.
  Diagnosis's two misses read the procedure in the same shell call that ran
  the reproduction, so the reproduction was chosen before the procedure was
  seen.

## Instrument fixes found during the sweep

Each fix is pinned in `tests/test_trigger_harness.py`. Records were re-scored
from their kept call lists under the final rules. 12 verdicts changed: 10 runs
that read the procedure and took no action (`read-noaction`, previously a
miss) and 2 domain-modeling runs that read through `cd <dir> && cat <file>`.
- Record keys use the full path when file names collide. The negatives' many
  `index.md` files had collapsed into one key; the first negative batch was
  dropped and rerun.
- Moments match only the real action: `git tag` listing and `git
  merge-base` no longer count as releasing, and `command -v grok` no longer
  counts as consulting Grok. Those first delivery and use-grok runs were
  dropped and rerun.
- The delivery fixture's `fix/divide` branch now carries a commit; with
  nothing to merge, Opus correctly stopped.
- A `grok` stub is on PATH for non-Grok hosts, so the use-grok row spends no
  credits.

## Not measured

- Codex, Grok and OpenCode verification cells after the row reword (#182
  acceptance criterion 2): not run, because this task was limited to Opus 5.5
  medium. The row text changes on every host.
- A PreToolUse hook on `gh pr create` was not built: the row reword reached
  5/5.
