# Analytics and warehouse evidence

Discover actual tables, columns, definitions, access, and query cost. Prefer the
project's established typed and deduplicated models when their lineage fits the
question. Never copy a source author's company table names as universal schema.
Read-only SQL still requires appropriate data and spending authority.

Record the exact query, table/model revision when available, time window,
population, units, aggregation, and result. Start with bounded aggregates and
distributions, not complete user-level exports. Inspect lineage, refresh lag,
historical schema, missing data, sampling, and deduplication before interpreting
a trend. New instrumentation can imitate adoption or a sudden reliability change.

For experiments, distinguish eligible users, exposed users, assigned variants,
and actual usage. Compare like populations and periods. A threshold change may
need a distribution and tail behavior, not only an average. Examine whether
selection, seasonality, another release, or a changed denominator explains the
effect. Observational alignment supports a hypothesis; it is not automatic
causal proof.

Use existing statement/job IDs to poll a submitted query instead of accidentally
launching duplicates. SQL access does not imply notebook access or permission to
modify dashboards. Return compact results and reproducible queries without
leaking sensitive rows. If access or retention prevents the decisive comparison,
name that gap and the weaker claim the available evidence can support.
