
# Ticket decomposition

## 1. Gather source

For direct [to-tickets](../index.md) entry, use the conversation already in context. Fetch full
body and comments for a named Issue. Read relevant instructions, new-name glossary,
ADRs, open Issues/PRs, and current repository state. Confirm the owning repository;
search open and closed Issues for duplicates.

For [to-spec](../../to-spec/index.md) continuation, use its verified parent and full current request;
reuse its completed source gathering without restarting settled decisions.

## 2. Draft complete outcomes

Draft the smallest useful graph of independently provable tracer bullets. Each
Issue crosses the layers needed for one usable outcome, fits one fresh context,
and is independently demoable/verifiable. Blockers must genuinely prevent starting.
A small prefactor may lead only if materially useful and independently green.
Avoid horizontal documentation, test, API, or UI Issues that become useful only together.

Use expand-migrate-contract only when a wide mechanical refactor prevents green
tracer bullets: expand beside the old form, migrate independently green batches
blocked by Expand, then contract after all migrations. Use a shared integration
branch only when even migration batches cannot stay green. This is no excuse for
ordinary horizontal slicing.

For each acceptance criterion, name the observable result and evidence that can
prove it. Keep parent requirements stable and user-visible. Put current paths,
commands, fixtures, exact revisions, and environment gotchas in the implementation
packet after orientation. Completion requires the stated evidence for the current
candidate, not a checked box or worker summary.

## 3. Approve

Show a numbered graph with **Title**, **Blocked by**, and **What it delivers**
for each Issue. Ask whether merge/split choices are right. Obtain approval of
granularity, blocking edges, and publication. Revise and repeat until the user
approves the complete graph or stops.

## 4. Publish and verify

After the user approves, create Issues in dependency order using the template
below. Add each as a native sub-Issue; add native blocking relationships after
real identifiers exist. Leave the parent body/state unchanged. Deferred future
work stays standalone when parent completion does not depend on it. Add no
automatic readiness label; explicit fields establish readiness.

Re-fetch parent children and every native blocking edge. Report final Issue URLs
and graph only after the complete publication and relationships are verified.

## 5. Continue at the implementation boundary

Identify the first unblocked implementation Issue. Evaluate authority from the
full current request. When already authorized, begin under the core's
direct/delegated boundary without another prompt; follow Authority and continuation
in `AGENTS.md`. For delegation, read Operations orchestration and use its minimal
durable context packet, not the prior conversation.

For planning-only work or otherwise missing authority, ask exactly once, naming
that Issue, and await authority before implementation edits. This step ends when
implementation begins within authority or that one named-Issue request awaits
response.

## Issue template

```markdown
## Parent
<parent Issue reference>

## Outcome
<one narrow, complete, user-visible result>

## Acceptance criteria
- [ ] Observable criterion

## Non-goals
- Adjacent excluded work

## Blocked by
- <blocking Issue reference>, or `None`

## Required proof
- Evidence independently proving the outcome
```
