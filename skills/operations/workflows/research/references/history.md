# History and causality

## Anchor before searching outward

Identify the code, symbol, constant, behavior, or decision in question. Collect
relevant revisions, dates, substantive changes, PRs, and linked records. This
anchor supplies shared search terms and a time window; it is not the answer.
Blame identifies the latest touch, which may be formatting or a move.

Select sources by the explanation they could distinguish:

| Evidence category | Read | Potential contribution |
| --- | --- | --- |
| Code and review history | [Code archaeology](sources/code-history.md) | Implementation-time rationale and accepted constraints |
| Tracker, design records, discussion | [Decision records](sources/decision-records.md) | Business need, alternatives, deliberation, deadlines |
| Metrics, logs, traces, errors | [Operational evidence](sources/operational-evidence.md) | Runtime conditions and concrete failure modes |
| Product data, experiments, warehouse lineage | [Analytics](sources/analytics.md) | Usage, thresholds, exposure, and measured outcomes |
| Incident/postmortem | Relevant references above | Connect symptom, cause, mitigation, prevention across sources |

Record selected, unnecessary, unsearched, and unavailable categories honestly.
Seven connected tools do not require seven queries or workers. A direct
contemporaneous record may settle a small question. Deleting defensive behavior
with unclear history may justify a wider incident search.

## Gather evidence before constructing a story

Search variants of the technical and business terms. Open full relevant records,
including replies and linked alternatives. Capture author, date, version, status,
exact location, and short quotes when wording matters. Preserve search queries
and failed searches that bound a material unknown. Respect available access and
topic scope; do not search unrelated private material to fill a gap.

Follow cross-source leads before synthesizing. If workers split the investigation,
route a discovered PR, incident, document, or thread to its source owner for one
bounded follow-up pass. An exhaustive initial fan-out can still miss the decisive
record found only through another source.

## Calibrate the conclusion

| Label | Meaning |
| --- | --- |
| Direct | An attributable record explicitly states the reason; report whose stated reason it is |
| Supported | Independent indirect evidence favors the explanation after relevant alternatives are checked |
| Inferred | Reasoning goes beyond what the record establishes; show the inference |
| Speculative | Plausible explanation with weak evidence or substantial alternatives |
| Unknown | The bounded investigation cannot answer the question |

A direct statement establishes stated intent, not that the intent was correct or
the change succeeded. Code shows mechanics. Tests encode behavior. Neither alone
proves historical motivation. A monitor threshold resembling a constant is a lead,
not a causal link. Several records copied from one incident remain one source.

For a causal claim, examine competing releases, instrumentation changes, exposure,
selection effects, and the counterfactual. A change preceding an improvement is
insufficient. Describe correlation or a supported mechanism when no controlled
evidence distinguishes the cause.

Resolve apparent conflicts by checking date, version, author role, accepted versus
draft status, and scope. Business and technical explanations can coexist. Keep
genuine disagreement visible, with the next evidence that could resolve it.
Git owns repository state; it does not make every commit message a more reliable
account of intent than a contemporaneous approved decision.

## Turn history into useful constraints

For a proposed change, conclude with the applicable constraints:

- **Preserve:** behavior or invariant still supported by evidence.
- **Change:** historical conditions that no longer hold, with current proof.
- **Avoid:** known failed approaches and why they failed.
- **Risk:** unresolved history or assumptions that need a check before deletion.

Attach these to the existing task or research note. Do not create another active
tracker. A failed search establishes only what that search did not find. State
retention, access, and scope limits instead of claiming no reason ever existed.
