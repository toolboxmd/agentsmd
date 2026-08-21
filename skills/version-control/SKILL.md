---
name: version-control
description: >
  Use whenever a task may change tracked files in a Git repository, including
  code, documentation, AGENTS.md, skills, plugins, prompts, configuration,
  schemas, tests, or data. Run before the final commit or handoff so every
  completed deliverable has one reviewable SemVer transition. Also use for an
  explicitly requested WIP checkpoint. Do not use for strictly read-only
  audits, diagnoses, explanations, reviews, or status checks.
---

# Version Control

Use semantic judgment for impact and delegate all file and Git mechanics to
`versionctl`. This separation keeps meaning reviewable without duplicating
version algorithms in agent instructions.

## Decision tree

1. Strictly read-only task: stop applying this skill, do not bump, and base any
   audit conclusion only on evidence actually inspected. Never fill missing CI
   or repository facts from the version policy.
2. Intentionally incomplete checkpoint: use the WIP path below and do not bump.
3. Completed tracked deliverable: run the full workflow.
4. Missing `.version-policy.json` or `VERSION`: report that adoption is needed.
   Do not invent an initial version unless adoption is in scope.

## Locate the CLI

From the repository root, prefer `versionctl` on `PATH`. Otherwise use an
executable `tools/versionctl/bin/versionctl` in the repository. When this skill
comes from an installed plugin, resolve the directory containing this
`SKILL.md` and use the executable at `../../bin/versionctl` relative to it.
Stop if none exists because manual version or mirror edits are invalid.

Set `VERSIONCTL` to the selected executable for the commands below.

## Completed-deliverable workflow

1. Before edits, run `$VERSIONCTL doctor --json` and retain its evidence.
2. Complete only the requested work.
3. Inspect the final diff and identify the repository's public contract.
4. Choose the highest semantic impact in the complete deliverable:
   - `major`: an incompatible behavior or contract;
   - `minor`: a backward-compatible capability;
   - `patch`: every other completed change.
5. Preview with `$VERSIONCTL prepare <impact> --reason "<summary>" --dry-run`.
6. Apply the same command without `--dry-run`.
7. Inspect the canonical version, every reported mirror, and `CHANGELOG.md`.
8. Stage and commit the deliverable, version, mirrors, and changelog together.
9. On the clean commit, run `$VERSIONCTL release-check`.
10. Push only when the task's Git authority permits it. A policy value of
    `on-version-commit` authorizes the configured release workflow, but does
    not broaden permission for registry publication, deployment, or install.

When multiple changes ship together, the highest impact wins. Re-running
`prepare` before commit preserves or raises an existing pending impact.

## WIP checkpoints

WIP is for an intentionally incomplete checkpoint, never a completed handoff.
With installed hooks, use both the explicit environment marker and an allowed
message prefix:

```sh
VERSIONCTL_WIP=1 git commit -m "wip: <checkpoint>"
```

The pre-commit phase defers the bump, and commit-msg verifies the real prefix.

## Boundaries

- Never edit `VERSION` or a declared mirror manually.
- Never rewrite or reuse a version tag.
- `prepare` does not commit, tag, push, release, publish, install, or deploy.
- A tag or GitHub Release does not prove later publication or deployment.
- Report version, commit, tag, push, GitHub Release, registry or marketplace
  publication, deployment, installation, and live verification separately.
- Ask only when compatibility or an external publication boundary cannot be
  determined safely.

Read [bump-rules.md](references/bump-rules.md) for classification examples and
[project-policy.md](references/project-policy.md) for schema, adoption, hooks,
and release behavior.
