# Algorithm

Apply after Project Direction is loaded. Keep a small direct microfix direct.
Use this method to choose the work, not to narrate a checklist.

## Ordered procedure

1. Question every requirement. Identify the wanted result, its owner, evidence,
   constraints, and required proof. Separate explicit requirements from assumptions
   introduced by the proposed solution. Complete when the outcome, constraints,
   owner, and required proof are explicit.
2. Delete the unnecessary part or process. Add a component only when you can
   identify what fails without it. Apply this test to code, dependencies, tools,
   documents, handoffs, and checks. Start with existing capabilities. Test
   deletions reversibly and scale the experiment to its consequences. Retain
   unique regression proof while the requirement it protects still applies.
   Restore a removed part when evidence shows it is needed; addback is not a quota.
   Complete when every survivor has an evidence-linked reason to exist.
3. Simplify or optimize only what survives deletion. Choose the smallest solution
   that meets the requirement. Before acceleration or automation, record the
   requirement, supporting evidence, cuts, and smallest surviving solution in
   the existing task record. Complete when the surviving path is the simplest
   known to meet the requirement.
4. Accelerate cycle time through the active constraint. Apply only when faster
   execution is needed. Use [Current constraint](current-constraint.md) to choose
   the smallest intervention before adding workers or tooling. Complete when
   the next action follows the shortest safe feedback path through that constraint.
5. Automate last. Apply only to a necessary, stable, proven, recurring loop
   whose failure modes are understood. Complete when automation preserves the
   proven behavior and exposes failures.

The order is binding; acceleration and automation are conditional. Reuse settled
reasoning. When evidence changes, return to the earliest affected step and
resolve it and its affected successors before proceeding.
Test the smallest candidate with a check that can falsify the assumption.
Inspect the result, correct the approach, and repeat before expanding it.
Fast feedback does not replace required final proof.

A small reproduction or measurement script is an instrument, not necessarily
automation of a recurring process. For bulk edits or repeated analysis, first
understand one representative case. Build a rerunnable tool when its coverage,
repeatability, or saved work justifies maintenance; compare its output with the
understood case before expansion. Do not require tooling for every nontrivial
task. Recurring orchestration still waits for step 5 and its authority boundary.

The core owns authority, Project Direction, explicit user constraints, and
user-owned dirty work. Operations owns required proof and review.

The [Marketplace regression](marketplace-project-record-regression.md) records
an earlier failure to delete machinery before implementation.
