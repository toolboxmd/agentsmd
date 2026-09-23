
# Orchestration and dependencies

## One final approval PR

For multiple PRs, create an exclusive integration branch from the intended base;
target components there, stack dependencies, and retarget in merge order. Small
tasks use one ordinary PR; local microfix exceptions remain.

Verify protections/CI permit unreleased internal pushes/merges without release,
publication, deployment, or protected impact. Otherwise use [repository setup](repository-setup.md),
never bypass checks. Agents may merge components into integration only after
exact-head/current-base checks and independent [review](verification.md).

The final PR targets the intended base with cumulative diff, component map,
outcome acceptance, combined proof, and independent exact-candidate review.
Component checks alone are insufficient. Apply existing merge approval under
the core's Authority and continuation contract;
[delivery](delivery.md) owns the single version transition. Component Issues stay
open with integration evidence; only the final PR carries closing linkage.
Internal integration is not delivery. After authorized delivery, [finalize](finalization.md).
Other Human Gates remain.

## Execution and dependencies

Choose the smallest valid mode under the core's direct/delegated rule:

| Mode | Use when |
| --- | --- |
| Sequential direct work | One merge unit has no useful parallelism. |
| Independent worktree pull requests | Independent merge units have exclusive branches, workspaces, and file sets. |
| Dependent stacked pull requests | Each predecessor is review-ready at an exact SHA. |
| Tightly coupled single-writer integration | Contracts, migrations, generated outputs, release identity, or acceptance builds cannot safely separate. |

Different files alone never prove independence. Keep a dependent Issue natively
blocked until its predecessor publishes a complete review-ready PR at an exact
SHA. Record PR, exact head, proof, and dependency state before clearing only that
blocker. Use native stacking from that SHA when available; otherwise preserve
equivalent exact-base, review, rebase, revalidation, retarget, and merge-order
invariants on an ordinary dependent branch. Independent work may continue.

Fix the earliest layer owning failed acceptance. Checkpoint descendants and cascade
rebase/revalidation after lower-layer changes without losing later work. Merge in
dependency order and
verify automatic rebase/retarget before calling upper layers current. Preserve
exact stack state across interruption and handoff. Report review-ready,
blocker-cleared, stacked, rebased, revalidated, retargeted, and merged separately.

A dependency transfers context as well as order. Relay the exact upstream
artifact, relevant decisions, proof, and remaining limitations to its consumer.
Assign one writer to topology changes, including rebases, retargets, and merge
order. Refresh affected observations after topology changes under the proof
policy; prior branch names alone do not establish current identity.

## Workers and recovery

Seed a fresh child with repository, complete Issue, exact base/dependencies, full
current Project Direction and applicable instructions, durable decisions, authority,
and exclusive workspace. Include canonical instruction path/SHA-256; the child
verifies the live source and reads current instructions/adjacent private preferences
when freshness is unproved. Startup text alone is insufficient. Never publish
private preferences. Use repository/GitHub evidence instead of prior transcripts
when sufficient.

Include the unit's outcome, allowed and forbidden writes, shared-resource limits,
acceptance, proof seam, known gotchas, report shape, and bounded escalation
condition. Do not dispatch unresolved ownership or acceptance. Before parallel
work, read [bounded delegation](bounded-delegation.md) for alternative-versus-
coverage aggregation, capacity, pilots, and failure recovery. For an authorized
external intake or automation adapter, also read [external handoffs](external-handoffs.md).

Use a nested child with that packet and no prior transcript; do not fork the parent
transcript. Direct work needs no worker. A separate host task is only for work that
must outlive the parent, be independently openable by a human, or continue after
the parent stops. Close finished, errored, or idle children so each leaves the
working state. Keep writers few, exclusive, and bounded; no unbounded children.
Do not copy worker transcripts into the coordinator.

For retained supporting files, follow [artifact placement](artifacts.md). Model
Router reports stay in its existing state directory; link their identities.
Keep one canonical durable handoff on the owning Issue, linked from PR/consumers:
branch, workspace, exact base/HEAD, proof commands/results/links, review identity/
verdict, version, authority, dependencies, delivery, cleanup, finalization, blockers,
and next action. Update it instead of duplicating prose. For local work, report
relevant fields in the final response.

The coordinator independently verifies Git/GitHub state and reuses valid
exact-candidate proof under [verification](verification.md); transcripts and duplicate
checks are unnecessary. Start the next unblocked substantive Issue with its own
packet. Resume the same Issue when context remains useful; recover current state
from Git, GitHub, instructions, and handoff. Never recreate completed work or
request completed approvals again.

Tasks, threads, and worktrees are host-neutral adapter choices. Do not create a
persistent orchestration service without later evidence and authority.

For long or uncertain work whose consequential choices would otherwise disappear,
keep a material-decision trail in the existing task evidence notes, linked from
the canonical handoff under [artifact placement](artifacts.md). Record the
decision, reason, evidence, and observed result at meaningful pivots. A routine
task needs no extra journal. The trail owns history, never current acceptance,
delivery state, or decisions that belong in an ADR. Keep private material local;
publish only sanitized evidence within authority. Correct or supersede earlier
claims explicitly instead of rewriting them into eventual success. Before
handoff, resolve material evidence pointers and include the trail in required
review when it supports the outcome.
