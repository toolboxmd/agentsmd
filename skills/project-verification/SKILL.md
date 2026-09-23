---
name: project-verification
description: >
  Create or maintain a repository's executable verification skill, driver
  recipes, and feature map. Use when agents cannot reliably launch, drive, or
  observe the product, or when its verification instructions drift. Ordinary
  task proof remains owned by operations.
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
This Skill authors verification support; it does not impose a new release gate,
authorize external effects, or replace the project's required proof.

Read [the verification contract](references/verification-contract.md). Use
[create and maintain](references/create-and-maintain.md) for the selected mode.
Use [observation recipes](references/observations.md) when designing the checks.

Keep setup, runtime identity, feature recipes, evidence, and teardown under one
project-local owner. Put the Skill in the host-supported project discovery path;
verify that path rather than assuming a Cursor directory. Shared portable
instructions can link host-specific driver details where necessary.

Finish by executing the authored instructions through launch, identity check,
one representative feature, evidence capture, and owned cleanup. An unexecuted
procedure remains a draft. Report which routes were exercised and which remain
unverified. A successful initial recipe proves runnability, not complete product
coverage. Required credentials or unsafe fixtures are explicit blockers, not
permission to use another person's session or weaken expectations.
