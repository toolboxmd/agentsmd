---
name: writing-for-agents
description: Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md.
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/productivity/writing-for-agents
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Writing for agents

Write for the decisions an agent must make: select the right path, perform it,
and recognize completion. Keep reasoning and examples that prevent a plausible
wrong interpretation. Word count alone cannot prove better behavior.
Before choosing frontmatter or invocation, read [SKILL-MECHANICS.md](SKILL-MECHANICS.md).

## Behavior and order

Identify the reader, loading moment, and decision or action the document changes.
Separate required steps from reference material. Order dependencies correctly;
keep conditions, definitions, and exceptions beside their rules.

Use direct verbs, familiar words, and exact technical terms. Replace vague advice
such as "be thorough" with an action. Keep explicit prohibitions where boundaries
matter, with an allowed path when needed: "Preserve dirty files; use a separate
worktree."

## Ownership and discoverability

Give each rule one authoritative owner. A context pointer must name its purpose
and distinct loading triggers: "Before publishing a release, read delivery.md"
works; "See delivery.md" does not. Collapse synonymous triggers, not distinct
cases. Sharpen missed triggers before copying procedures into callers.

Choose placement by reader and timing. Always-loaded prose costs every task;
on-demand references need discoverable triggers; human-only discovery requires
the user to remember routing. Keep shared constraints in the entrypoint, short
explanations beside rules, and substantial branch-specific detail behind a
conditional link. A deployment entrypoint may own target and authorization
selection while linking platform procedures. Do not split every step into a file.

## Completion and examples

Make completion observable: an API migration must identify affected callers and
their compatibility needs. Require exhaustive coverage only when omission defeats
the outcome; a wording fix need not review every document. Distinguish intermediate
feedback from final acceptance.

If agents rush past a step, clarify its completion condition first. Isolate stages
only when observed failures justify it. Splitting files does not erase later
instructions already in context; a fresh worker has real coordination cost.

Use established terms precisely: "red test" means a failing test demonstrating
the bug; "tight" cannot replace explicit speed, determinism, and cost requirements.
Define unfamiliar terms once. Retain examples that distinguish interpretations or
teach difficult boundaries; remove examples that merely restate a rule.

## Prune

Delete duplicate rules, stale instructions, irrelevant branches, and explanations
that change no decision. Read discoverable facts from code/configuration; document
hidden conventions and costly context. Apparently obvious advice may prevent an
observed failure, so do not assume redundancy. Preserve triggers, order, authority,
exceptions, and completion conditions. Restore explanation when shortening permits
a wrong path. Tests can check links and declared contracts; behavioral claims
require observed use.
