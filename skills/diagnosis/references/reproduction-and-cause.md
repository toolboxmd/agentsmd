# Reproduction and cause

## Find the actual defect and its owner

Start at the reported user action and trace the likely execution path. Surface
ownership can differ from cause ownership: a UI error may originate in storage,
serialization, or a stale background result. Read the relevant types and callers
before assigning the problem to a module or person.

Search existing work by source link, exact error signature, trigger, symptom,
affected version, and neighboring changes. Use this evidence ladder:

- Confirmed same defect: matching cause or a discriminating failure signature.
- Possible relation: overlap worth investigating, with the missing link named.
- Superficial resemblance: similar words or screen, different causal evidence.
- No match in the stated search boundary.

A closed Issue may identify a regression, incomplete fix, or historical reason.
Do not silently reopen, reprioritize, or reassign another owner's work. Check
whether an active writer owns the fix and whether a concrete PR or commit exists.
Someone collecting logs is not necessarily the implementation owner.

## Reproduce at the cheapest faithful seam

Name the correct final state, broken final state, and observation separating
them. A parser defect may need only the real parser and captured bytes. Focus,
ordering, or navigation failures may require the real event sequence and runtime.
Preserve causal conditions rather than always choosing the broadest test.

Reach the point of divergence. A setup dialog, loading screen, app title, or
successful build does not establish the symptom. Fixture setup can prepare the
conditions; injecting the broken state does not reproduce the transition that
allegedly creates it. Use read-only internal inspection to corroborate an
observable result, not manufacture it.

Capture exact revision, configuration, data, actions, and evidence. Reset and
repeat when state or timing could make one attempt accidental. If a production
environment is translated into a safe local one, name every material difference.
When a difference could cause the defect, label the result partial or inconclusive.
Do not touch production, credentials, or customer state without exact authority.

## Distinguish causes

Generate plausible mechanisms from the observed path. For each, predict an
observation that would differ if the mechanism were false. Prefer one controlled
intervention or focused inspection over several simultaneous changes. Follow
the causal chain beyond the line that throws: who created the invalid state,
which invariant allowed it, and why the expected owner failed to prevent it.

Intermittence requires timing and lifecycle evidence. Record creation, ownership,
cancellation, completion, and teardown when relevant. A convincing source story
does not make a race deterministic. If several repairs fail through one shared
assumption, inspect that assumption and all actors holding the relevant state.

Preserve negative results when they rule out a plausible cause. Stop gathering
unrelated logs after the next decision is supported. Broaden investigation when
the leading explanation cannot account for a material observation.

## Verify an existing fix

Obtain the exact candidate and base. Tracker status, a chat claim, or a similarly
named branch is not a fix artifact. Reproduce the baseline and run the candidate
under equivalent conditions. Inspect the diff's mechanism and nearby behavior.
If the baseline does not expose the defect, the comparison alone cannot prove
the fix; report what it does show and what remains missing.

Prefer this evaluation to competing authorship when another person owns a
plausible fix. Report evidence to the canonical task within granted authority.
Do not modify another writer's candidate or claim their work as independently
verified based only on a summary.

## Repair and close the causal loop

For authorized repair, make one interpretable change. Add a regression at the
faithful seam when practical and show it fails on the baseline for the intended
reason. A test failure caused by unavailable credentials or broken setup is not
the bug reproduction. Re-run the same observable path and nearby affected cases.

If the root cause is external or outside scope, record the evidence and use a
bounded mitigation only when authorized. State the mitigation's limit and owner.
Keep required proof and delivery with `operations`; reproducing a defect is a
milestone, not proof that an entire outcome is delivered.
