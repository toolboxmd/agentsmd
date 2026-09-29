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
applicable rows below. Read their linked procedure before the dependent action;
then follow only its relevant conditional links. Do not preload the catalogue or
all procedures. Recheck selection when evidence changes, for example when a
review becomes an authorized repair. Explicit workflow names select the same
procedures; no separate invocation is needed.

For material work, apply [Elon method](workflows/elon-method/index.md) before
accepting requirements or an approach. Record the Elon record (Requirements and who
asked, Deleted, Bottleneck, Checked myself) in the existing task record. Loading the method is
not completing it. A clear microfix stays direct.

| Current need | Read |
| --- | --- |
| Initialize or reload Project Direction | [Context](workflows/project-direction/references/context.md) |
| Repair or change Project Direction | [Project Direction](workflows/project-direction/index.md) |
| Research facts, mechanics, history, prior work, or explain a system | [Research](workflows/research/index.md) |
| Choose interfaces, state, architecture, migration, or concurrent behavior | [Software design](workflows/software-design/index.md) |
| Resolve a question with a disposable experiment or UI/logic demo | [Prototype](workflows/prototype/index.md) |
| Reproduce a defect, test a fix, investigate runtime behavior or performance | [Diagnosis](workflows/diagnosis/index.md) |
| Resolve unresolved human-owned choices, or the user asks to be grilled or stress-test their thinking | [Grilling](workflows/grilling/index.md); [grill with docs](workflows/grill-with-docs/index.md) when terminology or ADR work is needed |
| Before editing `GLOSSARY.md`, `GLOSSARY-MAP.md`, or an ADR, or when agreeing a term | [Domain modeling](workflows/domain-modeling/index.md); [GLOSSARY-FORMAT.md](workflows/domain-modeling/GLOSSARY-FORMAT.md) before editing a glossary |
| Map dependent unresolved decisions | [Wayfinder](workflows/wayfinder/index.md) |
| Produce a specification or decompose a plan | [Specify](workflows/to-spec/index.md), or [tickets](workflows/to-tickets/index.md) for an existing plan or parent Issue |
| Edit tracked files or select a workspace | [Implementation](references/implementation.md) |
| Before editing or adding a test file | [Test design](references/test-design.md) |
| Delegate or coordinate dependencies, recover a handoff | [Orchestration](references/orchestration.md) |
| Before opening or updating a PR, claiming readiness, or choosing or running proof or review | [Verification](references/verification.md); [code review](workflows/code-review/index.md) for review findings |
| Create or repair product-driving verification instructions | [Project verification](workflows/project-verification/index.md) |
| Retain research, experiment, review, or other task evidence | [Artifact placement](references/artifacts.md) |
| Before editing a `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or other agent instructions | [Writing for agents](workflows/writing-for-agents/index.md); [prose](workflows/technical-writing/references/prose.md) before editing a `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or other agent instructions; [SKILL-MECHANICS.md](workflows/writing-for-agents/SKILL-MECHANICS.md) before editing a `SKILL.md` or a Skill description |
| Before editing a README, CHANGELOG, `docs/` page, or other human-facing documentation | [Technical writing](workflows/technical-writing/index.md) and [prose](workflows/technical-writing/references/prose.md) |
| Learn from corrections, repeated friction, or requested reflection | [Reflection](workflows/reflection/index.md) |
| Before editing `PREFERENCES.md` | [Preferences pruning](workflows/reflection/references/preferences-pruning.md) |
| Change tracked files or make an explicit WIP checkpoint | [Version control](workflows/version-control/index.md) |
| Use `.toolboxmd/delivery.json` or decide delivery configuration | [Delivery profile](workflows/delivery-profile/index.md) |
| Deliver a PR, merge, release, promote an artifact, classify website impact | [Delivery](references/delivery.md) |
| Close a terminal outcome or retire task resources | [Finalization](references/finalization.md) |
| Resolve repository capability or settings drift | [Repository setup](references/repository-setup.md) |
| Reconcile legacy or drifted repository resources | [Reconciliation](references/reconciliation.md) |
| User explicitly asks to consult Grok | [Use Grok](workflows/use-grok/index.md) |

The old `algorithm` name selects Elon method's Algorithm reference. Planning
procedures retain their concrete human decision and approval gates; selecting
one automatically does not approve its proposal. The routing tool still owns
model and effort selection when dispatch is warranted. Workers use this entry point
for their assigned scope; it does not authorize another dispatch.
