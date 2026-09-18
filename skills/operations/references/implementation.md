# Implementation

Before tracked mutation, apply the core's orientation, authority, user-work,
and single-writer rules. Record intended base, branch, exclusive workspace,
ownership, and exact starting `HEAD`. Reuse that workspace for continuation
when ownership and availability remain established. A sequential writer needs no
extra worktree. Cleanliness alone proves neither ownership nor availability. Preserve/report ambiguous, dirty, or active state
and select another workspace unless exact ownership and availability are
established. Treat unknown ownership or independence as unsafe. Unsafe overlap
or a moving base stops only the affected writer.

Keep the canonical checkout as stable coordination/integration view. Task
worktrees and equivalent checkouts are temporary through Delivery Finalization.
Keep required persistent state, including databases/configuration, outside them;
secrets and databases never belong in Git. Read-only work may share state only
without mutating or interfering. Concurrent mutating Issues need separate
workspaces and disjoint ownership of branch, workspace, and file set.

## Git and versioning

Resolve the intended base instead of assuming `main`. Fetch when current base
or PR state matters; do not routinely pull, merge, rebase, stash, reset, or
discard. Understand divergence and deliberately include or omit unpublished
commits. Create or reuse one task branch for the Issue or authorized direct task.
Keep commits useful and reviewable.

Every completed tracked deliverable has one SemVer transition before commit:
major for incompatible behavior, minor for compatible capability, patch otherwise.
Read-only work and explicit WIP checkpoints are exempt. Components defer to
[final delivery](delivery.md). Use `version-control` for canonical version,
mirrors, changelog, commits, tags, and release. Missing policy requires separately
authorized adoption.

Before proof/review, read [verification](verification.md). For delegation,
dependencies, component PRs, or interrupted recovery, read
[orchestration](orchestration.md). Apply the core's execution choice without
creating an Issue or worker for ceremony.

## Workflow routing

Apply the core Delivery qualification rules before choosing a lane. Search open
Issues for duplicates; ask if the owning repository is unclear.

Choose the smallest suitable lane:

- **Clear:** implement the ready Issue.
- **Shape:** use `grill-with-docs` for bounded unresolved terminology or user decisions.
- **Specify:** use `to-spec` when requested. That Skill owns the complete workflow
  through approved parent and ticket publication, Parent Spec only opt-out, and
  continuation to the first unblocked Issue under existing implementation authority.
  Read it when selected; preserve both publication gates and its single named-Issue
  authority question when implementation is not authorized.
- **Wayfind:** use `wayfinder` when dependent unresolved decisions prevent a reliable
  spec, regardless of effort size. Stop when ready for explicit `to-spec` selection.

For planning invocation, approval gates, and provenance, apply the core Delivery
section; this routing table grants no additional invocation authority.
