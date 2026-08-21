# Project policy and operations

Schema 1 is stored at the repository root in `.version-policy.json`:

```json
{
  "schema": 1,
  "bumpPolicy": "every-deliverable",
  "versionSource": "VERSION",
  "tagPattern": "v{version}",
  "tagPolicy": "every-version",
  "githubReleasePolicy": "on-version-commit",
  "distributionPolicy": "released-tags-only",
  "publishPolicy": "manual",
  "releaseBranch": "main",
  "wipPrefixes": ["wip:"],
  "mirrors": []
}
```

`releaseBranch` defaults to `main` and `wipPrefixes` defaults to `["wip:"]`.
Schema 1 canonical versions are stable `MAJOR.MINOR.PATCH` values. Prerelease
channels and independently released monorepo components are deferred.

## Mirrors

Each mirror has a repository-relative `path` and absolute JSON Pointer. JSON
and TOML are supported. TOML pointers map section tokens and a final key, such
as `/project/version` or `/tool/poetry/version`.

```json
{
  "path": "package.json",
  "pointer": "/version"
}
```

Only `versionctl adopt` or `versionctl prepare` may write the canonical version
and mirrors. JSON mirrors are reserialized with detected indentation and the
CLI reports that normalization. TOML assignment formatting is preserved.

## Initial adoption

Choose the initial version and record why. Then preview and apply:

```sh
versionctl adopt 0.1.0 --reason "Adopt repository versioning" --dry-run
versionctl adopt 0.1.0 --reason "Adopt repository versioning"
```

Adoption is allowed only when `VERSION` is absent from both HEAD and the working
tree. The policy and declared mirror files must already exist.

## Hooks

`versionctl install-hooks` installs managed `pre-commit` and `commit-msg`
hooks in Git's configured `core.hooksPath`, or the repository hook directory
when no override exists. It refuses to replace an unmanaged hook. The staged
check blocks a completed change without a staged transition and prints the
three prepare alternatives. Because Git runs pre-commit before the final
message is available, a WIP checkpoint requires `VERSIONCTL_WIP=1`;
commit-msg then verifies the configured prefix.

## Exit codes

| Code | Name | Meaning |
|---:|---|---|
| 0 | `OK` | Validation or write completed. |
| 10 | `NOT_GIT_REPOSITORY` | Repository discovery failed. |
| 11 | `INVALID_POLICY` | Schema or policy is invalid. |
| 12 | `MISSING_VERSION` | Canonical version is absent. |
| 13 | `INVALID_VERSION` | Version is not stable SemVer. |
| 14 | `NO_CHANGES` | No deliverable exists to version. |
| 15 | `STALE_MIRROR` | A mirror differs or cannot be read. |
| 16 | `BUMP_REQUIRED` | Content lacks a valid transition. |
| 17 | `CHANGELOG_INVALID` | Matching changelog entry is absent. |
| 18 | `VERSION_CONFLICT` | Version or release SHA identity conflicts. |
| 19 | `TAG_CONFLICT` | Tag name, type, or target conflicts. |
| 20 | `DIRTY_TREE` | Release validation found local changes. |
| 21 | `AUTHORIZATION_REQUIRED` | A hook or external boundary needs authority. |
| 22 | `INVALID_ARGUMENT` | Command arguments conflict. |
| 23 | `IO_ERROR` | A transactional write failed. |
| 24 | `GIT_ERROR` | A required Git command failed. |

## Release states

`release-check` validates a clean exact commit, canonical version, mirrors,
changelog, tag policy, version reuse, and proposed distribution SHA. It does
not write. When `githubReleasePolicy` is `on-version-commit`, the configured
release-branch workflow may create the annotated tag and GitHub Release in one
job. Registry publication, marketplace promotion, deployment, and installation
remain manual under schema 1.
