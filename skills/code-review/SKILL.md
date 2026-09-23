---
name: code-review
description: >
  Review a change for reachable defects, hidden contracts, blast radius, and
  unnecessary complexity. Use for independent implementation review, adversarial
  review, or a requested impact analysis. Review-only requests stay read-only.
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/interrogate
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Code review

Establish intended behavior, exact base/head, acceptance, scope, and relevant
project rules. Read the complete diff and surrounding consumers needed to judge
it. Treat the author's explanation and test report as claims to check. Preserve
`operations`' required independent exact-candidate review; this Skill supplies
the method and does not waive that gate or grant merge authority.

Read [review and adjudication](references/review-method.md). For a risky boundary,
API change, or safety claim, also read [impact analysis](references/impact-analysis.md).
For structural simplification or comments, read
[structure and constraints](references/structure-and-constraints.md).

Use narrow independent lenses when complexity or a real unresolved disagreement
justifies them. All reviewers receive the same relevant intent, candidate, rules,
and proof limits. Follow installed model routing and explicit user choices.
Different opinions do not require different models, and agreement is not proof.

Return actionable findings with location, triggering conditions, reachable path,
effect, and evidence. Distinguish required fixes, optional improvements, cleared
concerns, and unproven assumptions. A clean review means no supported actionable
finding in the inspected scope; it does not prove the absence of every defect.
For implementation work, adjudicate findings and revalidate changes under
`operations`. For review-only work, report findings without modifying the target.
