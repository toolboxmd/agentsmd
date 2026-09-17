# Orchestration and dependencies

## One final approval PR

- For multiple PRs, create an exclusively owned integration branch from the
  intended base. Target components there; stack dependencies and retarget in
  merge order using the rules below. Small tasks use one ordinary PR; local
  microfix exceptions remain.
- Verify protections and CI accept unreleased components without release,
  publication, deployment or other protected impact on internal pushes/merges.
  Otherwise use [repository setup](repository-setup.md), never bypass checks.
- Agents may merge components only into integration after exact-head/current-base
  checks and independent [review](verification.md) pass.
- The final PR targets the intended base: complete cumulative diff, component
  map, outcome acceptance, combined proof and independent review of the exact
  candidate. Component checks alone are insufficient. Its merge requires human
  approval; [delivery](delivery.md) owns the single version transition.
- Keep component Issues open with integration evidence; only the final PR carries
  closing linkage. Internal integration is not delivery. After authorized delivery,
  [finalize and clean up](finalization.md). Other Human Gates remain.

## Execution and dependencies

- Choose the smallest valid execution mode. **Sequential direct work** serves
  one merge unit without useful parallelism. Sequential describes writer
  concurrency: substantive work still uses a delegated single writer. **Independent worktree pull
  requests** serve genuinely independent merge units with exclusive branches,
  workspaces, and file sets. **Dependent stacked pull requests** serve layers
  whose predecessor is review-ready at an exact SHA. **Tightly coupled
  single-writer integration** serves work whose contracts, migrations,
  generated outputs, release identity, or acceptance build cannot safely
  separate. Different files alone do not prove independence.

- Keep a dependent Issue natively blocked until its predecessor publishes a
  complete review-ready pull request at an exact SHA. Record the predecessor
  pull request, exact head, proof state, and dependency state before clearing
  only that native blocker. Start a native stacked pull request from that exact
  predecessor when available. Otherwise use an ordinary dependent branch with
  equivalent exact-base, review, rebase, revalidation, retarget, and
  dependency-ordered merge invariants. Independent work remains free.

- Apply each review fix to the earliest layer that owns the broken acceptance
  criterion. Cascade rebase and revalidation through every affected dependent
  layer after a lower-layer change. Merge in dependency order, and verify
  automatic rebase or retarget before treating an upper layer as current.
  Preserve exact stack state across interruption, fresh context, and durable
  handoff. Report review-ready, blocker-cleared, stacked, rebased, revalidated,
  retargeted, and merged as separate states.

- Delegate substantive implementation to a fresh child with the repository,
  complete Issue, exact base and dependency state, complete current Project
  Direction and applicable instructions, relevant durable decisions, and
  granted authority. Repository and GitHub evidence replace prior transcripts
  when sufficient. Use a nested child with that seed packet and no prior
  transcript; do not fork the parent transcript. Bounded settled direct work
  follows the core's qualitative token-cost rule and needs no worker.
  Open a separate host task only when the slice must outlive the parent, a
  human must open it independently, or the writer must continue after the
  parent stops.

- Keep one canonical durable handoff on the owning Issue, linked from the PR
  and other consumers. Record branch, workspace, exact base and `HEAD`, proof
  commands/results and evidence links, review identity/verdict, version state,
  granted authority, dependency state, delivery state, cleanup state,
  finalization state, blockers, and next action. Update that record when facts
  change rather than duplicating Issue/PR prose. For local work without an
  Issue, put the same relevant fields in the final response.
- The coordinator independently verifies current Git and GitHub state from
  that evidence. Reuse valid exact-candidate proof under
  [verification](verification.md); reading a worker transcript or rerunning
  identical checks is not required. Start the next unblocked substantive Issue
  with its own seed packet.

- When a child finishes, errors, or goes idle, close it so it leaves the
  working state. Do not copy worker transcripts into the coordinator. Keep
  concurrent mutating writers few, exclusive, and bounded; do not fan out
  unbounded children.

- An interrupted task may resume the same Issue when its context remains
  useful. A resumed or fresh task recovers the current Issue, workspace,
  branch, `HEAD`, proof state, granted authority, delivery state, cleanup state,
  finalization state, blockers, and next action from Git, GitHub, project
  instructions, and the durable handoff.
  Do not recreate completed work or request completed approvals again.

- Keep the contract host-neutral. Tasks, threads, worktrees, and equivalent
  mechanisms are adapter choices, not global controls. Do not create a
  persistent orchestration service without later evidence and authority.
