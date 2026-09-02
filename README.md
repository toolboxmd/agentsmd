# agentsmd

AgentsMD is the ToolboxMD source of truth for a portable agent operating
contract, an approved workflow Skill Catalogue, and deterministic repository
version control. It also owns Project Direction, the confirmed Vision, Mission,
and Objective that keep agent work purposeful and focused. The installable
plugin exposes the same owned workflow suite to Codex, Claude Code, and Grok
Build.

Project instructions remain closer to the code and take precedence over the
global baseline. This matches the discovery model documented for
[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Package contents

- `AGENTS.md`: portable global working agreements.
- `VISION.md`, `MISSION.md`, and `OBJECTIVE.md`: this project's current
  Project Direction.
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
- `bin/project-direction` and `hooks/hooks.json`: deterministic Project
  Direction loading and supported lifecycle registration.
- `.github/workflows/`: read-only transition validation and policy-authorized
  exact-SHA GitHub Release automation.

## Skill Catalogue

The [AgentsMD Skill Catalogue](SKILL_CATALOGUE.md) is the only authoritative
inventory for this package. The initial Active set is:

- AgentsMD-native: `project-direction` and `version-control`.
- ToolboxMD-native: `use-grok`.
- Adapted from Matt Pocock: `grilling`, `grill-with-docs`,
  `domain-modeling`, `prototype`, `research`, `to-spec`, `to-tickets`,
  `wayfinder`, and `writing-for-agents`.

The catalogue records exact source revisions, current ownership, origin,
licence, lifecycle, and local adaptation. Matt-derived material retains its
MIT notice. `use-grok` retains its Apache-2.0 licence and separate source
history. Deferred, retired, and upstream-reference Skills are documented but
remain outside active plugin discovery.

The AgentsMD workflow Skills `grilling`, `grill-with-docs`, `to-spec`,
`to-tickets`, and `wayfinder` are human-controlled planning workflows. They run
only when the user selects that workflow and stop at their documented approval
gates. When a session works a typed Wayfinder Decision Issue, it automatically
uses `research`, `prototype`, or `grilling` as recorded by that Issue; HITL
work still waits for the required human judgment. `use-grok` runs only after
the user explicitly asks to consult Grok.
`project-direction` is model-invoked when the triad is missing, unusable, stale,
contradictory, completed, or explicitly due for review. It requires user
confirmation before writing strategic direction.

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

## Project Direction

Every project repository governed by the AgentsMD contract requires root
`VISION.md`, `MISSION.md`, and `OBJECTIVE.md`:

- Vision is the grand and visionary aspirational long-range destination that
  expands ambition beyond the current work.
- Mission states the strategic present purpose, problem, and approach, grounded
  in what the project does now to move toward the Vision.
- Objective is the single current milestone-level outcome, narrower than the
  Mission but broader than an individual request, task, Issue, commit, or PR,
  with a recognizable completion condition.

The global contract requires the complete current triad in model context before
project discussion, research, planning, specification, implementation, review,
or delivery. A coherent triad whose currentness is established remains project
truth without repeated user confirmation. The model-invoked
`project-direction` Skill initializes or repairs it from repository, tracker,
ADR, glossary, product, and user evidence.
The Skill asks only unresolved strategic questions, shows exact drafts, and
waits for explicit user confirmation before writing. It treats the active task
as evidence rather than the default Objective, keeps a coherent milestone-level
Objective current across contributing work, and reviews a task-level Objective
instead of letting ordinary requests churn project direction.

After loading the local triad, currentness-sensitive conclusions resolve the
intended base, `HEAD`, configured upstream, and locally known ahead/behind
state. The loader exposes that local Git identity without network access or
checkout mutation. When a known upstream is ahead or diverged and changes a
Project Direction file relative to `HEAD`, the payload status is
`potentially_stale`, includes the changed direction filenames, and identifies
the loaded triad as checkout-scoped. Unrelated upstream changes remain `ready`.
Missing or unresolved Git state is explicit metadata and never suppresses the
complete local triad. After reconciliation, all three files must be reread
before subsequent strategic judgment.

For Codex, the plugin registers three deterministic lifecycle hooks:

- `SessionStart` loads at startup, resume, clear, and compact. A root-task
  automatic compaction reloads before the immediate model continuation.
- `UserPromptSubmit` reloads when the Git root or any content hash changes and
  stays silent for an already loaded session/root/hash state.
- `SubagentStart` loads the complete triad into each new worker.

The loader resolves the Git root, reads the files in Vision, Mission, Objective
order, and emits one bounded block with exact paths, SHA-256 hashes, and complete
contents. Missing, blank, unreadable, unsafe, or oversized direction produces
one explicit uninitialized state. It never emits a partial or truncated triad.
The limits are 8,192 bytes per file and 16,384 bytes combined. Direction-file
contents are repository data, not executable policy and not authority to cross
Human Gates.

Codex requires the user to review and trust a new or changed plugin hook hash.
Use `/hooks` in a fresh session to inspect that state. Hooks can also be disabled
by host or administrator policy, so the `AGENTS.md` first-read rule remains the
fallback. Current Codex hooks prove root-task post-compaction reload and
subagent-start injection. The public contract does not prove reinjection after
a subagent's private compaction. Automatic lifecycle behavior on other hosts is
not claimed until it receives equivalent host-level acceptance.

## Install boundary

Clone the repository wherever you keep shared tools:

```sh
git clone https://github.com/toolboxmd/agentsmd.git
cd agentsmd
AGENTSMD_DIR="$(pwd -P)"
```

The plugin installs the Active Skill set, Project Direction loader and hooks,
and bundled CLI entry points. It does not make this repository's `AGENTS.md`
global, put its CLIs on a normal terminal `PATH`, remove old global Skills, or
change another plugin. Full Project Direction behavior requires both the global
contract and the enabled, trusted plugin hooks.

Before migration, inspect every existing Skill with the same name. Hosts may
show duplicate Skill names instead of merging them. Keep the old installation
until the replacement release is installed and Live Verified, then remove or
disable the old copy only with explicit authorization. Never overwrite a
global instruction file or symlink without inspecting and backing it up. The
global-instruction installer enforces that boundary independently from plugin
installation.

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
description allows that behavior. Open `/hooks`, review the AgentsMD Project
Direction hook, and trust its current hash before relying on automatic loading.

Codex reads global guidance from `AGENTS.md` in `CODEX_HOME`, which defaults
to `~/.codex`. Configure that separately when you want the AgentsMD contract in
every repository:

```sh
./bin/agentsmd-global-instructions inspect
./bin/agentsmd-global-instructions install \
  --source "$AGENTSMD_DIR/AGENTS.md"
```

`inspect` exits non-zero for a missing target, a broken link, a link into a
plugin cache, or a pre-existing non-symlink. A first install creates the stable
link. Replacing any existing target requires explicit `--replace` authority;
the command first preserves it under `~/.codex/agentsmd-backups/` and then
verifies the new link and content digest. Re-running the same install is a
no-op and creates no new backup:

```sh
./bin/agentsmd-global-instructions install \
  --source "$AGENTSMD_DIR/AGENTS.md" \
  --replace
./bin/agentsmd-global-instructions inspect
```

The source must be an existing stable `AGENTS.md`, normally from the canonical
clone. The command rejects sources and targets under any `plugins/cache`
directory. Use `--target` only to configure an intentional non-default Codex
home, and `--backup-dir` only when the default adjacent backup directory is not
appropriate.

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
The `project-direction` Skill is packaged, but this release does not claim
Claude Code lifecycle-hook acceptance.

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
The `project-direction` Skill is packaged, but this release does not claim Grok
Build lifecycle-hook acceptance.

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
