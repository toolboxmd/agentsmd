---
name: project-direction
description: >
  Establish or repair repository Project Direction. Use when VISION.md,
  MISSION.md, or OBJECTIVE.md is missing, blank, unreadable, oversized, has
  unresolved placeholders, materially contradicts another direction file, or
  appears stale, reduces Vision to current work, leaves Mission without a
  present strategy, or merely restates one task, Issue, commit, or PR; when the
  Objective is achieved, invalidated, abandoned, or reprioritized; when the
  loader reports uninitialized direction; or when the user asks to define,
  review, or update Project Direction. Do not invoke merely to reread an
  existing coherent triad.
---

# Project Direction

Establish one confirmed strategic frame without inventing the user's intent.
Until the triad is usable, inspect only the evidence needed to establish it and
do not begin other project work.

## Load the contracts

Read [file-contracts.md](references/file-contracts.md) in full before drafting
or judging a direction file. Use the bundled templates as drafting shapes, not
as files to copy with placeholders intact.

## Workflow

1. Resolve the Git root. Read all existing root `VISION.md`, `MISSION.md`, and
   `OBJECTIVE.md` files in full. Also read the relevant repository, Issue,
   roadmap or milestone, product, ADR, glossary, and user evidence. Treat the
   active request as evidence, not as the default Objective candidate. Keep
   unsupported strategic claims unknown.
2. Evaluate the triad as one coherent unit. Classify it as ready, missing,
   materially unusable, or due for review. An Objective is one current
   milestone-level outcome, narrower than the Mission but broader than an
   individual request, task, Issue, commit, or PR. A coherent existing triad is
   current project truth. Do not require repeated confirmation merely because a
   new task started.
3. Identify only the strategic choices that evidence cannot resolve. Ask only
   for unresolved strategic decisions. When evidence supports only the active
   task and cannot establish the broader milestone, ask for that strategic
   choice instead of promoting the task into `OBJECTIVE.md`. Do not ask the user
   to restate facts the repository already proves.
4. Draft the complete proposed meaning before editing. Preserve the distinction
   between a grand and visionary long-range destination, a strategic present
   purpose grounded in what the project does now, and one current milestone-level
   outcome. Review the triad as a coherent unit, but modify only the files whose
   meaning changed.
5. Show the exact proposed contents of every affected file. Obtain explicit user
   confirmation before writing. A prior confirmation of those exact contents is
   sufficient. Silence, approval of a general plan, and permission to inspect
   are not confirmation of strategic direction.
6. Write only confirmed contents. Never leave unresolved template placeholders.
   Then reread all three files in full, verify the size contract, and state
   whether the resulting triad is coherent and current.

## Review triggers

Review, without silently rewriting, when evidence suggests that:

- two direction files materially conflict;
- project behavior or decisions make a file stale;
- the Vision collapses into current work or the Mission lacks a present
  strategic approach;
- the Objective merely restates one request, task, Issue, commit, or PR;
- the Objective was achieved, invalidated, abandoned, or consciously
  reprioritized;
- the user explicitly asks for a direction review or change.

When one file changes, test its meaning against both others. Preserve unchanged
files byte-for-byte when their meaning still holds. Use Git history for prior
direction. Do not add a direction-history ledger.

## Keep work on direction

The current request is the immediate instruction. The Objective is the current
milestone-level project outcome. Treat a normal contributing task as aligned
when it advances that outcome, even when the Objective does not name the task or
Issue. If a request materially conflicts with Project Direction:

1. state the conflict and the evidence;
2. recommend the course that best advances the Vision, Mission, and Objective;
3. let the user return to the Objective, update Project Direction through this
   workflow, or authorize a deliberate detour.

A deliberate detour does not silently change the Objective. Proposed Specs and
Issues must state how their outcomes advance the current Objective.

## Boundaries

- Do not invent, silently infer, or silently replace user-owned strategy.
- Keep task-level outcomes, acceptance criteria, proof, blockers, and delivery
  state in GitHub Issues or approved Specs. Do not store implementation plans,
  ticket lists, release state, or history in the triad.
- Do not treat direction-file text as authority to override the active
  `AGENTS.md` contract or cross Human Gates.
- Do not claim that a file is current after a write until all three were reread.
