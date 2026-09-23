# Runtime and trace forensics

## Preserve artifact identity

For supplied evidence, record format, producer, revision/build, source maps,
capture interval, workload, sampling, and environment. Keep the original artifact
immutable. Use an existing parser or query tool; convert to a queryable database
only when repeated analysis earns the cost. Preserve units and clock domains.

Start from the user-visible slow or broken interval. Locate its events and trace
causal relationships across threads, processes, tasks, or requests. Correlate by
actual identity when available. Similar timestamps alone can connect unrelated
work. Check gaps, dropped events, sampling, and instrumentation overhead before
interpreting apparent absence or a new hotspot.

## Interpret the evidence correctly

| Evidence | It can establish | It does not establish alone |
| --- | --- | --- |
| CPU samples | Where sampled CPU time accumulates | End-to-end latency or time waiting on another actor |
| Inclusive versus self time | Cost beneath a frame versus the frame's own work | Which caller makes that work necessary |
| Async spans | Recorded timing and relationships | Missing uninstrumented work or causal completeness |
| Heap retention path | Why an object remains reachable | Whether its lifetime violates a requirement |
| Repeated heap growth | Growth under the captured workload | A leak without expected lifetime and steady-state analysis |
| Paired captures | Differences under their recorded conditions | Causality without control of competing changes |

Resolve symbols against the matching build. Missing or mismatched symbols limit
source attribution; report unknown locations rather than inventing line numbers.
Inspect the owning implementation and dependency version before interpreting a
library frame. A hot utility can be downstream of excessive calls elsewhere.

For lifecycle failures, reconstruct creation, registration, observation,
cancellation, unsubscription, and teardown. Check whether stale callbacks or
retained subscriptions outlive their owner. A nil guard may hide that lifecycle
failure while leaking state or silently skipping required work.

## Observe running systems within authority

Reading supplied profiles is read-only. Evaluating injected code, adding probes,
hot-patching, restarting, and changing flags can mutate the system and alter the
behavior being measured. Use an authorized task-owned instance for interventions.
For a live protected target, keep observation within granted access or report
the exact intervention requiring authority.

Choose instrumentation that distinguishes the hypothesis and has bounded
overhead. Avoid logging secrets or complete customer payloads. Record what the
instrumentation changes. Retain useful sanitized artifacts, then remove temporary
probes unless ongoing observability belongs to the authorized outcome.

Conclude with an evidence chain: user-visible event, relevant runtime interval,
owning code path, supported mechanism, and the smallest experiment that could
disprove it. Use "consistent with" when confounders remain. A narrative linking
two screenshots is not a controlled causal test.
