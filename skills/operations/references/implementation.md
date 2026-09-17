# Implementation

- Before tracked mutation, select an exclusively owned task branch and
  workspace; reuse them for continuation when ownership and availability
  remain established. Record the intended base, branch, workspace path,
  ownership, and exact starting `HEAD`. Keep the canonical checkout as the
  stable coordination and integration view. Worktrees and equivalent task
  checkouts are temporary from creation through Delivery Finalization. Keep
  required persistent local state, including databases and configuration, in
  stable locations outside them; secrets and databases do not belong in Git.

- Read-only work may share repository state only when it cannot mutate or
  interfere with a writer. Independent mutating Issues may proceed in parallel
  only in separate workspaces with disjoint ownership. A branch, workspace,
  and file set each has one writer at a time.

- Preserve and report dirty, active, or ambiguous state before selecting a
  workspace. Select another workspace unless exact ownership and availability
  are established; cleanliness alone proves neither. Treat unknown ownership
  or independence as unsafe. A moving base or unsafe overlap stops only the
  affected writer; unrelated independent work continues. For delegation,
  dependencies or interrupted tracked-work recovery, apply [orchestration and
  handoff rules](orchestration.md).

## Git

- Resolve the intended base branch instead of assuming `main`.
- Fetch when current base or PR state matters. Avoid routine pull, merge,
  rebase, stash, reset, or discard operations.
- Understand local and remote divergence before branching. Include or omit
  unpublished commits deliberately.
- Create or reuse one task branch for the Issue or authorized direct task. Use
  the current branch when it is already the correct task branch.
- Reuse the exclusively owned task branch/workspace for continuation.
  Concurrent writers require separate workspaces and disjoint write scopes;
  a sequential writer needs no extra worktree solely for ceremony.
- Keep commits useful and reviewable.

## Versioning

- Every completed tracked deliverable has one SemVer transition before commit.
  Internal component checkpoints belong to the final merge unit, whose version
  transition follows [delivery](delivery.md). Read-only work and explicit WIP
  checkpoints are exempt.
- Use `major` for incompatible behavior, `minor` for a backward-compatible
  capability, and `patch` otherwise.
- Use the `version-control` skill for the canonical version, mirrors, changelog,
  commit, tag, and release contract.
- Preserve missing-policy boundaries. Adopt versioning only as its own
  authorized change.

Before proof or review, read [verification](verification.md). For delegated
work or recovery, read [orchestration](orchestration.md). Follow the core's small
direct path when eligible, without creating an Issue or worker for ceremony.

## Workflow routing

- Orient: inspect status, branch, HEAD, remotes, and the requested work before
  changing tracked files.
- Follow Authority and continuation after orientation establishes the exact
  scope and current state.
- GitHub: search for a matching open Issue before creating one.
- Ownership: create product Issues in the product repository. If no GitHub
  repository clearly owns the work, ask before creating Issues.
- An Issue is ready when its outcome, acceptance criteria, non-goals, blockers,
  and required proof are explicit.
- Read-only work, throwaway spikes, WIP checkpoints, and explicitly local
  microfixes stay off the Issue-to-PR lane.

Choose the smallest lane that fits:

- Clear: implement the ready Issue directly.
- Shape: use `grill-with-docs` when bounded work still has unresolved
  terminology or user-owned decisions.
- Specify: use `to-spec` when understood work spans multiple sessions.
  Selecting it selects the complete Specify workflow through verified ticket
  publication by default. Preserve approval before parent Issue publication
  and approval of ticket granularity, blocking edges, and publication. After
  verified parent Issue publication, continue directly through the same
  ticket-graph stage without invoking another planning Skill or asking another
  routing question. Then begin the first unblocked implementation Issue when
  the full current request already grants implementation authority; otherwise
  ask exactly once and name that Issue. An explicit Parent Spec only request
  stops after the verified parent Issue. Apply the direct/delegated boundary
  in `AGENTS.md` when starting implementation.
- Wayfind: use `wayfinder` when unresolved dependent decisions prevent a
  reliable spec, regardless of predicted effort size. Once the path is clear,
  stop with the route ready for the user to select `to-spec` explicitly.

The AgentsMD workflow Skills `grilling`, `grill-with-docs`, `to-spec`,
`to-tickets`, and `wayfinder` are human-controlled planning Skills. Use them
when the user names one or asks to follow that workflow, and stop at their
approval gates. Other Skills follow their own trigger and approval contracts.
Skill ownership and provenance live in the AgentsMD `SKILL_CATALOGUE.md`.

Substantive tracked implementation uses a ready Issue and one final approval
PR per requested outcome. When decomposition is useful, apply the internal
component structure in [orchestration](orchestration.md).
