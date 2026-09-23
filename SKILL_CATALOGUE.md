# AgentsMD Skill Catalogue

This is the authoritative human-readable inventory for Skills owned, adapted,
deferred, retired, or referenced by AgentsMD. The installable plugin exposes
only `operations`. Retained procedures live beneath it and load on demand.

## Source baselines

- **Matt pin**: [`mattpocock/skills`](https://github.com/mattpocock/skills) at
  `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`, MIT. The historical installation
  lock is preserved in `provenance/mattpocock-skills.lock.json`.
- **use-grok pin**: [`toolboxmd/use-grok`](https://github.com/toolboxmd/use-grok)
  at `a8ae6ab3c862de836ca576276a221610e3fe274c`, Apache-2.0. Its procedure retains the CLI and explicit-request contract. AgentsMD relocates
  the body and adjusts invocation/path guidance; it is no longer byte-identical.
- **AgentsMD-native source**: versioned directly with this repository and its
  release commit.
- **pstack pin**: Lauren Tan's [`cursor/plugins/pstack`](https://github.com/cursor/plugins/tree/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack)
  at `b42effe0aa50f59c693d7e2924714e015e00bf7c`, version 0.15.3, MIT.
  [The lock](provenance/pstack.lock.json) inventories every source file and maps
  all 50 skills and 23 playbooks to their adaptation destinations.
  [The full distillation](docs/work/119-pstack-integration/analysis.md) records
  the reasoning, corrections, consolidation, and deferred runtime ideas.

Upstream refreshes are intentional pinned reviews. No refresh may overwrite an
AgentsMD adaptation automatically.

## Lifecycle

- **Active**: owned by AgentsMD and exposed through plugin discovery.
- **Procedure**: retained behavior loaded through Operations, without a discovery entry.
- **Deferred**: inactive until a recorded reconsideration trigger occurs.
- **Retired**: intentionally absent from discovery; history remains here and in
  Git.
- **Upstream reference**: not yet accepted as AgentsMD behavior and not
  packaged.

## Invocation policy

`operations` is the sole Active, model-invocable Skill and allows implicit invocation. Every
Procedure below is an ordinary linked reference, selected automatically for the
current task or phase. Human decision and approval gates stay inside their
owning procedures. Selection grants no new authority. Old explicit skill names
can be used in natural requests, but only Operations remains a host command.

## Active entry and retained procedures

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD adaptation |
| --- | --- | --- | --- | --- | --- |
| `elon-method` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Procedure | [MIT](LICENSE) | Routes material work through first principles, cost investigation, evidence-based current-constraint selection and reassessment, and the ordered Algorithm. |
| `algorithm` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Retired | [MIT](LICENSE) | The five-step Algorithm remains in `elon-method`; its duplicate discovery/compatibility wrapper is removed. |
| `delivery-profile` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Procedure | [MIT](LICENSE) | Loads and validates Project-specific Delivery System commands, artifact build details, and website mapping without duplicating canonical truth. |
| `operations` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Active | [MIT](LICENSE) | The single automatic task/phase selector; loads only applicable engineering, planning and operating procedures. |
| `project-direction` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Procedure | [MIT](LICENSE) | Establishes and maintains confirmed Vision, Mission, and Objective with milestone-level scope; deterministic hooks reload the complete triad and expose locally known upstream currentness. |
| `version-control` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Procedure | [MIT](LICENSE) | Canonical SemVer, mirror, changelog, commit, tag, and release contract. |
| `use-grok` | ToolboxMD / AgentsMD | ToolboxMD-native `toolboxmd/use-grok`, use-grok pin, `skills/use-grok` | Procedure | [Apache-2.0](LICENSES/use-grok-Apache-2.0.txt) | Relocated as an ordinary procedure; invocation and relative-path guidance adapted. Explicit user invocation and real Grok Build behavior remain intact. |
| `grilling` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/productivity/grilling` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Package ownership and provenance metadata only. Exhaustive frontier behavior is unchanged. |
| `grill-with-docs` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/grill-with-docs` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Uses `grilling` with lazy `GLOSSARY.md` and ADR writes through `domain-modeling`. |
| `domain-modeling` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/domain-modeling` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Owns `GLOSSARY.md` and `GLOSSARY-MAP.md`; legacy names are read-only migration fallbacks. ADR threshold is unchanged. |
| `prototype` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/prototype`; pstack pin, prototype playbook | Procedure | [Matt MIT](LICENSES/mattpocock-skills-MIT.txt), [pstack MIT](LICENSES/pstack-MIT.txt) | Preserves human-facing logic/UI branches and owning verdict gates; adds empirical scripts/native harnesses for technical questions and keeps throwaway evidence off `main`. |
| `research` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/research`; pstack pin, `how`, `why`, `recall`, `teach` | Procedure | [Matt MIT](LICENSES/mattpocock-skills-MIT.txt), [pstack MIT](LICENSES/pstack-MIT.txt) | Unifies mechanics, historical rationale, scoped recall, and explanation with source-sensitive evidence, causal limits, and cited Issue resolutions. Direct read-only questions need no publication. |
| `to-spec` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/to-spec` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Operations-selected procedure for the complete Specify workflow through approved parent and verified ticket publication, with a Parent Spec only opt-out. |
| `to-tickets` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/to-tickets` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Operations-selected ticket decomposition that publishes an approved native Issue graph, then reuses or requests implementation authority at the first unblocked Issue. |
| `wayfinder` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/wayfinder` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Preserves destination-first planning, Research/Prototype/Grilling/Task Decision Issue types with HITL/AFK ownership, readable linked decisions, explicit fog and scope boundaries, assignee claims, and the visible GitHub frontier before handing a clear route to `to-spec`. |
| `writing-for-agents` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/productivity/writing-for-agents` | Procedure | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Explains triggers, information placement, completion, examples, and pruning; scopes exhaustive coverage and context splitting to demonstrated needs. |
| `software-design` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, `architect`, type and design principles | Procedure | [MIT](LICENSES/pstack-MIT.txt) | Caller-first sketches, compared structures, state and boundaries, corrected TypeScript patterns, safe migration, concurrency, and retry design. |
| `diagnosis` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, bug/performance/forensics playbooks and Benny | Procedure | [MIT](LICENSES/pstack-MIT.txt) | Discriminating reproduction, causal hypotheses, existing-fix verification, runtime/trace analysis, and bounded performance experiments. |
| `code-review` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, `interrogate`, `blast-radius`, corrected `no-comments` | Procedure | [MIT](LICENSES/pstack-MIT.txt) | Evidence-based independent review, reachable impact analysis, finding adjudication, and preservation of useful constraints. |
| `project-verification` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, `create-verification-skill`, `maintain-verification-skill`, Benny | Procedure | [MIT](LICENSES/pstack-MIT.txt) | One create/maintain owner for project-local launch, identity, driving, observation, feature recipes, evidence, and safe teardown. |
| `reflection` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, `reflect`, `automate-me`, structural-learning principle | Procedure | [MIT](LICENSES/pstack-MIT.txt) | Diagnose missing guidance, missed triggers, execution, and mechanism gaps; place authorized lessons with their real owner and keep preferences private. |
| `technical-writing` | ToolboxMD / AgentsMD | Lauren Tan, pstack pin, `technical-writing`, `unslop` | Procedure | [MIT](LICENSES/pstack-MIT.txt) | Reader-directed tutorials, how-to, reference, explanation, and shared prose guidance preserving meaning and uncertainty. |

The pstack lock also records adapted contributions to native `operations` and
`elon-method`, and to Matt-derived ticket proof and agent-writing guidance.
Twenty-three principle wrappers become concrete methods at these owners.
Arena/swarm become bounded delegation modes; how/why/recall/teach become research
modes. All separate entrypoints are consolidated under Operations. Useful procedures remain;
`algorithm` is an alias in the router, not a duplicate body. Vendor setup, the Benny pack,
and orchestration runtimes remain unbundled, with their useful mechanisms retained
and reconsideration boundaries documented in the distillation.

## Deferred

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD decision |
| --- | --- | --- | --- | --- | --- |
| `triage` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/engineering/triage` | Deferred | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Revisit after recurring genuine external Issues or the first genuine external contributor PR. Tracked by [Issue #14](https://github.com/toolboxmd/agentsmd/issues/14). |

## Retired

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD decision |
| --- | --- | --- | --- | --- | --- |
| `ask-matt` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/engineering/ask-matt` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | No separate wrapper is needed in the owned workflow. |
| `setup-matt-pocock-skills` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/engineering/setup-matt-pocock-skills` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | AgentsMD fixes GitHub Issues and glossary behavior directly. |
| `teach` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/productivity/teach` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Its broad knowledge-document role is outside the active glossary contract. |
| `grill-me` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/productivity/grill-me` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | The retained `grilling` procedure owns exhaustive decision discovery. |
| `wait-what` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/productivity/wait-what` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | The compact Re-pitch behavior lives in `AGENTS.md`. |

## Upstream references

These Skills remain Matt Pocock-owned upstream behavior. AgentsMD records the
same Matt pin and MIT licence for each, makes no adaptation claim, and keeps
them outside active plugin discovery.

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD adaptation |
| --- | --- | --- | --- | --- | --- |
| Matt `code-review` | Matt Pocock | Matt pin, `skills/engineering/code-review` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | This Matt source remains unadapted; the retained procedure of that name derives from pstack. |
| `codebase-design` | Matt Pocock | Matt pin, `skills/engineering/codebase-design` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `diagnosing-bugs` | Matt Pocock | Matt pin, `skills/engineering/diagnosing-bugs` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `implement` | Matt Pocock | Matt pin, `skills/engineering/implement` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; AgentsMD repository delivery remains separate. |
| `improve-codebase-architecture` | Matt Pocock | Matt pin, `skills/engineering/improve-codebase-architecture` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `resolving-merge-conflicts` | Matt Pocock | Matt pin, `skills/engineering/resolving-merge-conflicts` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `tdd` | Matt Pocock | Matt pin, `skills/engineering/tdd` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `wizard` | Matt Pocock | Matt pin, `skills/engineering/wizard` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `handoff` | Matt Pocock | Matt pin, `skills/productivity/handoff` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
| `to-questionnaire` | Matt Pocock | Matt pin, `skills/productivity/to-questionnaire` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |

## Registry boundaries

- [`toolbox.md`](https://github.com/toolboxmd/toolbox.md) is the Product
  Registry and Discovery Portal for the complete ToolboxMD portfolio.
- [`toolboxmd/marketplace`](https://github.com/toolboxmd/marketplace) is the
  Plugin Registry and distribution channel.
- This catalogue owns only the AgentsMD Skill inventory.

Karpathy Wiki, ContextMD, Building Agent Skills, GitPix, OpenBot, and other
independent ToolboxMD products keep their own product and release lifecycles.
They are not AgentsMD leaf Skills.
