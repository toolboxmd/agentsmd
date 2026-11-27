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

The severity rule in "Make a finding reviewable" binds the lead too. When
writing a blocking bar into a review brief, and again before accepting a
finding, name an input or event that can reach the failure, with its
consequence: who can supply the value at the reviewed boundary, an untrusted
caller included, and what enforces a limit there; or an event such as a restart
between two writes or two concurrent calls. A case for which no such input or
event can be named, such as a value only a fake in place of the real producer
could supply, is a note with a follow-up.

When an accepted finding is one case of a boundary contract (a parser, a mapping
from an input to a published value, a state or verdict table), do not request a
fix for that case alone. First check each row's origin: who required it (the
Spec, the user, or a constraint with evidence) and what fails without it. Code
that deviates from a row only the implementation or the author's own list
introduced is not a defect: delete the row or send it back as a question; do not
complete it. Then state the contract as a table of the input classes it covers
plus one row for all other input, each with its required result; the fix
implements it in one place with a table-driven test at that boundary that checks
every row, and the next review brief asks for the code to be checked against the
table. A fix request states requirements, not mechanisms: a mechanism you name,
such as when a value is read, is a claim to verify in the code first.

An external review bot supplies leads. Confirm its candidate, full thread,
context, and current status before acting. Do not equate an empty truncated API
page, absent checks, unknown mergeability, or unfulfilled review requirements with
approval. PR status helpers inform progress; the live forge and delivery contract
own admission and merge readiness.

After fixes or synthesis, the artifact is a changed candidate. Apply required
proof and review identity rules to that candidate. Do not transfer the verdict
from an earlier SHA by describing the changes as small.
