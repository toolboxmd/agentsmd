---
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/domain-modeling
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Domain Modeling

Sharpen language during design: challenge terms, test relationships with concrete
scenarios, and record each agreed term. Reading an existing glossary alone is
orientation, not invocation.

## Ownership

Create files lazily. Most repositories use root `GLOSSARY.md` for their first
resolved project-specific term and `docs/adr/` for their first qualifying ADR.
Multiple distinct domains use root `GLOSSARY-MAP.md` as an index, with each domain's
own glossary and ADR directory. Root `docs/adr/` owns system-wide decisions;
domain directories own domain-specific decisions. No extra glossary is needed
in the map.

Legacy `CONTEXT.md`/`CONTEXT-MAP.md` are read-only fallbacks only when new names
are absent. Identify migration explicitly and write only new filenames.

## Resolve language

1. Read the relevant glossary. If the user's term conflicts, state both meanings
   and ask which is canonical. For vague or overloaded terms, propose one precise
   name and distinguish adjacent concepts.
2. Test realistic boundary/edge scenarios for relationships, ownership, and lifecycle.
   Cross-check code, tests, Issues, and decisions; surface contradictions instead
   of silently choosing a source.
3. Write agreed terms immediately using [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md).
   Keep only canonical project terms, short definitions, and avoided synonyms.
   Specs, plans, scratch notes, implementation, and decision logs have other owners.
4. Offer an ADR only when all three hold: meaningful reversal cost, surprising
   without context, and a real trade-off among alternatives with specific selection
   reasons. Otherwise skip it. For qualifying decisions, use [ADR-FORMAT.md](ADR-FORMAT.md).
