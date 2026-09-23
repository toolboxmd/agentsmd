# Review and adjudication

## Inspect by failure mechanism

Use the relevant lenses, not a quota of findings:

- **Behavior:** acceptance, defaults, errors, boundaries, cancellation, and real
  caller expectations. Does the check observe the promised result?
- **State and lifetime:** ownership, transitions, stale work, cleanup, retries,
  concurrency, and partial failure. Does an old actor still have write access?
- **Boundaries:** trust, authorization, parsing, serialization, persisted versions,
  and integration assumptions. Is a guarantee still valid at the actual effect?
- **Design:** responsibilities, caller burden, repeated special cases, hidden
  state, and avoidable coordination. Can a smaller model remove the problem?
- **Proof:** faithful seam, independent oracle, meaningful baseline, complete
  required coverage, artifact identity, and honest environmental limits.
- **Delivery:** migrations, public compatibility, generated artifacts, version
  identity, safe rollback, and changes outside the authorized scope.

Read relevant paths far enough to demonstrate reachability. An alarming line
without a possible input or execution path is a question, not yet a defect.
Conversely, unchanged code can become reachable through a changed caller; being
outside the diff does not invalidate a finding. Decide repair scope separately.

## Make a finding reviewable

State the concrete trigger, actual versus required behavior, location, and
impact. Include the shortest useful reproduction or code path. Name uncertainty
when an assumption remains untested. Severity follows consequence and reachable
conditions, not the intensity of wording or an invented probability.

Separate a required correction from taste or speculative generality. Do not
compel a major restructure to demonstrate rigor. An optional improvement should
say what burden it removes and why that benefit matters now. No fixed five-item
cap should hide real defects; no quota should manufacture them.

## Adjudicate every substantive claim

The lead verifies findings, including those labeled notes or suggestions when
they reveal a real defect. Classify each as accepted, rejected with evidence,
optional, or unresolved with a concrete next check. Deduplicate by mechanism,
not just by line number. Minority evidence can defeat unanimous intuition.

Resolve conflicts against the code, requirement, and a discriminating test.
Do not vote, dismiss a third review round by default, or accept a finding because
several reviewers copied the same premise. Carry previously found failure modes
into the next review brief so fixes are checked for regressions.

An external review bot supplies leads. Confirm its candidate, full thread,
context, and current status before acting. Do not equate an empty truncated API
page, absent checks, unknown mergeability, or unfulfilled review requirements with
approval. PR status helpers inform progress; the live forge and delivery contract
own admission and merge readiness.

After fixes or synthesis, the artifact is a changed candidate. Apply required
proof and review identity rules to that candidate. Do not transfer the verdict
from an earlier SHA by describing the changes as small.
