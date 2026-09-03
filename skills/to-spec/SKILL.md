---
name: to-spec
description: Run the complete Specify workflow through an approved parent Issue and verified implementation ticket publication.
disable-model-invocation: true
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
  parent-publication-approval: required
  ticket-publication-approval: required
  continuation-stage: ticket-graph
  parent-only-opt-out: supported
  implementation-target: first-unblocked-issue
  implementation-context: fresh
  implementation-authority-source: full-current-request
  missing-authority-prompt-limit: 1
  invocation: user
---

# To Spec

Synthesize the current conversation and repository understanding into a ready
GitHub parent Issue, then continue the complete Specify workflow through
verified ticket publication by default. Do not restart the interview or reopen
settled decisions.

An explicit Parent Spec only request opts out after verified parent Issue
publication. Otherwise this Skill continues directly through the ticket-graph
stage below. It does not invoke another planning Skill. Evaluate that opt-out
and later implementation authority from the full current request, not from the
Skill invocation alone.

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
Retain approval before parent Issue publication: publish only after the user
approves the outcome, scope, testing seam, and remaining blockers. When the user
rejects or revises the draft, update it and repeat this gate until the user
approves it or stops the workflow.

### 5. Publish and verify

Create the GitHub parent Issue or update the exact existing Issue the user
approved. Do not add an automatic readiness label. Readiness comes from the
explicit outcome, acceptance criteria, non-goals, blockers, and required
proof.

Re-fetch the published body and comments. Report the Issue number and URL.

If the full current request explicitly requested Parent Spec only, stop after
this verified publication. Otherwise continue the selected workflow.

### 6. Draft the implementation ticket graph

Use the verified parent Issue and the full current request as the source. Draft
the smallest useful graph of implementation Issues. Prefer independently
provable tracer bullets. Use expand-migrate-contract only when a true wide
refactor prevents independently green slices.

Every proposed Issue must name its title, blockers, and delivered outcome. Each
Issue must include the parent reference, acceptance criteria, non-goals, and
required proof.

### 7. Approve the ticket graph

Obtain approval of ticket granularity, blocking edges, and publication. Ask
whether the merge or split choices are right. When the user rejects or revises
the draft, update it and repeat this gate until the user approves the complete
graph or stops the workflow.

### 8. Publish and verify implementation Issues

After approval, create Issues in dependency order. Add every implementation
Issue as a native sub-Issue of the parent and add native blocking relationships
after real Issue identifiers exist. Leave the parent body and state unchanged.
Do not add an automatic readiness label.

Re-fetch the parent's children and every native blocking edge. Report the final
Issue URLs and graph only after publication and relationship verification.

### 9. Continue at the implementation boundary

Identify the first unblocked implementation Issue and evaluate implementation
authority from the full current request.

- When that request already authorizes implementation, begin the Issue in a
  fresh context without another authorization prompt. Follow Authority and
  continuation in `AGENTS.md` and seed its minimal durable context packet.
- When the request was planning-only or otherwise lacks implementation
  authority, ask exactly once for authorization and name the Issue. Await that
  authority before changing implementation files.

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
