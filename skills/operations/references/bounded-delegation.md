# Bounded delegation

## Declare how results combine

- **Alternatives:** independent candidates answer the same question. Compare
  against shared constraints, choose one coherent base, and incorporate useful
  details deliberately. Disagreement may reveal a real tradeoff. Inspect every
  candidate used in the decision; a judge's vote does not establish truth.
- **Coverage:** workers own disjoint required slices. Every slice needs accepted
  evidence or an explicit gap. A failed worker cannot disappear from the verdict.
- **Race:** state whether first adequate, all-ranked, or best-of is intended, and
  what adequate means. First arrival alone is not quality or completeness.

Synthesizing candidates creates a new artifact needing its own required proof.
Do not combine incompatible state owners or transfer a candidate's verdict to
the synthesis. Report optional candidate failures and required coverage failures
differently, while accounting for both honestly.

## Prove and size the workflow

Before multiplying a novel workflow, run one representative unit through brief,
implementation, proof, review, and the last authorized integration state. Learn
whether the packet, unit size, capabilities, and evidence survive the handoff.
The first ordinary unit is enough for a known repetitive workflow; do not add a
separate pilot without a question it can falsify. Missing merge authority limits
the pilot's tested boundary rather than granting permission.

Bound in-flight work by the coordinator's capacity to validate and integrate,
not the harness's maximum worker count. When children share one machine, also
bound concurrency by that machine's free memory and the agents already running
there, checking before each wave and shrinking after a resource kill. Use a
rolling window when independent work remains. Add a sub-coordinator only for
observed coordination load that the extra orientation and reporting actually
reduces. Reserve effort for proof, integration,
and durable recovery instead of spending it all on fresh dispatches.

Treat ordinary completion messages as pending evidence. Finish a brief, topology
change, conflict decision, or durable-state update before draining them. Validate
at safe boundaries and before reporting. User stops, revoked authority, unsafe
writes, and shared-state failures interrupt immediately. The harness's existing
message tools usually suffice; do not build a queue service by default.

A negative result says the work cannot be done: not possible, cannot remove,
blocked, no recipe, or failed. This gate covers any agent's own claim in
conversation or delegated work. An ordinary failed slice, one that does not say
the work cannot be done, is still recorded at once. Accept a negative result
only when it lists what was tried and which primary sources were checked: the
tool's own docs and bundled README, its `--help`, its environment variables,
and its config keys. Before reporting your own claim, relaying another agent's
result to the user, or filing anything from either, try the work once yourself
or assign one challenger whose only job is
to make the work succeed. Report only a
negative result that survives that attempt, and include the attempts.

Integrate reviewed components as they become ready under the one-final-approval-
PR contract. Preserve accepted outputs promptly in their authorized durable owner.
A disposable worker's confident transcript is not durable delivery evidence.

## Recover by failure mode

Observe progress through harness status, artifact changes, running checks, and task-
appropriate evidence. Silence alone does not prove a stall, especially during a
legitimate long check. Do not restart an idle worker merely to ask for status.

| Failure | Response |
| --- | --- |
| Scope/context exhaustion | Reduce or partition the unit and preserve useful evidence |
| Transient network/tool failure | Retry within a bounded policy after checking partial effects |
| Broken dependency or contract | Repair its owning layer before refilling affected consumers |
| Unknown termination | Inspect durable state and establish ownership before replacement |
| Late or stale result | Reconcile current base/head, ownership, dependencies, and proof |

Confirm a writer has stopped before reusing its resources. If stopping is
unconfirmed, isolate the replacement from every shared resource or keep that
action blocked. Propagate user stops to every affected worker and record any
unconfirmed stop. The routing tool owns model changes for work it accepted;
explicit user choices still apply.

An escalation names the decision needed, its evidence, the remedies tried, and a
recommendation. Answer with direction, an eligible alternative, or a Human Gate;
never with a silent takeover of the delegated work.

Salvage useful late findings through the current task; never merge a stale result
blindly. Account for each unit as accepted, failed, stopped, superseded, or
explicitly absorbed. Stopping a worker does not remove its acceptance criterion.
Recover from Git, GitHub, current instructions, and the canonical handoff. A
compact frontier can be derived from those owners; it must not become a second
task database or omit complete authority-bearing constraints.
