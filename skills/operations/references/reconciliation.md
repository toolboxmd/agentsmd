# Repository Reconciliation

- Repository Reconciliation is a bounded repair path triggered when orientation
  detects drift. Run it only for the identified drift, not as a daemon or a full
  sweep on every task. Refresh exact repository, tracker, settings, workspace,
  process, temporary-resource, dependency, and ownership evidence. For every
  candidate, record its exact identity, evidence, classification, proposed
  action, reversibility, reason, and next action.

- Obtain one scoped batch approval before mutating legacy resources. Cleanup
  execution must query each approved target's live owning Issue, pull request,
  and exact resource state immediately before mutation. Record each exact
  target, observed state, timestamp, source, and result from those responses.
  Bind them to the pending mutation: accept observations no older than 60
  seconds and never after the recorded mutation timestamp. Narrative claims
  are not evidence. Bind one approved manifest identity across the request,
  mutation, recovery, and restoration: candidate ID, exact target, branch,
  commit, owning Issue and pull request, expected states, action, force flag,
  and branch-deletion flag. Apply only an approved action whose
  structured observations all match the manifest; otherwise preserve it.
  The approval record carries a canonical SHA-256 over that exact target,
  action, force=false, and branch-deletion=false. Each request and pending
  or completed mutation must repeat and match the approved values and digest
  before execution, recovery, or restoration proceeds.
  Load that recorded approval from its durable approval evidence separately
  from mutable execution, recovery, and restoration claims. Select the durable
  approval record and its expected byte digest outside the mutable workflow
  input; the workflow cannot supply or replace either value.
  Verify every exact after-state. Preserve unknown, dirty, active, shared,
  persistent, unique, user-owned, ambiguous, protected, and materially changed
  state. Keep historical evidence and deferred or incomplete work truthful; a
  proven unrelated preserved resource does not keep the original delivery open.
  Report inspected, proposed, approved, cleaned, closed, preserved, reconciled,
  released, and Live Verified states separately.

- If an authorized cleanup completed without immediate-check evidence, recover
  without notifying the user or requesting another approval when authoritative
  event history proves every precondition held continuously, the exact targets
  match, retained branches and commits remain recoverable, and authority is
  unchanged. Record the omission, interval proof, contract regression, and
  result. When history proves a precondition failed, restore the exact prior
  worktree from its preserved branch and commit without conflict or data loss.
  Recovery reuses the approved target and action; it does not add cleanup
  targets, delete branches, use force, or broaden authority.
  Escalate only when restoration is unsafe, proof is unavailable or ambiguous,
  target or authority expands, uncommitted or user data may be affected, or a
  user-owned decision remains.
