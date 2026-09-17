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

Write instructions that help an agent choose and complete the right work.
Keep explanations and examples when they teach a decision the agent would
otherwise miss. Concision removes redundancy, not the reasoning needed to act.

For skill frontmatter and invocation, read [SKILL-MECHANICS.md](SKILL-MECHANICS.md).

## Start with the behavior

Identify who reads the document, when they read it, and what decision or action
it should change. Separate required steps from reference material. Order steps
by their real dependencies; keep definitions, conditions, and exceptions beside
the rule they qualify.

Use direct verbs, familiar words, and exact technical terms. State the desired
action rather than relying on broad advice such as "be thorough." Keep explicit
prohibitions when a boundary matters, and explain the allowed path when unclear.
For example, "Preserve dirty files; use a separate worktree" gives both the
boundary and the next action.

## Make references discoverable

A context pointer names material outside the current document and says when to
read it. Skill descriptions and links in AGENTS.md both serve this purpose.
A useful reference behind a vague trigger may never be read.

State the purpose and distinct triggering conditions. For example, "Before
publishing a release, read delivery.md" is actionable; "See delivery.md" is not.
Collapse synonymous triggers, but keep different cases that need the reference.
If agents miss a reference, sharpen its trigger before copying its contents into
the calling document.

## Put detail where it is needed

Always-loaded instructions spend context on every task. On-demand references
spend context when selected, but need clear pointers. Human-only discovery also
costs attention: the user must remember what exists and when to invoke it.
Choose placement from who needs the guidance and when, not just document length.

- Keep shared steps and constraints in the entrypoint.
- Keep short supporting explanations beside their rules.
- Move substantial branch-specific detail behind a conditional reference.
- Keep each rule in one authoritative place so a change does not leave competing
  versions. A short reminder can link to the owner without repeating its procedure.

For example, a deployment skill can keep target selection and authorization in
its entrypoint while linking separate platform procedures. Splitting each step
into another file adds lookups without reducing the material every run needs.
Long documents can benefit from splitting even when every line is useful, but
the split should follow actual reading paths.

## Define completion and coverage

A completion criterion tells the agent when to move on. Replace vague milestones
such as "understand the migration" with observable evidence: "identify affected
callers and the compatibility behavior each requires."

Choose coverage from the task. An API migration may require every caller to be
accounted for; a wording fix does not require reviewing every document. An
exhaustive criterion is useful only when an omission would defeat the outcome.
Keep intermediate feedback distinct from final acceptance.

When an agent rushes past a step, first clarify its completion condition. Split
sequences only when observed failures justify isolating a stage. A separate file
does not erase later instructions already in context; a fresh worker introduces
real coordination cost. Do not add a handoff merely to make the document shorter.

## Use terms and examples precisely

A familiar term can compress a shared concept: "red test" names a failing test
that demonstrates the bug. Use it when that meaning is established. A vague word
such as "tight" does not preserve explicit requirements for speed, determinism,
and cost. Define unfamiliar terms once and use them consistently.

Keep examples that distinguish plausible interpretations or show a difficult
boundary. Remove examples that only repeat the rule. Prefer one discriminating
example over a catalogue of speculative cases.

## Prune without losing guidance

Review the decisions the document must support before cutting text:

- Delete duplicate rules, stale instructions, irrelevant branches, and explanation
  that changes no decision.
- Read discoverable facts from code or configuration. Document hidden conventions,
  expensive-to-recover context, and reasons a future agent would otherwise miss.
- Check whether apparently obvious advice prevents an observed failure. Do not
  assume an instruction is redundant merely because the model should know it.
- Preserve triggers, ordering, authority, exceptions, and completion conditions.
  Restore explanation when the shortened version permits a wrong interpretation.

Judge the result by whether an agent can still select the right path, perform it,
and recognize completion. Word count alone cannot establish that. Existing tests
can check links and declared contracts; behavioral claims need observed use.
