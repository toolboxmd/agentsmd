---
name: prototype
description: Build a throwaway prototype to answer a concrete logic, state-model, behavior, or UI design question, including a Wayfinder Prototype Decision Issue.
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/prototype
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Prototype

A prototype is throwaway code answering a concrete question. On claiming a
Wayfinder **Prototype Decision Issue**, invoke this Skill without another human
selection. Build the artifact and obtain the owning Issue's required decision.
For direct requests, the user's question owns the work. Record question, artifact
location, and decision on the owning GitHub Issue.

## Select the branch

- Logic/state/data questions: read [LOGIC.md](LOGIC.md). Build one shareable HTML
  file with free-play buttons and tabbed guided scenarios a non-developer can drive.
- Appearance questions: read [UI.md](UI.md). Build radically different variants
  on one route with URL selection and a floating bottom bar.

Resolve ambiguity from prompt, code, or the available user. If unreachable, choose
the closest branch (backend logic versus page/component UI) and state that
assumption at the prototype's top.

## Common rules

1. Clearly name the throwaway artifact near its module/page; follow project routing
   and component conventions. UI starts with one existing task-runner command;
   logic remains one self-contained HTML file.
2. Keep state in memory unless persistence is the question, then use unmistakably
   disposable data. Render relevant state after every action or variant switch.
3. Learn before polishing. Skip production abstractions, exhaustive error handling,
   and production tests. Run the smallest smoke check proving startup and the
   decision-critical interaction.
4. Record the decision and evidence that changed it on the owning Issue. Preserve
   the prototype as primary evidence on a clearly named throwaway branch when
   existing Git authority permits publication; otherwise report local path and
   publication state.
5. After an authorized decision-maker accepts or rejects it, resume the owning
   workflow's next incomplete step. Acceptance supplies decision evidence, not
   production code. Only validated decisions enter production implementation;
   prototype shells, rejected variants, and temporary switchers stay off main.
