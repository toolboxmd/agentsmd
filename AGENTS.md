# Global Agent Rules

Opinionated, issue-first, speed-first defaults. Closer project instructions take
precedence.

Never use em dashes.

Git is the source of truth for repository state. The live system is the source
of truth for external state. The configured issue tracker owns active intent.

## Work

- Do the requested work and the minimum needed to make it function.
- Keep audits, diagnoses, explanations, and reviews read-only unless the user
  asks for implementation.
- Make reversible assumptions within scope. Ask only when a decision changes
  scope, risk, authority, or the user-visible result.
- Preserve dirty and untracked user work. Stop for unsafe overlap, a moving
  base, or a material decision.
- Keep each branch and file set under one writer. Parallelize only independent
  work.
- Keep the diff focused on the source issue. Leave adjacent cleanup for a
  separate issue.

## Delivery

- Orient: inspect status, branch, HEAD, remotes, and the requested work before
  changing tracked files.
- Tracker: before tracker reads or writes, read
  `docs/agents/issue-tracker.md` when present.
- Domain: before changing terminology or a locked decision, read `CONTEXT.md`
  and the relevant ADRs when present.
- Issue-first: requested tracked implementation in a GitHub-backed repository
  uses an existing or new GitHub issue, one task branch, and one PR unless the
  user says `local-only` or closer project rules choose another workflow.
- Search before creating an issue. Reuse a matching open issue.
- An issue is ready when its outcome, acceptance criteria, non-goals, blockers,
  and required proof are explicit.
- Read-only work, throwaway spikes, WIP checkpoints, and explicitly local
  microfixes stay off the issue-to-PR lane.

Choose the smallest lane that fits:

- Clear: implement the ready issue directly.
- Shape: use `grill-with-docs` when bounded work still has unresolved
  terminology or user-owned decisions.
- Specify: use `to-spec`, then `to-tickets`, when understood work spans
  multiple sessions.
- Wayfind: use `wayfinder` only when a large effort still has a foggy decision
  path before it can be specified.

Matt workflow skills are human-controlled. Use them when the user names one or
asks to follow this workflow. Stop at their approval gates.

Implement one vertical ticket in one fresh context. A vertical ticket delivers
a narrow, complete, independently provable outcome.

A PR is ready when every acceptance criterion is satisfied, required proof is
current, the final diff passed self-review, and the version transition is
committed. A blocked issue ends in a blocker handoff, not a ready-PR claim.

## Git and proof

- Resolve the intended base branch instead of assuming `main`.
- Fetch when current base or PR state matters. Avoid routine pull, merge,
  rebase, stash, reset, or discard operations.
- Understand local and remote divergence before branching. Include or omit
  unpublished commits deliberately.
- Create or reuse one task branch for the implementation issue. Use the current
  branch when it is already the correct task branch.
- Use a normal branch by default. Use a worktree when the user or closer
  project workflow selects additional isolation.
- Keep commits useful and reviewable.
- Loop on the smallest relevant checks while implementing.
- Proof comes from the issue, project instructions, selected skill, and risk.
- Use TDD for bug reproductions and high-risk behavioral seams. Otherwise prove
  behavior at the highest practical seam.
- When `implement` is selected, follow its stronger TDD, suite, review, and
  commit requirements.
- Self-review the complete diff against the issue, project rules, scope,
  secrets, generated files, and unrelated changes.
- Verify the final artifact when a build, unit test, fake harness, or HTTP
  response cannot prove the required behavior.
- PR: before opening or updating a PR, read `CONTRIBUTING.md` when present.

## Versioning

- Every completed tracked deliverable has one SemVer transition before commit.
  Read-only work and explicit WIP checkpoints are exempt.
- Use `major` for incompatible behavior, `minor` for a backward-compatible
  capability, and `patch` otherwise.
- Use the `version-control` skill for the canonical version, mirrors, changelog,
  commit, tag, and release contract.
- Preserve missing-policy boundaries. Adopt versioning only as its own
  authorized change.
- Report version, commit, push, PR, merge, tag, release, publication,
  deployment, installation, and live verification as separate states.

## External actions and human gates

- A requested GitHub implementation authorizes source-issue updates,
  task-branch pushes, and opening or updating its PR unless the user says
  `local-only`.
- Confirm the live target before an external mutation and verify the resulting
  state.
- Merge, auto-merge, release, publication, deployment, installation,
  production impact, credentials, access, billing, money movement, destructive
  deletion outside the repository, and irreversible migration are human gates.
- Keep secrets, private data, and unrelated personal information out of
  commits, issues, PRs, logs, and screenshots.

## Project truth

- `AGENTS.md` owns stable operating rules and context pointers.
- Issues own active intent, acceptance criteria, blockers, and implementation
  evidence.
- Code, tests, and configuration own implementation truth.
- `README.md` serves users. `CONTEXT.md` is a glossary. ADRs preserve costly,
  surprising, hard-to-reverse decisions. `CHANGELOG.md` records released
  outcomes.
- `STATUS.md` is an optional current snapshot containing only `Verified`,
  `Stage`, `Current`, `Evidence`, `Next`, and `Blocker`.
- `TODO.md` is immediate local action. `ISSUES.md`, when intentionally present,
  is a local known-problem ledger. `IDEAS.md` is optional future work. None
  duplicates the configured tracker.
- Every project `AGENTS.md` keeps its five newest meaningful dated changes, or
  all entries until five exist. Older completed history belongs in
  `CHANGELOG.md`.
- Use `GOAL_TEMPLATE.md` only when tracker state does not provide the required
  continuation contract.

## Handoff

Report the source issue, branch and HEAD, delivered outcome, proof, version,
commit, push, PR, unchecked areas, decisions, and blockers.

Distinguish implemented, proved, committed, pushed, PR-opened, approved, merged,
released, published, deployed, installed, and live-verified.

## Recent Changes

- 2026-08-26: Added the compact issue-first delivery contract and size-gated
  routing to Matt Pocock's workflow skills.
- 2026-08-21: Packaged the version-control skill and CLI as the `agentsmd`
  plugin, with Claude-compatible metadata kept separate from host verification.
- 2026-08-21: Added repository SemVer rules and the shared `version-control`
  skill and CLI contract.
- 2026-08-21: Removed redundant per-harness Goal-template links; the global
  rules now resolve the bundled template beside their canonical source.
- 2026-08-21: Published the harness-neutral global rules and shared Goal
  contract.
