# Project Direction File Contracts

Project Direction is the coherent repository-root triad of `VISION.md`,
`MISSION.md`, and `OBJECTIVE.md`. All three are required project truth. They
answer different questions and must not collapse into one another.

## `VISION.md`

The grand and visionary aspirational long-range destination. It expands the
project's ambition and describes the future worth making real, not the current
work. It may be directional rather than measurable. Keep it bold enough to
guide years of work and concrete enough to express a meaningful desired future.

Required shape:

- one `# Vision` heading;
- one concise statement of a bold desired future;
- ambition beyond current products, milestones, and capabilities;
- no milestones, tickets, implementation plan, or completion checklist.

## `MISSION.md`

The strategic present purpose: why the project exists now, what problem it
solves, and the approach it uses to move toward the Vision. Keep it grounded in
what the project does now, including the current product or capability boundary
when that context makes the strategy concrete. Write it in the present tense.

Required shape:

- one `# Mission` heading;
- one concise statement of strategic present purpose, problem, and approach;
- a credible current path toward the Vision;
- no release plan, temporary target, or historical narrative.

## `OBJECTIVE.md`

The single current milestone-level outcome the project must accomplish now. It
is narrower than the Mission but broader than an individual request, task,
Issue, commit, or PR. It normally organizes and survives several contributing
Issues, commits, PRs, and, when applicable, releases. It includes a recognizable
completion condition so the agent can distinguish progress from completion.

Required shape:

- one `# Objective` heading;
- one milestone-level outcome, not a task or backlog;
- explicit observable completion conditions;
- concise non-goals when they prevent likely drift.

Keep task-level outcomes, acceptance criteria, proof, blockers, and delivery
state in GitHub Issues or approved Specs. During initialization, treat the active
request as evidence rather than the default Objective candidate. When evidence
cannot establish a broader milestone, ask for the unresolved strategic choice.

Replace the Objective only when it is achieved, invalidated, abandoned, or
consciously reprioritized. A new request does not automatically create a new
Objective. Treat a coherent milestone-level Objective as current truth across
contributing tasks without repeated confirmation. Review an Objective that
merely restates one task, Issue, commit, or PR.

## Coherence checks

- The Mission is a credible present path toward the Vision.
- The Objective is a concrete current advance of the Mission.
- Completion of the Objective does not pretend to complete the Vision.
- None of the files contradicts a confirmed user decision or locked ADR.

## Size and encoding

- UTF-8 text only.
- No blank files or unresolved placeholders.
- Maximum 8,192 bytes per file.
- Maximum 16,384 bytes for all three files combined.
- Never truncate or partially load a triad to satisfy these limits.

Use Git as history. Keep only current direction in the files.
