
# Project Direction context

Project Direction is the mandatory root triad: `VISION.md` owns the grand and visionary aspirational
long-range destination; `MISSION.md` the present purpose, problem, and strategy,
grounded in what the project does now;
`OBJECTIVE.md` one milestone-level outcome with recognizable completion. The Objective
is narrower than the Mission and broader than an individual request, task, Issue, commit, or PR.

## Load and retain

Honor explicit local opt-outs only for their stated scope. Otherwise keep all
three complete current files in context at task/subagent start and after context
loss, before discussion, research, planning, specification, Issue creation,
implementation, review, or delivery. Until loaded, the task is not initialized.
Reuse unchanged full contents; memory or a compaction summary is insufficient.
Reread all three immediately when any changes or their full contents leave context.

Accept runtime injection only with repository root, exact paths, hashes, and all
three complete current files. Otherwise locating and fully reading them is the
first task action. Where a host delivers injection only with the first tool
result, such as Grok Build, the first response has none, so read the triad
explicitly until it arrives. Grok Build 1.0.34 executes no plugin-provided hook,
so injection there needs the global hook file the README describes; without it
no injection arrives at all and every task starts by reading the triad.
Repository files remain truth.

## Currentness

Before treating loaded direction as confirmed-current, resolve intended base,
`HEAD`, configured upstream, and locally known ahead/behind state. Use sufficient local
remote-tracking evidence; fetch only when current remote state matters and known
information is insufficient. Do not routinely pull. Loaders/hooks inspect local
Git only, without network access or checkout mutation.

If known upstream is ahead or diverged and changes any direction file relative
to `HEAD`, treat `potentially_stale` as checkout-scoped evidence. Reconcile the
intended base while preserving user work and reread all three before further
strategic judgment. Unknown Git metadata qualifies currentness; it never suppresses
the local triad.

## Repair and alignment

Invoke `project-direction` immediately for absent, unreadable, blank, or oversized
files. Until the user confirms and all three are written and read, only the
Skill's necessary repository/tracker inspection may proceed.

Also invoke it for unresolved placeholders, material contradictions, stale meaning,
Vision reduced to current work, Mission lacking grounded present strategy, an
Objective restating one task/Issue/commit/PR, an achieved/invalidated/abandoned/
reprioritized Objective, or a user request to define, review, or update direction.
Distinguish repository/tracker facts from inference and user choices. Semantic
writes require explicit confirmation.

Before judging alignment or acting on drift, apply the core `AGENTS.md` Project
Direction section. It owns contribution, detour, and strategic confirmation rules.
