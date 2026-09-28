# Core rewrite behavioral comparison (#157)

Question: does the shortened core keep agent behavior on weaker hosts while
making replies to the user brief?

## Method

- Harnesses, each isolated from installed rules (candidate installed as the
  global rules file in a temporary home): Codex CLI 0.158.0 (`gpt-6-astra`,
  low effort), Grok CLI 1.0.41 (default model), OpenCode 1.18.32
  (`opencode/muse-spark-1.3-contributor-free`), Claude Code 2.1.283 (Haiku,
  `--setting-sources project,local --append-system-prompt-file`).
- 13 single-turn scenarios (`harness/scenarios.json`), no tools, answer as
  ACTIONS plus REPLY. Blind grading by Claude Sonnet against per-scenario
  rubrics (`harness/judge.py`). Runner: `harness/run.py`.
- Rubrics for S06, S07 and S09 were corrected after round one: they had
  failed agents for not running tools the prompt forbade.

## Results

| Version | Criteria passed | Avg reply words |
| --- | --- | --- |
| Old core, round 1 | 100/120 (83%) | 66 |
| Old core, round 2 | 105/120 (88%) | 69 |
| Final core, one full round | 103/120 (86%) | 43 |

- Final-report brevity (S01): old 8/12 criteria per round with every agent
  failing the brevity criterion; final 12/12.
- No scenario regressed consistently. Approval carry-through (S10) is noisy
  in both versions (old 6/8 and 4/8, final 4/8).
- Two draft cuts caused regressions and were reverted: dropping "follow-up" and
  "or ship" from approval carry-through made agents ask again; "evidence goes in
  the Issue or PR" made Grok and OpenCode post read-only reviews to the PR until
  the read-only exception was added (then 16/16 over two rounds).
- Claude Haiku is the weakest host in both versions (em dashes in both,
  guesses on S07, one secret echoed in chat).

## Limits

Single-turn text scenarios, one grader model, 1 to 2 rounds per cell. They show
no loss of tested behavior and much shorter replies; they do not prove behavior
in real multi-turn work. Raw outputs were not retained.
