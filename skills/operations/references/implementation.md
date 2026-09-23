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

## Engineering method

Choose technical work by the claim being changed, while retaining the lane above:

| Need | Method |
| --- | --- |
| Understand mechanics, historical constraints, or earlier failed work | `research` |
| Choose an API, boundary, state model, or migration | `software-design` |
| Explain a defect, reproduce it, verify another fix, or improve performance | `diagnosis` |
| Preserve behavior while restructuring or migrating callers | `software-design`, [change existing systems](../../software-design/references/change-existing-systems.md) |
| Select behavioral proof or pin a regression | [Test design](test-design.md) |
| Repair missing or stale product-driving instructions | `project-verification` |

Search duplicate work by cause, signature, affected version, and concrete existing
artifacts. Similar wording is not sufficient. Use diagnosis when that distinction
or fix ownership is unclear. Do not author a competing patch in another owner's
active scope when the useful next step is evaluating their exact candidate.

For unfamiliar material work, state an observable done condition and what would
falsify it. Capture the relevant baseline before it disappears. Resolve the
riskiest uncertainty first, then sequence units that produce useful evidence.
Keep tightly coupled work under one owner. For each uncertain unit, make the
smallest authorized experiment, inspect the actual artifact, and keep or revise
the result. Inconclusive observations do not pass.

Build only proof support that distinguishes success from failure. If a result
passes suspiciously easily, check that the observer exercised the intended
behavior and artifact. Correct defective gates in a reviewable change; never
weaken acceptance to fit the implementation. Unit checks lead to whole-outcome
verification under the existing proof contract.
