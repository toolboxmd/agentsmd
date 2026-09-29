# Before-and-after trigger test (Issue #164, step 3)

Run 2026-09-29 with [trigger_test.py](trigger_test.py): `claude -p --model haiku`,
5 runs per cell, one fresh throwaway git repository per run. Arm `main` is the
installed AgentsMD 14.0.0 (identical to `origin/main` `53296e5` under
`skills/`); arm `branch` is this branch's rewording. Evidence only, not a
release gate.

- **Naive prompt**: asks for the edit without naming the file. Counts when the
  file is read before the first Edit/Write (scored from `stream-json`).
- **Negative prompt**: an edit where the file must not be opened. Counts when
  it is never read.
- **Plain**: the prompt as written. **Entry loaded** (`--entry`): the prompt is
  prefixed with `/agentsmd:operations`, so the routing table is in context and
  only the routing and procedure wording is under test.

## Results

| Target | File | Plain, naive: main / branch | Entry loaded, naive: main / branch | Negative, never opened (all conditions, both arms) |
| --- | --- | --- | --- | --- |
| technical-writing | `prose.md` | 0/5 / 0/5 | 0/5 / 2/5 | 5/5 each |
| writing-for-agents | `SKILL-MECHANICS.md` | 0/5 / 0/5 | 0/5 / 2/5 | 5/5 each |
| writing-for-agents | `prose.md` | 0/5 / 0/5 | 0/5 / 0/5 | 5/5 each |
| test-design | `test-design.md` | 0/5 / 0/5 | 0/5 / 2/5 | 5/5 each |
| domain-modeling | `GLOSSARY-FORMAT.md` | 0/5 / 0/5 | 0/5 / 4/5 | 5/5 each |

**Finding: plain prompts never opened the operations entry point**, in 0 of 80
runs on either arm (plus 0 of 20 in the confined writing-for-agents rerun).
Haiku edited directly. The rewording can only help once the entry point is
loaded; with it loaded, the branch read the required file before the first edit
in 10 of 25 naive runs against 0 of 25 on main, with no over-triggering on the
negative prompts. Writing-for-agents `prose.md` still never fired.

Codex was not tested: no per-run way to load the branch was used here.

## Escape and confinement

The first entry-loaded batch let runs escape their throwaway repository. With
`/agentsmd:operations` loaded, the Skill's base directory (the plugin path) was
in context; the writing-for-agents prompt named `skills/greet` relatively, and
Haiku resolved it against the plugin, found nothing, and searched
`~/dev/toolboxmd`. It created `skills/greet/index.md` in the canonical checkout
`~/dev/toolboxmd/agentsmd`; later runs of both arms edited it and two
committed it there. Nine of the ten writing-for-agents naive entry-loaded runs
were affected. The harness had allowed it: `--dangerously-skip-permissions`,
the real HOME, and no post-run check. No other run wrote outside its repository
(every Edit/Write path and mutating shell command in all runs was checked). The
checkout was restored to `origin/main`; the escape is kept on the local branch
`backup/164-test-escape-20260929`.

All writing-for-agents results from that batch were discarded. The
writing-for-agents rows above come from a rerun under confinement, now built
into `trigger_test.py`:

- a temporary HOME whose `~/.claude` holds only the global contract as
  `CLAUDE.md`, plus a copy of the plugin under test loaded with `--plugin-dir`;
  login reuses the macOS keychain through a link to `~/Library/Keychains` and
  account metadata from `~/.claude.json` (no token copied);
- `--permission-mode acceptEdits --add-dir <temp repo>` instead of skipping
  permissions;
- absolute in-repo paths in every prompt;
- after every run, `git status --porcelain` and `HEAD` of the canonical checkout
  and this checkout must match the pre-batch snapshot, or the batch aborts.

The other three targets' rows come from the unconfined batches, with relative
paths in the prompts and the real HOME; their transcripts show no writes outside
their repositories. Condition differences between those rows and the
writing-for-agents rerun are therefore possible.

## Code review not reworded

The baseline's 1/64 for `review` is explained by its caveat. `measure.py --show
review` lists 64 trigger sessions: 43 are dispatched reviewer packets that
carry their own method (for example the #125 packet names the diff range, the
checks to run, severity levels and the required `VERDICT:` reply), and most of
the rest are keyword false positives (planner turns, OpenCode `TASK (complete)`
handoffs, tool-call echoes, and the session that commissioned this change).
Only one human review request remains ("can you review the PR #95?", Codex,
skipped). One missed human request is too small a sample to justify rewording.
