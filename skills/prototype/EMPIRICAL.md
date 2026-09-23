# Empirical prototype

Use a throwaway experiment when evidence can resolve a technical question without
a subjective verdict. State the hypothesis, alternatives, predicted observations,
falsifier, relevant environment, and stopping condition before building it.

Choose a script, native test harness, type-checking example, benchmark, or small
integration probe according to the uncertainty. A browser presentation is useful
only when interaction or human inspection is part of the question. Reuse the
actual dependency version and critical boundary when a toy replacement would
remove the behavior being tested.

Keep setup and effects isolated and disposable within the task's authority. No
production data or protected target becomes available merely because the code is
throwaway. Run the smallest smoke check and then the discriminating experiment.
Inspect the real result; setup success is not a hypothesis verdict.

Record artifact identity, command, conditions, observations, confidence, and what
the experiment does not cover. Inconclusive evidence leaves the question open.
A changed method needs a comparable rerun; a failed hypothesis is useful evidence,
not an invitation to redefine success.

Use the common capture and continuation procedure in [SKILL.md](SKILL.md).
Preserve the decision owner. An experiment can inform a human taste or costly
architecture choice without making that choice. Carry validated findings into
production design, leaving the disposable shell off main.
