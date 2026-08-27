# agentsmd

A small, opinionated, speed-first policy pack for coding agents. It keeps the
same global working agreements, long-running Goal contract, and deterministic
repository version discipline across supported agent harnesses.

## Files

- `AGENTS.md`: portable global working agreements.
- `GOAL_TEMPLATE.md`: harness-neutral `GOAL.md` and `STATUS.md` contract for
  work that must continue across sessions.
- `VERSION`: canonical SemVer identity for this repository.
- `.version-policy.json`: version, mirror, tag, release, and publication policy.
- `CHANGELOG.md`: one dated entry for each completed repository version.
- `.codex-plugin/`, `.claude-plugin/`, `.grok-plugin/`: plugin identity on
  Codex, Claude Code, and Grok Build. Install from marketplace toolboxmd.
- `skills/version-control/`: semantic-impact workflow for coding agents.
- `bin/versionctl`: plugin-relative entry point for the bundled CLI.
- `tools/versionctl/`: dependency-free Python CLI for deterministic version
  mechanics and commit-hook enforcement.
- `.github/workflows/`: read-only transition validation and policy-authorized
  exact-SHA GitHub Release automation.

Project-level instructions remain closer to the code and take precedence over
the global baseline. This matches the discovery model documented for
[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Install

Clone the repository wherever you keep shared tools:

```sh
git clone https://github.com/toolboxmd/agentsmd.git
cd agentsmd
AGENTSMD_DIR="$(pwd -P)"
```

Before linking, move any existing target file to a timestamped backup. Do not
overwrite an existing file or symlink without inspecting it.

Link `AGENTS.md` and the `version-control` skill into each harness. The Goal
rule resolves the global rules link to this clone and reads the adjacent
`GOAL_TEMPLATE.md` on demand. Install or link `versionctl` once so adopted
repositories can use the same mechanics implementation.

### Codex

The `agentsmd@toolboxmd` plugin bundles the `version-control` skill and CLI.
Add marketplace toolboxmd, then install this plugin:

```sh
codex plugin marketplace add toolboxmd/marketplace
codex plugin add agentsmd@toolboxmd
```

Start a new Codex session after installation. Invoke the bundled skill with
`$version-control`; its description also allows implicit invocation for tracked
repository changes.

Plugin installation does not make this repository's `AGENTS.md` global and
does not put `versionctl` on the PATH of ordinary terminal sessions. Keep the
global rules and stable CLI links below when those behaviors are required.

```sh
mkdir -p "$HOME/.codex"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.codex/AGENTS.md"
```

Codex officially reads global guidance from `AGENTS.md` in `CODEX_HOME`, which
defaults to `~/.codex`. It rebuilds the instruction chain on each new run or
TUI session.

Link the skill and CLI without copying their implementations:

```sh
mkdir -p "$HOME/.codex/skills" "$HOME/.local/bin"
ln -s "$AGENTSMD_DIR/skills/version-control" \
  "$HOME/.codex/skills/version-control"
ln -s "$AGENTSMD_DIR/tools/versionctl/bin/versionctl" \
  "$HOME/.local/bin/versionctl"
```

Ensure `$HOME/.local/bin` is on `PATH` for coding-agent shells.

### Claude Code compatibility

Add extraKnownMarketplaces `toolboxmd` pointing at `toolboxmd/marketplace`,
then enable `agentsmd@toolboxmd`. If you previously used `agentsmd-local`,
rename it. The namespaced skill is `/agentsmd:version-control`.

The plugin does not install global instructions. Configure the canonical
`AGENTS.md` or a `CLAUDE.md` link separately when global policy is desired.

### Grok Build CLI

```sh
grok plugin marketplace add toolboxmd/marketplace
grok plugin install agentsmd --trust
```

Global `AGENTS.md` is still a separate link if you want it in every session:

```sh
mkdir -p "$HOME/.grok"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.grok/AGENTS.md"
```

Verified with Grok Build CLI 1.0.5. Grok loads the global `AGENTS.md`
automatically. The Goal rule locates the adjacent template on demand.

### Other harnesses

Configure the cloned `AGENTS.md` as global instructions, expose
`skills/version-control/` through the harness skill discovery path, and keep
`GOAL_TEMPLATE.md` beside its canonical source. The Goal files remain useful
even without a native Goal feature because Git stores the approved contract and
current status.

## Version an adopted repository

An adopted repository has a root `VERSION`, `.version-policy.json`, and
`CHANGELOG.md`. Native versions in JSON or TOML manifests are declared as
mirrors in policy. `versionctl` is their only writer.

Before work:

```sh
versionctl doctor --json
```

After completing the requested tracked change, choose semantic impact from the
outcome and preview it:

```sh
versionctl prepare patch --reason "Correct install documentation" --dry-run
versionctl prepare patch --reason "Correct install documentation"
```

Commit the deliverable, `VERSION`, declared mirrors, and `CHANGELOG.md`
together. Validate the clean commit before handoff:

```sh
versionctl release-check
```

Use `major` for incompatible behavior or contract, `minor` for a
backward-compatible capability, and `patch` for every other completed change.
Strictly read-only work and explicitly incomplete `wip:` checkpoints do not
bump.

For a new adoption, create policy and mirror files, decide the initial version,
then let the CLI write the canonical state:

```sh
versionctl adopt 0.1.0 --reason "Adopt repository versioning" --dry-run
versionctl adopt 0.1.0 --reason "Adopt repository versioning"
```

The initial `0.1.0` in this repository identifies the first complete CLI,
skill, hook, fixture, and workflow implementation. It also communicates that
the cross-repository contract is still in its pilot stage.

## Enforcement and releases

Install the optional managed hooks inside an adopted repository:

```sh
versionctl install-hooks
```

Normal completed commits without a staged version transition are blocked. An
intentional checkpoint uses both an explicit marker and configured prefix:

```sh
VERSIONCTL_WIP=1 git commit -m "wip: checkpoint"
```

`version-check.yml` runs fixture validation, compares the exact base and HEAD,
and validates release identity with read-only permissions. For this repository,
policy explicitly enables `on-version-commit`: a push to `main` that changes
`VERSION` lets `release.yml` revalidate exact `GITHUB_SHA`, create its annotated
tag, and create the matching GitHub Release in one job. The workflow does not
publish a registry package, promote a marketplace version, install anything,
or deploy production.

A version bump, commit, tag, push, GitHub Release, registry or marketplace
publication, installation, deployment, and live verification are separate
states and must be reported separately.

## Customize

Read the policy before using it. Fork the repository or edit your local copy if
its assumptions do not match your workflow. Keep project-specific commands,
architecture, checks, and deployment rules inside each project.

## License

MIT. See `LICENSE`.
