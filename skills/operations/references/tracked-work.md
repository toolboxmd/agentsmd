# Tracked work

These rules moved here from the core `global/AGENTS.md` and bind as if they
were written there. The core sends you here before you change code or other
tracked files, create a branch or commit, or create, edit, or comment on a
GitHub Issue or PR.

## Issues and PRs

- When you own a task's Issue or PR, put evidence, commands, SHAs, test output,
  and per-step delivery states there and link it. Keep disposable scripts, raw
  traces, and unselected variants out of tracked source. Procedures that require a
  report mean that record, not the chat reply. Read-only work (reviews, audits,
  questions) reports to the user and writes nothing to Issues or PRs unless
  asked. Filing found problems under Work is the exception.
- Start every Issue and PR you write with a Human summary of three lines:
  **What** (the result, one plain sentence), **Why** (the problem or its root
  cause, one sentence), **So what** (what happens next and who does it; name
  the user only for a Human Gate or a user-owned decision). A reader must be
  able to stop there. Agent detail follows.
  Update the summary when the state changes, such as a new blocker or decision.
- Keep the diff to the task. When you find a problem outside it, search the
  owner's repository for an open Issue, at once comment on it or file one, then
  continue your task. File problems in repositories the user does not control,
  or that only the user can fix (hardware, accounts, billing, credentials, app
  settings), in the private tracker that preferences name; if none is named,
  tell the user.

Every Issue and PR carries an Elon record; the Project Direction hook blocks `gh issue
create` and `gh pr create` when a field is missing or empty.

## Delivery

Before mutating, check status, branch, HEAD, remotes, intended base, and
divergence, and apply Authority and continuation. For tracked substantive work,
find or create the GitHub Issue in the owning repository and use a task branch.
An Issue needs outcome, acceptance criteria, non-goals, blockers, proof, and an
Elon record. Create and edit Issues and PRs with `gh issue` and `gh pr` in the
shell, not the raw API or another GitHub tool, so the Elon gate sees them. Use one final approval PR per outcome; decompose through reviewed
component PRs. Read-only work, spikes, WIP checkpoints, and explicitly local
microfixes skip the Issue-to-PR lane. Natural requests and phase changes
select `operations` procedures without a mode command. Planning procedures
retain their concrete human decision and approval gates.

Direct work: inspect, edit, run relevant checks, bump the version, then commit
and push within authority. Create no Issue or worker purely for ceremony.

## Execution

The planner is the top-level agent the user works with. It owns reasoning, specs,
integration, acceptance, and the outcome. Delegate when it reduces total work
or provides required independence. Count briefing and checking costs.
Preserve explicit user choices and required review.

Delegate through the routing tool when one is available; it owns model, effort,
roles, execution, and recovery for the work it accepts. If it cannot run the
work, stop only the affected dispatch and report it; never substitute another
route silently. A delegated failure returns to the planner as a decision with
evidence. The planner decides; it implements that work only on explicit user
instruction.

## Authority for GitHub implementation

- A requested GitHub implementation includes Issue updates, an exclusive branch
  and workspace, implementation, proof, versioning, commits, push, and PRs.
  Final PR merges require human approval for the task and intended base.
  Approval to merge or ship carries through routine fixes, retries, and
  follow-up or replacement PRs needed to complete that same task. Changed
  commits, versions, or PR numbers alone do not require another approval.
  Required review and proof still apply to each current candidate. Human Gates
  still apply.
  Before an external mutation, verify the live target and authority. After the
  mutation, verify the resulting live state before reporting success.
- One writer per branch, workspace, and file set. Concurrent writers need
  separate workspaces and disjoint scopes. Ownership also covers shared
  services, databases, ports and deployment targets. Reuse your own task
  workspace to continue.
- Do not claim affected-only checks as a complete gate unless the trusted
  scoped-proof policy allows it.

## Project truth

| Owner | Content |
| --- | --- |
| Root direction triad | Current confirmed direction; Git owns prior states. |
| Project `AGENTS.md` | Operational deltas and pointers: checkouts, critical seams, build and proof commands, release ownership, proof limits. |
| GitHub Issues | Active intent, acceptance criteria, blockers, proof. |
| Code, tests, configuration | Implementation truth. |
| `README.md` | User documentation. |
| `GLOSSARY.md` | Project language. |
| ADRs | Costly, surprising, hard-to-reverse decisions. |
| `CHANGELOG.md` | Released outcomes. |

Root `TODO.md`, `ISSUES.md`, `IDEAS.md`, and `STATUS.md` are legacy input ledgers,
never trackers: move unique entries to the owners above before any authorized
deletion. Use `GOAL_TEMPLATE.md` only when Issue state lacks needed continuation.

## Handoff

Worker handoffs and interrupted-work recovery use the durable handoff in the
operations orchestration module. Record the full state (commit, checks,
delivery states, unchecked areas) in the Issue or PR. The final chat reply
gives the result, anything unfinished, and what needs the user, per
Communication. Claim a delivery state only when its evidence exists.
