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
not the host's maximum worker count. Use a rolling window when independent work
remains. Add a sub-coordinator only for observed coordination load that the extra
orientation and reporting actually reduces. Reserve effort for proof, integration,
and durable recovery instead of spending it all on fresh dispatches.

Treat ordinary completion messages as pending evidence. Finish a brief, topology
change, conflict decision, or durable-state update before draining them. Validate
at safe boundaries and before reporting. User stops, revoked authority, unsafe
writes, and shared-state failures interrupt immediately. The host's existing
message tools usually suffice; do not build a queue service by default.

Integrate reviewed components as they become ready under the one-final-approval-
PR contract. Preserve accepted outputs promptly in their authorized durable owner.
A disposable worker's confident transcript is not durable delivery evidence.

## Recover by failure mode

Observe progress through host status, artifact changes, running checks, and task-
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
unconfirmed stop. Follow installed routing and explicit user choices for any
justified model change.

Salvage useful late findings through the current task; never merge a stale result
blindly. Account for each unit as accepted, failed, stopped, superseded, or
explicitly absorbed. Stopping a worker does not remove its acceptance criterion.
Recover from Git, GitHub, current instructions, and the canonical handoff. A
compact frontier can be derived from those owners; it must not become a second
task database or omit complete authority-bearing constraints.

## Router-managed planner, dispatcher, and worker boundary

For Router-managed execution the direct-work default does not apply. The
planner clarifies outcomes, performs only the bounded inspection a decision
needs, writes specifications and handoffs, and reviews evidence. The dispatcher
owns execution and routine recovery: it assigns correction and recovery,
resumes the original objective, and preserves job and Observer task identities
where safe. Assigned agents own implementation, code debugging, test execution,
and mechanical recovery. A failure, timeout, or incomplete candidate never
implicitly authorizes the planner to implement, debug, or rerun the worker
loop.

Escalation carries the specific decision required, supporting evidence,
attempted remedies, and the dispatcher's recommendation. The planner supplies
direction or selects an eligible stronger agent or approach through the
dispatcher, then returns control. Authority and consequential scope decisions
still reach the appropriate human gate. The planner keeps the acceptance duty
described in verification: it assesses evidence and coordinates required
host-specific verification, never silently waiving proof.

Existing Observer lifecycle records may identify planner execution beyond the
assigned role. That observation is measurement, not a second monitoring
system, and instructions cannot mechanically prevent every out-of-band action.

Examples. A timed-out worker returns its partial candidate and timing evidence
to the dispatcher, which assigns bounded correction; the planner does not
rerun the worker commands. A broken runtime reaches the dispatcher with the
failure evidence, which recovers or reassigns the job; the planner does not
debug the runtime itself. Failed verification returns the candidate with the
failing evidence; the dispatcher first determines whether a coherent candidate
exists before requesting further proof, and required final checks stay. A
planner decision for a stronger eligible agent goes through the dispatcher,
which assigns that work under the routing policy. Planner specification
writing, such as a revised handoff or acceptance specification, is permitted
planning work. An explicit user instruction to perform an implementation step
stays authoritative when recorded with the task, and ordinary direct work
outside a Router-managed job is unaffected.
