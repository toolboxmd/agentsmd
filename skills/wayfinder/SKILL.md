---
name: wayfinder
description: Map persistent decision fog as a parent GitHub Issue and a visible frontier of Decision Issues, then resolve one decision at a time until a reliable spec is possible.
disable-model-invocation: true
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/wayfinder
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
  completion: explicit-to-spec-selection
---

# Wayfinder

Use Wayfinder when persistent decision fog prevents a reliable spec,
regardless of predicted session length. Even a one-session effort may need a
map when several dependent questions obscure the route. A large but clear
effort does not: stop and tell the user it is ready for explicit `to-spec`
selection instead.

Wayfinder finds the route to a destination. It does not implement the
destination.

## Name the destination

Name the destination before charting anything else. It is the spec, decision,
or change that the map must make reachable. It fixes the scope and gives every
Decision Issue a common direction.

## Plan, don't do

Each Decision Issue resolves a question. It is not a slice of implementation.
When the next step is clear execution, the map has reached its edge: stop when
the route is clear and present it for explicit `to-spec` selection.

Research, a prototype, access, or a human conversation may be necessary to
resolve a decision. Record that need as the Decision Issue type. Charting
creates the typed Issues; working an Issue dispatches its required workflow.

## Refer by name

In narration and in the map, refer to every Issue by its descriptive linked
title, never by a bare number or slug. The title lets a human scan the route;
the link carries the Issue identity.

## Ownership first

Confirm the owning GitHub repository before mapping. Product decisions belong
in the product repository. Cross-project decisions belong in their designated
owner. If no repository clearly owns the map, ask the user before creating
Issues.

## The map

The map is one parent GitHub Issue. Its native child Issues each resolve one
currently precise decision or investigation. Native blocking relationships
show which decisions are on the visible decision frontier.

The map is an index, not a store. Each decision lives in exactly one Decision
Issue. After that Issue closes, the map records only its descriptive linked
name and a one-line gist.

```markdown
## Destination

<the spec, decision, or change this map must make reachable>

## Notes

<standing constraints and relevant Skills>

## Decisions so far

- [<closed Decision Issue title>](url): <one-line result>

## Not yet specified

<in-scope fog that cannot yet be stated as a precise question>

## Out of scope

<work beyond the destination>
```

Every Decision Issue starts with the smallest useful body:

```markdown
## Question

<the decision or investigation this Issue resolves>

## Type

<Research | Prototype | Grilling | Task>
```

## Decision Issue types

The type states how the question can be resolved. **HITL** requires live work
with a human who speaks for themselves. **AFK** can be resolved by an agent
from evidence without live human judgment.

- **Research (AFK):** Invoke the bundled `research` Skill when a session claims
  the Issue. Establish the external fact the decision depends on and record
  the cited answer on the Issue.
- **Prototype (HITL):** Invoke the bundled `prototype` Skill when a session
  claims the Issue. Build a cheap, rough artifact that gives the human
  something concrete to react to, then wait for the human verdict. The
  prototype informs the decision; it is not production implementation.
- **Grilling (HITL):** resolve product taste, consequential architecture, or
  another human-owned judgment through live conversation. Invoke the bundled
  `grilling` and `domain-modeling` Skills when a session claims the Issue. The
  agent never stands in for the human or answers its own questions.
- **Task (HITL or AFK):** complete manual work, access, setup, or data movement
  required before a decision can be made. A Task earns its place by unblocking
  a decision, not by implementing the destination.

The type is a routing contract, not merely a label. When a session works the
Issue, dispatch from its type without asking the human to select a workflow.
Charting still resolves none of the Issues it creates.

A session claims a Decision Issue by assigning it before beginning work. That
assignee is the claim, so concurrent sessions can skip open Issues already in
progress. An Issue is on the frontier when it is open, unblocked, and
unclaimed.

## Fog and frontier

Create a Decision Issue when its question is precise now, even when blocked.
Keep it under **Not yet specified** when the question itself still depends on
an unresolved decision.

Map only the visible decision frontier. Do not predict a complete work
breakdown through the fog. A newly resolved decision may expose new Issues,
collapse suspected work, or move work out of scope.

Fog is in scope but not yet sharp enough to express as a question. It is not a
synonym for "hard to answer." Use this test:

- **Decision Issue:** the question is precise now, even if its answer is
  blocked or unknown.
- **Not yet specified:** an earlier decision must resolve before the question
  itself can be stated precisely.

## Out of scope

Work beyond the destination is out of scope, not fog. It never graduates onto
the frontier unless the destination changes. If an existing Decision Issue is
discovered to be out of scope, close it and add one descriptive linked line to
**Out of scope** with the reason. Do not record it under **Decisions so far**.

## Chart the route

1. Confirm the owning repository.
2. Establish the destination, then explore breadth-first across the whole
   problem to surface distinct decisions, dependencies, and remaining fog.
3. If this clears the fog and the route fits a reliable spec, stop and tell the
   user it is ready for explicit `to-spec` selection. Do not create a map.
4. Show the proposed map and visible Decision Issues. Publish only after the
   user approves.
5. Create the map, then its native child Issues. Add native blocking edges in
   a second pass after every Issue has an identity.
6. Assign each Decision Issue its type.
7. Verify parent-child and blocking relationships, then stop. Charting
   resolves none of the decisions.

## Work the route

Resolve at most one non-research Decision Issue per fresh context:

1. Read the map at low resolution and query its open native children.
2. Select the first unblocked, unclaimed Decision Issue unless the user named
   another.
3. Claim it by assigning it before work so concurrent sessions skip it.
4. Dispatch the workflow recorded by the Issue type without asking the human
   to select it. Research Issues may proceed in parallel when their questions
   and file ownership are independent.
5. Post the resolution, close the Issue, and add one linked gist to
   **Decisions so far**.
6. Create only newly visible Decision Issues, wire their native relationships,
   and remove any fog that has now graduated from **Not yet specified**.
7. Close and classify any Issue exposed as out of scope.

Do not require every imaginable decision to disappear. When the remaining
route can be stated as a reliable spec, Wayfinder is complete. Present it for
explicit `to-spec` selection and stop.
