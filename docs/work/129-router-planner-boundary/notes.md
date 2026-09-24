# Issue 129: Router-managed planner boundary, task notes

Owning Issue: https://github.com/toolboxmd/agentsmd/issues/129
Parent spec: https://github.com/toolboxmd/model-router/issues/87 (owns Router wording; not edited here)

## Elon decision (also recorded on the Issue)

- Wanted: authoritative AgentsMD contract makes the Router-managed
  planner/dispatcher/worker boundary unambiguous, preserving acceptance and
  the Objective.
- Evidence: toolboxmd/t3code#1 planner takeover after worker/runtime failures;
  broad core delegation language plus upstream critical-lane wording permits it.
- Cuts: no new orchestration layer, logger, watchdog, recovery engine,
  role redesign, routing-table copy, universal read-only sandbox, unrelated
  cleanup, or Project Direction change.
- Smallest surviving: short scoped rule in core AGENTS.md, recovery and
  escalation detail with six examples in bounded-delegation, acceptance duty
  in verification, one-line pointer in orchestration, one glossary entry,
  focused contract tests.
- Current constraint: contradictory role wording was the earliest limiter.

## Contradiction inventory (read-only inspection, 2026-09-24)

AgentsMD-owned text reconciled in this change:

- `AGENTS.md` execution routing: "The main agent owns reasoning, planning,
  integration, and the outcome" plus unrestricted "Direct work: inspect
  affected state, edit, run relevant checks" had no Router-managed scoping.
- `skills/operations/references/bounded-delegation.md` recovery table had no
  statement that failure never authorizes planner implementation, and no
  escalation shape.
- `skills/operations/references/verification.md` acceptance text had no
  explicit no-waiver and no-takeover clause for Router-managed execution.

Upstream Router wording (owned by model-router#87, recorded for final
reconciliation, not edited):

- `skills/model-routing/references/codex.md:14`: "critical | planner itself |
  planner; a load-bearing step or prose the rest depends on is done by the
  planner itself in its own host session; the runner never dispatches it"
- `skills/model-routing/references/codex.md:29`: "Classify by consequences,
  not file type. A step or prose that the rest of the work depends on is
  `critical`: do it in the planner session yourself, then submit the
  remainder."
- `skills/model-routing/SKILL.md:26-27`: "A critical step stays with the
  planner; submit the remainder."
- `RUNNER.md:74-75`: "`critical` lane is planner-executed and `submit`
  rejects it: do that step in the planner session, then submit the remainder."
- Policy identity: `durable-runner-policy-v2` 2.7.0.

Residual for coordinator integration: the upstream `critical` row and
"classify by consequences" rule still read broadly enough to cover a failed
worker's repair. AgentsMD now scopes its side; the Router side reconciles
under model-router#87.

## Proof log

Required proof (run on exact final candidate; see final report for SHAs):

- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `python3 -m unittest discover -s tools/versionctl/tests -p 'test_*.py'`
- Cross-repo link closure: `python3 tests/check_model_router_bundle.py
  /Users/lukaszmaj/dev/toolboxmd/model-router` (optional, no model calls).
- Contradiction sweep: rg over owned contract files for `read-only planner`,
  route slugs (`muse-spark`, `planner_rungs`), and one-owner marker
  duplication.

## Observer and behavioral proof limits

- Observer task identity: agentsmd-129. No installed Observer skill or CLI in
  this worker sandbox; the local agent-observer checkout database copy holds
  no agentsmd-129 rows; dispatcher-side sync earlier failed with `unable to
  open database file`. Capture gap reported, not blocking.
- Requested route: muse-spark-xhigh-free under durable-runner-policy-v2
  2.7.0. Observed: execution as muse-spark-1.3-contributor; exact pool
  unknown to the worker.
- No genuine routed-task Observer trace demonstrating the boundary was
  available in this sandbox. Behavioral proof remains pending; nothing here
  fabricates agent compliance or Live Verification.
- Independent final review is coordinator-owned and remains required.
