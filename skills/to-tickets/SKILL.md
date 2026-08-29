---
name: to-tickets
description: Break an approved plan or parent Issue into a small graph of complete GitHub Issues with explicit proof and native relationships.
disable-model-invocation: true
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/to-tickets
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# To Tickets

Turn an approved plan, parent Issue, or conversation into the smallest useful
graph of implementation GitHub Issues. Each Issue owns one narrow, complete,
independently provable outcome and fits one fresh context.

Tracer-bullet and expand-contract language guides the decomposition. The
published artifacts are called GitHub Issues.

## Process

### 1. Gather the complete source

Use the conversation already in context. When the user passes an Issue number
or URL, fetch its full body and comments. Read relevant project instructions,
the new-name glossary, ADRs, open Issues, pull requests, and current repository
state.

Confirm the owning GitHub repository before drafting. Search open and closed
Issues for duplicates.

### 2. Draft complete outcomes

Prefer tracer bullets:

- Each Issue crosses every layer required for one usable outcome.
- Completion is independently demoable or verifiable.
- The work fits one fresh context.
- Each blocker genuinely prevents the Issue from starting.
- A small prefactor may go first only when it makes the outcome materially
  easier and remains independently green.

Avoid horizontal Issues for documentation, tests, API, or UI when those layers
only become meaningful together.

### 3. Handle a true wide refactor

A wide mechanical change may make every caller fail at once, preventing any
independent green tracer bullet. Use expand-migrate-contract only in that case:

1. **Expand**: introduce the new form beside the old.
2. **Migrate**: move callers in independently green batches, each blocked by
   Expand.
3. **Contract**: remove the old form after every migration completes.
4. **Integrate and verify**: use a shared integration branch only when even the
   migration batches cannot remain green independently.

Do not use this exception to justify ordinary horizontal slicing.

### 4. Approval gate

Present a numbered breakdown. For every proposed Issue show:

- **Title**
- **Blocked by**
- **What it delivers**

Ask whether the granularity, blocking edges, and merge or split choices are
right. Iterate until the user approves the complete graph.

### 5. Publish GitHub Issues

After the user approves:

1. Create Issues in dependency order.
2. Include the parent reference, outcome, acceptance criteria, non-goals,
   blockers, and required proof in every Issue.
3. Add each implementation Issue as a native sub-Issue of its parent.
4. Add native blocking relationships after real Issue identifiers exist.
5. Keep intentionally deferred future work standalone when the current parent
   does not depend on its completion.
6. Leave the parent body and state unchanged.
7. Do not add an automatic readiness label. Explicit fields establish
   readiness.

Re-fetch the parent children and every native blocking edge. Report the final
Issue URLs and graph. Stop unless the user explicitly asks to continue into
implementation.

## Issue template

```markdown
## Parent

<parent Issue reference>

## Outcome

<one narrow, complete, user-visible result>

## Acceptance criteria

- [ ] Observable criterion

## Non-goals

- Adjacent work excluded from this Issue

## Blocked by

- <blocking Issue reference>, or `None`

## Required proof

- Evidence that independently proves the outcome
```
