# Global Agent Rules

Opinionated, speed-first defaults. Closer project instructions take precedence.

Never use em dashes.

Git is the source of truth for repository state; the live system is the source
of truth for external state.

## Work

- Do the requested work and the minimum needed to make it function.
- Do not turn audits, diagnoses, explanations, or reviews into implementation
  unless asked.
- Make reasonable, reversible assumptions that do not change scope or risk.
  Ask only for decisions that materially affect the result.
- Do not add speculative cleanup, hardening, refactors, or adjacent features.
- Dirty trees and broad diffs are not blockers. Preserve user work. Stop only
  for unsafe overlap, a moving HEAD, or a material decision.
- Use one writer per branch and file set. Delegate only independent work.

## Git and checks

- Inspect status, branch, and HEAD. Work on the current branch. Do not create
  branches, worktrees, PRs, or reviews unless asked.
- Fetch only when current remote state matters. Do not routinely pull, merge,
  rebase, stash, reset, or discard work.
- Keep diffs focused. Prefer scoped formatters. If a required formatter expands
  the diff, inspect, continue, and report unless user work is at risk.
- Make small commits and commit useful work before handoff. Push only to a
  known non-deploying remote; otherwise ask.
- Tests are not the default deliverable. Run at most one cheapest existing
  happy-path check. Do not create test infrastructure or run broad suites unless
  asked or required by project rules.
- Verify the final artifact when an intermediate build is insufficient. If no
  cheap relevant check exists, run none and say so.

## External actions and secrets

- Before external changes, confirm live state and target. Preview when possible
  and verify the result. Accepted or queued is not completed.
- Ask before production impact, publication, credential or access changes,
  irreversible migrations, destructive deletion outside the repository,
  billing, money movement, or merge.
- Do not read, expose, or commit secrets or private data unless required.

## Project files

- Keep architecture, commands, pitfalls, checks, and deployment rules in the
  project `AGENTS.md`. Prefer a `CLAUDE.md` symlink when both names are needed.
- Every project `AGENTS.md` keeps its five newest meaningful dated changes, or
  all entries until five exist. Older history belongs in `CHANGELOG.md`.
- `STATUS.md` is an optional current snapshot containing only `Verified`,
  `Stage`, `Current`, `Evidence`, `Next`, and `Blocker`.
- `CHANGELOG.md` is completed history, `TODO.md` is open actions, `ISSUES.md` is
  known problems, and `IDEAS.md` is uncommitted options. Do not mix their roles.
- Use the bundled `GOAL_TEMPLATE.md` for long-running work. If unavailable,
  ask instead of inventing a format.

## Handoff

Report changes, branch and HEAD, commit and push state, the one check or none,
unchecked areas, and any decision or wait. Distinguish implemented, tested,
committed, pushed, deployed, published, and live-verified when relevant.

## Recent Changes

- 2026-08-21: Published the harness-neutral global rules and shared Goal
  contract.
