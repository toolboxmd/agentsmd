---
name: algorithm
description: >
  Apply the fixed five-step Algorithm to material requirements, solution
  design, process design, and recurring-loop automation. Use before material
  implementation, acceleration, or automation; keep small direct microfixes
  direct.
---

# Algorithm

Apply this Skill after the complete current Project Direction is loaded. Run
all five steps again for every material requirement, solution, process, and
recurring loop. The fixed order is binding and matters more than any single
step. It prevents perfect execution of the wrong requirement, optimization of
work that should not exist, speed in the wrong direction, and automation that
hardens waste.

Keep a small direct microfix direct when its requirement and solution are
already clear and it adds no material design, process, or recurring loop.

Do not narrate the Algorithm as ceremony. Use it to choose the next action.
Explain its application only when the reasoning, decision, or tradeoff is
useful to the user.

## Boundaries

The Algorithm chooses means. It does not replace the current request, confirmed
Project Direction, explicit user constraints, or user authority. Preserve
Human Gates, user-owned dirty work, unique regression proof, and the final
Proof required by the Issue and risk.

## Ordered procedure

1. Question every requirement. Establish the useful outcome, supporting
   evidence, responsible person or authoritative source, constraints,
   acceptance criteria, and required proof. Requirements from experts and
   inherited process need scrutiny because their authority can hide a wrong
   problem statement. Treat governing instructions and explicit user
   constraints as binding; question the proposed interpretation and path, not
   the authority that owns them. Complete this step when outcome, ownership,
   constraints, acceptance, and proof are explicit.
2. Delete the unnecessary part or process. Test whether the requirement,
   scope, code, test, dependency, artifact, handoff, or ceremony should exist
   at all. Deletion is stronger than cleanup because each survivor creates
   secondary implementation, maintenance, coordination, and failure costs.
   Make deletion risk-scaled and reversible. Use committed Git history to
   recover in-scope tracked work. Keep uncommitted user work, user data,
   credentials, legal controls, production state, and irreversible changes
   outside this experiment and subject to their Human Gates. Required proof
   and unique regression tests survive unless the requirement they prove is
   deleted. Restore work only when evidence proves it is required. Addback
   maps the boundary; it is not a quota. Complete this step when every survivor
   has an evidence-linked reason to exist.
3. Simplify or optimize only what survives deletion. Prefer fewer states,
   narrower interfaces, direct paths, clear ownership, smaller diffs, and less
   duplicated process. Simplicity must preserve necessary behavior, error
   handling, proof, safety, and user-visible capability. It is a design result,
   not a reason to hide complexity that still exists. Complete this step when
   the surviving path is the simplest one known to meet the requirement.

Before step 4, ensure the current material-work artifact or evidence records
the questioned requirement and its supporting evidence, the requirement
outcome and owner, deletion decisions and evidence-linked reasons for every
survivor, and the simplified surviving path. This evidence need not become
user-facing narration unless it helps a decision or handoff.

4. Accelerate cycle time through the active constraint. Speed means faster
   validated learning after the right work and structure are established, not
   generalized haste. Use direct source inspection, smaller checks, fewer
   handoffs, cached work, and parallel execution only for genuinely independent
   ownership and dependencies. Keep proof and single-writer boundaries intact.
   Complete this step when the next unit of effort follows the shortest safe
   feedback path through the current constraint.
5. Automate last. Automation magnifies the process chosen before it. Automate
   only a necessary, stable, proven, recurring semantic loop whose invariants
   and failure modes are understood. Keep one-off or ambiguous work explicit
   until evidence makes it repeatable. Complete this step when automation
   preserves the proven semantics and exposes failures.

When evidence changes a requirement or reveals unnecessary work, return to the
earliest affected step before proceeding. Resolve every earlier step before
optimizing, accelerating, or automating.

## Closed evidence loop

Run the Algorithm inside a closed evidence loop. Start from the useful outcome
and inspect the exact source, work, state, or user surface. Identify the active
constraint. Make the smallest meaningful reversible change or experiment, run
the fastest check that can falsify the current assumption, inspect the result,
correct the model and implementation, expose bad news, and repeat. Scale
failure tolerance to consequence: move quickly on cheap reversible learning
and increase control as impact and irreversibility rise.

A fast cycle check is feedback, not final Proof. Completion still requires the
highest practical Proof seam and the exact delivery state must remain explicit.

The real Marketplace Project Record failure and correction are preserved in
[the regression reference](references/marketplace-project-record-regression.md)
for future changes to this Skill. It is evidence, not a template for ordinary
work.
