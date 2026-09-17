# Project Direction context

- Project Direction is the mandatory repository-root triad: `VISION.md`,
  `MISSION.md`, and `OBJECTIVE.md`. `VISION.md` owns the grand and visionary
  aspirational long-range destination. `MISSION.md` owns the strategic present
  purpose, problem, and approach, grounded in what the project does now.
  `OBJECTIVE.md` owns one current milestone-level outcome and its recognizable
  completion condition. It is narrower than the Mission but broader than an
  individual request, task, Issue, commit, or PR.
- Context invariant: the full current contents of all three files must be
  present in model context at task and subagent start and after context loss.
  Reuse unchanged full contents already in context during follow-ups; a
  recollection or compaction summary does not replace them. Reload when any
  file changes or full contents leave context. A project task is not
  initialized until this invariant is satisfied. Without it, the agent cannot
  judge usefulness, priority, deletion, drift, or completion. The repository
  files remain project truth.
- Context load: first honor an explicit local Project Direction opt-out; it
  removes the triad requirement only for its stated scope. Otherwise reuse
  complete unchanged contents already present in context, or use a
  runtime-injected Project Direction block only when it identifies the
  repository root, exact file paths, and hashes and contains all three
  complete current files. Otherwise, the first task action is to locate and
  read all three files in full before any other work. This applies to
  discussion, research, planning, specification, Issue creation,
  implementation, review, and delivery.
- Currentness guard: after the complete local triad is loaded and before a
  repository-dependent conclusion treats it as confirmed-current, resolve the
  intended base, `HEAD`, configured upstream, and locally known ahead/behind
  state. Use known remote-tracking information when it is sufficient. Fetch
  only when current remote state matters and the known information is
  insufficient; do not make pull routine. When a known upstream is ahead or
  diverged and changes any Project Direction file relative to `HEAD`, treat a
  loader status of `potentially_stale` as checkout-scoped direction, reconcile
  the intended base while preserving user work, and reread all three files
  before subsequent strategic judgment. Unknown Git metadata limits the
  currentness claim; it does not suppress the local triad. Loaders and hooks
  inspect only local Git state and do not access the network or mutate the
  checkout.
- Missing direction: when any file is absent, unreadable, blank, or reported as
  oversized, invoke `project-direction` immediately to establish the complete
  triad. Only the repository and tracker inspection required by that Skill may
  proceed until the user confirms the direction and all three files have been
  written and read.
- Unusable direction: invoke `project-direction` when a file contains
  unresolved placeholders, conflicts materially with another direction file,
  appears stale, reduces Vision to current work, leaves Mission ungrounded in
  present strategy, or merely restates one task, Issue, commit, or PR; when the
  Objective is achieved, invalidated, abandoned, or reprioritized; or when the
  user asks to define, review, or update direction. Use repository and tracker
  evidence, distinguish fact from inference and user-owned choice, and obtain
  explicit user confirmation before writing semantic direction.
- Context continuity: reread all three files immediately after any one changes.
- Alignment: evaluate every request, recommendation, Spec, Issue, and change
  against all three files. Surface material drift before proceeding and
  recommend returning to the Objective, updating Project Direction, or
  authorizing a deliberate detour. Only explicit user confirmation changes
  Project Direction or authorizes the detour. Treat ordinary work as
  contributing when its outcome advances the Objective even when the Objective
  does not name its task or Issue. Every proposed Spec and Issue must state how
  its outcome advances the current Objective.
