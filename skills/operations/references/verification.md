# Verification

- Proof comes from the Issue or authorized direct task, project instructions, selected skill, and risk.
- Use TDD for bug reproductions and high-risk behavioral seams. Otherwise prove
  behavior at the highest practical seam.
- When `implement` is selected, follow its stronger TDD, suite, review, and
  commit requirements.
- Self-review the complete diff against the Issue or authorized direct task,
  project rules, scope,
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

- Give each authored implementation slice an independent Codex review against
  its exact SHA through the core execution routing contract, unless it consists
  solely of an exact user-approved prose replacement, matching expected-text
  assertions, and required version bookkeeping. Self-review and relevant
  checks still apply. A deterministically generated
  Toolybara promotion pull request uses generated-scope validation instead.
  Apply a lower-layer review fix in the earliest owning layer, checkpoint every
  descendant, rebase it onto the corrected exact SHA, and re-prove every
  affected head without losing later work.

- Use GitHub-hosted runners for ordinary CI and release builds. Project-owned
  proof adapters may choose the appropriate host for reusable affected tests.
  Reserve Rocky for agentic development and genuine macOS proof, Cavallo for
  human control
  and acceptance, and Bigbrain for activation, health checks, and rollback of
  trusted artifacts. Untrusted pull request code does not run on
  production-connected infrastructure.

- The complete merge gate proves the whole required merge unit; the complete
  release gate binds that coverage and release identity to the exact release
  SHA. When declaring or reusing scoped proof, read [the scoped-proof
  contract](../../../docs/scoped-proof.md). A Project's trusted explicit
  policy may compose unaffected complete-baseline coverage with current
  affected and artifact proof. An ordinary changed-scope check remains
  feedback. Unsupported scope stops with a reason; select the complete path
  explicitly. Report executed, reused and unverified proof separately. Keep
  independent review and fresh external-state checks.

- Evidence binds the owning Issue or authorized direct task, branch, exact
  base and head SHAs, commands, results, review identity and verdict, version
  transition, artifact digest, external target, authority, timestamps where
  state can drift, and each lifecycle state. A summary or earlier run never
  replaces exact current proof.

- Assign each required check an owner and retain its command, result and exact
  candidate. Reuse valid proof from that owner; coordinator and worker need
  not rerun identical checks against an unchanged candidate with unchanged relevant
  environment and input assumptions. Changed inputs,
  stale external state or incomplete evidence require affected revalidation
  under the scoped-proof contract, or the complete path when unsupported.
  This does not waive independent review, release identity, complete coverage,
  or fresh external-state checks.
