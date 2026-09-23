
# Delivery Profile

Load optional Project deltas to `AGENTS.md` and Operations delivery. The profile
does not own canonical version, Project Record, release policy, documentation,
or delivery state.

## Load

1. Complete Project Direction loading (or confirm an explicit local opt-out for
   its stated scope) and orientation: exact root, branch, `HEAD`, upstream, and known ahead/behind state.
2. Locate executable `bin/delivery-profile` in the canonical AgentsMD installation
   resolved from the native global instruction link. A full plugin package also
   contains it at `../../../../bin/delivery-profile` relative to this procedure
   directory. A copied Model Router kit need not contain executables. Report a
   missing loader and stop.
3. If `.toolboxmd/delivery.json` is absent, record no declared deltas and finish.
   Otherwise run `bin/delivery-profile load --root "$PROJECT_ROOT" --json`.
   Require one structured `valid` or `invalid` result for the exact path.
4. On `invalid`, stop delivery configuration/execution, retain every error in
   the handoff, and apply no delta. Never infer validity from nearby docs.
5. On `valid`, bind each declared delta to its delivery step and infer none.
   Shared lifecycle, review, version, CI, artifact, website, and evidence rules
   remain in the core and Operations.

## Change

Keep v1 narrow: `commands` names changed-scope, complete, and release proof;
`artifact` names one exact-SHA build, versioned output, and SHA-256 digest;
`website` maps repository, HTTPS origin, and route. Validate through the public
loader with fixtures for each new valid/invalid boundary. Shared decisions belong
in the core, procedures in Operations. Add fields only for genuine Project variation.

When declaring or reusing scoped proof, read [its contract](../../references/scoped-proof.md).
Keep the scope map outside v1 and bind command lanes to a trusted Project adapter.
Finish only when it identifies complete baseline, frozen candidate, separately
trusted policy, authenticated execution, and current input assumptions, or explains
why scoped delivery is unsupported. Unchanged legacy profiles retain complete proof.
