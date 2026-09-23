---
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/create-verification-skill
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Project verification

Turn actual product behavior into a runnable, project-local verification
procedure. Inspect existing project instructions, tools, drivers, and proof
policy first. Reuse a working capability instead of creating another harness.
This procedure authors verification support; it does not impose a new release gate,
authorize external effects, or replace the project's required proof.

Read [the verification contract](references/verification-contract.md). Use
[create and maintain](references/create-and-maintain.md) for the selected mode.
Use [observation recipes](references/observations.md) when designing the checks.

Keep setup, runtime identity, feature recipes, and teardown under one project-local
owner. Reuse an existing verification procedure. Otherwise use
`.toolboxmd/verification/index.md` with conditional driver/feature references in
that directory. Add one short pointer to project `AGENTS.md`; do not register a
new globally advertised skill. Follow [artifact placement](../../references/artifacts.md)
for each run's evidence, separate from reusable recipes.

Before product-driving verification, Operations reads that project pointer or
the default path directly. Model Router's isolated kits disable project skill
discovery, so worker packets carry the procedure's exact path. Verify direct
file access in the assigned workspace; never assume a host discovered it.
Shared instructions can link host-specific driver details where necessary.

Finish by executing the authored instructions through launch, identity check,
one representative feature, evidence capture, and owned cleanup. An unexecuted
procedure remains a draft. Report which routes were exercised and which remain
unverified. A successful initial recipe proves runnability, not complete product
coverage. Required credentials or unsafe fixtures are explicit blockers, not
permission to use another person's session or weaken expectations.
