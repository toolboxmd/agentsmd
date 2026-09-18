
# Verification

Proof comes from the Issue/authorized task, project instructions, selected Skill,
and risk. Use TDD for bug reproductions and high-risk behavioral seams; otherwise test the highest
practical seam. Selected `implement` retains its stronger TDD, suite, review,
and commit requirements. Self-review the complete diff for acceptance, rules,
scope, secrets, generated files, and unrelated changes. Verify the final artifact
when lower-level checks cannot prove required behavior.

## Live Verification

When required, exercise the exact artifact/commit through the production public
path and runtime, with real APIs, accounts, auth, permissions, quotas, and credits
where applicable and explicitly authorized. Tests, mocks, fake harnesses, synthetic
responses, and shallow smoke checks are not Live Verification. If prerequisites
are unavailable/unauthorized, report not live-verified; required Live Verification
remains blocked.

## Independent review

Each authored implementation slice needs independent Codex review of its exact
SHA under core execution routing. The exception is a slice consisting solely of an exact
user-approved prose replacement, matching expected-text assertions, and required version
bookkeeping; self-review and relevant checks still apply.

A deterministically generated promotion PR may use generated-scope validation only
when a trusted generator reproduces its exact diff from reviewed inputs, all changes
lie within declared generated paths, and exact-candidate validation proves this.
Authored changes retain review. Before applying review fixes to dependent layers,
read [orchestration](orchestration.md) for the stack-fix procedure.

## Hosts and complete coverage

Use GitHub-hosted runners for ordinary CI/release builds; Project proof adapters
may choose hosts for reusable affected tests. Development hosts serve agent work
and platform proof, human workstations acceptance. Production-connected hosts
serve only authorized trusted-artifact activation, health checks, and rollback;
never run untrusted PR code there.

The complete merge gate covers the whole merge unit. The complete release gate
binds coverage and identity to the exact release SHA. Before declaring/reusing
scoped proof, read [its contract](../../../docs/scoped-proof.md): a trusted explicit
Project policy may combine unaffected complete-baseline coverage with current
affected/artifact proof. Ordinary changed-scope checks remain feedback. Unsupported
scope stops with a reason; explicitly choose complete proof. Report executed,
reused, and unverified coverage separately. Retain independent review and fresh
external-state checks.

## Evidence and reuse

Bind evidence to Issue/task, branch, exact base/head, commands/results, reviewer/
verdict, version transition, artifact digest, external target, authority, timestamps where state can drift, and lifecycle state. Summaries or earlier runs cannot
replace exact current proof.

Assign each check an owner and retain command, result, and exact candidate.
Coordinator/worker may reuse that proof without duplicate runs when candidate,
relevant environment, and input assumptions are unchanged. Changed inputs, stale
external state, or incomplete evidence require affected revalidation under scoped
policy, otherwise complete proof. Reuse never waives independent review, release
identity, complete coverage, or fresh external-state checks.
