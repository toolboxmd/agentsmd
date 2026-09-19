# AgentsMD instruction reduction, Issues #101–103

This audit records the portable setup and instruction reduction outcome. Active
requirements remain in `AGENTS.md` and their linked Skills and references.
The change advances the Objective through clearer workflow routing and one-time
setup of shared instructions with private user defaults.

## What changed

- One ticket-decomposition procedure serves both `to-spec` and `to-tickets`.
  Both entrypoints retain their invocation, approval and continuation contracts.
- Prototype, direction, language, writing and operations guidance loses repeated
  explanations while retaining decision-critical conditions and examples.
- Four native harness paths resolve to one stable instruction source. Private
  `PREFERENCES.md` stays beside it, outside Git and release archives. Setup copies
  the tracked example only when the private file is absent.
- Personal host names and a named product review exception become generic trust
  and generated-change eligibility rules. The README gives one setup walkthrough.

## Measurement

Baseline: `bceb00a6d4a95f612cac4d6c7477beb45136f5b9`, 21,466 whitespace-separated
words across `AGENTS.md` and 42 bundled Skill Markdown files. Candidate counts
include the extracted shared ticket procedure. The expanded total also charges
`PREFERENCES.example.md` and every added README, OpenCode-guide and glossary line;
removed preexisting text outside the baseline corpus earns no deletion credit.

| Scope | Words | Reduction from baseline |
| --- | ---: | ---: |
| Original corpus plus extracted ticket procedure | 16,428 | 23.47% |
| Above plus private-preference example | 16,528 | 23.00% |
| Above plus conservatively charged setup/glossary guidance | 18,415 | 14.21% |

The roughly 50% aim was not reached. Communication, pinned Grok instructions,
Project Direction, authority, ownership, proof and detailed recovery conditions
were preserved. Source size establishes neither runtime-token savings nor better
command following.

Reproduce the complete per-file word/hash inventory from this commit:

```sh
python3 docs/reviews/count-101.py . --candidate HEAD
```

This report and its counting script are audit evidence. They introduce no new
operating requirements and are outside the instruction count.

## Rule ownership

| Retained contract | Owner |
| --- | --- |
| Communication, partnership, judgment, authority, user work and private defaults | `AGENTS.md` |
| Direction loading, freshness and semantic file requirements | `project-direction` and its triggered references |
| Workspace, dependencies, workers, proof, delivery and cleanup | The applicable `operations` reference |
| Parent specification | `to-spec` |
| Ticket slicing, approval, native relationships and continuation | `to-tickets/references/ticket-decomposition.md`, loaded by both entrypoints |
| Prototype decisions and artifacts | `prototype` and the selected logic or UI reference |
| Decision mapping, project language and writing | `wayfinder`, `domain-modeling`, `writing-for-agents` |
| Ordered design reasoning and version mechanics | `elon-method`, `version-control` |

## Review and proof

Claude Opus 5 (`claude-opus-5`) at explicit high effort reviewed the complete
original-to-candidate instructions and deletions at `a12f193183333fa5a283ef8508cbcd451dbc81d7`.
It requested changes, then approved `7ee0be55108103690b0b15203e68827b3f2a9ec9`
after inspecting the corrections and additional consolidation. A separate Codex
reviewer using Astra medium also approved that corrected checkpoint.

The corrected checkpoint passed 235 repository tests and 6 versionctl tests:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m unittest discover -s tools/versionctl/tests -p 'test_*.py'
```

These are pre-version reviews. The final versioned candidate receives follow-up
review and complete proof before the final approval PR is marked ready.

The first independent reviews caught lost qualifiers in the prose-only review
exception, exact workspace ownership and availability, explicit direction
opt-outs, prototype layout separation, and preference precedence. The corrections
restore or clarify existing boundaries. Review also identified further duplicate
passages whose owning procedures remain explicitly reachable.

The complete suites cover deterministic contracts, installer/loader behavior and
packaging. Communication, confirmed direction and the pinned Grok subtree remain
byte-identical. The final versioned-candidate review, commands, SHA, archive digest
and delivery state are recorded in the [canonical Issue handoff](https://github.com/toolboxmd/agentsmd/issues/103#issuecomment-5731326542).

## Remaining limits

Native discovery was inspected where installed harnesses exposed deterministic
surfaces. Complete Claude/OpenCode native loading, Grok compatibility duplicate
suppression, non-Codex hook parity and user behavioral Live Verification remain
unproved. Manual reading and discovery checks are documented in the README.
The separate Model Router dependency had no published release at inspection.

Website impact is narrative: setup and capability documentation changed. The
public route is unchanged; no URL migration is introduced. Website updates,
release, live installation and behavioral verification retain their own authority
and evidence requirements.
