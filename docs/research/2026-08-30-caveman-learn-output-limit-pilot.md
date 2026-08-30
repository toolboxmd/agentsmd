# Caveman Learn output-limit pilot: smaller tool results increased total cost

**Status:** Controlled pilot complete; hard 4,000-token rule rejected

**Date:** 2026-08-30

**Issue:** [#25](https://github.com/toolboxmd/agentsmd/issues/25)

**Scope:** Test whether a compact exploration rule derived from a local Caveman
Learn report lowers token use without lowering answer quality. This report
records the experiment. It does not adopt agent policy.

## Executive conclusion

Do not add the tested hard 4,000-token exploration rule to global `AGENTS.md`.

The rule reduced locally counted command-output tokens by about one third in
the five completed control/treatment pairs. It also increased provider-reported
raw input by 89.8%, uncached input by 24.2%, command calls by 30.1%, and elapsed
time by 35.3%. Blind quality was equal at 47/50 per arm in those completed
pairs. A sixth treatment pair at `max` timed out without a final answer while
its control completed and scored 10/10.

The intervention optimized an intermediate measure rather than the outcome.
Smaller individual tool results caused more reads and more accumulated context
to be presented across turns. In the timed-out run, the agent split a
4,029-token result solely because it exceeded the threshold by 29 tokens. It
later found the required evidence but did not finish.

The useful Caveman Learn direction remains measurement before adoption. A
future experiment should test a softer no-refetch rule that discourages broad,
unrelated reads without making a numeric output threshold the objective.

## Hypothesis

The local Caveman Learn report ranked large tool outputs as a material context
sink. Historical output above 10,000 tokens formed a small heavy tail. The
pilot asked whether a stricter 4,000-token routine ceiling would reduce total
input while preserving evidence and answer quality.

The tested treatment added this rule to otherwise identical fixture prompts:

> During routine exploration, keep each tool result below 4,000 tokens. Use
> `rg` first, then targeted line ranges. Parallel tool calls are allowed, but
> do not combine broad multi-file reads into one result. Summarize successful
> checks and expand failures only. Never omit errors, exact values, authority,
> exceptions, or required proof to meet the limit; exceed it when full evidence
> is genuinely necessary and state why.

The control received no output-limit rule.

## Experimental design

The pilot used three fixed OpenBot repository fixtures. Each fixture ran once
per arm at both `gpt-5.6-sol` `high` and `max`, for twelve runs total.

| Fixture | Fixed source | Required outcome |
| --- | --- | --- |
| Architecture lookup | Commit `c4fdb2fc007d84e924701e115a373083aae1df4c` | Recover five specified contract elements and exact evidence |
| Standards review | Diff `8ada14d556b1e6a4fa389e8805f218153b9e9e58..8ccaef8078334a1c1ea5506289c9c11c8eacc109` | Find terminology and design-token violations and separate visual proof |
| Transaction diagnosis | Commit `be59df29fe660caa01b469107e434974b53673ac` | Explain persistence, throw path, inconsistency, correction, and regression seam |

Controls used the same model, reasoning effort, repository state, task, and
600-second timeout as their treatments. Run order was counterbalanced within
the effort and fixture groups.

Each run used:

- an isolated read-only shared clone;
- ephemeral Codex state;
- approval disabled;
- no network, GitHub, live resources, or subagents;
- a fixed answer key prepared before execution.

Run outputs were frozen with SHA-256 before randomized blind scoring. The blind
mapping was revealed only after the scores were recorded.

## Aggregate results

### High: all three pairs completed

| Measure | Control | Treatment | Treatment change |
| --- | ---: | ---: | ---: |
| Blind quality | 27/30 | 27/30 | equal |
| Elapsed time | 533.4 s | 770.3 s | +44.4% |
| Raw input tokens | 1,495,222 | 3,534,537 | +136.4% |
| Cached input tokens | 1,236,736 | 3,252,992 | +163.0% |
| Uncached input tokens | 258,486 | 281,545 | +8.9% |
| Model output tokens | 23,285 | 26,556 | +14.0% |
| Command calls | 66 | 70 | +6.1% |
| Command-output tokens | 187,355 | 126,435 | -32.5% |

### Max: completed architecture and transaction pairs

| Measure | Control | Treatment | Treatment change |
| --- | ---: | ---: | ---: |
| Blind quality | 20/20 | 20/20 | equal |
| Elapsed time | 655.9 s | 839.0 s | +27.9% |
| Raw input tokens | 2,378,369 | 3,819,209 | +60.6% |
| Cached input tokens | 2,180,864 | 3,534,336 | +62.1% |
| Uncached input tokens | 197,505 | 284,873 | +44.2% |
| Model output tokens | 27,613 | 30,460 | +10.3% |
| Command calls | 47 | 77 | +63.8% |
| Command-output tokens | 105,726 | 69,423 | -34.3% |

The `max` standards control completed in 344.8 seconds and scored 10/10. The
treatment reached the fixed 600-second timeout with no final answer and scored
0/10. Provider usage was unavailable because the interrupted turn did not emit
a completion event, so its input and model-output tokens are not included in
the completed-pair table.

### Five completed pairs across both efforts

Quality was equal at 47/50 per arm. Treatment changed the measured costs as
follows:

- command-output tokens: -33.2%;
- raw input tokens: +89.8%;
- cached input tokens: +98.6%;
- uncached input tokens: +24.2%;
- model output tokens: +12.0%;
- command calls: +30.1%;
- elapsed time: +35.3%.

Raw input includes context presented again as later turns accumulate, much of
it cached. It is a provider usage measure, not a dollar-cost claim. The pilot
did not price either arm.

## Per-run record

Provider input and model-output fields are unavailable for the timed-out run.
Command-output tokens are local counts, not provider billing fields.

| Fixture | Effort | Arm | Score | Time s | Raw input | Uncached input | Model output | Calls | Command output | Timeout |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Architecture | high | control | 10 | 126.4 | 444,845 | 74,157 | 5,256 | 8 | 49,398 | no |
| Architecture | high | treatment | 10 | 213.2 | 755,384 | 64,440 | 6,510 | 17 | 31,416 | no |
| Architecture | max | control | 10 | 171.7 | 356,836 | 71,652 | 8,131 | 6 | 40,534 | no |
| Architecture | max | treatment | 10 | 263.2 | 822,259 | 72,179 | 11,021 | 18 | 33,257 | no |
| Standards | high | control | 7 | 185.8 | 451,187 | 85,619 | 7,920 | 29 | 75,402 | no |
| Standards | high | treatment | 7 | 271.3 | 1,137,805 | 112,781 | 9,802 | 25 | 39,532 | no |
| Standards | max | control | 10 | 344.8 | 570,583 | 84,695 | 15,638 | 40 | 91,354 | no |
| Standards | max | treatment | 0 | 600.0 | n/a | n/a | n/a | 50 | 47,983 | yes |
| Transaction | high | control | 10 | 221.3 | 599,190 | 98,710 | 10,109 | 29 | 62,555 | no |
| Transaction | high | treatment | 10 | 285.8 | 1,641,348 | 104,324 | 10,244 | 28 | 55,487 | no |
| Transaction | max | control | 10 | 484.3 | 2,021,533 | 125,853 | 19,482 | 41 | 65,192 | no |
| Transaction | max | treatment | 10 | 575.8 | 2,996,950 | 212,694 | 19,439 | 59 | 36,166 | no |

## Quality findings

- All four architecture answers scored 10/10.
- All four completed transaction answers scored 10/10.
- Both `high` standards answers scored 7/10 and missed the design-token
  violation.
- The `max` standards control found both violations and scored 10/10.
- The timed-out treatment found the missing design-token evidence internally,
  but a discovery that never reaches the final answer is not a successful
  result.

This small sample suggests that `max` can add useful adversarial review depth,
but it also makes the strict threshold's extra interaction rounds especially
expensive. It is not sufficient evidence for a permanent effort-routing rule.

## Observed failure mechanism

The hard number became a local objective. In the timed-out treatment, the agent
reported that a grouped diff exceeded the 4,000-token limit by 29 tokens and
was truncated. It replaced that read with zero-context hunks and targeted
numbered ranges. The candidate rule contained an exception for necessary full
evidence, but the agent chose threshold compliance instead.

The metric pattern is consistent with that trace:

1. Treatment reduced the size of individual command results.
2. Treatment increased the number of command and interaction rounds.
3. Later rounds carried more accumulated conversation context.
4. Total input and elapsed time increased even when final quality was equal.
5. One evidence-heavy treatment failed the completion gate.

This is a causal interpretation supported by one direct trace and the aggregate
pattern. The pilot does not prove that every numeric limit causes this behavior.

## Decision and next hypothesis

The hard 4,000-token rule is rejected. Global `AGENTS.md` was not changed.

The next candidate should target broad reads and redundant refetching rather
than the byte size of every result:

> During exploration, use `rg` and targeted ranges before broad reads. Avoid
> combining unrelated full-file or full-history outputs. Do not repeat a read
> solely to meet an output limit. Summarize passing checks; preserve complete
> failures and authority-bearing evidence.

This is an untested hypothesis, not adopted guidance. If a numeric guardrail is
still useful, a later experiment can treat output above 10,000 tokens as an
exceptional heavy-tail event. It should not make the threshold a success metric
or force refetching evidence already obtained.

The separate workflow proposal to retire long mixed-purpose tasks and start
fresh bounded tasks remains plausible. This pilot tested only the per-result
output rule and cannot be cited as evidence for or against fresh-task
boundaries.

## Limitations and confounders

- There were three fixtures with one sample per effort and arm. Model
  nondeterminism was not averaged out.
- The fixtures were read-only repository investigations, not implementation,
  browser acceptance, or live-system work.
- All runs logged plugin-manifest or state-database warnings.
- WebSocket setup returned HTTP 426 and fell back to HTTP.
- Some Git commands emitted nonfatal macOS cache-write warnings in the
  read-only sandbox.
- These runtime conditions appeared across arms but limit generalization.
- The pilot measured tokens and completion time, not monetary cost.

## Artifact identity

The raw JSONL bundle remains local because it contains machine-specific paths
and execution metadata. This page preserves the complete scored measurements.
The frozen local artifacts had these SHA-256 identities:

| Artifact | SHA-256 |
| --- | --- |
| Pilot report | `b55cd85eb42787140ffc1ffd3c055c2a91ce0b78d6025aa438d2b19540a9bfa5` |
| Run manifest | `b9e68d65d0fbfd964de205e4fe4b0842006faa68c27df518a97be475b31db66a` |
| Metrics | `808e7cae7e5471988fc6a22f9d363efa97f7b04e93d53f218d9e71dc3d7e4269` |
| Blind mapping | `0cec1a850e8323f954161268d6efbd49593fb987883ae9d4198285ad2286f66f` |
| Blind scores | `a8e987eaee7c9362d817b2fd9cb1e188257c26315ae6523b193d81451ee2f563` |
| Frozen run checksums | `c9724d811b2ea58a9bf7a4137003a241ed1658ccb73261afd9b128be3b2c8d43` |

All three test clones were clean after execution. The existing dirty AgentsMD
checkout, global instructions, GitHub state, and live systems were not modified
by the experiment.
