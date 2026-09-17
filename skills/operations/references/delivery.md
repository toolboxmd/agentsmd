# Delivery

The Delivery System is the shared lifecycle contract. A root
`.toolboxmd/delivery.json`, when present, contains only Project-specific deltas
and must be loaded through the `delivery-profile` Skill after Project Direction
and repository orientation. The profile never owns canonical version, Project
Record, release policy, documentation, or current delivery state.

- Report qualified, implemented, proved, reviewed, merged, released,
  distributed or deployed, installed or activated, loaded, Live Verified, and
  website-current as separate states. A state is positive only after its own
  required evidence exists. Qualifying work identifies the owning Issue (or
  authorized direct task), outcome, authority, dependencies, acceptance
  criteria, and Proof before implementation begins.

- Give one complete merge unit or dependent stack exactly one SemVer
  transition. Classify it from the highest semantic impact in everything that
  ships. Internal component PRs and intermediate stack layers are incomplete
  checkpoints of that merge unit, not completed deliverables with independent
  version bumps or releases. Prepare the single transition on the cumulative
  final approval PR under `version-control`.

- Every deployable artifact is built once from the exact release SHA, assigned
  an immutable digest, and promoted unchanged through distribution,
  deployment, installation, and activation. Rebuilding creates a different
  artifact and requires new proof.

- Classify website impact for every merge unit as none, generated, narrative,
  or runtime. `none` requires a recorded reason. A major version requires a
  complete website review. For minor and patch changes, update affected public
  capability, setup, compatibility, pricing, screenshots, metadata,
  documentation, and URLs before website-current becomes true. Record SEO
  impact and treat URL changes as migrations; the full SEO program remains a
  separate outcome.

- Before opening or updating a PR, read `CONTRIBUTING.md` when present.
- A final approval PR is ready when every acceptance criterion is satisfied,
  required proof is current, the final diff passed self-review, and the version
  transition is committed. Blocked work ends in a blocker handoff, not a ready-PR claim.
- Internal component readiness and merge follow [orchestration](orchestration.md).
  Final approval PR merges require explicit human approval under the core.
- For an authorized merge, re-check the exact PR head and readiness, use the
  repository's supported merge path, and verify the result.
- Reuse established repository capability evidence while its assumptions hold.
  For an unverified required capability, settings change or detected drift, read
  [repository setup](repository-setup.md). Fresh checks of mutable PR heads,
  readiness and permissions remain required.
  Before review or proof claims, read [verification](verification.md).
  At terminal disposition, read [finalization](finalization.md).
