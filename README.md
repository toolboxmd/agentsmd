# agentsmd

AgentsMD is the ToolboxMD source of truth for a portable agent operating
contract, an approved workflow Skill Catalogue, and deterministic repository
version control. The installable plugin exposes the same owned workflow suite
to Codex, Claude Code, and Grok Build.

Project instructions remain closer to the code and take precedence over the
global baseline. This matches the discovery model documented for
[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Package contents

- `AGENTS.md`: portable global working agreements.
- `GLOSSARY.md`: canonical AgentsMD project language.
- `SKILL_CATALOGUE.md`: authoritative ownership, lifecycle, provenance,
  licence, and adaptation inventory.
- `THIRD_PARTY_NOTICES.md` and `LICENSES/`: redistributed-source notices.
- `skills/`: only the Active Skills in the catalogue.
- `GOAL_TEMPLATE.md`: harness-neutral continuation contract when GitHub Issue
  state is insufficient.
- `VERSION`, `.version-policy.json`, and `CHANGELOG.md`: canonical release
  identity and history.
- `.codex-plugin/`, `.claude-plugin/`, and `.grok-plugin/`: host package
  identity for the ToolboxMD Plugin Registry.
- `bin/versionctl` and `tools/versionctl/`: the plugin entry point and
  dependency-free version mechanics.
- `.github/workflows/`: read-only transition validation and policy-authorized
  exact-SHA GitHub Release automation.

## Skill Catalogue

The [AgentsMD Skill Catalogue](SKILL_CATALOGUE.md) is the only authoritative
inventory for this package. The initial Active set is:

- AgentsMD-native: `version-control`.
- ToolboxMD-native: `use-grok`.
- Adapted from Matt Pocock: `grilling`, `grill-with-docs`,
  `domain-modeling`, `to-spec`, `to-tickets`, `wayfinder`, and
  `writing-for-agents`.

The catalogue records exact source revisions, current ownership, origin,
licence, lifecycle, and local adaptation. Matt-derived material retains its
MIT notice. `use-grok` retains its Apache-2.0 licence and separate source
history. Deferred, retired, and upstream-reference Skills are documented but
remain outside active plugin discovery.

The workflow Skills are human-controlled. `grilling`, `to-spec`,
`to-tickets`, and `wayfinder` run only when the user selects that workflow and
stop at their documented approval gates. `use-grok` runs only after the user
explicitly asks to consult Grok.

## Registry boundaries

Product Registry, Plugin Registry, and Skill Catalogue are separate ownership
surfaces:

- [`toolbox.md`](https://github.com/toolboxmd/toolbox.md) is the Product
  Registry and Discovery Portal for the complete ToolboxMD portfolio.
- [`toolboxmd/marketplace`](https://github.com/toolboxmd/marketplace) is the
  Plugin Registry and distribution channel for installable plugins.
- The [Skill Catalogue](SKILL_CATALOGUE.md) owns only AgentsMD Skill discovery
  and lifecycle.

Karpathy Wiki, ContextMD, Building Agent Skills, GitPix, OpenBot, and other
independent ToolboxMD products keep separate product and release lifecycles.
They are not AgentsMD leaf Skills.

## Glossary convention

`GLOSSARY.md` owns canonical project language for one domain.
`GLOSSARY-MAP.md` routes agents only when several distinct domains need
separate glossaries. A missing glossary is valid. Create one lazily when the
first project-specific term is agreed.

Legacy `CONTEXT.md` and `CONTEXT-MAP.md` files are read-only migration
fallbacks when the new files are absent. Active AgentsMD Skills never create
or update the legacy names. ContextMD remains the reserved name for the future
ToolboxMD Agent Knowledge and Learning System.

## Install boundary

Clone the repository wherever you keep shared tools:

```sh
git clone https://github.com/toolboxmd/agentsmd.git
cd agentsmd
AGENTSMD_DIR="$(pwd -P)"
```

The plugin installs the Active Skill set and bundled CLI entry point. It does
not make this repository's `AGENTS.md` global, put `versionctl` on a normal
terminal `PATH`, remove old global Skills, or change another plugin.

Before migration, inspect every existing Skill with the same name. Hosts may
show duplicate Skill names instead of merging them. Keep the old installation
until the replacement release is installed and Live Verified, then remove or
disable the old copy only with explicit authorization. Never overwrite a
global instruction file or symlink without inspecting and backing it up.

After installing or updating the plugin, start a fresh session. Existing
sessions retain the Skill inventory and instruction chain loaded at startup.

### Codex

Add the ToolboxMD marketplace and install the plugin:

```sh
codex plugin marketplace add toolboxmd/marketplace
codex plugin add agentsmd@toolboxmd
```

In a fresh session, type `$` or use `/skills` to select a bundled Skill. Plugin
Skills use the AgentsMD namespace, for example `$agentsmd:to-spec` and
`$agentsmd:version-control`. A Skill may also activate implicitly when its
description allows that behavior.

Codex reads global guidance from `AGENTS.md` in `CODEX_HOME`, which defaults
to `~/.codex`. Configure that separately when you want the AgentsMD contract in
every repository:

```sh
mkdir -p "$HOME/.codex"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.codex/AGENTS.md"
```

Do not also link the packaged Skills into `$HOME/.agents/skills`; that creates
duplicate active copies. Link only the standalone CLI when ordinary terminal
sessions require it:

```sh
mkdir -p "$HOME/.local/bin"
ln -s "$AGENTSMD_DIR/tools/versionctl/bin/versionctl" \
  "$HOME/.local/bin/versionctl"
```

Ensure `$HOME/.local/bin` is on `PATH` for coding-agent shells.

### Claude Code

Add the `toolboxmd/marketplace` repository as the `toolboxmd` marketplace,
then install and enable `agentsmd@toolboxmd`. In a fresh session, select the
namespaced command, for example `/agentsmd:to-spec` or
`/agentsmd:version-control`.

The plugin does not install global instructions. Configure the canonical
`AGENTS.md` or a `CLAUDE.md` link separately when global policy is desired.

### Grok Build

```sh
grok plugin marketplace add toolboxmd/marketplace
grok plugin install agentsmd --trust
```

Start a fresh session and select the AgentsMD Skill from the host's Skill
surface. Global `AGENTS.md` remains a separate installation:

```sh
mkdir -p "$HOME/.grok"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.grok/AGENTS.md"
```

`use-grok` still requires an authenticated Grok Build CLI and explicit user
invocation. Authentication, quota, and credit use are separate Human Gates.

### Other harnesses

Configure the cloned `AGENTS.md` as global instructions, expose only the
Active `skills/` directories through the harness Skill discovery path, and
keep `GOAL_TEMPLATE.md` beside its canonical source. Do not expose the same
Skill through both the plugin and a global directory.

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
