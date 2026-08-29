# Response economy evaluation

This record preserves the evidence used for
[Issue #3](https://github.com/toolboxmd/agentsmd/issues/3) and
[PR #9](https://github.com/toolboxmd/agentsmd/pull/9). It reports observed
Grok and Codex behavior from 2026-08-29. It does not claim universal savings.
Rejected local 4B-model runs are excluded.

## Policies

The baseline was `AGENTS.md` at
`f0001d7923c555b6522b0faaf983bc51ce55af32`. Its Communication section said to
lead with the outcome, use clear technical English, keep each answer
stand-alone, match the user, and re-pitch explanations that did not land.

The Grok candidate also replaced the stand-alone-context sentence with: “Give
enough local context to prevent ambiguity without repeating shared context.” It
then added this 66-word response-economy draft:

> Default to concise. Lead with the outcome. Keep decision-relevant evidence,
> material caveats, and the next action; drop filler, repetition, generic
> reassurance, optional background, and routine progress.
>
> Compress phrasing, not meaning. Preserve negation, uncertainty, exact values
> and strings, exceptions, permissions, and delivery states.
>
> Expand for risk, ambiguity, ordering, an unfamiliar audience, or when asked.
> Before sending, check that brevity preserved status, risk, permission, and the
> next action.

The lossy control policy was:

> Respond with the fewest words possible. Fragments preferred. Drop articles,
> subjects, and complete sentences when the meaning can be guessed.

All arms received the same repository-truth, Human Gate, delivery-state, and
read-only-work rules. The final policy in `AGENTS.md` was hardened after the
failures below. It adds exact errors, ownership, permission gates, established
next actions, and the instruction to expand when asked. The later standards
review also narrowed `routine progress` to `routine process recaps` and removed
an unknown-state sentence already owned by Judgment. The final subsection is 67
whitespace-delimited words and 549 bytes, including its Markdown structure.
The complete `AGENTS.md` grows by 65 words relative to the baseline.

## Grok protocol

- Model: `grok-4.6` through Grok Build CLI `1.0.13`.
- Reasoning: `high`.
- Isolation: one turn, no tools, no web search, no subagents, and identical
  authoritative facts for every arm.
- Generations: six task shapes times three policies, 18 outputs total, one
  sample per cell.
- Review: six separate blinded judge calls. Labels were shuffled with a fixed
  seed before the policy mapping was restored.
- Scoring ignored length and style. It checked negation, uncertainty, exact
  values, permissions, delivery states, risk, correct next action, and concrete
  omissions or inversions.

### Fixed tasks

| ID | Shape | Required meaning and exact facts |
|---|---|---|
| `t1` | Simple answer | API port `8088`; TLS is not enabled. |
| `t2` | Delivery status | Issue `#42`; commit `a1b2c3d`; PR `#91` open but not approved or merged; not released, published, deployed, or live-verified; version `2.1.0` untagged. |
| `t3` | Permission gate | Merge and production deploy are Human Gates; PR `#91` is not approved; staging is not production; live cluster `prod-eu-1`; nothing merged or deployed. |
| `t4` | Exact-error diagnosis | Command `npm test -- --runInBand`; exact error `TypeError: Cannot read properties of undefined (reading 'id')`; `src/billing/invoice.ts:142`; not a timeout; suspected cause remains unconfirmed; no patch applied. |
| `t5` | Nontechnical stale-data explanation | UI is not the cause; Redis key `dash:v2:metrics`; TTL `6 hours`; refresh `2026-08-28 14:22 UTC` contains `2026-08-21` data; job failed `2026-08-22 03:10 UTC` with `permission denied for relation payments_v3`; later permission status is unknown. |
| `t6` | In-progress update | Issue `#42`; branch `fix/42-samesite`; tests still running at `12 of 40` after `2m10s`; test `sets SameSite=Lax on session cookie`; nothing committed; `package-lock.json` is user-owned and untouched; no blocker; finish tests and commit only if green. |

### Results

| Task | Baseline words | Draft words | Lossy-control words | Draft preservation finding | Lossy-control preservation finding |
|---|---:|---:|---:|---|---|
| `t1` | 19 | 11 | 1 | None | None required beyond `8088`. |
| `t2` | 53 | 48 | 35 | None | None. |
| `t3` | 93 | 37 | 30 | Omitted the explicit Human Gate and production-risk language. | None. |
| `t4` | 66 | 67 | 33 | None. | Omitted `npm test -- --runInBand`. |
| `t5` | 83 | 84 | 65 | Invented cache-rewrite and remediation claims from an unknown permission state. | Omitted the `6 hours` TTL. |
| `t6` | 58 | 52 | 34 | Kept the file untouched but omitted that it was user-owned. | Also omitted the ownership label. |
| **Total** | **372** | **299** | **198** | | |
| **Median** | **62** | **50** | **33.5** | | |

The draft reduced total visible words by 73, or 19.6%, relative to the
baseline. The smaller lossy control removed more words but failed exact command,
TTL, and ownership checks. The draft itself exposed three hardening needs:
explicit permission-gate language, no next action inferred from an unknown, and
preserved ownership.

The judge also found that the baseline weakened `package-lock.json` from
user-owned and untouched to merely unstaged. The task therefore tested whether
the new policy could improve precision as well as reduce length.

## Codex observations

All Codex runs used `gpt-5.6-sol`; no 4B-model result is included.

- An isolated low-effort candidate search used eight fixed tasks per policy.
  Baseline output was 704 reported tokens. `Be concise.` used 525. Three
  precision-preserving candidates used 554, 562, and 477. A Caveman-like
  67-word control used 551. These were policy-search observations, not the
  final comparison.
- Three paired one-shot checks at ultra effort produced shorter visible answers
  with the compact policy. Low-effort repeats did not show a consistent visible
  reduction. Hidden reasoning varied enough that no total-cost conclusion was
  drawn.
- One five-turn continuation used 873 visible output tokens and 140,414
  reported input tokens under the baseline, versus 681 visible output tokens
  and 138,044 reported input tokens under the compact draft. That is 192 fewer
  visible output tokens and 2,370 fewer reported input tokens in one
  trajectory, not a stable percentage.
- A final hardening check covered the permission gate, unknown permission
  status, exact dates and error, user-owned file boundary, and established next
  action. The final wording preserved them in that check.

The Grok task requirements, tested policy text, aggregate counts, and failure
findings are recorded above. The original runner, per-call JSON, individual
Codex outputs, and five-turn event stream are not included in this repository
artifact. The figures are reviewable summaries rather than independently
replayable evidence.

## Interpretation

- The policy can reduce visible output on representative tasks without adopting
  a skill, proxy, hidden mode, or broken grammar.
- The preservation and expansion clauses do real work. A shortest-output rule
  alone is unsafe.
- Static instruction cost can outweigh output savings in a short exchange.
  Savings compound only when later requests resend prior assistant replies.
- Prompt caching can change billed cost without changing the semantic context
  presented to the model. Clients that do not resend full history will not get
  the same input-token effect.
- One sample per model-task-policy cell is directional evidence. It does not
  establish a universal reduction for every model, reasoning level, or task.
- The final two wording refinements were standards-driven and were not followed
  by another model benchmark.
