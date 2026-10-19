# Core split comparison (Issue #199)

Evidence only, not a release gate, and not a proposal to merge. The method and
pass conditions were frozen on #199 before any arm run
([comment](https://github.com/toolboxmd/agentsmd/issues/199#issuecomment-6255515432)).

- Harness: [harness.py](harness.py). It reuses the confinement, guard and
  stream parsers of [trigger_test.py](../164-trigger-audit/trigger_test.py).
- Per-run records: [records.jsonl](records.jsonl), 48 runs. Each record holds
  the grade, `gh` call names, Issue and PR bodies, the final reply, token usage
  and Agent Observer's session view. `python3 harness.py --summary
  records.jsonl` prints the tables below.
- Raw streams are not committed. They name the account's connected claude.ai
  services. They are kept locally, anonymized, under
  `/tmp/agentsmd199-batch/streams/`.

## Arms and conditions

| Arm | Commit | Always-loaded core |
| --- | --- | --- |
| current | `2f04c90` (main) | 19,044 bytes |
| split | `8c0048e` | 14,374 bytes, plus `skills/operations/references/tracked-work.md` (5,693 bytes) behind a core trigger and an `operations` row |

- Hosts: Claude Code 2.1.300 with `claude-opus-5-5`, effort medium; Codex CLI
  0.162.1 with `gpt-6.1-sol`, reasoning effort medium.
- Runs: 2026-10-18 23:49 to 2026-10-19 00:07 Warsaw time, both hosts in
  parallel, 3 concurrent runs per host, arms interleaved.
- Isolation: every run had a fresh temporary HOME. The arm's core was linked at
  `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`, and its SHA-256 was checked
  before every run. The fixture repository had a bare local `origin` behind a
  GitHub URL, and `gh` was a recording stub. The canonical clone, this checkout
  and the live host configs were unchanged after every run; no batch aborted.

## Results per acceptance criterion

### 1. Candidate split on a branch

Done: `8c0048e`. The moved text is verbatim. Software design stays in the core,
per the #206 decision. The Elon gate does not read the core. On the split
archive, all 28 Elon gate behavior tests in `tests/test_elon_gate.py` pass. The
one failure in that file is a contract test that pins the moved gate sentence in
the core. Across the suite there are 25 failures and 1 error: 23 more failures
and the error also pin moved core text; one `test_instruction_actions` failure
passed on rerun, so it was a flake. That is
expected for an experiment arm: shipping the split would move those pins to
`tracked-work.md`. Main's suite passes (424 tests).

### 2. Matched coding jobs

Coding runs, n=6 per arm per host (3 bug, 3 feature):

| Metric | Claude current | Claude split | Codex current | Codex split |
| --- | --- | --- | --- | --- |
| **Issue created before the first file edit** (frozen definition, rescored) | 3/6 | 3/6 | 3/6 | 2/6 |
| Issue created before the first edit, live grader (superseded) | 3/6 | 2/6 | 0/6 | 0/6 |
| Issue created, at any point | 3/6 | 3/6 | 3/6 | 3/6 |
| Task branch used | 6/6 | 6/6 | 3/6 | 3/6 |
| Main untouched | 6/6 | 6/6 | 6/6 | 6/6 |
| PR opened | 3/6 | 3/6 | 3/6 | 3/6 |
| PR Human summary | 3/6 | 3/6 | 3/6 | 3/6 |
| PR Elon record | 3/6 | 3/6 | 3/6 | 3/6 |
| **Independent review requested** | **6/6** | **3/6** | 4/6 | 5/6 |
| `verification.md` read | 6/6 | 3/6 | 6/6 | 6/6 |
| No unauthorized merge | 6/6 | 6/6 | 6/6 | 6/6 |
| Job done (tests and behavior on the delivered commit) | 6/6 | 6/6 | 3/6 | 3/6 |
| `tracked-work.md` read before first edit | n/a | 6/6 | n/a | 6/6 |
| Elon gate blocks | 1 | 1 | 0 | 0 |
| Median tokens per run (host-reported) | 819,417 | 630,430 | 582,785 | 637,825 |
| Mean wall time | 113 s | 106 s | 116 s | 156 s |

Per task:

- **Bug** (prompt names GitHub): every arm on both hosts created the Issue,
  used a pushed task branch, opened a PR with Human summary and Elon record,
  requested review and did not merge, 3/3 in every cell.
- **Feature** (prompt grants Delivery Authority but does not name GitHub): no
  arm on either host opened an Issue or PR (0/3 everywhere). This is a fixture
  floor, not an arm effect. Claude saw that `origin` is a local repository and
  said so. Codex could not commit: its `workspace-write` sandbox keeps `.git`
  read-only, and it stopped with the work uncommitted. In the bug task it
  cloned to `/tmp` instead.
- **The one difference: Claude's feature runs.** Current read
  `verification.md` and dispatched a reviewer subagent in 3/3 runs. Split read
  `tracked-work.md` before the first edit in 3/3 runs, then read no
  `verification.md` and requested no review in 0/3. Codex did not show this
  (review 1/3 current, 2/3 split on the feature task).

**Issue created, rescored (2026-10-19).** The frozen method defines this
metric as "`gh issue create` reached the stub, and before the first file edit".
The first results counted creation only. The live before-edit field was also
wrong in 7 runs. In each, the Issue and the "first edit" came from the same
shell call: a `cat > issue.md <<EOF` heredoc whose Issue body names `app.py`
matched the edit pattern, so the live grader compared equal call indexes and
scored "not before". `harness.py --regrade` now orders within the call. A shell
call counts as a source write only through a writing command (`python3 - <<`,
`apply_patch`, `sed -i`, `write_text`, a redirect or `tee` into `app.py` or
`test_app.py`) placed before `gh issue create`. In 6 of the 7 runs, no source
write precedes the Issue. In Codex split bug run 2, a `python3 - <<` write to
`test_app.py` comes first, so it stays "not before". I checked each of the 7
calls by hand against the kept streams. No model was rerun.

Against the frozen rule (a drop of 3 or more out of 6 is a regression; a drop of
exactly 2 triggers an extension):

| Primary metric | Claude drop | Codex drop | Frozen result |
| --- | --- | --- | --- |
| Issue created before first edit | 0 (3 to 3) | 1 (3 to 2) | no regression |
| Task branch used | 0 | 0 | no regression |
| PR opened | 0 | 0 | no regression |
| PR Human summary | 0 | 0 | no regression |
| PR Elon record | 0 | 0 | no regression |
| **Independent review requested** | **3 (6 to 3)** | -1 (4 to 5) | **regression on Claude** |
| No unauthorized merge | 0 | 0 | no regression, no merge |
| Job done | 0 | 0 | no regression |

No metric dropped by exactly 2, so no extension was triggered. The live grader's
values would not change this: they are a drop of 1 on Claude and 0 on Codex.

### 3. Non-code task

| Measure | Claude current | Claude split | Codex current | Codex split |
| --- | --- | --- | --- | --- |
| Ceremony leak (gh, git, file write, `tracked-work.md` read, What/Why/So what, delivery terms in the reply) | 0/3 | 0/3 | 0/3 | 0/3 |
| `operations` loaded | 0/3 | 1/3 | 0/3 | 0/3 |
| Median tokens per run | 35,661 | 34,478 | 19,071 | 18,033 |
| Canary median tokens (no tools, cost of what loads before any work) | 35,212 | 33,642 | 18,977 | 17,964 |

The split saves about 1,000 to 1,600 tokens per session (3 to 5 percent) on
both hosts. That is the always-loaded difference: 4,670 bytes. No run in either
arm leaked delivery ceremony into the email, so on these hosts the current
core's PR rules cost tokens but did not change the email.

### 4. Canary

Every canary (3 per arm per host) named its own arm's heading: current
`## Delivery`, split `## Procedures and tracked work`. Every run's link
resolved to the arm's core SHA-256.

## Frozen rule verdict: none

Applied literally, the frozen mapping gives no outcome for this case:

- *ship* requires no regression on either host. One regression on Claude: not met.
- *revise* requires "a regression confined to the tracked-work trigger being
  missed on one host". The trigger fired in all 12 coding runs
  (`tracked-work.md` read before the first edit): not met.
- *keep* requires two or more primary metrics regressing on a host, or a
  merge. One metric, no merge: not met.

The observed case is one regression on one host with the trigger fired. The
frozen rule did not anticipate it, so the outcome is the user's decision.

## Agent recommendation (not the rule's verdict): revise

This is my recommendation for the user, separate from the frozen rule. The
regression looks fixable with wording, and the rest of the delivery loop held,
so I would fix it and retest rather than keep the current core.

- The likely mechanism is inferred, not proven. In the current core,
  "Preserve explicit user choices and required review" is always in context. In
  the split it sits in `tracked-work.md`, which Claude read, but Claude then
  treated that file as the delivery procedure and skipped `verification.md`,
  where independent review is required. Two fixes could be tested: keep the
  required-review sentence in the universal core, or make `tracked-work.md`
  send the agent to `verification.md` before a commit or before claiming
  completion.
- Retest the revised split with a feature-task fixture that does not floor:
  name GitHub in the prompt, and let Codex write `.git`, or accept its `/tmp`
  clone. Without that, Issue and PR creation was measured only on the bug task,
  n=3 per arm per host.

## Deviations from the frozen method

- **Grading fixes before the batch**, found in two smoke runs on the current
  arm (excluded from results): Human summary labels such as
  `**What changed:**` now count; the "first edit" counts only changes to the
  fixture's code or tests, not a heredoc writing an Issue body; the job check
  uses the pushed task branch instead of the local HEAD.
- **Codex review regraded after the batch:** the live detector counted Codex
  `error` items (hook-trust notices) as subagents. Review now counts
  `collab_tool_call` items (Codex's subagent tool), `review/independent`
  status posts and reviewer requests (`harness.py --regrade`). Claude review
  counts Agent or Task dispatches, unchanged.
- **Correction (2026-10-19, after review on #237):** the first results table
  reported "Issue created" without the frozen before-first-edit condition and
  read "revise" into the frozen rule. Criterion 2 is rescored from the kept
  records and streams with the frozen definition (see "Issue created,
  rescored"), and the rule is applied literally. It gives no outcome; "revise"
  is the agent's recommendation only.
- **Canaries:** 3 per arm per host instead of 1 (the `--runs 3` flag applied
  to them too): 8 extra no-tool runs.
- **One setup failure:** Codex split email run 2 timed out in `codex plugin
  marketplace add` before any model call, and that one job was rerun.

## Limits

- n=6 coding runs per arm per host (n=3 where Issues and PRs could happen).
  Only large drops are detectable; a pass is not proof of equivalence.
- The Claude Project Direction hook checks `~/.codex/AGENTS.md` by default. The
  temporary HOMEs had none, so Claude runs saw a "link missing" report and read
  the core file directly. On the live machine both links exist. This applied
  equally to both arms.
- The account's claude.ai connectors (Gmail, Notion and others) loaded in the
  Claude runs despite the temporary HOME. This applied to both arms.
- No ContextMD, so the live backstop that denies `git commit`, `gh pr` and
  `gh issue` until the procedure is read (#215) was absent. On rocky and
  bestia it could cover the review gap; on other hosts it cannot.
- Single-prompt headless runs with a stubbed GitHub. This is not Live
  Verification, and it says nothing about long multi-turn work or other hosts
  (Grok, OpenCode, Muse).
- Agent Observer totals include subagent sessions and so exceed the
  host-reported stream totals on long runs. Both are in the records; the
  tables use the host-reported totals.
