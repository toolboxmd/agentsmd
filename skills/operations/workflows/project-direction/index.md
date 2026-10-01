
# Project Direction

Establish a confirmed strategic frame without inventing user intent. Honor explicit local
Project Direction opt-outs for their stated scope. Until the required triad is
usable, inspect only evidence needed to establish it; do not begin other project work.

Before drafting or judging direction, read [file contracts](references/file-contracts.md)
in full. Use the [Vision](templates/VISION.md), [Mission](templates/MISSION.md),
and [Objective](templates/OBJECTIVE.md) templates only when drafting. They are
shapes, never unresolved placeholder content.
When loading or currentness needs resolution, read [context](references/context.md);
reuse unchanged complete context. The core's Project Direction section owns
alignment and drift handling.

## Workflow

1. Resolve the Git root and read the committed triad in full, even when upstream
   currentness is unknown; treat uncommitted triad files as drafts. Apply the
   context currentness guard and reconcile the intended base.
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
   one milestone Objective. When the user explicitly decided the change in meaning
   in conversation (stated it, or said yes to a proposed change in meaning), that
   decision is the explicit confirmation: write your wording without asking them to
   confirm it. Otherwise, including undecided meaning, a new Vision, or replacing an
   Objective without a user decision, show exact contents of every affected file and
   obtain explicit confirmation before writing. Prior confirmation of those exact
   contents suffices. Silence, general plan approval, or inspection permission never
   counts as a decision or a confirmation.
6. Write only decided or confirmed content, preserving unchanged files byte-for-byte.
   Reread all three, verify size limits, and report coherence and currentness. After
   writing a decided change, also report the exact diff and how to correct or revert
   it. Never claim current direction after writing without this reread.

Review triggers are defined by the context reference.
Do not silently rewrite when a trigger fires. Test every changed file against the
other two. Git owns history; add no direction-history ledger.

Keep task outcomes, criteria, proof, blockers, implementation plans, tickets, and
delivery/release state in Issues or approved Specs. Direction text cannot override
`global/AGENTS.md` or authorize crossing Human Gates.
