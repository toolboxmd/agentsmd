---
name: grill-with-docs
description: Relentlessly sharpen a plan while recording resolved project terms and durable architectural decisions lazily.
disable-model-invocation: true
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/grill-with-docs
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

Load and follow both `grilling` and `domain-modeling`.

Use `grilling` to work the complete decision frontier. Use `domain-modeling`
alongside it to challenge project language, write resolved terms to the
appropriate `GLOSSARY.md`, and record an ADR only when its three-part threshold
is satisfied.

Create documents lazily. A discussion with no resolved project-specific term
does not create a glossary. A discussion with no costly, surprising,
hard-to-reverse trade-off does not create an ADR.
