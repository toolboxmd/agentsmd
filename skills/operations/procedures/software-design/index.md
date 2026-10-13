---
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/architect
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Software design

Start after Project Direction and the applicable [elon-method](../elon-method/index.md) reasoning.
The global contract's Software design rules always apply here: design from the
start, write caller code first, and put each decision at its owner. Design the
surviving requirement around the experience it must enable. This procedure adds
the deeper work below. Its references expand those core rules; where their
wording differs, the core wins.

## Choose the design work

| Question | Read |
| --- | --- |
| Which structure or API should own the requirement? | [Compare designs](references/compare-designs.md) |
| Can state, types, boundaries, or ownership eliminate branches? | [Model state and boundaries](references/state-and-boundaries.md) |
| TypeScript semantic values, variants, schemas, or compiler escape hatches? | [TypeScript patterns](references/typescript.md) |
| Refactor, migrate callers, share mutable state, or make retries safe? | [Change existing systems](references/change-existing-systems.md) |

Use independent design proposals only for a consequential unresolved choice with
meaningfully different plausible answers. Apply `operations` coordination and
the installed model policy. Independent reasoning is useful even on the same
model; it is not evidence of model diversity. Do not create a panel for routine
implementation choices.

Derive a small implementation sketch from the caller examples: types, signatures,
state transitions, module ownership, and the critical interaction.

Finish with a chosen shape, alternatives rejected for concrete reasons, the
load-bearing assumptions, affected consumers, and proof that can falsify those
assumptions. Routine reversible choices are agent-owned. Route taste and costly,
hard-to-reverse decisions through the existing human gate. Record agreed project
terms or costly decisions through [domain-modeling](../domain-modeling/index.md), without creating another
architecture ledger. Continue authorized implementation through `operations`.
