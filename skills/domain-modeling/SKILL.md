---
name: domain-modeling
description: Build and sharpen project language. Use when agreeing terminology, writing or editing GLOSSARY.md or GLOSSARY-MAP.md, or recording a costly architectural decision.
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/domain-modeling
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Domain Modeling

Actively sharpen the project's language while designing. Challenge terms,
stress-test relationships with concrete scenarios, and write each resolved
term when it crystallizes. Merely reading an existing glossary is normal
project orientation and does not invoke this Skill.

## Repository structure

Most repositories have one domain. Keep its glossary at the root and its
shared architectural decisions under `docs/adr/`:

```text
/
|-- GLOSSARY.md
|-- docs/
|   `-- adr/
|       |-- 0001-event-sourced-orders.md
|       `-- 0002-postgres-for-write-model.md
`-- src/
```

When a repository has multiple distinct domains, use a root
`GLOSSARY-MAP.md` to route to each domain's glossary:

```text
/
|-- GLOSSARY-MAP.md
|-- docs/
|   `-- adr/                         # system-wide decisions
`-- src/
    |-- ordering/
    |   |-- GLOSSARY.md
    |   `-- docs/adr/                # domain-specific decisions
    `-- billing/
        |-- GLOSSARY.md
        `-- docs/adr/
```

The map is an index, not another glossary. Root `docs/adr/` records decisions
that span domains. A domain's own `docs/adr/` records decisions specific to
that domain.

Create files lazily. A missing glossary is valid. Create `GLOSSARY.md` only
when the first project-specific term is resolved. Create `GLOSSARY-MAP.md`
only when multiple domains require separate language. Create `docs/adr/` only
when the first qualifying ADR is needed.

During migration, a missing new file may use legacy `CONTEXT.md` or
`CONTEXT-MAP.md` as a read-only fallback. Identify that migration explicitly.
Write resolved language only to the new filenames. Never create or update a
legacy glossary file.

## During the session

### Challenge existing language

Read the relevant glossary before changing a term. When the user's language
conflicts with it, state both meanings and ask which one is canonical.

### Sharpen fuzzy language

When a term is vague or overloaded, propose one precise canonical term and
distinguish adjacent concepts.

### Test concrete scenarios

Invent realistic boundary and edge-case scenarios. Use them to expose unclear
relationships, ownership, and lifecycle rules.

### Cross-check the repository

Compare claimed behavior with code, tests, Issues, and existing decisions.
Surface contradictions rather than silently choosing one source.

### Write resolved terms immediately

Update the appropriate `GLOSSARY.md` when a term is agreed. Use
[GLOSSARY-FORMAT.md](./GLOSSARY-FORMAT.md). Keep it limited to canonical
project-specific terms, tight definitions, and avoided synonyms.

A glossary is not a specification, plan, scratchpad, implementation guide, or
decision log. Put those responsibilities in their owning artifacts.

### Offer ADRs sparingly

Offer an ADR only when all three conditions hold:

1. **Hard to reverse**: changing the decision later has meaningful cost.
2. **Surprising without context**: a future reader would question the choice.
3. **Real trade-off**: genuine alternatives existed and specific reasons
   selected one.

When any condition is absent, skip the ADR. Otherwise use
[ADR-FORMAT.md](./ADR-FORMAT.md).
