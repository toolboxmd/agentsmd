---
name: operations
description: >
  Route AgentsMD work to the procedure needed now: investigate, design, implement,
  review, or deliver. Use at task start and when work changes phase; load only
  the selected references.
metadata:
  agentsmd-layout: procedures-v1
---

# Operations

Select by the user's outcome and the current action, without a mode command.
The core `global/AGENTS.md` owns direction, authority, user work, and required context.
This entry point selects procedures; it grants no permission.

Resolve this file from installed discovery or the canonical AgentsMD source
behind the global instruction link. Resolve links relative to this actual file,
never the target project's cwd. Keep core and procedures on one compatible
revision. A missing required reference blocks only the dependent action; report
its resolved path. Reuse unchanged reference contents already in context.

At task start, after context loss, and when the action changes, select the
applicable rows below. Read their linked procedure in full before the dependent action;
then follow only its relevant conditional links. Do not preload the catalogue or
all procedures. Recheck selection when evidence changes, for example when a
review becomes an authorized repair. Explicit procedure names select the same
procedures; no separate invocation is needed.

For material work, apply [Elon method](procedures/elon-method/index.md) before
accepting requirements or an approach. Record the Elon record (Requirements and who
asked, Deleted, Bottleneck, Checked myself) in the existing task record. Loading the method is
not completing it. A clear microfix stays direct.

| Current need | Read in full |
| --- | --- |
| Initialize or reload Project Direction | [Context](procedures/project-direction/references/context.md) |
| Repair or change Project Direction | [Project Direction](procedures/project-direction/index.md) |
| Before researching facts, mechanics, history, or prior work, or explaining how a system works (not for a direct answer from the code at hand) | [Research](procedures/research/index.md) |
| Choose an interface or architecture, compare structures, model state or types, migrate callers, share mutable state, or make retries safe (the core's Software design rules are always loaded) | [Software design](procedures/software-design/index.md) |
| Before running a disposable experiment or building a UI/logic demo to resolve a question | [Prototype](procedures/prototype/index.md) |
| Before running, reproducing, or testing anything for a defect, a fix, or runtime behavior or performance | [Diagnosis](procedures/diagnosis/index.md) |
| Resolve unresolved human-owned choices, or the user asks to be grilled or stress-test their thinking | [Grilling](procedures/grilling/index.md); [grill with docs](procedures/grill-with-docs/index.md) when terminology or ADR work is needed |
| Before editing `GLOSSARY.md`, `GLOSSARY-MAP.md`, or an ADR, or when agreeing a term | [Domain modeling](procedures/domain-modeling/index.md); [GLOSSARY-FORMAT.md](procedures/domain-modeling/GLOSSARY-FORMAT.md) before editing a glossary |
| Map dependent unresolved decisions | [Wayfinder](procedures/wayfinder/index.md) |
| Produce a specification or decompose a plan | [Specify](procedures/to-spec/index.md), or [tickets](procedures/to-tickets/index.md) for an existing plan or parent Issue |
| Edit tracked files or select a workspace | [Implementation](references/implementation.md) |
| Before editing or adding a test file | [Test design](references/test-design.md) |
| Delegate or coordinate dependencies, recover a handoff | [Orchestration](references/orchestration.md) |
| Before opening or updating a PR, claiming readiness, or choosing or running proof or review | [Verification](references/verification.md); [code review](procedures/code-review/index.md) for review findings |
| Create or repair product-driving verification instructions | [Project verification](procedures/project-verification/index.md) |
| Before editing a `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or other agent instructions | [Writing for agents](procedures/writing-for-agents/index.md); [prose](procedures/technical-writing/references/prose.md) before editing a `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or other agent instructions; [SKILL-MECHANICS.md](procedures/writing-for-agents/SKILL-MECHANICS.md) before editing a `SKILL.md` or a Skill description |
| Before editing a README, CHANGELOG, `docs/` page, or other human-facing documentation | [Technical writing](procedures/technical-writing/index.md) and [prose](procedures/technical-writing/references/prose.md) |
| Learn from corrections, repeated friction, or requested reflection | [Reflection](procedures/reflection/index.md) |
| Before editing `PREFERENCES.md` | [Preferences pruning](procedures/reflection/references/preferences-pruning.md) |
| Change tracked files or make an explicit WIP checkpoint | [Version control](procedures/version-control/index.md) |
| Use `.toolboxmd/delivery.json` or decide delivery configuration | [Delivery profile](procedures/delivery-profile/index.md) |
| Deliver a PR, merge, release, promote an artifact, classify website impact | [Delivery](references/delivery.md) |
| Close a terminal outcome or retire task resources | [Finalization](references/finalization.md) |
| Resolve repository capability or settings drift | [Repository setup](references/repository-setup.md) |
| Reconcile legacy or drifted repository resources | [Reconciliation](references/reconciliation.md) |

The old `algorithm` name selects Elon method's Algorithm reference. Planning
procedures retain their concrete human decision and approval gates; selecting
one automatically does not approve its proposal. The routing tool still owns
model and effort selection when dispatch is warranted. Workers use this entry point
for their assigned scope; it does not authorize another dispatch.
