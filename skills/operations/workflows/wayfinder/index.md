---
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/wayfinder
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
  completion: resolved-decisions-and-workflow-continuation
---

# Wayfinder

Map dependent decisions that prevent a reliable spec, regardless of predicted
session length. A large but clear effort needs no map: return to Operations to select the
smallest suitable lane. Wayfinder resolves decisions, never implements
the destination.

Confirm the owning repository first: product decisions belong in the product
repository; cross-project decisions in their designated owner. Ask before
creating Issues if ownership is unclear. Name the destination, which bounds
scope and directs every Decision Issue. Refer to Issues by descriptive linked
titles, never bare numbers or slugs.

## Map and frontier

Use one parent GitHub Issue as an index and native child Issues for decisions.
Native blocking relationships define dependencies. Each decision lives in exactly
one Issue; after closure the map retains only its linked title and one-line gist.

```markdown
## Destination
<spec, decision, or change this map must make reachable>

## Notes
<standing constraints and relevant Skills>

## Decisions so far
- [<closed Decision Issue title>](url): <one-line result>

## Not yet specified
<in-scope questions that cannot yet be stated precisely>

## Out of scope
<work beyond the destination>
```

Start each Decision Issue with:

```markdown
## Question
<decision or investigation to resolve>

## Type
<Research | Prototype | Grilling | Task>
```

A precise question earns an Issue even when blocked or hard to answer. Use
**Not yet specified** only when an earlier decision must resolve before the
question itself becomes precise. Map the visible frontier, not an imagined
complete breakdown. New answers may expose, collapse, or exclude work.

Work beyond the destination is out of scope and cannot enter the frontier unless
the destination changes. Close an Issue found out of scope and add its linked
title and reason under **Out of scope**, never **Decisions so far**.

## Typed routing

HITL requires a human's live judgment; AFK can resolve from evidence. When a
session claims an Issue, dispatch its type without another workflow-selection
question:

- **Research (AFK):** Invoke the [research](../research/index.md) procedure. Establish the external
  fact and post a cited answer.
- **Prototype (HITL):** Invoke the [prototype](../prototype/index.md) procedure. Build a cheap concrete
  artifact and await the human verdict. It is decision evidence, not production.
- **Grilling (HITL):** Invoke the [grilling](../grilling/index.md) and [domain-modeling](../domain-modeling/index.md) procedures
  for taste, consequential architecture, or another human-owned judgment.
  Never impersonate the human or answer your own questions.
- **Task (HITL or AFK):** manual work, access, setup, or data movement needed to
  unblock a decision. It cannot be destination implementation.

Assign an Issue before working it. Assignment is its claim; concurrent sessions
skip claimed Issues. A frontier Issue is open, unblocked, and unclaimed.

## Chart

1. Confirm ownership and destination. Explore breadth-first across the problem
   for distinct decisions, dependencies, and fog.
2. If a reliable spec is now possible, return to Operations without creating a map.
   Select [to-spec](../to-spec/index.md) if a specification is needed; preserve its
   publication approval gates.
3. Show the proposed map and visible Decision Issues. Publish only after approval.
4. Create the map and typed native children, then native blocking edges once
   real identities exist. Verify both relationships and stop. Charting resolves
   none of its decisions.

## Work

Resolve at most one non-research Decision Issue per fresh context.

1. Read the map at low resolution and query open native children. Select the first
   unblocked, unclaimed Issue unless the user names another; assign it before work.
2. Dispatch its typed workflow. Research Issues may run in parallel only with
   independent questions and file ownership.
3. Post the resolution, close the Issue, and add its linked gist to **Decisions
   so far**. Create only newly visible Issues with native relationships; remove
   graduated fog. Close and classify newly discovered out-of-scope Issues.
4. Stop when a reliable spec can be stated, without eliminating every imaginable
   decision. Return to Operations and continue the smallest suitable lane under existing
   authority. Load [to-spec](../to-spec/index.md) when specification is needed.
