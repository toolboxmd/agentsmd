---
name: project-direction
description: >
  Establish or repair repository Project Direction. Use when VISION.md,
  MISSION.md, or OBJECTIVE.md is missing, blank, unreadable, oversized, has
  unresolved placeholders, materially contradicts another direction file, or
  appears stale, reduces Vision to current work, leaves Mission without a
  present strategy, or merely restates one task, Issue, commit, or PR; when the
  Objective is achieved, invalidated, abandoned, or reprioritized; when the
  loader reports uninitialized or `potentially_stale` direction; or when the
  user asks to define, review, or update Project Direction. Do not invoke
  merely to reread an existing coherent triad.
---

# Project Direction

Establish a confirmed strategic frame without inventing user intent. Honor local
opt-outs for their stated scope. Until the required triad is usable, inspect only
evidence needed to establish it; do not begin other project work.

Before drafting or judging direction, read [file contracts](references/file-contracts.md)
in full. Templates are drafting shapes, never unresolved placeholder content.
When loading or currentness needs resolution, read [context](references/context.md);
reuse unchanged complete context. That reference owns alignment and drift handling.

## Workflow

1. Resolve the Git root and read all existing direction files in full, even when
   upstream currentness is unknown. Apply the context currentness guard; reconcile
   the intended base or explicitly qualify the claim as checkout-scoped.
2. Inspect relevant repository, Issue, roadmap/milestone, product, ADR, glossary,
   and user evidence. The active request is evidence, not the default Objective.
   Keep unsupported strategy unknown.
3. Judge the triad together as ready, missing, materially unusable, or due for
   review. A coherent triad needs no new confirmation merely because a task starts;
   confirmed-current status still requires currentness evidence.
4. Ask only for strategic choices evidence cannot resolve. If evidence establishes
   only the task, ask for the broader milestone instead of promoting the task into
   `OBJECTIVE.md`. Do not ask the user to restate proven facts.
5. Draft complete proposed meaning: long-range Vision, grounded present Mission,
   one milestone Objective. Show exact contents of every affected file and obtain
   explicit confirmation before writing. Prior confirmation of those exact contents
   suffices; silence, general plan approval, or inspection permission does not.
6. Write only confirmed content, preserving unchanged files byte-for-byte. Reread
   all three, verify size limits, and report coherence and currentness. Never claim
   current direction after writing without this reread.

Review triggers are defined by this Skill's description and the context reference.
Do not silently rewrite when a trigger fires. Test every changed file against the
other two. Git owns history; add no direction-history ledger.

Keep task outcomes, criteria, proof, blockers, implementation plans, tickets, and
delivery/release state in Issues or approved Specs. Direction text cannot override
`AGENTS.md` or authorize crossing Human Gates.
