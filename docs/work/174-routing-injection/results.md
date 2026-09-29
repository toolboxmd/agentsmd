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
- **A shell read with a non-zero exit still counts** (added after the tables
  above were recorded). Claude reports a chained command such as `cat
  prose.md; ls missing` as an error although the file was read, so only
  `permission_denials` fail a shell call now; Read calls still fail on an
  error result. Two base-arm Opus test-design runs in `records.jsonl` read
  `test-design.md` through such a command and were scored `skip`, so Opus base
  may be 5/20 rather than 3/20. No shipped-arm cell is affected: none of their
  failed shell calls names a required file.

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

The pre-fix mid-task batch (`midtask-prefix.jsonl`) was rerun with the fixed
harness for Claude Code and OpenCode; see "Mid-task moments" below. Its Codex
and Grok cells, which the defects did not affect, stand as measured there.

## Mid-task moments

The required file must be read before the first `git commit` (version-control
`index.md`) or the first `gh pr create` (`references/verification.md`). A `gh`
stub on PATH answers with a fake URL, so nothing reaches GitHub. Claude Code
and OpenCode reran with the fixed harness ([midtask.jsonl](midtask.jsonl), 40
runs, arms base `42152be` and shipped `8094d41`); Codex and Grok are from the
pre-fix batch, which did not affect them.

| Host, model | Version control before `git commit`: base / shipped | Verification before `gh pr create`: base / shipped |
| --- | --- | --- |
| Claude Code, Opus 5.5, medium | 0/5 / **5/5** | 0/5 / **0/5** (Bash allowed; `gh pr create` reached in 10/10) |
| OpenCode, Muse 1.3 | 4/5 / **5/5** | 5/5 / **5/5** |
| Codex, `gpt-6-astra`, low (pre-fix batch) | 4/5 | 5/5 |
| Grok Build, `grok-4.7`, medium (pre-fix batch) | 5/5 | 4/5 |

**Claude skips verification before `gh pr create`.** The first rerun could
not reach the moment: `claude -p --permission-mode acceptEdits` denied every
non-read Bash call. The harness now passes `--allowedTools Bash` (the run stays
in its temporary HOME and repository, as on the other hosts), and the verification
case was rerun on Claude (10 runs, arms base `42152be` and shipped `3fa82c0`,
the #179 merge). Every run branched, tested, committed and called `gh pr
create`; none read `verification.md` first. With the pointer, Opus invokes
`operations` at the start and reads no procedure file before the PR. The
version-control cell above is from the run with Bash denied; it scores the read
against the first `git commit` attempt.

**Proposal (not built), per #174's mid-task criterion:** injection at the
action for Claude Code, a PreToolUse hook on `gh pr create` whose context
points at `references/verification.md`, measured with this case.

## Post-install canary

[canary.jsonl](canary.jsonl): one naive technical-writing prompt per host
against the live v14.4.0 installs (not harness copies), in a fresh throwaway
repository, 2026-09-29. `prose.md` was read before the first edit on all four:
Claude Code Opus 5.5 medium, Codex `gpt-6-astra` low, Grok 4.7 medium and
OpenCode Muse 1.3 (4/4). The canonical checkout was unchanged afterwards.

## Shell confinement for Claude runs

The 10 Claude verification runs above allowed Bash with no OS-level limit;
the guard then covered only the canonical checkout, the harness checkout and
the selected live configuration. Claude runs now enable Claude Code's Bash
sandbox in the temporary HOME's settings (`sandbox.enabled`,
`allowUnsandboxedCommands: false`, `failIfUnavailable: true`, and
`filesystem.denyRead` of the real home and the temporary HOME's keychain link
with `allowRead` of the temporary HOME). Shell writes are limited to the run's
repository, the `--add-dir` directories and the per-user temp directory; shell
reads of the real home and the linked login are denied.

Smoke runs (Opus 5.5 medium, harness setup):

- `cat` of a file in a fresh directory under the real home, `touch` there, and
  `ls` of the temporary HOME's keychain link: all `Operation not permitted`,
  and no file was created.
- `head` of the repository's README and of the plugin copy's `SKILL.md`, and
  `touch` in the repository: all succeeded.
- `git checkout -b`, `git commit`, a python import, a `cat` of a procedure and
  `gh pr create` behave as without the sandbox, so the benchmark was not rerun.

Known allowances: shell writes to the per-user temp directory; Claude's own
process (not sandboxed) reads its login through the keychain link; commands
cannot run tools installed under the real home (for example `node` from
`~/.nvm`), which the fixture does not use. The harness creates plain
repositories with `git init`, not linked worktrees, so the sandbox's allowance
for a linked worktree's shared `.git` directory does not apply.

## Conditions

Claude Code 2.1.284, OpenCode 1.18.33, Codex 0.159.0, Grok 1.0.44. Batches ran
19:41-19:49 (base and B2, 110 runs), 19:50-20:00 (B3, 70 runs) and
20:03-20:09 (mid-task, 40 runs) and 20:15-20:17 (Claude verification with
Bash allowed, 10 runs) from a
temporary worktree of this branch, with the canonical checkout held still. No
abort; no run wrote outside its repository.
