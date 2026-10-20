
# Orchestration and dependencies

## One final approval PR

For multiple PRs, create an exclusive integration branch from the intended base;
target components there, stack dependencies, and retarget in merge order. Small
tasks use one ordinary PR; local microfix exceptions remain.

Verify protections/CI permit unreleased internal pushes/merges without release,
publication, deployment, or protected impact. Otherwise use [repository setup](repository-setup.md),
never bypass checks. Agents may merge components into integration only after
exact-head/current-base checks and independent [review](verification.md), shown
on GitHub by `review/independent` `success` on the current head, or a recorded
exemption, as defined in [delivery](delivery.md).

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

Seed a fresh child with repository, complete Issue, exact base/dependencies,
applicable instructions, durable decisions, authority, and exclusive workspace.
Pass references (Issue, paths, exact commands), not restated Project Direction or
instruction hashes; the child's hook supplies both, and the child rereads current
instructions in full only when its hook reports a problem or did not run. Never publish
private preferences. Use repository/GitHub evidence instead of prior transcripts
when sufficient.

Include the unit's outcome, allowed and forbidden writes, shared-resource limits,
acceptance, proof seam, known gotchas, report shape, and bounded escalation
condition. The report shape for a negative result (not possible, cannot remove,
blocked, no recipe, or failed) lists what was tried and which primary sources
were checked: the tool's own docs and bundled README, its `--help`, its
environment variables, and its config keys. Do not dispatch unresolved
ownership or acceptance. Do not dispatch implementation of a new component or
system until the brief cites a Spec Issue
([to-spec](../procedures/to-spec/index.md)) whose Design review names the
reviewer, the verdict, and the user's decisions; acceptance criteria in a brief
are not a design. A microfix or a change inside an existing component says so in
the brief and needs no Spec. Review, research, and test dispatches are outside
this rule. A child, a reviewer included, may start in the coordinator's
checkout, which can be a live
install such as the canonical AgentsMD clone. Name its worktree or temporary
clone in every packet and forbid `gh pr checkout`, `git checkout`, switch,
reset, pull, and every other write in any main checkout; reviewers read with `gh pr diff`,
`git -C <worktree>`, or `git show <sha>:<path>`. Before parallel
work, read [bounded delegation](bounded-delegation.md) in full for alternative-versus-
coverage aggregation, capacity, pilots, and failure recovery. For an authorized
external intake or automation adapter, also read [external handoffs](external-handoffs.md) in full.

Before choosing, check every delegation tool the harness provides, including
deferred and MCP-supplied tools. Submit that packet through the routing tool for
work it accepts. When the harness has no routing tool, or the routing tool cannot
honor a model or effort the user named, report that, then use a harness child
mechanism that honors them and shows the child to the user, else a nested child
with the packet and no prior transcript; do not fork the parent transcript. Direct work needs no worker. A separate harness task is
only for work that must outlive the parent or continue after it stops, or when
the harness offers no visible child. Close finished, errored, or idle children so each leaves the
working state. Never delete shared temporary directories by wildcard. Keep writers few, exclusive, and bounded; no unbounded children.
Do not copy worker transcripts into the coordinator.

Routing tool reports stay in its own state directory; link their identities.
Keep one canonical durable handoff on the owning Issue, linked from PR/consumers:
branch, workspace, exact base/HEAD, proof commands/results/links, review identity/
verdict, version, authority, dependencies, delivery, cleanup, finalization, blockers,
and next action. Update it instead of duplicating prose. For local work, report
relevant fields in the final response.

The coordinator independently verifies Git/GitHub state and reuses valid
exact-candidate proof under [verification](verification.md); transcripts and duplicate
checks are unnecessary. Before you relay a negative result or file anything from
it, read [bounded delegation](bounded-delegation.md) in full and apply its
negative-result gate. When you file or find an Issue for work the user wants
done, including found defects in user-controlled repositories whose fixes need
no user-owned decision, leave that turn with a real owner: a running worker you
started within your authority, or a named agent that has accepted the handoff, message sent
and acknowledged. "X will pick it up", with no handoff, is not an owner. Name
the owner in the report to the user. Start the next unblocked substantive
Issue with its own packet. Resume the same Issue when context remains useful; recover current state
from Git, GitHub, instructions, and handoff. Never recreate completed work or
request completed approvals again.

Tasks, threads, and worktrees are harness-neutral adapter choices. Do not create a
persistent orchestration service without later evidence and authority.

For long or uncertain work whose consequential choices would otherwise disappear,
keep a material-decision trail on the owning Issue next to the canonical
handoff. Record the decision, reason, evidence, and observed result at meaningful pivots. A routine
task needs no extra journal. The trail owns history, never current acceptance,
delivery state, or decisions that belong in an ADR. Keep private material local;
publish only sanitized evidence within authority. Correct or supersede earlier
claims explicitly instead of rewriting them into eventual success. Before
handoff, resolve material evidence pointers and include the trail in required
review when it supports the outcome.
