---
name: software-design
description: >
  Design or reassess software architecture, APIs, domain state, boundaries, and
  migrations. Use for competing implementation shapes, growing special cases,
  shared-state problems, or a substantial refactor. Project terminology belongs
  to domain-modeling; small obvious edits stay direct.
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/architect
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Software design

Start after Project Direction and the applicable `elon-method` reasoning. Design
the surviving requirement around the experience it must enable. Ask what the
system would look like had this requirement existed from the beginning. A patch
to the current shape is one candidate, not the assumed answer.

Trace current callers, state owners, effects, and constraints before proposing a
boundary. Write representative caller code first: a common path, a failure, and
the awkward case. If every caller needs orchestration or defensive knowledge,
move that responsibility to its actual owner instead of documenting the burden.

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
state transitions, module ownership, and the critical interaction. If repeated
casts, workarounds, or deviations appear during implementation, revisit the
sketch's assumption before extending it with more exceptions.

Finish with a chosen shape, alternatives rejected for concrete reasons, the
load-bearing assumptions, affected consumers, and proof that can falsify those
assumptions. Routine reversible choices are agent-owned. Route taste and costly,
hard-to-reverse decisions through the existing human gate. Record agreed project
terms or costly decisions through `domain-modeling`, without creating another
architecture ledger. Continue authorized implementation through `operations`.
