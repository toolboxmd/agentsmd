# Performance experiments

## Define a measurement that can answer the question

Choose the user-visible start and end, workload, correctness constraints, metric,
and target. Distinguish latency, throughput, tail behavior, resource use, and cost.
Moving work after a measured checkpoint can improve a number while making the
actual user outcome worse. Measure the point the user is waiting for.

For a reported regression, first confirm the baseline workload exhibits the
reported slowdown. If it does not, investigate the mismatch before optimizing a
different path. An optimization request without a reported defect starts by
establishing its representative baseline.

Record exact revisions, build mode, flags, data, hardware/runtime, warm-up, cache
state, and competing load. First prove the harness exercises the intended path.
Check sensitivity with realistic easier/harder inputs or a controlled known
change. An unexpectedly easy pass warrants inspection of both system and observer.

Freeze the method and acceptance conditions during comparisons. Retain raw
samples, commands, and the summary statistic. Repeat according to observed noise;
alternate or randomize baseline/candidate order when warming or drift can bias
results. A median does not establish a tail improvement or statistical certainty.
Compare like workloads. If the baseline lacks the feature, use justified absolute
budgets for the new work rather than a ratio between different operations.

## Choose a hypothesis family from the evidence

| Family | Useful when | Constraint to prove |
| --- | --- | --- |
| Eliminate | Work has no required observable effect | Removed work is unnecessary for all relevant consumers |
| Partition | Cost grows with the portion being processed | Partitions preserve ordering and cross-partition invariants |
| Cache | Equivalent work repeats | Stable key, bounded storage, invalidation, and stale-data semantics |
| Index | Repeated scans dominate | Index maintenance and consistency cost is justified |
| Batch | Fixed per-operation overhead dominates | Batching preserves latency, failure, and ordering needs |
| Defer | Work is unused or not yet needed | Delayed work is still available by its real deadline |
| Reschedule | Required work blocks an interaction | Total work and downstream latency remain acceptable |
| Hedge | Tail waits dominate and extra capacity exists | Duplicate effects are safe; cancellation and resource cost are bounded |

Do not cycle through this list mechanically. Trace evidence should nominate the
family. A cache is a new state model, not a free speedup. Hedging an irreversible
operation can duplicate its effect. Moving work onto a shared queue can shift
latency to other users.

## Run a bounded optimization loop

For each experiment, record mechanism, predicted effect, candidate identity,
method, before/after observations, correctness result, and keep/revert decision.
Change one interpretable factor at a time unless the design requires a coupled
unit. Preserve only changes whose claimed benefit survives relevant noise and
whose behavior remains correct. Revert only task-owned rejected edits.

An equivalent but simpler implementation can be accepted as simplification;
do not call it a speedup. A noisy result is inconclusive, not a win. If a harness
defect requires changing the method, invalidate the affected comparison and
re-establish a comparable baseline. Do not relax the target after seeing failure.

For sustained optimization, agree or infer a bounded effort consistent with the
request and retain a compact attempt record. Stop when the target and required
proof are met, useful in-scope hypotheses are exhausted, or a real authority or
resource limit intervenes. No minimum iteration quota is needed after success.
At a plateau, reassess the workload, metric, active constraint, and hypothesis
family instead of accumulating tiny tweaks.

Report the measured improvement under its actual conditions, remaining variance,
correctness coverage, and any shifted cost. Operations owns exact-candidate final
proof; local benchmark success does not establish production Live Verification.
