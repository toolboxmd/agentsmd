# AgentsMD Skill Catalogue

This is the authoritative human-readable inventory for Skills owned, adapted,
deferred, retired, or referenced by AgentsMD. The installable plugin exposes
only the Active entries.

## Source baselines

- **Matt pin**: [`mattpocock/skills`](https://github.com/mattpocock/skills) at
  `6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`, MIT. The historical installation
  lock is preserved in `provenance/mattpocock-skills.lock.json`.
- **use-grok pin**: [`toolboxmd/use-grok`](https://github.com/toolboxmd/use-grok)
  at `a8ae6ab3c862de836ca576276a221610e3fe274c`, Apache-2.0. Its imported Skill
  directory is byte-identical to that commit.
- **AgentsMD-native source**: versioned directly with this repository and its
  release commit.

Upstream refreshes are intentional pinned reviews. No refresh may overwrite an
AgentsMD adaptation automatically.

## Lifecycle

- **Active**: owned by AgentsMD and exposed through plugin discovery.
- **Deferred**: inactive until a recorded reconsideration trigger occurs.
- **Retired**: intentionally absent from discovery; history remains here and in
  Git.
- **Upstream reference**: not yet accepted as AgentsMD behavior and not
  packaged.

## Active package

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD adaptation |
| --- | --- | --- | --- | --- | --- |
| `algorithm` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Active | [MIT](LICENSE) | Runs the fixed five-step Algorithm for material work through an observable closed evidence loop while keeping direct microfixes direct. |
| `delivery-profile` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Active | [MIT](LICENSE) | Loads and validates Project-specific Delivery System commands, artifact build details, and website mapping without duplicating canonical truth. |
| `project-direction` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Active | [MIT](LICENSE) | Establishes and maintains confirmed Vision, Mission, and Objective with milestone-level scope; deterministic hooks reload the complete triad and expose locally known upstream currentness. |
| `version-control` | ToolboxMD / AgentsMD | AgentsMD-native; this release commit | Active | [MIT](LICENSE) | Canonical SemVer, mirror, changelog, commit, tag, and release contract. |
| `use-grok` | ToolboxMD / AgentsMD | ToolboxMD-native `toolboxmd/use-grok`, use-grok pin, `skills/use-grok` | Active | [Apache-2.0](LICENSES/use-grok-Apache-2.0.txt) | Bundled unchanged. Explicit user invocation and real Grok Build behavior remain intact. |
| `grilling` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/productivity/grilling` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Package ownership and provenance metadata only. Exhaustive frontier behavior is unchanged. |
| `grill-with-docs` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/grill-with-docs` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Uses `grilling` with lazy `GLOSSARY.md` and ADR writes through `domain-modeling`. |
| `domain-modeling` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/domain-modeling` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Owns `GLOSSARY.md` and `GLOSSARY-MAP.md`; legacy names are read-only migration fallbacks. ADR threshold is unchanged. |
| `prototype` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/prototype` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Automatically serves a claimed Wayfinder Prototype Decision Issue, preserves logic/UI branches, requires a runnable smoke check and human verdict, and keeps throwaway evidence off `main`. |
| `research` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/research` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Automatically serves a claimed Wayfinder Research Decision Issue, distinguishes facts from inference, captures cited findings, and supports independent background delegation. |
| `to-spec` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/to-spec` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | User-invoked entry to the complete Specify workflow through approved parent and verified ticket publication, with a Parent Spec only opt-out. |
| `to-tickets` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/to-tickets` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | User-invoked standalone ticket decomposition that publishes an approved native Issue graph, then reuses or requests implementation authority at the first unblocked Issue. |
| `wayfinder` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/engineering/wayfinder` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Preserves destination-first planning, Research/Prototype/Grilling/Task Decision Issue types with HITL/AFK ownership, readable linked decisions, explicit fog and scope boundaries, assignee claims, and the visible GitHub frontier before handing a clear route to `to-spec`. |
| `writing-for-agents` | ToolboxMD / AgentsMD | Matt Pocock, Matt pin, `skills/productivity/writing-for-agents` | Active | [MIT](LICENSES/mattpocock-skills-MIT.txt) | Package ownership and provenance metadata only. The instruction-writing method is unchanged. |

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
| `grill-me` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/productivity/grill-me` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | The active `grilling` Skill owns exhaustive decision discovery. |
| `wait-what` | ToolboxMD / AgentsMD classification | Matt Pocock, Matt pin, `skills/productivity/wait-what` | Retired | [MIT](LICENSES/mattpocock-skills-MIT.txt) | The compact Re-pitch behavior lives in `AGENTS.md`. |

## Upstream references

These Skills remain Matt Pocock-owned upstream behavior. AgentsMD records the
same Matt pin and MIT licence for each, makes no adaptation claim, and keeps
them outside active plugin discovery.

| Skill | Current owner | Origin and source identity | Lifecycle | Licence | AgentsMD adaptation |
| --- | --- | --- | --- | --- | --- |
| `code-review` | Matt Pocock | Matt pin, `skills/engineering/code-review` | Upstream reference | [MIT](LICENSES/mattpocock-skills-MIT.txt) | None; evaluate after representative use. |
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
