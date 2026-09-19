
# Project Direction File Contracts

The complete repository-root triad owns current direction. Keep its roles distinct.

| File and heading | Required meaning and shape | Exclusions |
| --- | --- | --- |
| `VISION.md`, `# Vision` | One concise, bold, grand and visionary, aspirational long-range destination beyond current products and capabilities. Guide years of work with a meaningful future; it may be directional rather than measurable. | Current work, milestones, tickets, implementation plans, completion checklists. |
| `MISSION.md`, `# Mission` | One concise present-tense statement of why the project exists, its problem, and its strategic approach toward Vision. Keep it grounded in what the project does now; include the product/capability boundary when useful. | Release plans, temporary targets, historical narrative. |
| `OBJECTIVE.md`, `# Objective` | One current milestone-level outcome, narrower than the Mission but broader than an individual request, task, Issue, commit, or PR, normally surviving several contributing Issues and deliveries. Give observable completion conditions and non-goals when needed to prevent drift. | Task outcomes, backlogs, acceptance/proof/blocker/delivery records, which belong in Issues or approved Specs. |

Treat the active request as evidence, never the default Objective. If evidence
cannot establish the broader milestone, ask for that strategic choice. Replace
Objective only when achieved, invalidated, abandoned, or consciously reprioritized;
a new task does not require replacement or repeated confirmation. Review an
Objective that merely restates one task, Issue, commit, or PR.

Check that Mission credibly advances Vision and Objective concretely advances
Mission. Objective completion must not pretend to complete Vision. No file may
contradict a confirmed user decision or locked ADR.

Use UTF-8, no blank files or unresolved placeholders. Limits are 8,192 bytes per
file and 16,384 combined; never truncate or partially load to fit. Keep current
direction only; Git owns history.
