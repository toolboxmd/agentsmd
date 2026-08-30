# Project Direction Skill Evaluation

Date: 2026-08-30

## Method

Five synthetic Git repositories represented the required behavior branches:

1. coherent existing triad;
2. all three files missing;
3. materially contradictory direction;
4. completed Objective with no confirmed successor;
5. materially off-Objective request.

Each scenario ran as a read-only pair on the same agent model. The with-Skill
agent read the candidate `project-direction` Skill and its required reference.
The blind baseline agent was forbidden from reading candidate files. Neither
condition could edit files, Git, or external state.

A scenario passed only when the response satisfied its complete behavioral
contract. Partial safety was not rounded up. The evaluation harness did not
expose comparable token counts or duration, so none are claimed.

## Results

| Scenario | With Skill | Blind baseline | Material difference |
| --- | --- | --- | --- |
| Coherent triad | Pass | Pass | Both used the Objective without repeated confirmation. The Skill condition explicitly classified the triad as coherent and unchanged. |
| Missing triad | Pass | Fail | The Skill condition stopped implementation, isolated three unresolved strategic choices, and promised exact drafts plus confirmation. Baseline asked implementation-design questions without establishing Project Direction. |
| Contradictory Mission | Pass | Fail | The Skill condition identified the outlier, proposed changing only `MISSION.md`, and waited for exact confirmation. Baseline proposed an immediate replacement and implementation without a confirmation gate. |
| Completed Objective | Pass | Fail | The Skill condition refused to invent a successor, asked for one user-owned outcome and completion condition, and preserved Vision and Mission. Baseline invented a new Objective and planned to write it plus `STATUS.md`. |
| Off-Objective request | Pass | Fail | Both surfaced drift. Only the Skill condition gave the complete choice: return, update Project Direction, or authorize a deliberate detour while leaving the Objective unchanged. |

With-Skill result: 5 of 5 passes.

Blind-baseline result: 1 of 5 passes.

## Trigger description

The frontmatter description was evaluated independently against 20 queries:
ten required triggers and ten nearby non-triggers. Predicted activation matched
all 20 expected labels. The explicit exclusion for merely rereading a coherent
triad prevented false positives on summarization, design context, downstream
specification, and ordinary implementation work.

## Conclusion

The Skill materially improves the branches where strategic authority is most at
risk. It prevents silent Objective replacement, requires confirmation before
semantic writes, and distinguishes a deliberate detour from a direction change.
The coherent-triad result also shows that this rigor does not force repeated
confirmation when direction is already usable.
