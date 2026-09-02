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

A prototype is **throwaway code that answers a question**. The question decides the shape.

When a session claims a Wayfinder **Prototype Decision Issue**, invoke this
Skill without asking the human to select it. Build the concrete artifact, then
stop for the human verdict required by the HITL Issue. For a direct prototype
request, use the user's question as the owning question.

Record the question, artifact location, and verdict on the owning GitHub Issue.

## Pick a branch

Identify which question is being answered, using the user's prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model feel right?"** → [LOGIC.md](LOGIC.md). Build a single shareable HTML file (free-play buttons plus tabbed guided walkthroughs) that pushes the state machine through cases that are hard to reason about on paper, and that a non-developer can drive.
- **"What should this look like?"** → [UI.md](UI.md). Generate several radically different UI variations on a single route, switchable via a URL search param and a floating bottom bar.

The two branches produce very different artifacts, so getting this wrong wastes the whole prototype. If the question is genuinely ambiguous and the user isn't reachable, default to whichever branch better matches the surrounding code (a backend module → logic; a page or component → UI) and state the assumption at the top of the prototype.

## Rules that apply to both

1. **Throwaway from day one.** Put it near the relevant module or page and
   name it clearly as a prototype. Follow the project's existing routing and
   component conventions.
2. **Trivial to run.** Start a UI prototype with one existing task-runner
   command. Keep a logic demo in one self-contained HTML file.
3. **No persistence by default.** Keep state in memory unless persistence is
   the question. Use unmistakably disposable data when it is required.
4. **Learn before polishing.** Skip production abstractions, exhaustive error
   handling, and a production test suite. Run the smallest runnable smoke
   check that proves the artifact starts and its decision-critical interaction
   works.
5. **Surface the state.** Render the relevant state after each action or
   variant switch so the human can judge what changed.
6. **Capture the answer.** Record the human verdict and what evidence changed
   the decision on the owning GitHub Issue. Keep the prototype as primary
   evidence on a clearly named throwaway branch when existing Git authority
   permits that publication; otherwise report its local path and publication
   state.
7. **Keep main clean.** Only the validated decision proceeds into production
   implementation. The prototype shell, rejected variants, and temporary
   switcher stay off the main branch.
