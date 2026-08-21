# Long-Running Goal Template

Use this template only for work that must survive interruptions or continue
across multiple sessions. Use a normal task for focused one-session work.

This file defines a persistent, harness-neutral Goal contract. A harness may
add its own native Goal or job mechanism, but the files below remain the source
of truth.

Create exactly:

```text
SPECS/
└── goals/
    └── <slug>/
        ├── GOAL.md
        └── STATUS.md
```

Do not copy this template into the project or add a Goal `README.md` unless the
user asks.

## `GOAL.md`

```markdown
# Goal: <observable outcome>

## Objective

<One sentence describing the result, not the activity.>

## Done when

1. [ ] <Verifiable completion criterion.>
   Evidence: <test, artifact, commit, external state, or exact observation>
2. [ ] <Verifiable completion criterion.>
   Evidence: <test, artifact, commit, external state, or exact observation>

## In scope

- <Allowed repository, branch, module, file, or operation.>

## Out of scope

- <Work that must not be added.>

## Fixed constraints

- <Protected behavior, compatibility rule, or numeric threshold.>

## Ask before

- Changing this `GOAL.md`.
- Working outside `In scope` or beyond `Done when`.
- Changing a fixed constraint.
- Making a material product, policy, architecture, migration, publication,
  destructive, or merge decision.
```

## `STATUS.md`

```markdown
# Goal status

State: draft
Goal path: `SPECS/goals/<slug>/GOAL.md`
Approved Goal blob SHA: pending
User approval reference: pending

## Current checkpoint

<The one critical-path item currently being executed.>

## Verified evidence

- <Done-when item number>: <evidence or not yet verified>

## Remaining

- <Only work required by the approved Goal.>

## Waiting for

- Nothing.

## Proposed changes to GOAL.md

- None.
```

## Start

1. Draft both files outside an active Goal.
2. Show the exact `GOAL.md` and obtain explicit user approval.
3. Calculate its blob SHA:

   ```sh
   git hash-object SPECS/goals/<slug>/GOAL.md
   ```

4. Record the SHA and approval reference in `STATUS.md`, set `State: active`,
   and commit both files.
5. If the harness supports persistent Goals, include the Goal path and SHA in
   its native objective. Otherwise, the two files are the persistence layer.

## Continue

- Read both files and verify the current `GOAL.md` blob SHA before work.
- Stop on a SHA mismatch and ask the user. Never repair the approved SHA
  automatically.
- Work only on the current critical-path item.
- If waiting, monitor only the recorded dependency. Do not create substitute
  work merely to stay active.
- Put out-of-scope findings under `Proposed changes to GOAL.md` and ask before
  acting on them.

## Complete

- Record concrete evidence for every numbered `Done when` item.
- Verify the approved SHA again.
- Set `State: complete` only when every criterion is proven and no required
  work remains.
- Reserved actions such as merge still require explicit approval.
