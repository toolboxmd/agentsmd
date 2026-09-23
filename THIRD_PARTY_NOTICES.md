# Third-Party Notices

AgentsMD contains original ToolboxMD material under the repository
[MIT licence](LICENSE) and the following separately licensed Skill material.

## Matt Pocock Skills

The adapted `grilling`, `grill-with-docs`, `domain-modeling`, `prototype`,
`research`, `to-spec`, `to-tickets`, `wayfinder`, and `writing-for-agents`
directories derive from `mattpocock/skills` commit
`6654f6b60cd9d5be8b54c6fafe44346dabeb3b76`.

Copyright and permission terms are preserved in
[LICENSES/mattpocock-skills-MIT.txt](LICENSES/mattpocock-skills-MIT.txt).
Modified Skill files identify ToolboxMD ownership, the upstream origin, and the
source revision in their frontmatter. Their behavioral changes are summarized
in [SKILL_CATALOGUE.md](SKILL_CATALOGUE.md).

## ToolboxMD use-grok

The bundled `use-grok` Skill comes from `toolboxmd/use-grok` commit
`a8ae6ab3c862de836ca576276a221610e3fe274c` under Apache-2.0.

Copyright and licence terms are preserved in
[LICENSES/use-grok-Apache-2.0.txt](LICENSES/use-grok-Apache-2.0.txt). The
imported Skill directory is unmodified from that source revision.

## Lauren Tan's pstack

The `software-design`, `diagnosis`, `code-review`, `project-verification`,
`reflection`, and `technical-writing` Skills derive from pstack 0.15.3 in
`cursor/plugins` commit `b42effe0aa50f59c693d7e2924714e015e00bf7c`.
Its MIT notice, Copyright (c) 2026 Lauren Tan, is preserved verbatim in
[LICENSES/pstack-MIT.txt](LICENSES/pstack-MIT.txt).

pstack also contributes methods to `research`, `prototype`, `operations`,
`elon-method`, ticket proof, and agent-writing guidance. Matt-derived material
retains its separate lineage. The complete source inventory, hashes, and
source-to-destination decisions are in [provenance/pstack.lock.json](provenance/pstack.lock.json).
[The distillation](docs/research/2026-09-23-pstack-integration.md) explains local
adaptations, corrected assumptions, and excluded vendor runtime code. No pstack
runtime or external automation pack is bundled.
