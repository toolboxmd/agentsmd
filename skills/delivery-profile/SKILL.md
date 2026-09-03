---
name: delivery-profile
description: >
  Load and validate a Project's `.toolboxmd/delivery.json` when it exists, or
  when delivery commands, artifact promotion, website impact, or Delivery
  System configuration are being decided. Use after Project Direction is
  loaded and before relying on Project-specific delivery behavior.
---

# Delivery Profile

Use the profile as Project-specific deltas to the portable Delivery System in
`AGENTS.md`. This Skill only loads those deltas. Canonical version, Project
Record, release policy, documentation, and current delivery state remain in
their owning files.

## Load

1. Complete the Project Direction load and repository orientation required by
   `AGENTS.md`. Continue when the complete triad and exact repository root,
   branch, `HEAD`, upstream, and locally known ahead/behind state are present.
2. From the repository root, locate `bin/delivery-profile`. When this Skill is
   installed as part of AgentsMD, resolve it at `../../bin/delivery-profile`
   relative to this file. Continue when the resolved path is an executable
   file; otherwise report the missing loader and stop.
3. If `.toolboxmd/delivery.json` exists, run:

   ```sh
   bin/delivery-profile load --root "$PROJECT_ROOT" --json
   ```

   This step is complete when the loader returns one structured `valid` or
   `invalid` result for the exact profile path. When no profile exists, record
   that the Project declares no delivery deltas and finish this Skill.

4. Stop delivery configuration or execution when the loader reports
   `invalid`. This branch is complete when every reported error is preserved
   in the handoff and no profile delta has been applied.
5. On `valid`, apply only the loaded Project-specific deltas. The shared
   lifecycle, review, version, CI, artifact, website, and evidence semantics
   remain those in `AGENTS.md`. This branch is complete when each declared
   delta is bound to its owning delivery step and no undeclared delta is
   inferred.

The profile is optional for repositories that have no Project-specific
delivery differences. Never infer a valid profile from nearby documentation.

## Change

Keep the v1 shape narrow:

- `commands` names changed-scope, complete, and release proof commands.
- `artifact` names one exact-SHA build, its versioned output path, and SHA-256
  digest algorithm.
- `website` maps the Project to its website repository, HTTPS origin, and
  route.

Validate every profile change through the public loader. Add a schema fixture
for each new valid or invalid boundary. Put shared semantics in `AGENTS.md` and
add a profile field only when Projects can genuinely differ.
