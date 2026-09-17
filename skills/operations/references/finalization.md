# Delivery Finalization

- Delivery Finalization starts only after review and a verified terminal
  disposition: merge, approved alternative delivery, cancellation,
  duplication, supersession, or equivalent conclusive closure. Internal
  component integration is not terminal.
  An open pull request or review-ready candidate is not terminal. Successful delivery
  requires required code and documentation integrated into the intended base
  and every required delivery step verified before finalization, including
  deployment when required. A local-only required change is unfinished work.
  Cancellation, supersession, and other conclusive closures follow their
  verified disposition instead.

- Remove only clean, exact, task-owned transient resources that no remaining
  stack layer needs: local and remote branches, worktrees, disposable
  checkouts, temporary files, task processes, containers, images, sockets,
  ports, locks, PIDs, and explicitly disposable credentials, test accounts,
  or previews. Authority to create an explicitly disposable resource includes
  its teardown after the terminal-outcome, ownership, and need checks pass.
  Age or cleanliness alone never proves ownership or removal eligibility.

- Check every temporary checkout for removal after the required verified
  outcome. Within granted authority, retire obsolete task processes and replace
  cross-worktree dependency links with a stable arrangement, verify affected
  consumers still work, then remove the obsolete checkout. Preserve remaining
  stack needs and unrelated active work. Moving live databases or changing
  protected resources requires applicable authority and proof.

- Preserve Issues, pull requests, commits, tags, releases, proof, and other
  durable truth in their canonical locations. Verify existing Git history and
  durable records before relying on them; unpublished work is not assumed
  remotely recoverable. Preserve identified required information lacking a
  durable copy. Uniqueness alone does not establish importance. Generated
  packages, build output, disposable fixtures, and superseded experiments need
  no default archive or indefinite retention once verified disposable. Required
  evidence remains durable; redundant copies do not require their checkout.

- Preserve persistent, shared, production, materially changed, protected, gated,
  dirty, active, user-owned, or ambiguous resources until applicable authority
  exists. Inspect unique work before classifying it. For every retained
  exception, record the exact target, current need or unresolved condition,
  owner where known, and next action. Continue independent eligible cleanup.
  Transfer unknown residue to Repository Reconciliation with its exact path,
  branch, `HEAD`, files, reason, and next action; report the outcome closed but
  not fully finalized while classification or task-owned obstacles remain.
  Verify every removal's exact after-state and record cleanup or retained
  exceptions in the durable handoff. A verified continuing need may justify
  retention; an unresolved obstacle does not establish completed finalization.

- Use native closing linkage only for a pull request that fully resolves the
  Issue, and use references for partial work. Close parents only after their
  acceptance criteria are satisfied and required children are terminal. Close
  proof or experiment Issues after recording their evidence or decision. Close
  duplicate or superseded Issues with a durable link, keep deferred work open,
  and never delete Issues.

- Report outcome, review, merge, closure, cleanup, finalization, and behavioral
  Live Verification separately.

Read [legacy reconciliation](reconciliation.md) before mutating legacy
resources or recovering cleanup without immediate-check evidence.