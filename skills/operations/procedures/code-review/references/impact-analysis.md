# Impact analysis

Find the assumptions on which the change's safety depends. Start with direct
consumers, then cross text-search boundaries: serialized shapes, persisted fields,
other languages, dynamic dispatch, configuration, scheduled callbacks, feature
flags, and independently deployed users. An empty grep result cannot exclude
dynamic or external consumers.

For each material risk, record the invariant, affected actors, reachable failure
path, and evidence needed to confirm or clear it. Several independent facts may
be necessary. Rank by consequence and concrete triggering conditions rather
than unsupported numeric probabilities.

Read the actual dependency version and local patches. A remembered API contract
or current upstream documentation may differ from the installed implementation.
When a safety claim relies on obscure semantics, exercise the exact function or
dependency in an isolated check if practical.

For example, suppose eviction is safe only if it removes expired entries without
notifying live subscribers. Call the pinned implementation with a subscribed live
entry and an expired entry. Observe both retained data and notifications. A source
walk supports a mechanism; the execution adds evidence about the actual contract.
Neither alone proves all unrelated integration behavior.

Report confirmed risks, cleared paths, and unproven assumptions separately. Bind
the analysis to the candidate and dependency identities inspected. Use the map
to choose relevant checks and reviewer attention. It is not a trusted affected-test
policy and cannot authorize proof reuse or replace complete coverage. `operations`
and the project's explicit scoped-proof contract own those decisions.
