# Operations pointer on Claude Code and OpenCode (Issue #174)

Per-run evidence: [records.jsonl](records.jsonl) (naive and negative prompts)
and [midtask.jsonl](midtask.jsonl) (mid-task moments), in the #164 record
format; runs made before the rebase onto `68bb877` carry
`login_files_changed: null` (unknown). Regenerate the tables with
`python3 ../164-trigger-audit/trigger_test.py --summary <file>`. Evidence only,
not a release gate.

Run 2026-09-29 with [trigger_test.py](../164-trigger-audit/trigger_test.py),
5 runs per case per arm, one fresh throwaway repository per run, the #164
confinement (temporary HOME, guard on the canonical checkout, this checkout and
the live host configuration). Arms, each a git ref archived as the plugin:

| Arm | Ref | Change on top of #168 | Added context |
| --- | --- | --- | --- |
| base | `ad66028` | none (#168's wording) | 0 |
| A | `db9d5a5` | SessionStart hook injects the `operations` SKILL.md body plus one line naming its directory; OpenCode appends it through the plugin transform | 5,589 characters (about 1,400 tokens) |
| B | `0fca9bb` | same registration, but the hook only says to invoke `operations` before the first edit, commit, Issue or PR | 417 characters (about 105 tokens) |
| C | `e6032ad` | no hook; the Skill description names those moments | description only (all hosts) |

## Decision: ship B

No arm reaches 20/20 on every host. B is the best or tied-best arm on every
host it touches, at a quarter of A's context, and leaves Codex and Grok
unchanged. C ties B on Opus and OpenCode but changes the description on all four
hosts and does nothing on Haiku (0/20).

| Host, model | base | A | B | C |
| --- | --- | --- | --- | --- |
| Claude Code, Opus 5.5, medium | 1/20 | 15/20 | 17/20 | 17/20 |
| Claude Code, Haiku (floor) | 0/20 | 0/20 | 4/20 | 0/20 |
| OpenCode, Muse 1.3 (Go route) | 16/20 (#164) | 19/20 | 19/20 | 18/20 |
| Codex, `gpt-6-astra`, low | 20/20 (#164) | not run | not run | 20/20 |
| Grok Build, `grok-4.7`, medium | 20/20 (#164) | not run | not run | 20/20 |

Cells: target procedure read before the first edit, naive prompts. Negative
prompts stayed clean (target never opened) in every cell: 20/20 each. Codex
and Grok rows for A and B are not run because neither arm reaches them; with B
shipped they run #168's wording unchanged, measured 20/20 in #164.

### Why 20/20 is not reached

- **Opus misses one file, not the entry point.** With B, Opus invokes
  `operations` in 20/20 naive runs. All three misses are the writing-for-agents
  case, which needs two files: Opus reads `SKILL-MECHANICS.md` and
  `writing-for-agents/index.md`, then edits without `prose.md` (A 0/5, B 2/5,
  C 2/5). The routing row lists `prose` as a second link. Fixing that is a
  routing-content change, a non-goal here.
- **Haiku ignores the guidance.** Even with the whole table in context (A) it
  reads a target in 0/20; B gets 4/20, all test-design. More text at session
  start does not move it.
- **OpenCode's one B miss** is writing-for-agents `prose.md` too.

### Token cost per run

Mean tokens per run (input including cache, plus output), naive and negative
prompts together. Run-to-run spread is larger than the injected context, so
these show no measurable cost beyond the added context itself.

| Host, model | base | A | B | C |
| --- | --- | --- | --- | --- |
| Claude Code, Opus 5.5 | 137,813 | 143,236 | 135,431 | 147,253 |
| Claude Code, Haiku | 118,478 | 134,094 | 142,696 | 122,175 |
| OpenCode, Muse 1.3 | not run | 171,261 | 242,125 | 201,777 |
| Codex, `gpt-6-astra` | not run | not run | not run | 156,186 |
| Grok, `grok-4.7` | not run | not run | not run | 250,938 |

## Mid-task moments

The required file must be read before the first `git commit` (version-control
`index.md`) or the first `gh pr create` (`references/verification.md`). A `gh`
stub on PATH answers with a fake URL, so nothing reaches GitHub. Claude Code and
OpenCode ran base and B; Codex and Grok ran base, which B leaves unchanged.

| Host, model | Version control before `git commit`: base / B | Verification before `gh pr create`: base / B |
| --- | --- | --- |
| Claude Code, Opus 5.5, medium | 0/5 / 5/5 | not reached (0/5 / 0/5) |
| OpenCode, Muse 1.3 | 3/5 / 5/5 | 5/5 / 5/5 |
| Codex, `gpt-6-astra`, low | 4/5 | 5/5 |
| Grok Build, `grok-4.7`, medium | 5/5 | 4/5 |

Claude never ran `gh pr create` in either arm (10 of 10 `skip-nomoment`): it
checked `git remote -v`, found no remote in the fixture, and stopped after
creating the branch. The verification moment on Claude is therefore unmeasured,
not a skip. Proposal only, not built: if a fixture with a remote shows Claude
skipping `verification.md`, add a PreToolUse hook on `gh pr create` that points
at it. Every other host read the procedure before the moment in at least 4/5.

## Harness changes

`trigger_test.py` now archives any git ref as an arm (`--arms name=ref,...`),
runs the mid-task cases with `--midtask`, puts the `gh` stub on PATH for every
run, and records token usage per run. Summary tables add a mean-token row when
the records carry usage.

## Conditions and aborted batches

Claude Code 2.1.284, OpenCode 1.18.33, Codex 0.159.0, Grok 1.0.44, the same
confinement as #164. The first mid-task batch aborted on the guard on all four
hosts when the canonical checkout was fast-forwarded to v14.2.0 and Grok's live
plugin was reinstalled mid-batch (reflog 18:52:10, Grok registry 18:52:33); it
was discarded and rerun. In the rerun, OpenCode aborted again when v14.3.0 was
installed; its partial verification runs were discarded and that case was rerun
from a separate temporary worktree of this branch. No run wrote outside its
repository.
