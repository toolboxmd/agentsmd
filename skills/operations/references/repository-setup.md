# Repository capability setup

Reuse established capability evidence while its assumptions remain valid. This
module applies to an unverified required capability, settings change or detected
capability drift, not an automatic full inspection for every PR. Keep fresh
mutable target, permission and candidate checks at the action boundary.

- Repository capability setup starts with `inspection`: inspect the exact
  repository read-only before relying on its delivery capabilities. Record the
  default branch, applicable requirements, native Issue dependencies and
  dependent work, branch creation and push, closing linkage, the authorized
  ready-PR merge path, and local and remote branch retirement. Verify each
  capability from current evidence; report an unsupported capability
  explicitly.

- If inspection finds a required gap, record `proposed setup`: one complete
  setup bundle with the exact current state, proposed settings, expected
  effect, risks, and rollback path. At `approval`, obtain one scoped user
  approval before any `settings mutation`, then apply only that bundle without
  another prompt. Reuse that authority while the exact settings and risk
  remain unchanged. Require new authority when the settings, target, or risk
  changes materially.

- At `verification`, verify every approved mutation and that no unapproved
  repository setting changed before reporting success. A zero-mutation bundle
  needs no approval; record it and prove that no repository setting changed.
  Keep inspection, proposed setup, approval, settings mutation, and
  verification as separate states.
