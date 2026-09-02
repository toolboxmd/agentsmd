---
status: accepted
---

# Persistent host automation uses canonical sources and controlled deployed copies

Issue #31 approved this architecture decision.

Persistent Host Automation needs stable ownership across source control and
live-host state. AgentsMD separates canonical source from controlled deployed
copies so a working-tree change cannot alter a running service before
validation and a privileged entrypoint cannot resolve through a user-writable
checkout.

## Boundary

This contract applies to agent-created or agent-maintained host services,
scheduled jobs, and their health or recovery automation when they persist
beyond the current task. It does not absorb normal application code,
project-local build tooling, one-off diagnostics, or vendor-owned services
that an adopting repository has not explicitly taken over.

## Canonical ownership

Closer project instructions select the canonical repository and
platform-specific deployment rules when they do so. Otherwise, use the
user-selected repository. When ownership is unresolved and proceeding would
create a repository or another operational ownership surface, ask the user.

The canonical repository owns, as applicable:

- service scripts and definitions;
- non-secret configuration templates;
- explicit repository-to-runtime mappings;
- documentation for validation, installation, rollback, health, and read-only
  drift procedures;
- material change and recovery-test history.

Each repository-to-runtime mapping records the canonical source, runtime
destination, owner, group, mode, source validation, restart scope, health
proof, drift check, and rollback guidance. Closer rules may select the concrete
platform mechanism without weakening this contract or its Human Gates.

## Runtime contract

Persistent runtime scripts, service definitions, and configuration are
controlled deployed copies. A service entrypoint does not follow a symlink into
a writable checkout. The deployment mechanism applies the mapped destination,
owner, group, and mode explicitly, including a platform-required privileged
owner where applicable.

This boundary does not change an unrelated architecture that intentionally
uses symlinks for a global instruction file, developer CLI, package install, or
another non-service surface. Reconsider those models only on their own evidence
and authority.

## Change loop

The portable semantic loop is:

```text
edit canonical source
  -> validate canonical source
  -> preview deployment or drift
  -> install controlled copy
  -> restart only the affected service or scheduled runtime
  -> verify the live public health seam
  -> record canonical and deployed identity
```

Validation must finish before installation. Installation must verify the
mapped ownership and permissions before restart. The procedure defines how to
restore the prior deployed identity and recheck health when installation or
health proof fails. Installation, deployment, and restart remain external
mutations: confirm the exact live target and satisfy the applicable Human Gate
before acting.

## Drift and recovery

Provide a read-only drift check that compares each known canonical artifact
with its deployed artifact by cryptographic hash or a documented semantic
comparison. Report missing, inaccessible, and unmatched artifacts explicitly.
The check observes live state; it does not silently repair it. Rollback guidance
identifies the last known-good deployed identity and the verification needed
after restoration.

## Secrets

The canonical repository records each secret name, purpose, required
permissions, non-secret template references, and protected runtime location,
but never its value. Deployment obtains values through the approved host secret
mechanism or existing protected files. Logs and recorded deployment state
contain identities and outcomes, not secret material.

## State record

Record the canonical commit or content hash and the deployed content identity,
destination, ownership, permissions, restart result, and health result. Report
Issue, branch, implementation, commit, push, PR, merge, release, installation,
deployment, restart, and Live Verification as distinct states. When no
authorized live action occurred, report `not deployed` and `not live verified`
explicitly. Repository state and deployed live state remain separate even when
their content identities match.

## Representative boundaries

| Case | Contract result |
| --- | --- |
| Privileged boot service | Install explicitly owned copies of its script and service definition. Never point the privileged entrypoint through a writable checkout. |
| User-level scheduled service | Apply the same copy model with the mapped user-level owner, group, mode, restart, and health proof. |
| Service health or recovery script | Keep its source beside the associated service source and deploy or invoke it through the explicit mapping. |
| Project build script or one-off diagnostic | Keep it in the owning project. It is outside this boundary. |
| Secret-bearing service | Version only the secret contract and protected runtime location. Obtain the value from the approved protected source. |
| Unrelated intentional symlink | Preserve its owning architecture unless it is separately reconsidered. |
