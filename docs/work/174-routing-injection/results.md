# Operations pointer on Claude Code and OpenCode (Issue #174)

Per-run evidence: [records.jsonl](records.jsonl), 180 runs with the fixed
harness. Regenerate the tables with
`python3 ../164-trigger-audit/trigger_test.py --summary records.jsonl`.
Evidence only, not a release gate. Superseded pre-fix runs are kept in
[records-prefix.jsonl](records-prefix.jsonl) and
[midtask-prefix.jsonl](midtask-prefix.jsonl); see "Pre-fix numbers" below.

Run 2026-09-29 with [trigger_test.py](../164-trigger-audit/trigger_test.py),
5 runs per case per arm, one fresh throwaway repository per run, the #164
confinement. Haiku is out of scope by user decision (2026-09-29).

| Arm | Ref | Change on top of main (`42152be`, v14.3.1) |
| --- | --- | --- |
| base | `42152be` | none |
| B2 | `3dee7d6` | session-start pointer (417 characters, Claude Code and OpenCode only) plus the writing-for-agents row with `prose` in its own before-clause |
| B3 | `cbf7357` | B2 plus the `SKILL-MECHANICS.md` opening that names `prose` (the shipped state) |

## Result: 20/20 on every host in scope

Target procedure read before the first edit, naive prompts:

| Host, model | base | shipped (B2 rows, B3 for writing-for-agents) | Negatives clean |
| --- | --- | --- | --- |
| Claude Code, Opus 5.5, medium | 3/20 | **20/20** (B2 20/20; B3 writing-for-agents 5/5) | 20/20 (B2), 5/5 (B3) |
| OpenCode, Muse 1.3 (Go route) | 16/20 (#164) | **20/20** (B3, all four targets) | 20/20 |
| Codex, `gpt-6-astra`, low | 20/20 (#164) | writing-for-agents **5/5** (B2 and B3); other rows unchanged since #164 | 5/5 each |
| Grok Build, `grok-4.7`, medium | 20/20 (#164) | writing-for-agents **5/5** (B2 and B3); other rows unchanged since #164 | 5/5 each |

Codex and Grok get no pointer. For them only the writing-for-agents row and
`SKILL-MECHANICS.md` changed, so that case is the regression check; the other
three rows are byte-identical to the ones #164 measured at 20/20.

With the pointer, Opus invokes `operations` in 20/20 naive runs (base 4/20).
The base arm is 3/20 here against 1/20 in the pre-fix batch, and its misses are
the model editing without opening the Skill.

### Token cost per run

The pointer adds 417 characters (about 105 tokens) at session start. Mean
tokens per run (input including cache, plus output), naive and negative
prompts together: Opus base 150,264, B2 182,323. Reading the procedures is
the extra work the change asks for; the pointer itself is a small part of the
difference.

| Host, model | base | B2 | B3 |
| --- | --- | --- | --- |
| Claude Code, Opus 5.5 (all cases) | 150,264 | 182,323 | 220,378 (writing-for-agents only) |
| OpenCode, Muse 1.3 | not run | 252,247 (writing-for-agents only) | 232,852 (all cases) |
| Codex, `gpt-6-astra` (writing-for-agents) | not run | 173,287 | 192,131 |
| Grok, `grok-4.7` (writing-for-agents) | not run | 284,978 | 278,897 |

## Harness fixes (why earlier numbers were invalid)

- **Claude Code could not read the plugin copy.** The command allowed only the
  run's repository (`--add-dir <repo>`), so `claude -p --permission-mode
  acceptEdits` refused every procedure read, and the scorer counted the refused
  attempt as a read. Runs now add `--add-dir <plugin copy>`. The live Claude
  setting is `bypassPermissions`, so live use was not affected.
- **OpenCode could not read through its Skill link.** The Skill's base
  directory is the config-directory link, which the harness's
  `external_directory` rule denied; the model then retried through the plugin
  path. The config directory is now allowed too, as the live `"permission":
  "allow"` does.
- **Refused or failed reads no longer count.** Claude tool uses in the result
  event's `permission_denials` or answered by an error, and OpenCode parts in
  state `error`, are attempts, not reads. Records list them as `failed_calls`.
- **A positive run with no edit is `read-noedit` (or `skip-noedit`)**, not
  `fired`.

Deterministic tests in `tests/test_trigger_harness.py` pin these.

## Pre-fix numbers

Superseded. The first #174 batch compared arms A (whole SKILL.md body injected),
B (pointer only) and C (description only) on Claude Code and OpenCode with the
defects above. The Claude cells counted refused reads as hits (10 of arm B's
17 Opus "hits" never edited), and OpenCode reads through the Skill link were
denied, so neither comparison is valid. The records are kept in
`records-prefix.jsonl`. That batch still showed the pointer gets Opus to load
`operations` (20/20 against 1/20), which is why B was carried forward, and that
Codex and Grok reach 20/20 without it.

The pre-fix mid-task batch (`midtask-prefix.jsonl`: version-control before
`git commit`, verification before `gh pr create`) was not rerun. Its Claude
and OpenCode cells share the defects and are not evidence. On Codex and Grok,
unaffected, the procedure was read before the moment in 4/5 or 5/5 per case.
On Claude the verification moment was never reached: the fixture has no git
remote and Opus stopped before `gh pr create`.

## Conditions

Claude Code 2.1.284, OpenCode 1.18.33, Codex 0.159.0, Grok 1.0.44. Batches ran
19:41-19:49 (base and B2, 110 runs) and 19:50-20:00 (B3, 70 runs) from a
temporary worktree of this branch, with the canonical checkout held still. No
abort; no run wrote outside its repository.
