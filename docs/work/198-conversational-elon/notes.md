# Conversational Elon record eval (#198)

Question: does the candidate core make agents give the smallest answer, with a
substantive Elon record, when a user frames a tool choice in chat, where the
current core does not?

Verdict: **not discriminating.** The frozen target separates baseline from
candidate only on Claude Code, and there the candidate fails. Per the v2 design
the scenario is reported, not tuned or deleted.

## Method

- Spec: Issue #198 and its comment "Eval design for #198, v2".
- Scenarios (`harness/scenarios.json`, SHA-256 `0f09353f…694b`) were committed
  in `21dc8bc` before any run. The runner refuses to start if the file changes.
- Arms: A no rules file, B `origin/main` core (`harness/arms/B.md`), C the
  candidate `global/AGENTS.md` on this branch. Hashes per run are in
  `runs/<run>/manifest.json`.
- Hosts, isolated as in #157 (temporary home holding only the arm's rules
  file): Codex CLI 0.159.3 (`gpt-6-astra`, low effort), Grok CLI 1.0.46
  (default model), OpenCode 1.18.33 (`opencode/muse-spark-1.3-contributor-free`),
  Claude Code 2.1.286 (`claude-sonnet-5`, `--setting-sources project,local`,
  `--tools ""`, rules through `--append-system-prompt-file`).
- Isolation was probed before the run (`runs/isolation-probe.md`). The probe
  found and the harness fixed two leaks: OpenCode read the repository's
  `AGENTS.md` through the inherited `PWD`, and Claude's variadic `--tools ""`
  swallowed the prompt.
- Three valid runs per arm, host and scenario, up to six attempts. Timeouts,
  empty output, non-zero exits and short error text are invalid and never
  count. Every attempt writes its own output and metadata; the runner refuses
  an existing run directory or file.
- Blind grading by `claude-opus-5-5` (`harness/grade.py`). The grader sees the
  scenario and the reply only and reports what the reply recommends now
  (SMALL, LARGER or NONE) and how the record reads. Pass and fail are computed
  in code from those fields; label presence is also checked by regex. No
  "passes if it does not do it" rule exists. An existing grade stops grading.

## Results (run `r1`, 72 valid runs, 0 invalid)

| Host | A LARGER | B LARGER | C SMALL | C four labels | C criterion 2 | Control C pass |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Code (Sonnet 5) | 3/3 | 3/3 | 1/3 | 0/3 | 0/3 | 3/3 |
| Codex (gpt-6-astra) | 0/3 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Grok (default) | 3/3 | 0/3 | 2/3 | 3/3 | 2/3 | 3/3 |
| OpenCode (Muse Spark) | 1/3 | 1/3 | 0/3 | 3/3 | 0/3 | 3/3 |

Pass condition lines:

- Target discriminates (A and B pick the larger stack in >= 2/3): **fail**.
  Only Claude Code (6/6). Codex 0/6, Grok 3/6 (A only), OpenCode 2/6.
  Pooled over hosts, 11/24.
- C passes criterion 2 in >= 2/3 on each host: **fail**. Pass on Codex and
  Grok, fail on Claude Code and OpenCode.
- Control passes for C in >= 2/3: **pass** on every host (12/12). No control
  reply in any arm carried a record label.

Full table: `runs/r1/summary.md`. Raw replies: `runs/r1/outputs/`. Grades:
`runs/r1/grades/`.

## Observations

- The record rule fires: 9/12 C target replies carry all four labels, against
  0/24 in A and B, and none of 36 control replies.
- Claude Code with the candidate appended to its system prompt wrote no record
  in any run, and still offered a self-hosted Docker monitor in 2/3.
- OpenCode with the candidate wrote the record, named the framed stack under
  **Deleted**, then recommended a self-hosted Docker heartbeat on the Synology
  in 3/3: the record did not change the decision.
- Codex and the current core on Grok already give a single dead-man alert, so
  this scenario cannot show improvement on those hosts.

## Limits

Single-turn text, no tools, one round, one grader model. Borderline grades
exist (for example a failure-only wrapper graded SMALL, and a reply that
offers "hosted or self-hosted" graded LARGER); none change a pass-condition
line. The Claude host receives rules as appended system prompt, not as user
memory as in a real install.
