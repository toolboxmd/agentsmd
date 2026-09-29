---
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/to-spec
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
  workflow: specify
  workflow-stage: parent-spec
  default-completion: verified-ticket-publication
  parent-publication-approval: unresolved-user-decision-only
  ticket-publication-approval: unresolved-user-decision-only
  continuation-stage: ticket-graph
  parent-only-opt-out: supported
  implementation-target: first-unblocked-issue
  implementation-context: fresh
  implementation-authority-source: full-current-request
  missing-authority-prompt-limit: 1
  selection: operations
---

# To Spec

Synthesize the current conversation and repository understanding into a ready
GitHub parent Issue, then continue the complete Specify workflow through
verified ticket publication by default. Do not restart the interview or reopen
settled decisions.

An explicit Parent Spec only request opts out after verified parent Issue
publication. Otherwise this procedure continues directly through the ticket-graph
stage below. It does not invoke another planning procedure. Evaluate that opt-out
and later implementation authority from the full current request, not from the
procedure selection alone.

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
user only when choosing it is a user-owned decision.

### 3. Draft the parent Issue

Use the template below. Keep each section proportional to the work. Include
enough user stories to cover distinct actors and outcomes, without restating
every acceptance criterion as a story.

Avoid implementation paths and code snippets because they drift. A short
prototype-derived state machine, schema, or type shape may be included when it
records an approved decision more precisely than prose.

### 4. User-decision gate

A request to specify, plan, or decompose the work authorizes publishing its parent and
ticket Issues in the resolved owning repository. Without such a request, ask
once for that authority before publishing. Otherwise publish without a routine
approval stop. Stop before publication only when a
genuinely user-owned decision remains unresolved: product taste, consequential
or difficult-to-reverse architecture, or a change to confirmed scope or
authority. Ask only that decision, update the draft from the answer, and
continue. If the user stops the workflow, publish nothing.

### 5. Publish and verify

Create the GitHub parent Issue or update the exact existing Issue. Do not add an automatic readiness label. Readiness comes from the
explicit outcome, acceptance criteria, non-goals, blockers, and required
proof.

Re-fetch the published body and comments. Report the Issue number and URL.

If the full current request explicitly requested Parent Spec only, stop after
this verified publication. Otherwise continue the selected workflow.

### 6. Continue through ticket publication

Unless the full current request explicitly selects Parent Spec only, read and
perform [ticket decomposition](../to-tickets/references/ticket-decomposition.md)
after verified parent publication. Use the verified parent and full current
request as its source. This is the selected workflow's continuation, not an
selection of another planning procedure or another routing question. The shared
procedure owns its user-decision gate, native relationship verification, and the
first unblocked Issue's implementation-authority boundary.

## Parent Issue template

```markdown
**What:** <the result, one plain sentence>
**Why:** <the problem or its root cause, one sentence>
**So what:** <what happens next and who does it>

## Outcome

The observable result this effort must deliver.

## Problem Statement

The problem from the user's perspective.

## Solution

The proposed solution from the user's perspective.

## Elon record

- **Requirements and who asked:** <each requirement and its source>
- **Deleted:** <what was cut>
- **Bottleneck:** <where the work waits>
- **Checked myself:** <what you ran or read>

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
