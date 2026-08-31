---
name: to-spec
description: Turn the current conversation into an approved parent GitHub Issue without reopening settled decisions.
disable-model-invocation: true
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/to-spec
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# To Spec

Synthesize the current conversation and repository understanding into a ready
GitHub parent Issue. Do not restart the interview or reopen settled decisions.

## Process

### 1. Confirm ownership

Resolve the GitHub repository that owns the outcome. Product work belongs in
the product repository. Cross-project work belongs in its designated owning
repository. If ownership cannot be resolved from Git, project instructions, or
the conversation, ask before creating anything.

Fetch the full body and comments when the user names an existing Issue. Search
open Issues for the same outcome before proposing a new one.

### 2. Orient to the repository

If this conversation has not already established the current state of the
codebase, explore the relevant implementation and tests before drafting. Read
the relevant `GLOSSARY.md`, `GLOSSARY-MAP.md`, ADRs, instructions,
implementation seams, and existing proof. Legacy glossary files are read-only
migration fallbacks when the new names are absent.

Prefer an existing testing seam. Choose the highest public seam that can prove
the outcome. Introduce as few new seams as possible, ideally one, and only when
existing behavior cannot prove the outcome. Confirm the proposed seam with the
user and present any remaining user-owned decision before publishing.

### 3. Draft the parent Issue

Use the template below. Keep each section proportional to the work. Include
enough user stories to cover distinct actors and outcomes, without restating
every acceptance criterion as a story.

Avoid implementation paths and code snippets because they drift. A short
prototype-derived state machine, schema, or type shape may be included when it
records an approved decision more precisely than prose.

### 4. Approval gate

Show the complete draft or a precise change summary for an existing Issue.
Publish only after the user approves the outcome, scope, testing seam, and
remaining blockers.

### 5. Publish and verify

Create the GitHub parent Issue or update the exact existing Issue the user
approved. Do not add an automatic readiness label. Readiness comes from the
explicit outcome, acceptance criteria, non-goals, blockers, and required
proof.

Re-fetch the published body and comments. Report the Issue number and URL.
Stop after publication unless the user selected another workflow.

## Parent Issue template

```markdown
## Outcome

The observable result this effort must deliver.

## Problem Statement

The problem from the user's perspective.

## Solution

The proposed solution from the user's perspective.

## Acceptance criteria

- [ ] One externally meaningful result.

## User stories

1. As an <actor>, I want <capability>, so that <benefit>.

## Implementation decisions

- Approved modules and interfaces, technical clarifications, architectural
  decisions, schema or API contracts, and specific interactions.

## Testing decisions

- The external behavior to prove, modules exercised at the chosen public seam,
  and relevant prior test art.

## Non-goals

- Explicit adjacent work excluded from this outcome.

## Blockers

- Work or authority that genuinely prevents progress, or `None`.

## Required proof

- Evidence required before the implementation PR can be called ready.

## Further notes

Durable context that does not fit another section.
```
