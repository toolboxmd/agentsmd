
# ADR Format

Before offering an ADR, apply [SKILL.md](SKILL.md)'s three eligibility conditions:
meaningful reversal cost, surprising without context, and a real trade-off.

Create `docs/adr/` lazily for the first qualifying decision. Scan the highest
number and increment: `0001-slug.md`, `0002-slug.md`.

```md
# {Short decision title}

{1-3 sentences: context, decision, and reason.}
```

One paragraph may suffice. Add sections only when useful: status
(`proposed | accepted | deprecated | superseded by ADR-NNNN`) for revisited
choices, considered options for informative rejections, consequences for
non-obvious downstream effects.

Qualifying cases may include costly architecture or technology lock-in,
integration and data-ownership boundaries, deliberate deviations from expected
practice, and hidden constraints. For example, "Customer data belongs to Customer;
other contexts reference it by ID" records an important exclusion. A partner's
200ms requirement records a constraint code alone cannot explain. Preserve
non-obvious rejection reasons so future readers do not repeat the same debate;
ordinary libraries or obvious, reversible choices need no ADR.
