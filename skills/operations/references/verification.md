
# Verification

Proof comes from the Issue/authorized task, project instructions, selected
procedure or external Skill, and risk. Use TDD for bug reproductions and high-risk behavioral seams; otherwise
test the highest practical seam. Read [test design](test-design.md) when designing
behavioral proof; it owns faithful seams, independent oracles, and failing-before
evidence. Use [code-review](../workflows/code-review/index.md) for review method and impact analysis. Self-review the complete diff for acceptance, rules,
scope, secrets, generated files, and unrelated changes. Verify the final artifact
when lower-level checks cannot prove required behavior.

When an existing test fails after an intended change, decide what it protects
before editing it. Delete a test that protects no valid requirement. Rewrite one
that froze incidental detail, such as exact lists, counts, order, or whole
snapshots, to assert the requirement so the next compatible addition passes.
Otherwise fix the code. Never only update expected values to the new output.
Report which case applied.

For a claimed reproduction or fix, name the expected state, broken state, and
observation that distinguishes them. Inspect evidence, not just its existence or
a worker's summary. [project-verification](../workflows/project-verification/index.md) owns reusable product-driving recipes
and [observations](../workflows/project-verification/references/observations.md).
For a visual-preservation contract, read [visual parity](visual-parity.md).
For an explicitly requested model/workflow evaluation, read [evaluation](evaluation.md).
These methods do not add synthetic behavioral release gates or override a
Project's declared proof boundary.

Before driving the product, read its existing verification pointer from project
`AGENTS.md`, or `.toolboxmd/verification/index.md` when present. Pass that exact
path to workers and read it directly; isolated Model Router kits do not discover
project skills. If missing support prevents a reliable observation, select
[Project verification](../workflows/project-verification/index.md). Ordinary
repository checks need no new verification procedure.

For retained observations, use [artifact placement](artifacts.md). CI results
and runner-owned reports keep their existing durable owners.

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
scoped proof, read [its contract](scoped-proof.md): a trusted explicit
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
