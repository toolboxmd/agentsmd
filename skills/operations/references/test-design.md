# Design behavioral proof

Choose the cheapest seam that retains the risk: the real parser for captured
bytes, a public API for its contract, or a real event sequence for a focus or
timing defect. Compile success does not prove behavior. A broad harness can also
miss a defect when it never reaches the discriminating state.

For a regression or high-risk change, establish a failing-before case when
practical, then make the smallest change and show the same case passes. Verify
the initial failure has the intended cause rather than broken setup. If baseline
execution is unavailable, state the gap and use the strongest valid alternative
evidence; do not claim a red/green cycle that did not run. Required project gates
still apply.

Choose expected outcomes independently of the implementation. An expected URL
built with the same helper under test may repeat the same bug. Literal examples,
known fixtures, independent reference implementations, invariants, and metamorphic
relations can all supply valid oracles. Differential agreement needs additional
evidence when both implementations could share a defect.

Name a plausible faulty implementation that the check rejects. Replacing a
subject with `undefined` can expose a weak positive test, but it is not a universal
criterion or a blacklist of assertion names. Negative authorization, absence of
an effect, thrown errors, type errors, and interaction payloads are real behavior.
Pair negative checks with positive cases when that proves the path was exercised.

Use real code and dependencies where practical. Put fakes at meaningful external
boundaries. A fake can prove destination, payload, and idempotency key without
moving money; it cannot prove the provider accepted the operation. Distinguish
that limitation from a live integration claim.

Preserve tests for unique regressions while their requirement remains. Remove
tests that only mirror implementation details when they add no independent
contract. Exact text can be a valid requirement for legal wording, protocol
output, or instruction boundaries; incidental prose should not be frozen merely
to create test volume. Instruction-package checks prove structure and declared
contracts, not that a model behaves correctly in ordinary work.

Run focused feedback while changing a unit, then the complete required merge and
release proof. Test selection and impact analysis do not create a trusted scoped-
proof policy. Reuse and exact-candidate coverage remain owned by
[verification](verification.md).
