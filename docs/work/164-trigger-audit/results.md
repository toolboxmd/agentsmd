# Before-and-after trigger test (Issue #164, step 3)

Per-run evidence: [records.jsonl](records.jsonl), one line per run (condition,
host, model, arm, target, run, verdict, and the ordered tool calls with
anonymized paths up to the first edit). Raw streams are not committed.
`trigger_test.py --summary records.jsonl` regenerates the tables below.

## Four-host benchmark (the user's models)

Run 2026-09-29 with [trigger_test.py](trigger_test.py), 5 runs per cell, one
fresh throwaway git repository per run, plain prompts only (no forced entry
point). Arm `main` is `git archive origin/main` (`53296e5`); arm `branch` is
`git archive HEAD` of this branch (`ae9e261`). Evidence only, not a release
gate.

- **Entry point loaded**: the run called the `operations` Skill or read
  `operations/SKILL.md`, at any point.
- **Target read before first edit**: every required file was read before the
  first file edit (naive prompts).
- **Negative clean**: the required file was never opened (negative prompts).

### Summary

| Host, model | Entry point loaded, naive: main / branch | Target read before first edit: main / branch | Negatives clean: main / branch |
| --- | --- | --- | --- |
| Claude Code, Opus 5.5, medium | 0/20 / 0/20 | 0/20 / 0/20 | 20/20 / 20/20 |
| Codex, `gpt-6-astra`, low | 20/20 / 20/20 | 15/20 / 20/20 | 20/20 / 20/20 |
| Codex, `gpt-6-luna`, high | 20/20 / 20/20 | 9/20 / 20/20 | 20/20 / 20/20 |
| Grok Build, `grok-4.7`, medium | 20/20 / 20/20 | 15/20 / 20/20 | 20/20 / 20/20 |
| OpenCode, Muse 1.3 (Go route) | 16/20 / 16/20 | 0/20 / 16/20 | 20/20 / 20/20 |

**Finding: where the entry point loads, the branch wording makes the target
read happen**, on every host that loads it: Codex, Grok and OpenCode reach
20/20, 20/20, 20/20 and 16/20 on the branch, against 15, 9, 15 and 0 of 20 on
main. The branch fixed writing-for-agents `prose.md` everywhere (0/5 to 5/5).
No negative prompt opened a target file on any host or arm (200/200 clean).
OpenCode's branch reads match its entry-point loads: the 4 naive runs that
never loaded `operations` also never read the target.

**Claude Code Opus 5.5 is the exception: it never loaded the entry point on a
naive prompt** (0/40), so the wording could not act; it edited directly. It
loaded `operations` on 15 of 40 negative prompts (plain code edits), then never
read a target there either, correctly. Moving Claude needs a change to what
makes it load the entry point (the Skill description or the global contract),
not to the procedure wording tested here.

### Per host and model

#### claude-code, `claude-opus-5-5`, effort medium

80 of 80 runs valid (a run with no tool call is excluded).

| Measure | main | branch |
| --- | --- | --- |
| Entry point loaded, naive prompts | 0/20 | 0/20 |
| Entry point loaded, negative prompts | 7/20 | 8/20 |
| Target read before first edit (naive, every required file) | 0/20 | 0/20 |
| Negative clean (target never opened) | 20/20 | 20/20 |
| Naive, domain-modeling `GLOSSARY-FORMAT.md` read before first edit | 0/5 | 0/5 |
| Naive, technical-writing `prose.md` read before first edit | 0/5 | 0/5 |
| Naive, test-design `test-design.md` read before first edit | 0/5 | 0/5 |
| Naive, writing-for-agents `SKILL-MECHANICS.md` read before first edit | 0/5 | 0/5 |
| Naive, writing-for-agents `prose.md` read before first edit | 0/5 | 0/5 |

#### codex, `gpt-6-astra`, effort low

80 of 80 runs valid (a run with no tool call is excluded).

| Measure | main | branch |
| --- | --- | --- |
| Entry point loaded, naive prompts | 20/20 | 20/20 |
| Entry point loaded, negative prompts | 20/20 | 20/20 |
| Target read before first edit (naive, every required file) | 15/20 | 20/20 |
| Negative clean (target never opened) | 20/20 | 20/20 |
| Naive, domain-modeling `GLOSSARY-FORMAT.md` read before first edit | 5/5 | 5/5 |
| Naive, technical-writing `prose.md` read before first edit | 5/5 | 5/5 |
| Naive, test-design `test-design.md` read before first edit | 5/5 | 5/5 |
| Naive, writing-for-agents `SKILL-MECHANICS.md` read before first edit | 5/5 | 5/5 |
| Naive, writing-for-agents `prose.md` read before first edit | 0/5 | 5/5 |

#### codex, `gpt-6-luna`, effort high

80 of 80 runs valid (a run with no tool call is excluded).

| Measure | main | branch |
| --- | --- | --- |
| Entry point loaded, naive prompts | 20/20 | 20/20 |
| Entry point loaded, negative prompts | 19/20 | 19/20 |
| Target read before first edit (naive, every required file) | 9/20 | 20/20 |
| Negative clean (target never opened) | 20/20 | 20/20 |
| Naive, domain-modeling `GLOSSARY-FORMAT.md` read before first edit | 3/5 | 5/5 |
| Naive, technical-writing `prose.md` read before first edit | 5/5 | 5/5 |
| Naive, test-design `test-design.md` read before first edit | 1/5 | 5/5 |
| Naive, writing-for-agents `SKILL-MECHANICS.md` read before first edit | 5/5 | 5/5 |
| Naive, writing-for-agents `prose.md` read before first edit | 0/5 | 5/5 |

#### grok, `grok-4.7`, effort medium

80 of 80 runs valid (a run with no tool call is excluded).

| Measure | main | branch |
| --- | --- | --- |
| Entry point loaded, naive prompts | 20/20 | 20/20 |
| Entry point loaded, negative prompts | 20/20 | 20/20 |
| Target read before first edit (naive, every required file) | 15/20 | 20/20 |
| Negative clean (target never opened) | 20/20 | 20/20 |
| Naive, domain-modeling `GLOSSARY-FORMAT.md` read before first edit | 5/5 | 5/5 |
| Naive, technical-writing `prose.md` read before first edit | 5/5 | 5/5 |
| Naive, test-design `test-design.md` read before first edit | 5/5 | 5/5 |
| Naive, writing-for-agents `SKILL-MECHANICS.md` read before first edit | 5/5 | 5/5 |
| Naive, writing-for-agents `prose.md` read before first edit | 0/5 | 5/5 |

#### opencode, `opencode-go/muse-spark-1.3-contributor`

80 of 80 runs valid (a run with no tool call is excluded).

| Measure | main | branch |
| --- | --- | --- |
| Entry point loaded, naive prompts | 16/20 | 16/20 |
| Entry point loaded, negative prompts | 13/20 | 12/20 |
| Target read before first edit (naive, every required file) | 0/20 | 16/20 |
| Negative clean (target never opened) | 20/20 | 20/20 |
| Naive, domain-modeling `GLOSSARY-FORMAT.md` read before first edit | 0/5 | 2/5 |
| Naive, technical-writing `prose.md` read before first edit | 0/5 | 5/5 |
| Naive, test-design `test-design.md` read before first edit | 0/5 | 4/5 |
| Naive, writing-for-agents `SKILL-MECHANICS.md` read before first edit | 0/5 | 5/5 |
| Naive, writing-for-agents `prose.md` read before first edit | 0/5 | 5/5 |

### Conditions and confinement

Each run gets a temporary HOME and host configuration directory holding only
the arm's global contract (a copy), a copy of the arm's plugin or Skills, and
links to the host's existing login, removed in a `finally`. Nothing was
installed into the live host configuration.

| Host | Plugin or Skills loaded from | Permissions and sandbox | Login |
| --- | --- | --- | --- |
| Claude Code 2.1.284 | `--plugin-dir <copy>` | `acceptEdits`, `--add-dir <repo>` | link to `~/Library/Keychains` plus account metadata (no token) |
| Codex 0.159.0 | local marketplace in a temp `CODEX_HOME`, `codex plugin add` | `-s workspace-write`; plugin hooks run (`--dangerously-bypass-hook-trust` stands in for the live trusted hook hash) | `auth.json` link |
| Grok 1.0.44 | `grok plugin install <copy> --trust` in a temp `GROK_HOME`, plus the live-style Project Direction hook file pointed at the copy | `--always-approve` (the live setting) inside `--sandbox workspace` | `auth.json` link |
| OpenCode 1.18.33 | Skill and plugin links into the copy in a temp `OPENCODE_CONFIG_DIR`; XDG dirs under the temp HOME | edits and shell allowed, external directories denied except the copy | `auth.json` link |

Before its first batch every host passed the guard self-check (a new ignored
file is detected) and the cleanup self-check (a setup failure leaves no
temporary directory or login link). After every run the canonical checkout and
this checkout must match their pre-batch `git status --porcelain --ignored
--untracked-files=all` and HEAD, and the live host configuration files their
pre-batch content, or the batch aborts. No run wrote outside its repository.

The fixture repository now carries a minimal `VISION.md`, `MISSION.md` and
`OBJECTIVE.md`. Without them Codex stopped before any edit to ask for the
triad, as the global contract requires, so nothing could be measured.

### What could not be tested, and caveats

- **OpenCode free route.** `opencode/muse-spark-1.3-contributor-free` returned
  `Rate limit exceeded` for 36 of 40 branch runs after the main arm had run
  (arms were not yet interleaved), then `OpenCode's free tier can only be used
  from within OpenCode`. That batch was discarded. The table uses the same
  model on the Go route, `opencode-go/muse-spark-1.3-contributor`, with default
  variant (no effort was specified). The harness now interleaves arms and
  scores a run with no tool call as `no-output` instead of a miss.
- **Discarded or aborted batches, not in the records.** A first Claude batch and
  a first Codex batch aborted when the harness's own record append (and a stray
  `__pycache__` from a debug import) changed this checkout; a first Codex
  `gpt-6-astra` batch was misscored (reads through shell brace lists such as
  `references/{implementation,test-design}.md` were missed; scoring now expands
  them and records keep full commands); a first `gpt-6-luna` batch aborted when
  another session wrote `tmp/diagrams/` into the canonical checkout (not a run:
  the Codex sandbox blocks writes outside the run's repository).
- **Global contract is a copy, not a link.** Live installs link it to the
  canonical clone. In 34 of 80 `gpt-6-luna` runs the model searched the system
  temp directory for that clone and read contract and README files from the
  batch's source archive. No run read a target file from there, and none wrote
  outside its repository, but those runs spent calls on the search.
- **Claude and Grok records predate two scoring fixes** (brace expansion, full
  commands). Both hosts read through their Read tools; their records show no
  shell read of a target through a brace list.
- Grok does not run plugin hooks, so Project Direction reached it through the
  hook file, as on the live machine.

## Earlier Haiku pilot (not a benchmark)

The rows below are from `claude -p --model haiku` against the installed
AgentsMD 14.0.0 (identical to `origin/main` `53296e5` under `skills/`), before
the fixture carried a direction triad. They are kept as history.

### Results

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

### Escape and confinement

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
- after every run, `git status --porcelain --ignored --untracked-files=all` and
  `HEAD` of the canonical checkout and this checkout must match the pre-batch
  snapshot, or the batch aborts; each batch first proves the guard detects a new
  ignored file;
- the temporary repository, HOME and keychain link are removed in a `finally`
  after every run, also on failure or abort (added after review; the earlier
  batches left their temporary directories behind).

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
