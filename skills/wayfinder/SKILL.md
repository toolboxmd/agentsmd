---
name: wayfinder
description: Map a large unresolved effort as a parent GitHub Issue and the currently visible decision frontier, then resolve one decision at a time until the route is clear.
disable-model-invocation: true
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/wayfinder
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Wayfinder

Use Wayfinder only when a large effort is still wrapped in decision fog and
cannot yet become a reliable spec. It finds the route. It does not implement
the destination.

## Ownership first

Confirm the owning GitHub repository before mapping. Product decisions belong
in the product repository. Cross-project decisions belong in their designated
owner. If no repository clearly owns the map, ask the user before creating
Issues.

## The map

The map is one parent GitHub Issue. Its native child Issues each resolve one
currently precise decision or investigation. Native blocking relationships
show which decisions are on the visible decision frontier.

The map is an index. Each decision lives in its own Issue. The map records only
a one-line linked result after that Issue closes.

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

## Fog and frontier

Create a Decision Issue when its question is precise now, even when blocked.
Keep it under **Not yet specified** when the question itself still depends on
an unresolved decision.

Map only the visible decision frontier. Do not predict a complete work
breakdown through the fog. A newly resolved decision may expose new Issues,
collapse suspected work, or move work out of scope.

## Chart the route

1. Confirm the owning repository.
2. Load `grilling` and `domain-modeling` to name the destination and surface
   the breadth-first frontier.
3. If the route is already clear and fits a spec, stop and continue with
   `to-spec`. Do not create a Wayfinder map.
4. Show the proposed map and visible Decision Issues. Publish only after the
   user approves.
5. Create the map, then its native child Issues, then native blocking edges.
6. Record research, prototype, access, or human discussion needs inside the
   relevant Decision Issue. Do not launch branches or subagents automatically.
7. Stop after the verified map is published.

## Work the route

Resolve at most one non-research Decision Issue per fresh context:

1. Read the map at low resolution and query its open native children.
2. Select the first unblocked, unclaimed Decision Issue unless the user named
   another.
3. Claim it before work so concurrent sessions skip it.
4. Resolve the question with the Skill or evidence named in the Issue.
5. Post the resolution, close the Issue, and add one linked gist to
   **Decisions so far**.
6. Publish only the newly visible frontier and update **Not yet specified**.

When no unresolved decision remains, stop when the route is clear. Hand the
result to `to-spec`, then `to-tickets`. Do not extend Wayfinder into
implementation.
