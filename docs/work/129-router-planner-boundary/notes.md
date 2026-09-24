# Issue 129: Router-managed planner boundary, task notes

Owning Issue: https://github.com/toolboxmd/agentsmd/issues/129
Parent spec: https://github.com/toolboxmd/model-router/issues/87 (owns Router wording; not edited here)

## Elon decision (also recorded on the Issue)

- Wanted: authoritative AgentsMD contract makes the Router-managed
  planner/dispatcher/worker boundary unambiguous, preserving acceptance and
  the Objective.
- Evidence: toolboxmd/t3code#1 planner takeover after worker/runtime failures;
  broad core delegation language plus upstream critical-lane wording permits it.
  Verified 2026-09-24 in this worktree: installed Model Router 0.29.1 still
  directs planner-executed critical and planner-chosen rungs and returns the
  job to the planner after recovery; AgentsMD owned files before this fix had
  no terminal no-eligible-agent path and scoped the direct-work carve-out as
  "outside a Router-managed job".
- Cuts: no new orchestration layer, logger, watchdog, recovery engine,
  role redesign, routing-table copy, universal read-only sandbox, unrelated
  cleanup, or Project Direction change.
- Smallest surviving: short scoped rule in core AGENTS.md, recovery and
  escalation detail with seven examples in bounded-delegation, acceptance duty
  in verification, pointer-only orchestration reference, one glossary entry,
  focused contract tests.
- Current constraint: contradictory role wording was the earliest limiter.
  Residual limiter is upstream Router wording owned by model-router#87.

## Contradiction inventory (read-only inspection, 2026-09-24)

AgentsMD-owned text reconciled in this change:

- `AGENTS.md` execution routing: "The main agent owns reasoning, planning,
  integration, and the outcome" plus unrestricted "Direct work: inspect
  affected state, edit, run relevant checks" had no Router-managed scoping.
  Fixed with a short Router-managed rule, an explicit no-eligible-agent
  terminal path, and a carve-out scoped to tasks not submitted to Model
  Router; a submitted task remains Router-managed through terminal
  disposition.
- `skills/operations/references/bounded-delegation.md` recovery table had no
  statement that failure never authorizes planner implementation, and no
  escalation shape. Fixed with dispatcher-owned recovery, escalation shape,
  terminal path, and the integration precedence sentence below.
- `skills/operations/references/verification.md` acceptance text had no
  explicit no-waiver and no-takeover clause for Router-managed execution.
  Fixed; verification retains acceptance and proof ownership.
- `skills/operations/references/orchestration.md` restated the boundary in
  its own words and used the shifting scope term "Router-managed job".
  Trimmed to a pointer; "Router-managed execution" is now the single scope
  term in AGENTS.md, bounded-delegation, orchestration, verification, and
  GLOSSARY.md.

Upstream Router wording (owned by model-router#87, recorded for final
reconciliation, not edited here or in any installed cache):

- `skills/model-routing/references/codex.md` critical lane: a load-bearing
  step or prose the rest depends on is done by the planner itself in its own
  host session; the runner never dispatches it.
- `skills/model-routing/references/codex.md` consequences rule: a step or
  prose that the rest of the work depends on is `critical`: do it in the
  planner session, then submit the remainder.
- Recovery lane: one escalation per job, then the job returns to the planner.
- Planner rungs: the planner chooses a rung and runs it in its own session;
  the runner never dispatches these.
- Installed-cache policy identity observed in this sandbox:
  `durable-runner-policy-v2` 2.7.0. Prior-job runner report and proof-log
  identities cited in review could not be verified here; the referenced
  turn report, proof log, and worker log files are absent from this sandbox.

Required integration wording for final reconciliation (sanitized):

- A Router critical or planner-chosen step never covers implementation,
  repair, recovery, or completion of a submitted candidate; those remain
  dispatcher-assigned work.

Residual for coordinator integration: the upstream `critical` row and
"classify by consequences" rule still read broadly enough to cover a failed
worker's repair. AgentsMD now scopes its side with the sentence above; the
Router side reconciles under model-router#87. This correction does not claim
AgentsMD alone resolves the cross-repo conflict.

## Proof log

Required proof (run on exact final candidate; exact commands, results, and
final SHA are recorded in the worker handoff and PR130):

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 -m unittest discover -s tools/versionctl/tests -p 'test_*.py'`
- Cross-repo link closure: `python3 tests/check_model_router_bundle.py
  <model-router-checkout>` (optional, no model calls; not run in this
  correction sandbox).
- Contradiction sweep: rg over owned contract files for `read-only planner`,
  route slugs (`muse-spark`, `planner_rungs`), scope-term drift
  (`Router-managed job`), and one-owner marker duplication.

Base: 56fdd26536a23560cd164539557ee805740ed63f. Prior candidate:
56b802a79025a0be67e0bdde6d87d4e8d6ff2ed2. Version stays 12.3.0; no
additional bump for this correction.

## Observer and behavioral proof limits

- Observer task identity: agentsmd-129. No installed Observer skill or CLI in
  this worker sandbox. The local opencode database exposes session and part
  tables but no Observer task linkage, and no genuine sanitized ordinary
  routed-task trace for agentsmd-129 demonstrating the boundary was available
  here. Capture gap reported, not blocking.
- Requested versus observed route: the prior-job requested route and policy
  version cited in review could not be verified in this sandbox because the
  referenced runner report files are absent. This correction ran as the
  implementation worker under the fixed task-local runtime snapshot; no
  route or pool claim is made for it.
- No genuine routed-task Observer trace demonstrating the boundary was
  available in this sandbox. Behavioral proof remains pending; nothing here
  fabricates agent compliance or Live Verification. Package instruction
  checks are not behavioral proof.
- Independent final review is coordinator-owned and remains required.
