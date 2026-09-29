# Baseline trigger skip rates (Issue #164, step 2)

Measured 2026-09-29 with `measure.py` (this folder) over sessions started on or
after 2026-09-15. Row definitions: [triggers.md](triggers.md). Reproduce:

```sh
python3 measure.py --since 2026-09-15 --exclude c7f31b0b-ddfa-4114-b228-66e51a88127c
python3 measure.py --since 2026-09-15 --exclude c7f31b0b-... --top-level
python3 measure.py --since 2026-09-23 --exclude c7f31b0b-...
python3 measure.py --since 2026-09-15 --exclude c7f31b0b-... --include-tmp
python3 measure.py --show <row>   # list each triggering session, call and fired/SKIP
```

The excluded session is the one that built this audit.

**Skip rate** = sessions where the trigger happened but no required file was
read at or before the first triggering call, divided by trigger sessions.

## Host coverage

| Host | Source read | Sessions counted (14 days) | Subagent/child | Dropped as tmp/eval cwd |
| --- | --- | ---: | ---: | ---: |
| Claude Code | `~/.claude/projects/**/*.jsonl`, including `*/subagents/*.jsonl` | 188 | 22 | 468 |
| Codex | `~/.codex/sessions/**/*.jsonl` (tool arguments, `exec` code-mode blobs split into commands and `apply_patch` paths) | 418 | 177 | 23 |
| Grok Build | `~/.grok/sessions/*/*/chat_history.jsonl` (assistant `tool_calls`); session start from `events.jsonl` | 43 | 0 | 49 |
| OpenCode | `~/.local/share/opencode/opencode.db`, `part` and `message` tables, opened read-only | 334 | 16 | 118 |

All four hosts load AgentsMD through a global link to the canonical
`AGENTS.md` (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.grok/AGENTS.md`,
`~/.config/opencode/AGENTS.md`); the script does not check this per session.

Agent Observer (`agent-observer` 0.5.0, synced 2026-09-29) was checked first. Its
ledger imports all four hosts but truncates command targets at 500 characters
and stores no arguments for Codex `exec` calls, so procedure reads and trigger
commands cannot be matched from it. The script reads the native records
directly instead. Grok is the thinnest source: most of its sessions in the
window are Imagine media runs, and only a few rows see a Grok trigger at all.

"Dropped as tmp/eval cwd" are sessions whose working directory is under `/tmp`
or `/var/folders`: evaluation harness runs, compaction probes and synthetic
scenarios (for example 460 Claude sessions since 2026-09-23). The
`--include-tmp` column shows they barely change the rates.

## Results

The workflows moved under `operations/` on 2026-09-23 (#120), inside the
window. Reads of the old standalone paths (`skills/<name>/SKILL.md`) and
old Skill names count as firing, so the 14-day column covers both layouts. The
"Since 2026-09-23" column is the current layout only.

| Row | Procedure and trigger | 14 days: fired/trigger (skip) | Top-level only | Since 2026-09-23 | With tmp/eval sessions | By host, 14 days (fired/trigger) |
| --- | --- | --- | --- | --- | --- | --- |
| `entry` | Operations entry point | 119/361 (67%) | 104/274 (62%) | 95/190 (50%) | 121/378 (68%) | claude 22/78, codex 40/113, grok 1/2, opencode 56/168 |
| `elon` | Elon method (material work) | 25/43 (42%) | 24/40 (40%) | 12/28 (57%) | 25/46 (46%) | claude 9/24, codex 16/19 |
| `elon>algorithm` | Elon method -> algorithm.md | 19/43 (56%) | 18/40 (55%) | 8/28 (71%) | 19/46 (59%) | claude 3/24, codex 16/19 |
| `pd` | Repair or change Project Direction | 4/4 (0%) | 4/4 (0%) | 2/2 (0%) | 4/4 (0%) | claude 1/1, codex 3/3 |
| `pd>contracts` | Project Direction -> file-contracts.md | 3/4 (25%) | 3/4 (25%) | 1/2 (50%) | 3/4 (25%) | claude 0/1, codex 3/3 |
| `grilling` | Grilling (explicit request) | 0/3 (100%) | 0/3 (100%) | 0/1 (100%) | 0/3 (100%) | claude 0/1, codex 0/2 |
| `domain` | Domain modeling | 2/32 (94%) | 2/30 (93%) | 1/15 (93%) | 2/32 (94%) | codex 2/7, opencode 0/25 |
| `domain>glossary` | Domain modeling -> GLOSSARY-FORMAT.md | 1/32 (97%) | 1/30 (97%) | 0/15 (100%) | 1/32 (97%) | codex 1/7, opencode 0/25 |
| `domain>adr` | Domain modeling -> ADR-FORMAT.md | 0 | 0 | 0 | 0 | - |
| `wayfinder` | Wayfinder (explicit request) | 1/6 (83%) | 1/6 (83%) | 0/5 (100%) | 1/6 (83%) | codex 1/6 |
| `spec` | Specify or tickets (explicit request) | 3/9 (67%) | 3/9 (67%) | 0/6 (100%) | 3/14 (79%) | claude 1/2, codex 2/7 |
| `tickets>decomp` | Tickets -> ticket-decomposition.md (2+ Issues created) | 5/31 (84%) | 5/29 (83%) | 4/19 (79%) | 5/31 (84%) | claude 4/16, codex 1/15 |
| `impl` | Implementation | 87/323 (73%) | 81/252 (68%) | 73/167 (56%) | 87/325 (73%) | claude 11/55, codex 27/98, grok 1/2, opencode 48/168 |
| `impl>verif` | Implementation -> verification.md (tests after edit) | 56/165 (66%) | 50/140 (64%) | 44/123 (64%) | 56/165 (66%) | claude 5/35, codex 21/38, grok 1/1, opencode 29/91 |
| `test-design` | Test design (test file edited) | 12/227 (95%) | 12/195 (94%) | 12/146 (92%) | 12/227 (95%) | claude 1/42, codex 6/43, grok 0/1, opencode 5/141 |
| `orch` | Orchestration (delegation) | 20/115 (83%) | 18/84 (79%) | 12/48 (75%) | 20/121 (83%) | claude 6/34, codex 13/57, grok 0/1, opencode 1/23 |
| `orch>bounded` | Orchestration -> bounded-delegation.md (parallel spawn) | 0/7 (100%) | 0/7 (100%) | 0/2 (100%) | 0/7 (100%) | codex 0/1, opencode 0/6 |
| `verif` | Verification (readiness claim: gh pr create/ready) | 34/105 (68%) | 34/92 (63%) | 31/80 (61%) | 34/105 (68%) | claude 8/59, codex 15/28, opencode 11/18 |
| `review` | Code review (review request, incl. dispatched packets) | 1/64 (98%) | 1/55 (98%) | 1/57 (98%) | 1/102 (99%) | claude 0/5, codex 1/37, opencode 0/22 |
| `review>method` | Code review -> review-method.md | 1/64 (98%) | 1/55 (98%) | 1/57 (98%) | 1/102 (99%) | claude 0/5, codex 1/37, opencode 0/22 |
| `proj-verif` | Project verification | 1/1 (0%) | 1/1 (0%) | 1/1 (0%) | 1/1 (0%) | codex 1/1 |
| `artifacts` | Artifact placement | 3/5 (40%) | 3/5 (40%) | 3/5 (40%) | 3/5 (40%) | claude 2/3, opencode 1/2 |
| `wfa` | Writing for agents | 13/32 (59%) | 10/28 (64%) | 8/21 (62%) | 13/32 (59%) | claude 2/9, codex 9/11, opencode 2/12 |
| `wfa>mechanics` | Writing for agents -> SKILL-MECHANICS.md (SKILL.md edited) | 6/15 (60%) | 5/14 (64%) | 3/12 (75%) | 6/15 (60%) | claude 0/2, codex 5/5, opencode 1/8 |
| `wfa>prose` | Writing for agents -> prose.md | 3/32 (91%) | 3/28 (89%) | 3/21 (86%) | 3/32 (91%) | claude 0/9, codex 2/11, opencode 1/12 |
| `tw` | Technical writing | 4/76 (95%) | 4/64 (94%) | 4/43 (91%) | 4/76 (95%) | claude 0/7, codex 2/24, grok 0/1, opencode 2/44 |
| `tw>prose` | Technical writing -> prose.md | 2/76 (97%) | 2/64 (97%) | 2/43 (95%) | 2/76 (97%) | claude 0/7, codex 2/24, grok 0/1, opencode 0/44 |
| `reflection` | Reflection (request; memory write as proxy) | 1/15 (93%) | 1/15 (93%) | 1/12 (92%) | 1/16 (94%) | claude 0/14, codex 1/1 |
| `vc` | Version control (git commit) | 95/186 (49%) | 54/132 (59%) | 40/117 (66%) | 95/198 (52%) | claude 13/70, codex 69/72, opencode 13/44 |
| `vc>bump` | Version control -> bump-rules.md (version change) | 0/4 (100%) | 0/4 (100%) | 0/3 (100%) | 0/4 (100%) | opencode 0/4 |
| `delivery-profile` | Delivery profile | 14/77 (82%) | 8/45 (82%) | 2/26 (92%) | 14/79 (82%) | claude 0/7, codex 14/67, opencode 0/3 |
| `delivery` | Delivery (PR, merge, release) | 31/112 (72%) | 31/97 (68%) | 26/84 (69%) | 31/112 (72%) | claude 6/62, codex 17/31, opencode 8/19 |
| `delivery>final` | Delivery -> finalization.md (gh pr merge) | 9/38 (76%) | 9/34 (74%) | 6/27 (78%) | 9/38 (76%) | claude 1/22, codex 8/16 |
| `final` | Finalization (close Issue, retire worktree/branch) | 15/72 (79%) | 15/70 (79%) | 10/59 (83%) | 15/72 (79%) | claude 2/47, codex 13/22, opencode 0/3 |
| `repo-setup` | Repository setup (settings mutation) | 1/3 (67%) | 1/3 (67%) | 1/3 (67%) | 1/3 (67%) | claude 0/2, codex 1/1 |
| `grok` | Use Grok (grok CLI run) | 10/15 (33%) | 9/14 (36%) | 4/9 (56%) | 10/15 (33%) | claude 2/5, codex 8/8, grok 0/1, opencode 0/1 |

Rows not in the table have no observable trigger; triggers.md says why.

## Weakest rows

Rows with at least 10 trigger sessions, 14-day window, highest skip rate first:

| Rank | Row | Fired/trigger | Skip | Note |
| ---: | --- | --- | ---: | --- |
| 1 | `review` code review | 1/64 | 98% | 43 of 64 triggers are dispatched reviewer packets ("Independent code review ...", "Perform ... review"); the packet may carry its own method, but only one session opened the procedure |
| 2 | `review>method` review-method.md | 1/64 | 98% | Same trigger as `review` |
| 3 | `tw>prose` technical writing -> prose.md | 2/76 | 97% | |
| 4 | `domain>glossary` GLOSSARY-FORMAT.md | 1/32 | 97% | 25 of 32 are OpenCode sessions |
| 5 | `test-design` test-design.md | 12/227 | 95% | Trigger is any test-file edit; broad |
| 6 | `tw` technical writing | 4/76 | 95% | README/docs edits |
| 7 | `domain` domain modeling | 2/32 | 94% | |
| 8 | `reflection` | 1/15 | 93% | 14 of 15 are Claude memory writes (proxy); 1 is a prompt |
| 9 | `wfa>prose` writing for agents -> prose.md | 3/32 | 91% | Matches the #164 evidence of skipping prose.md |
| 10 | `tickets>decomp` ticket-decomposition.md | 5/31 | 84% | Proxy trigger: second `gh issue create` in a session |

Next: `orch` 20/115 (83%), `delivery-profile` 14/77 (82%), `final` 15/72
(79%), `delivery>final` 9/38 (76%).

Small samples with high skip rates, not ranked: `grilling` 0/3, `orch>bounded`
0/7, `vc>bump` 0/4, `wayfinder` 1/6.

Best-firing rows: `pd` 4/4, `grok` 10/15, `elon` 25/43 (42% skip), `vc`
95/186 (49%).

## Host pattern

Codex fires far more often than Claude on the delivery-side rows: `vc` codex
69/72 vs claude 13/70, `delivery` 17/31 vs 6/62, `final` 13/22 vs 2/47,
`elon>algorithm` 16/19 vs 3/24. The data does not show why. Many Codex
sessions are Model Router workers whose packets may name the procedure files,
so a Codex read may follow the packet rather than the routing table. Checking
that needs the packet text per session, which this script does not classify.

## Limits

- A read proves the file was opened, not that the agent applied it. A skip
  proves only that no matching read appears in the transcript.
- Reads earlier in the session count, even before a compaction; a file read
  before a context reset counts as fired.
- Reads the script cannot see are counted as skips: a relative
  `references/...` path in a command without `operations` in it, a file opened
  by a script or a subagent, content pasted into a packet by the dispatcher,
  and Claude's automatic skill loading without a Skill call. `workflows/...`
  relative paths are recognized.
- Trigger patterns are observable proxies for judgment triggers. Prompt rows
  (`grilling`, `wayfinder`, `spec`, `review`, `reflection`) count only
  keyword matches; `grilling`, `wayfinder` and `spec` use prompts of 1200
  characters or less to skip dispatched packets that merely mention the word.
  `test-design` counts any test-file edit, and `tickets>decomp` uses a second
  `gh issue create` as its trigger. `--show <row>` lists every match for audit.
- Shell edits through `python3 -` heredocs or `sed -i` are not seen as edits;
  `cat >` and `tee` are.
- Subagent and dispatched sessions are included in the main column; they
  receive AgentsMD through the same global link but often work from a packet.
  The top-level column removes them (Claude `subagents/`, Codex spawned agents,
  OpenCode child sessions). Codex `codex exec` workers and Claude `claude -p`
  workers still count as top-level.
- The session that built this audit is excluded. Other AgentsMD development
  sessions in the window (for example #120, #138, #146, #161) are included and
  are heavier on procedure reads than ordinary product work.
- The Context row (Project Direction loading) is enforced by hook and not
  measured here.
- Eight days of the window (2026-09-15 to 2026-09-22) predate the workflow
  move; legacy paths are matched, but those sessions saw separate skill
  descriptions instead of the routing table.
