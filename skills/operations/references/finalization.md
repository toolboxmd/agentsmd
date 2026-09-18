
# Delivery Finalization

Begin only after review and a verified terminal disposition: merge, approved
alternative delivery, cancellation, duplication, supersession, or equivalent
closure. Internal integration and open/review-ready PRs are not terminal.
Successful delivery requires code/docs in the intended base and all required
steps verified, including deployment when required. Required local-only changes
remain unfinished. Conclusive cancellations/supersessions follow their verified
disposition instead.

## Resources

Remove only clean, exact, task-owned transient resources no stack layer still needs:
local/remote branches, worktrees/checkouts, temporary files, processes, containers,
images, sockets, ports, locks, PIDs, and explicitly disposable credentials, test
accounts, or previews. Authority to create explicitly disposable resources includes
teardown after terminal-outcome, ownership, and need checks. Age/cleanliness alone
never establishes eligibility.

Check every temporary checkout for removal. Within authority, retire obsolete
processes and replace cross-worktree dependency links with stable arrangements;
verify consumers before removal. Preserve stack needs and unrelated active work.
Moving live databases or changing protected resources requires authority and proof.

Preserve Issues, PRs, commits, tags, releases, proof, and durable truth in canonical
locations. Verify history/records before relying on recoverability; unpublished
work is not assumed remotely recoverable. Preserve required information lacking
a durable copy, but uniqueness alone does not establish importance. Verified
disposable packages, builds, fixtures, and superseded experiments need no archive
or indefinite retention. Redundant evidence copies need no retained checkout.

Preserve persistent, shared, production, materially changed, protected, gated,
dirty, active, user-owned, or ambiguous resources until authorized. Inspect unique
work before classification. For each exception record exact target, current need
or unresolved condition, known owner, and next action. Continue eligible independent
cleanup. Send unknown residue to [Reconciliation](reconciliation.md) with exact path,
branch, HEAD, files, reason, and next action. Report closed but not fully finalized
while classification or task-owned obstacles remain. Verify each removal's after-state
and record cleanup/exceptions in the handoff. Verified continuing need permits
retention; unresolved obstacles do not prove completed finalization.

## Tracker and reporting

Use native closing linkage only for full Issue resolution, references for partial
work. Close parents after acceptance and required children are terminal. Close
proof/experiment Issues after recording evidence/decision; duplicates/supersessions
need a durable link. Keep deferred work open; never delete Issues.

Report outcome, review, merge, closure, cleanup, finalization, and behavioral Live
Verification separately. Before legacy mutation or cleanup recovery without
immediate-check evidence, read [Reconciliation](reconciliation.md).
