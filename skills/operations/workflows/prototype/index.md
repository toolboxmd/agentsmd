---
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/prototype
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
  additional-origin: cursor/plugins/pstack
  additional-source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Prototype

A prototype is throwaway code answering a concrete question. On claiming a
Wayfinder **Prototype Decision Issue**, invoke this procedure without another human
selection. Build the artifact and obtain the owning Issue's required decision.
For direct requests, the user's question owns the work. Record question, artifact
location, and decision on the owning GitHub Issue when one exists; otherwise
report them in the direct task. Use [artifact placement](../../references/artifacts.md)
for retained evidence. Reuse the task's evidence folder rather than creating a
second prototype report.

## Select the branch

- Human-facing logic/state/data decisions: read [LOGIC.md](LOGIC.md). Build one shareable HTML
  file with free-play buttons and tabbed guided scenarios a non-developer can drive.
- Appearance questions: read [UI.md](UI.md). Build radically different variants
  on one route with URL selection and a floating bottom bar.
- Empirical semantics, integration, ordering, or timing questions: read
  [EMPIRICAL.md](EMPIRICAL.md). Use the smallest executable script or native harness
  that distinguishes the alternatives, without a presentation shell.

Resolve ambiguity from prompt, code, or the available user. If unreachable, choose
the closest branch (backend logic versus page/component UI) and state that
assumption at the prototype's top. Preserve the owning decision's HITL/AFK type.
An empirical artifact does not convert a human-owned Wayfinder decision into an
agent-owned one.

## Common rules

1. Clearly name the throwaway artifact in task-owned temporary storage or an
   explicitly disposable branch; follow project routing and component conventions
   when an in-project runtime is necessary. UI starts with one existing task-runner command;
   a human-facing logic demo remains one self-contained HTML file. Empirical
   work uses its documented native invocation.
2. Keep state in memory unless persistence is the question, then use unmistakably
   disposable data. Render relevant state after every action or variant switch.
3. Learn before polishing. Skip production abstractions, exhaustive error handling,
   and production tests. Run the smallest smoke check proving startup and the
   decision-critical interaction.
4. Record the decision and decisive evidence on the owning Issue or direct task. Preserve
   the prototype as primary evidence on a clearly named throwaway branch when
   existing Git authority permits publication; otherwise report local path and
   publication state.
5. After an authorized decision-maker accepts or rejects it, or the empirical
   completion condition resolves an agent-owned question, resume the owning
   workflow's next incomplete step. Acceptance supplies decision evidence, not
   production code. Only validated decisions enter production implementation;
   prototype shells, rejected variants, and temporary switchers stay off main.
