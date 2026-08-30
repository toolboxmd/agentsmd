# Project Direction File Contracts

Project Direction is the coherent repository-root triad of `VISION.md`,
`MISSION.md`, and `OBJECTIVE.md`. All three are required project truth. They
answer different questions and must not collapse into one another.

## `VISION.md`

The aspirational long-range destination. It describes the future the project
wants to make real, not the current work. It may be directional rather than
measurable.

Required shape:

- one `# Vision` heading;
- one concise statement of the desired future;
- no milestones, tickets, implementation plan, or completion checklist.

## `MISSION.md`

Why the project exists now, what problem it solves, and what it does to move
toward the Vision. Write it in the present tense.

Required shape:

- one `# Mission` heading;
- one concise statement of present purpose, problem, and approach;
- no release plan, temporary target, or historical narrative.

## `OBJECTIVE.md`

The single current outcome the project must accomplish now. It includes a
recognizable completion condition so the agent can distinguish progress from
completion.

Required shape:

- one `# Objective` heading;
- one current outcome, not a backlog;
- explicit observable completion conditions;
- concise non-goals when they prevent likely drift.

Replace the Objective only when it is achieved, invalidated, abandoned, or
consciously reprioritized. A new request does not automatically create a new
Objective.

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
