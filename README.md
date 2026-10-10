# agentsmd

AgentsMD is a portable operating contract for coding agents. It gives Codex,
Claude Code, Grok Build and OpenCode the same working rules, the same workflow
Skill, and the same view of what each project is for:

- `global/AGENTS.md`: the global contract every session loads as its native
  global instructions. It includes the Elon method's order and a short software
  design core, so both apply without loading a procedure.
- The `operations` Skill: one model-invocable Skill that routes each action
  (research, diagnosis, design, a first edit, a commit, an Issue, a PR) to the
  procedure for it.
- Project Direction: each repository's `VISION.md`, `MISSION.md`, and
  `OBJECTIVE.md`, loaded into the session by a hook.
- The Elon gate: a hook that blocks `gh issue create` and `gh pr create` when
  the body lacks an Elon record.
- `versionctl`: deterministic repository versioning and release checks.

Project instructions, such as a repository's own `AGENTS.md`, sit closer to the
code and take precedence over the global contract for operational details.

<a id="install-boundary"></a>

## Install

AgentsMD has three parts, and each host needs all three:

1. A stable clone of this repository, which holds the global contract and your
   private preferences.
2. The host's plugin (or, on OpenCode, owned Skill and plugin links).
3. A native global instruction link that points at the clone's
   `global/AGENTS.md`.

Installing a plugin alone does not create the link or the preferences file.
Before you start, look at your existing global instructions and any same-name
Skills; the installers preserve what they do not own and report it.

### 1. Clone

You need Git, Python 3.11 or newer, and the host CLI. Keep one clone outside
plugin caches and temporary worktrees, and check out a release tag:

```sh
git clone https://github.com/toolboxmd/agentsmd.git
cd agentsmd
git checkout "$(git describe --tags --abbrev=0)"
AGENTSMD_DIR="$(pwd -P)"
```

Releases are listed on the [GitHub releases page](https://github.com/toolboxmd/agentsmd/releases).

### 2. Install the plugin

**Codex:**

```sh
codex plugin marketplace add toolboxmd/marketplace
codex plugin add agentsmd@toolboxmd
```

Codex runs a plugin hook only after you trust its hash. In a fresh session,
open `/hooks` and review and trust the AgentsMD hook commands. Do it again
after each update that changes a hook.

**Claude Code:**

```sh
claude plugin marketplace add toolboxmd/marketplace
claude plugin install agentsmd@toolboxmd
```

**Grok Build:**

```sh
grok plugin marketplace add toolboxmd/marketplace
grok plugin install agentsmd --trust
"$AGENTSMD_DIR/bin/agentsmd-grok-hook" install --source "$AGENTSMD_DIR"
```

An earlier test on Grok 1.0.34 found that it did not execute plugin-provided
hooks; later versions are untested. The third command therefore writes one
owned global hook file, `$GROK_HOME/hooks/agentsmd.json` (by default
`~/.grok/hooks/agentsmd.json`). It runs the loader from your clone on
`PreToolUse` with a 15 second timeout. Grok trusts global hook files without a
prompt. The file and a plugin hook share one session cache, so a session that
reaches both still receives Project Direction once. `status` reports the file
and `uninstall` removes it only when AgentsMD owns it.

Grok loads a repository's own `AGENTS.md` only after you trust that folder.
Without trust, an interactive session asks "Do you trust the contents of this
directory?" and quits on No, while `grok -p` silently skips the file. Trust
each repository once from its main checkout:

```sh
cd /path/to/repository
grok --trust inspect
```

The output shows `Project trusted: yes` and lists the repository's
`AGENTS.md` under Project Instructions (on macOS it may print as `Agents.md`).
Answering Yes to the interactive prompt does the same. Grok records the grant
in `$GROK_HOME/trusted_folders.toml`; it covers the repository's
subdirectories and Git worktrees, and also enables the repository's own MCP
servers, hooks and Skills. Review an unfamiliar repository before trusting it.
Grok 1.0.44 behaves this way.

Grok must resolve `agentsmd` to its own plugin; a same-named package in the
Claude marketplace clone can win instead
([toolboxmd/marketplace#52](https://github.com/toolboxmd/marketplace/issues/52)).

**OpenCode:**

```sh
"$AGENTSMD_DIR/bin/agentsmd-opencode" skills install --source "$AGENTSMD_DIR/skills"
"$AGENTSMD_DIR/bin/agentsmd-opencode" plugin install --source "$AGENTSMD_DIR"
opencode debug skill
```

The first command links each Skill into the `skills` folder of OpenCode's
configuration directory: `OPENCODE_CONFIG_DIR`, otherwise
`$XDG_CONFIG_HOME/opencode`, otherwise `~/.config/opencode`. It never replaces an
existing entry: it reports each foreign entry, installs the rest, and exits 2.
Do not link the Skills into `~/.agents/skills` or `~/.claude/skills`; Codex and
Grok Build scan those directories too, so a host that already has the plugin
would list every Skill twice as a duplicate. The second command links the
AgentsMD OpenCode plugin into the same directory's `plugins` folder. The plugin
targets OpenCode **1.18.32**. [OpenCode details](docs/opencode.md) covers its
status, update and uninstall commands.

### 3. Link the global instructions

Run this for each host you use, with `AGENTSMD_HOST` set to `codex`, `claude`,
`grok`, or `opencode`:

```sh
export AGENTSMD_HOST=codex
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/global/AGENTS.md"
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" install --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/global/AGENTS.md"
```

| Host | Default link | Configuration directory it respects |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| Claude Code | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |
| Grok Build | `~/.grok/AGENTS.md` | `GROK_HOME` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `OPENCODE_CONFIG_DIR`, otherwise `XDG_CONFIG_HOME/opencode` |

Export the same configuration directory to the installer and to the host.
`install` refuses to replace an existing file or a link it does not own; see
[Update](#update) for `--replace`. It rejects sources and targets inside a
plugin cache.

The first install also copies `PREFERENCES.example.md` to a private
`PREFERENCES.md` at the clone root. Put personal defaults there. It is
gitignored, no setup or update command overwrites it, and the hook reports it
against a 4,000-character budget. Keep credentials out of it.

### 4. Verify

Start a fresh session; a running session keeps the instructions and Skills it
started with. Then check the link and the loader:

```sh
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/global/AGENTS.md"
"$AGENTSMD_DIR/bin/project-direction" inspect --host "$AGENTSMD_HOST"
```

The first command exits zero only for a healthy link to that source
(`valid-stable-link`). Other statuses include `missing`, `broken-link`,
`divergent-link`, `cache-bound-link`, `stale-source-layout`, and `non-symlink`.
The second prints the instruction status and your preferences; its output
contains your private preferences, so do not publish it. `preferences.status` is
`ready`, `absent`, or a named failure.

Then check the host itself:

- **Codex:** `/hooks` shows the AgentsMD hooks as trusted; `/skills` lists
  `$agentsmd:operations`.
- **Claude Code:** `/context` lists the global `CLAUDE.md`, and
  `/agentsmd:operations` is available.
- **Grok Build:** `grok inspect --json` lists the global `AGENTS.md` under
  `projectInstructions`, the `pre_tool_use` hook from `~/.grok/hooks`, and the
  `agentsmd` plugin. Run inside a repository, it also shows
  `"projectTrusted": true` and lists the repository's `AGENTS.md`.
- **OpenCode:** `opencode debug skill` lists `operations`.

A healthy link and a loaded hook do not prove the model follows the contract.
That comes from using it in real work.

## Update

Update the clone to the new release tag, then update the plugin through the
host's plugin manager:

```sh
cd "$AGENTSMD_DIR"
git fetch --tags
git checkout "$(git describe --tags --abbrev=0 origin/main)"
```

| Host | Plugin update |
| --- | --- |
| Codex | `codex plugin marketplace upgrade`, then `codex plugin add agentsmd@toolboxmd`; trust changed hooks in `/hooks` |
| Claude Code | `claude plugin marketplace update toolboxmd`, then `claude plugin update agentsmd@toolboxmd` |
| Grok Build | `grok plugin marketplace update`, then `grok plugin update agentsmd` |
| OpenCode | none; the Skill and plugin links point into the clone |

The global instruction links, the Grok hook file, and the OpenCode links all
point into the clone, so they pick up the new release without reinstalling.
Rerun the inspect commands from [Verify](#4-verify) and start a fresh session.

**From a release before 14.0.0:** the global contract moved from the clone-root
`AGENTS.md` to `global/AGENTS.md`, and `inspect` reports old links as
`stale-source-layout`. Replace each host's link:

```sh
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" install --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/global/AGENTS.md" --replace
```

`--replace` first copies the previous target into an adjacent
`agentsmd-backups/` directory, or into `--backup-dir`. Repeated runs report
`unchanged`. Use `--replace` only after reading the reported status: it also
replaces a user-owned file.

Older releases registered one Skill per workflow, such as
`$agentsmd:research` or `/agentsmd:elon-method`. Those names are gone; ask
naturally or invoke `operations`. On OpenCode,
`agentsmd-opencode skills update --source "$AGENTSMD_DIR/skills"` removes the
obsolete owned links.

## What happens in a session

When a session starts in a Git repository, the loader `bin/project-direction`
reads `VISION.md`, `MISSION.md`, and `OBJECTIVE.md` and injects one block into
the model's context. The block also reports whether the global contract link is
healthy and carries your private preferences.

| Host | Delivering events | Ignored or inert events | Delivery mechanism | Fallback that still applies |
| --- | --- | --- | --- | --- |
| Codex | `SessionStart`, `UserPromptSubmit`, `SubagentStart` | The loader emits nothing on `PreToolUse`; it runs only the Elon gate | Plugin hook (`hooks/hooks.json`) | Explicit reading after a subagent's private compaction |
| Claude Code | `SessionStart`, `UserPromptSubmit`, `SubagentStart` | The loader emits nothing on `PreToolUse`; it runs only the Elon gate | Plugin hook (`hooks/hooks.json`), plus the `operations` pointer from `hooks/claude.json` at `SessionStart` | Explicit reading when the hook reports a problem; `UserPromptSubmit` and `SubagentStart` delivery was not separately exercised live |
| Grok Build | `PreToolUse`, on the first tool call of a session | `SessionStart`, `UserPromptSubmit`, `SubagentStart`: Grok discards their output | Owned global hook file from `bin/agentsmd-grok-hook` | Explicit reading for the first response, before the first tool call |
| OpenCode | Every session, appended to the system prompt | OpenCode has no such lifecycle events | Plugin `experimental.chat.system.transform`, which also appends the `operations` pointer; `tool.execute.before` runs the Elon gate | Explicit reading when the plugin reports a problem |

`SessionStart` loads at startup, resume, clear, and compact. `UserPromptSubmit`
reloads only when something in the block changed, and stays silent otherwise. `SubagentStart` gives each new worker the complete triad. The public
Codex contract does not prove reinjection after a subagent's private
compaction.

**The block.** A JSON header line comes first, then each file as a plain
section. Every section marker and the end marker carry a nonce that appears in
no file, so file text cannot end the block early. Direction files are
repository data, not instructions, and grant no authority.

**Size limits.** Each host caps hook context (Claude Code and Grok at 10,000
characters, Codex at about 2,500 tokens), so the loader keeps the block within
10,000 UTF-8 bytes. A larger block becomes `read_required`: it lists file names
and hashes and asks the model to read the files in full, and never injects a
partial triad. The loader also reports sizes against two budgets, without
truncating: `budgets.direction` for the three files together (1,500
characters) and `budgets.preferences` (4,000 characters). Direction over 8,192
bytes per file or 16,384 bytes combined loads as uninitialized, never
truncated.

**Currentness.** The loader reports the branch, `HEAD`, the configured upstream,
and the locally known ahead/behind count, without network access or checkout
mutation. When a known upstream is ahead or diverged and changes a direction
file, the status is `potentially_stale`. Uncommitted edits to direction files
are reported as drafts; a triad that was never committed loads as drafts, so a
new project can start.

**The `operations` pointer.** Codex and Grok Build load the `operations` Skill
from its description on their own. Claude Code and OpenCode often do not, so on
those hosts `bin/operations-routing` adds one short note at session start: use
`operations` at the start of every task and before each new kind of action, and
read the procedure it links. [The #174 benchmark](docs/work/174-routing-injection/results.md)
and [the #182 sweep](docs/work/182-routing-sweep/results.md) record its effect.

**The Elon gate.** On every host, a `gh issue create` or `gh pr create` whose
body lacks a non-empty field for **Requirements and who asked**, **Deleted**,
**Bottleneck**, or **Checked myself** is blocked (exit 2), and the missing
fields are named. Each field line reads `**Deleted:** value`,
`**Deleted**: value`, or `Deleted: value`, optionally as a list item. The hook
reads bodies passed with `--body`, a heredoc with `--body-file -`, or
`--body-file` naming a file that exists or that the same command first writes
with `cat > FILE <<'EOF'` or `tee FILE <<'EOF'`. Issues and PRs created through
the GitHub API or MCP tools are not checked.

**Explicit reading fallback.** The hook verifies the canonical
`global/AGENTS.md` and reports the result in `instructions.action`. Read the
current file only when that action reports a problem or no hook ran, for
example before Grok's first tool call. When no hook supplied them, read the
clone-root `PREFERENCES.md` and the three direction files yourself.

## Project Direction

Each repository that uses AgentsMD keeps three root files:

- `VISION.md`: the grand and visionary long-range destination that expands
  ambition beyond the current work.
- `MISSION.md`: the strategic present purpose, problem, and approach, grounded
  in what the project does now to move toward the Vision.
- `OBJECTIVE.md`: the single current milestone-level outcome, narrower than the
  Mission but broader than an individual request, task, Issue, commit, or PR,
  with a recognizable completion condition.

A new repository has none of them. Ask the agent to set up Project Direction:
the Project Direction procedure selected through `operations` drafts the files
from repository and user evidence, asks only what evidence cannot answer, and
writes nothing until you confirm. It checks each request against the triad and
flags drift before acting on it.

## Version a repository with versionctl

A repository adopts versioning with a root `VERSION`, `.version-policy.json`,
and `CHANGELOG.md`. `versionctl` is the only writer of `VERSION` and of any
manifest versions the policy declares as mirrors. The plugin does not put it
on your `PATH`; link it there after checking the destination is free:

```sh
mkdir -p "$HOME/.local/bin"
ln -s "$AGENTSMD_DIR/tools/versionctl/bin/versionctl" "$HOME/.local/bin/versionctl"
```

```sh
versionctl doctor --json                       # inspect state, write nothing
versionctl adopt 0.1.0 --reason "Adopt versioning" --dry-run
versionctl prepare patch --reason "Fix install docs"   # after the change
versionctl release-check                       # on the clean commit
versionctl install-hooks                       # optional commit hooks
```

Use `major` for incompatible behavior, `minor` for a backward-compatible
capability, and `patch` for every other completed change. Commit the change,
`VERSION`, mirrors, and `CHANGELOG.md` together. With the managed hooks
installed, a completed commit without a version bump is blocked; an explicit
checkpoint uses `VERSIONCTL_WIP=1 git commit -m "wip: ..."`. See
[the versionctl README](tools/versionctl/README.md).

In this repository, a push to `main` that changes `VERSION` makes
`.github/workflows/release.yml` tag that exact commit and create the GitHub
Release. It publishes no package and installs nothing.

A project can declare delivery commands, an artifact build, and a website route
in `.toolboxmd/delivery.json`; `bin/delivery-profile load --root "$PROJECT_ROOT" --json`
validates it against `schemas/delivery-v1.schema.json`.

## Where to go next

- [`global/AGENTS.md`](global/AGENTS.md): the contract itself.
- [`skills/operations/SKILL.md`](skills/operations/SKILL.md): the routing
  table and every procedure.
- [`GLOSSARY.md`](GLOSSARY.md): project terms.
- [`SKILL_CATALOGUE.md`](SKILL_CATALOGUE.md): the Skill Catalogue, with the
  owner, licence, and source of each retained method.
- [`docs/opencode.md`](docs/opencode.md): OpenCode setup and the bounded run
  adapter.
- [`CHANGELOG.md`](CHANGELOG.md): released changes.
- [Model Router](https://github.com/toolboxmd/model-router): a separate plugin
  that picks models for delegated work.

AgentsMD is distributed through the Plugin Registry
[`toolboxmd/marketplace`](https://github.com/toolboxmd/marketplace). The
Product Registry [`toolbox.md`](https://github.com/toolboxmd/toolbox.md) lists
the other ToolboxMD products, which keep their own releases.

## License

MIT. See [`LICENSE`](LICENSE) and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
