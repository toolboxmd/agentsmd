# Compare designs

## Establish the actual problem

Describe the observable result, who needs it, and what would fail without it.
Separate product constraints from accidents of the present implementation.
Inspect the relevant execution path, callers, data lifetime, and failure history.
Check whether deletion or an existing primitive solves the requirement before
inventing a layer. Treat proposed storage, frameworks, services, and workers as
means that need a reason to exist.

Write the public usage before the internals. Include cancellation, partial
failure, and ownership when they shape the API. Compare what the caller must
know, not only line counts inside the implementation. A small function with a
large implicit protocol may cost more than a larger function hiding that protocol.

## Produce alternatives that disagree

When uncertainty merits comparison, develop two or three genuinely different
shapes: for example, explicit state versus derived state, immutable snapshots
versus shared mutation, or one owner versus distributed coordination. Renaming
the same abstraction is not a competing design. Include the simplest credible
candidate and the existing shape when it remains viable.

Give independent designers the same outcome, evidence, constraints, and proof
question. Do not seed every proposal with the lead's preferred answer. Ask each
to identify its strongest reason to lose. Keep proposed code small enough to
compare. The coordinator checks facts, resolves disagreements, and chooses;
counting votes does not establish correctness.

Compare candidates against concrete pressure:

| Pressure | Evidence to seek |
| --- | --- |
| Caller burden | Representative call sites, required sequencing, error handling |
| State complexity | Valid states, transitions, duplicated facts, synchronization |
| Change cost | Real consumers, migration path, external compatibility |
| Failure behavior | Partial completion, retries, cancellation, cleanup |
| Reader load | Layers between question and answer, hidden mutable context |
| Operational cost | Deployment units, ownership, observability, recovery |
| Experience | The result users see and the time until they see it |

Do not turn this table into an unweighted numerical score. A hard constraint
eliminates a candidate even when it wins several softer preferences.

## Probe the deciding assumption

Build a disposable experiment when reading cannot settle a load-bearing claim.
Use [Prototype](../../prototype/index.md) to select a script, type check, benchmark,
state simulator, or UI demo and capture the discriminating evidence. Its empirical
branch resolves technical questions without an artificial human verdict; its
human-facing branches preserve the decision owner.

Prefer one end-to-end slice over a skeleton that defers every difficult seam.
The first slice should expose the risky boundary, persist or transmit realistic
data when relevant, and produce an observation. Throw away experimental shells;
retain the evidence and validated decision.

## Review the chosen shape

Look for a special case that really names an unmodeled domain concept; parallel
arrays that should be records; booleans whose combinations are impossible;
wrappers that add no invariant; and defensive checks whose owner is unclear.
Ask whether the new requirement reveals a wrong foundational assumption.

If two attempted repairs fail through the same premise, stop optimizing the
repair. Choose an observation that distinguishes the premise from alternatives.
For a state or resource imbalance, enumerate its actors, who creates the imbalance,
and who merely observes it. Revisit the premise with that evidence. Do not
generalize a single symptom into a rewrite without this investigation.

Record only the rationale needed to preserve the decision: why this shape,
what it assumes, the strongest rejected option, and what evidence would reopen
it. Keep mutable implementation facts in code and current task records.
