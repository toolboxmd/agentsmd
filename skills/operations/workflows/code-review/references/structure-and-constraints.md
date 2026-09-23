# Structure and constraints

Use reader effort as a design signal. Follow a real question through the code:
how many layers and mutable facts must a reader reconstruct? Inspect cohesion,
hidden policy, and repeated caller coordination. File length, function length,
or one caller can prompt inspection; none is an automatic deletion threshold.

Prefer a structure that expresses the invariant to a comment asking every caller
to remember it. Examples include a named unit, a validated constructor, an owned
state transition, a schema, or a deterministic check. Prove that the replacement
actually carries the constraint before removing its explanation.

Classify comments by purpose:

| Purpose | Treatment |
| --- | --- |
| Restates obvious code | Remove when no useful context is lost |
| Explains a non-obvious invariant | Encode where practical; preserve rationale that still matters |
| Records external limitation or historical constraint | Verify current relevance; keep the reason and precise source |
| Public API contract, legal notice, accessibility need | Preserve its required communication role |
| Suppression or workaround | Check the exact necessity and removal condition; do not delete blindly |
| TODO or unresolved decision | Keep useful scope/owner/evidence until resolved or deliberately retired |

Ambiguity is a reason to investigate, not to erase. Missing authority to implement
a structural replacement is not permission to delete the warning it would replace.
Negative type tests can legitimately use a scoped compiler suppression. Comments
and tests serve different readers and may both be needed.

Keep simplification within the requested scope. A review can identify a broader
design opportunity without silently turning a bug fix into a codebase rewrite.
For authorized structural work, use [software-design](../../software-design/index.md) to compare shapes and
preserve consumer behavior during migration.
