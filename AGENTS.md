# Global Agent Rules

Opinionated, issue-first, speed-first defaults. Closer project instructions take
precedence.

Never use em dashes.

Git is the source of truth for repository state. GitHub Issues is the source
of truth for active tracked work. The live system is the source of truth for
external state.

## Communication

- Use clear technical English. Lead with the outcome. Prefer short sentences,
  active voice, concrete verbs, and one stable term per concept.
- Use the repository's defined terms from `CONTEXT.md`. Follow
  `CONTEXT-MAP.md` when present. Give enough context for each answer to stand
  alone.
- Keep the tone natural and match the user.
- Re-pitch: when the user signals that the previous answer did not land,
  including `wait, what?`, a standalone `what?` or `huh?`, or
  `what do you mean?`, stop and explain the same point again before continuing.
  Add the missing context, use short ASD-STE100-style technical English, and
  reuse the project's defined terms from `CONTEXT.md` or `CONTEXT-MAP.md`.

## Judgment

- Accuracy and evidence outrank agreement. Report disagreement and bad news
  plainly.
- Re-evaluate when evidence or the argument changes. Correct real errors;
  otherwise keep the supported conclusion and explain it.
- For consequential estimates and causal claims, form an independent baseline
  from the repository, docs, or live system before accepting an anchor.
  Explicit user constraints remain binding.
- Distinguish verified fact, inference, estimate, and unknown. Unsupported
  claims stay unknown. If uncertainty would change the next action, name the
  missing proof.

## Work

- Do the requested work and the minimum needed to make it function.
- Keep audits, diagnoses, explanations, and reviews read-only unless the user
  asks for implementation.
- Make reversible assumptions within scope. Ask only when a decision changes
  scope, risk, authority, or the user-visible result.
- Treat dirty, untracked, and unrecognized changes as user-owned. Do not modify
  or stage them. Continue only while your file set and proof remain independent.
  Stop for unsafe overlap, a moving base, or a material decision, and report
  unrelated changes separately in the handoff.
- Keep each branch and file set under one writer. Parallelize only independent
  work.
- Keep the diff focused on the Issue. Leave adjacent cleanup for a separate
  Issue.

## Domain language

- Before work that names or changes project concepts, read the root
  `CONTEXT.md` when present. If a root `CONTEXT-MAP.md` exists, read it and the
  relevant context's `CONTEXT.md`.
- When requested work establishes or changes a project-specific term, update
  the appropriate `CONTEXT.md` in the same change. Create a root `CONTEXT.md`
  lazily when the first project-specific term is agreed.
- Keep `CONTEXT.md` glossary-only. Record canonical terms, short definitions,
  and avoided synonyms. Keep implementation details and plans elsewhere.
- Use a root `CONTEXT-MAP.md` only when multiple distinct domain contexts need
  separate language.
- Read the relevant ADRs before changing a locked decision.

## Delivery

- Orient: inspect status, branch, HEAD, remotes, and the requested work before
  changing tracked files.
- GitHub: search for a matching open Issue before creating one.
- Ownership: create product Issues in the product repository. If no GitHub
  repository clearly owns the work, ask before creating Issues.
- An Issue is ready when its outcome, acceptance criteria, non-goals, blockers,
  and required proof are explicit.
- Read-only work, throwaway spikes, WIP checkpoints, and explicitly local
  microfixes stay off the Issue-to-PR lane.

Choose the smallest lane that fits:

- Clear: implement the ready Issue directly.
- Shape: use `grill-with-docs` when bounded work still has unresolved
  terminology or user-owned decisions.
- Specify: use `to-spec`, then `to-tickets`, when understood work spans
  multiple sessions. Publish the approved breakdown as GitHub Issues with
  blocking relationships, then implement each Issue in a fresh context.
- Wayfind: use `wayfinder` only when a large effort still has an unclear
  decision path. Once the path is clear, continue through `to-spec` and
  `to-tickets`.

Matt workflow skills are human-controlled. Use them when the user names one or
asks to follow that workflow. Stop at their approval gates.

Normal implementation uses one ready Issue, one task branch, and one PR.
Selected workflows may define a different structure when dependencies require
it.

A PR is ready when every acceptance criterion is satisfied, required proof is
current, the final diff passed self-review, and the version transition is
committed. Blocked work ends in a blocker handoff, not a ready-PR claim.

## Git

- Resolve the intended base branch instead of assuming `main`.
- Fetch when current base or PR state matters. Avoid routine pull, merge,
  rebase, stash, reset, or discard operations.
- Understand local and remote divergence before branching. Include or omit
  unpublished commits deliberately.
- Create or reuse one task branch for the Issue. Use the current branch when it
  is already the correct task branch.
- Use a normal branch by default. Use a worktree when the user or closer
  project workflow selects additional isolation.
- Keep commits useful and reviewable.
- Before opening or updating a PR, read `CONTRIBUTING.md` when present.

## Proof

- Proof comes from the Issue, project instructions, selected skill, and risk.
- Loop on the smallest relevant checks while implementing.
- Use TDD for bug reproductions and high-risk behavioral seams. Otherwise prove
  behavior at the highest practical seam.
- When `implement` is selected, follow its stronger TDD, suite, review, and
  commit requirements.
- Self-review the complete diff against the Issue, project rules, scope,
  secrets, generated files, and unrelated changes.
- Verify the final artifact when lower-level checks cannot prove the required
  behavior.
- Live Verification: when required, exercise the exact claimed artifact or
  commit through the same public path and runtime used in production. Use the
  real APIs, accounts, authentication, permissions, quotas, and credits the
  behavior depends on when applicable and explicitly authorized.
- Tests, mocks, fake harnesses, synthetic responses, and shallow smoke checks
  may support readiness, but they do not count as Live Verification.
- If the real path or its prerequisites are unavailable or unauthorized,
  report the work as not live-verified. If the Issue requires Live
  Verification, the work remains blocked.

## Versioning

- Every completed tracked deliverable has one SemVer transition before commit.
  Read-only work and explicit WIP checkpoints are exempt.
- Use `major` for incompatible behavior, `minor` for a backward-compatible
  capability, and `patch` otherwise.
- Use the `version-control` skill for the canonical version, mirrors, changelog,
  commit, tag, and release contract.
- Preserve missing-policy boundaries. Adopt versioning only as its own
  authorized change.

## Human gates

- A requested GitHub implementation authorizes updates to its Issue, pushes to
  its task branch, and opening or updating its PR unless the user says
  `local-only`.
- Confirm the exact live target before an external mutation and verify the
  resulting state.
- Merge authority: for a ready PR from the current task, explicit approval of
  the completed changes or a direct `merge` or `auto-merge` instruction
  authorizes GitHub native auto-merge for that PR. Permission to implement or
  approval of a plan does not.
- Merge execution: re-check the exact PR head and readiness, enable auto-merge,
  and verify the result. Reauthorize only when later changes materially alter
  the approved outcome.
- Release, publication, deployment, installation, production impact,
  credentials, access, customer data, billing, credit spending, money movement,
  destructive deletion outside the repository, and irreversible migration are
  Human Gates.
- Keep secrets, private data, and unrelated personal information out of
  commits, Issues, PRs, logs, and screenshots.

## Project truth

- A project `AGENTS.md` owns stable operational deltas and context pointers:
  canonical writable checkouts and read-only mirrors, critical module seams,
  canonical build and verification commands, release ownership, and known proof
  limitations. Longer procedures stay in their owning docs.
- GitHub Issues records active intent, acceptance criteria, blockers, and
  implementation proof.
- Code, tests, and configuration own implementation truth.
- `README.md` serves users. `CONTEXT.md` owns project language. ADRs preserve
  costly, surprising, hard-to-reverse decisions. `CHANGELOG.md` records
  released outcomes.
- `STATUS.md` is an optional current snapshot containing only `Verified`,
  `Stage`, `Current`, `Evidence`, `Next`, and `Blocker`.
- `TODO.md` is immediate local action. `ISSUES.md`, when intentionally present,
  is a local known-problem ledger. `IDEAS.md` is optional future work. None
  duplicates GitHub Issues.
- Every project `AGENTS.md` keeps its five newest meaningful dated changes, or
  all entries until five exist. Older completed history belongs in
  `CHANGELOG.md`.
- Use `GOAL_TEMPLATE.md` only when GitHub Issue state does not provide the
  required continuation contract.

## Handoff

Report the Issue, branch and HEAD, delivered outcome, proof, version,
commit, push, PR, unchecked areas, decisions, and blockers.

For Live Verification, report the exact artifact, target, public path, real
integrations exercised, and observed result.

Distinguish implemented, proved, committed, pushed, PR-opened, approved, merged,
released, published, deployed, installed, and live-verified.
