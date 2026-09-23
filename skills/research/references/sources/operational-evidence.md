# Operational metrics and error records

## Metrics, logs, and traces

Identify the owning service, environment, dependencies, release, and interval.
Inspect the actual dashboard or monitor query, units, aggregation, threshold,
and sampling. A graph's title can conceal a different population or statistic.
Aggregate first; inspect bounded raw samples only when needed to distinguish a
hypothesis. Keep payloads, credentials, and unrelated customer data out of notes.

Compare the relevant window with a justified baseline. Check neighboring releases,
traffic mix, instrumentation changes, retention, and clock alignment. A monitor
shows an operational concern; it does not alone explain why code was written.
Follow incident records and operator notes when they connect observation to action.

Read-only queries may still incur costs or access sensitive data. Preserve the
existing access, spending, and data boundaries. Prefer the smallest query that
can answer the question; do not run an expensive analysis merely because a tool
is available.

## Error tracking

Confirm organization, project, release, and environment before searching exact
exceptions, paths, symbols, and messages. Examine first and last seen, affected
population, sampling, release trajectory, and a representative event's stack and
breadcrumbs. Check whether grouping changed or the error moved elsewhere.

A resolved marker or disappearance does not prove a fix. A lower sample rate,
disabled feature, unrelated commit, or upstream change may explain it. An AI
diagnostic summary is a hypothesis; verify consequential claims against the
event and code. Do not invoke paid diagnostic products as an automatic extra.

Connect the observed failure to its Issue, incident, PR, and deployed revision.
Preserve symptom, proposed cause, mitigation, and tested prevention as separate
claims. If runtime artifacts need deeper interpretation, use `diagnosis` rather
than inventing a causal conclusion from a dashboard alone.
