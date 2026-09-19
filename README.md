# agentsmd

AgentsMD is the ToolboxMD source of truth for a portable agent operating
contract, an approved workflow Skill Catalogue, and deterministic repository
version control. It also owns Project Direction, the confirmed Vision, Mission,
and Objective that keep agent work purposeful and focused. The installable
plugin exposes the same owned workflow suite to Codex, Claude Code, and Grok
Build. OpenCode uses shared Skills and its native global instruction link.

For a new install, follow the [setup walkthrough](#install-boundary). It covers
plugins or shared Skills, one canonical instruction source, and private defaults.

Project instructions remain closer to the code and take precedence over the
global baseline. This matches the discovery model documented for
[Codex AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Package contents

- `AGENTS.md`: portable global working agreements.
- `PREFERENCES.example.md`: generic template for private adjacent `PREFERENCES.md`.
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
- `.toolboxmd/delivery.json`, `schemas/delivery-v1.schema.json`, and
  `bin/delivery-profile`: Project delivery deltas, their strict schema, and the
  dependency-free loader.
- `bin/project-direction` and `hooks/hooks.json`: deterministic Project
  Direction loading and supported lifecycle registration.
- `.github/workflows/`: read-only transition validation and policy-authorized
  exact-SHA GitHub Release automation.

## Skill Catalogue

The [AgentsMD Skill Catalogue](SKILL_CATALOGUE.md) is the only authoritative
inventory for this package. The initial Active set is:

- AgentsMD-native: `algorithm`, `elon-method`, `delivery-profile`, `operations`,
  `project-direction`, and `version-control`.
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
gates.
Selecting `to-spec` runs the complete Specify workflow through verified ticket
publication by default. It waits for approval before publishing the parent
Issue and before publishing the ticket graph, then starts the first unblocked
Issue only when the full current request already authorizes implementation. A
planning-only request asks exactly once for that authority, and an explicit
Parent Spec only request stops after the verified parent. `to-spec` owns its
ticket-graph continuation directly, while `to-tickets` remains available only
when the user explicitly selects it for standalone ticket decomposition.

Issue #39 supersedes only the Issue #5 human-routing decision that stopped the
selected Specify workflow between established stages; all other Issue #5
outcomes remain unchanged.

When a session works a typed Wayfinder Decision Issue, it automatically uses
`research`, `prototype`, or `grilling` as recorded by that Issue; HITL work still
waits for the required human judgment. `use-grok` runs only after the user
explicitly asks to consult Grok.
`project-direction` is model-invoked when the triad is missing, unusable, stale,
contradictory, completed, or explicitly due for review. It requires user
confirmation before writing strategic direction.
`elon-method` is model-invoked for material design, task selection and
reassessment, inherited assumptions, cost claims, and stalled progress. It
routes to first principles, idiot index, current constraint, and the ordered
Algorithm. Constraint selection uses evidence and a falsifying check; cost
comparisons require comparable units and scope. `algorithm` remains a
compatibility router. Small direct microfixes remain direct.
`delivery-profile` is model-invoked when a Project delivery profile exists or
Project-specific commands, artifacts, or website mapping are being used.

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

## Delivery System v1

The core in `AGENTS.md` owns alignment, authority, and routing. The applicable
[`operations` modules](skills/operations/SKILL.md) own lifecycle, execution,
review, artifact, website, and evidence procedures; `version-control` owns
version mechanics. Each delivery state is reported separately. Projects can
[reuse scoped proof](docs/scoped-proof.md)
under an explicit trusted policy: complete baseline coverage plus current affected
and artifact checks. Unknown scope stops with a reason. Projects without an
adapter retain their complete merge and release gates.

A Project may add `.toolboxmd/delivery.json` for only three kinds of real
difference:

- changed-scope, complete, and exact-SHA release commands;
- one exact-SHA artifact build, versioned output path, and SHA-256 digest;
- the website repository, HTTPS origin, and route.

Canonical version remains in `VERSION`; Project identity and discovery remain
in `.toolboxmd/project.json`; release rules remain in
`.version-policy.json`; documentation and current delivery evidence remain in
their normal owners. The strict schema rejects fields that would duplicate
those facts.

Load and validate a profile from any directory below its Project root:

```sh
bin/delivery-profile load --root "$PROJECT_ROOT" --json
```

The AgentsMD profile uses the real repository test suites, exact-SHA
`release-check`, reproducible plugin archive command, and ToolboxMD website
mapping. Profile validation resolves each command executable without running
the delivery commands.

For Codex, the plugin registers three deterministic context-loading lifecycle
hooks:

- `SessionStart` loads at startup, resume, clear, and compact. A root-task
  automatic compaction reloads before the immediate model continuation.
- `UserPromptSubmit` reloads when the Git root or any content hash changes and
  stays silent for an already loaded session/root/hash state.
- `SubagentStart` loads the complete triad into each new worker.

A fourth manifest entry, `PreToolUse`, serves Grok Build alone. It exits without
output unless Grok's own hook environment is present, so Codex and Claude Code
behavior is unchanged.

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

Use this walkthrough for a new installation or migration. AgentsMD has three
separate parts: a plugin or shared Skills, a native global instruction link,
and private preferences beside that link's canonical source. Installing a
plugin alone does not configure the other two.

### 1. Prepare the canonical clone

Use a POSIX host with Git, Python 3.11 or newer, and your chosen harness CLI.
Keep one stable clone outside plugin caches and temporary task worktrees:

```sh
git clone https://github.com/toolboxmd/agentsmd.git
cd agentsmd
AGENTSMD_DIR="$(pwd -P)"
```

Use a published release tag for production setup. The installer checks source
identity and bytes, not release provenance. Inspect existing global instructions
and same-name Skills first. Preserve unrelated files, settings and credentials.
Do not remove an old Skill installation until its replacement is verified and
removal is authorized. Existing sessions may retain their startup instructions
and Skill inventory; start a fresh session after setup or updates.

### 2. Install the host's plugin or supported Skills

**Codex:** automatic delegated model selection requires the separate
[Model Router `model-routing` Skill](https://github.com/toolboxmd/model-router).
AgentsMD does not bundle it. At this change's verification date, that repository
has no published release and the Skill is unavailable in the inspected install.
Do not invent a release tag or treat link/preferences setup as working automatic
routing. Follow Model Router's supported release instructions when available;
missing routing resources stop the affected dispatch under the core contract.
Direct work and other hosts remain available.

```sh
codex plugin marketplace add toolboxmd/marketplace
codex plugin add agentsmd@toolboxmd
```

In a fresh Codex session, use `/skills` or `$` to inspect namespaced Skills such
as `$agentsmd:to-spec`. Open `/hooks`, review the AgentsMD hook commands, and
trust the current hook hash. Recheck trust after hook updates. Disabled or
untrusted hooks require the explicit reading fallback below.

**Claude Code:**

```sh
claude plugin marketplace add toolboxmd/marketplace
claude plugin install agentsmd@toolboxmd
```

In a fresh session, inspect the plugin and select `/agentsmd:to-spec` or another
bundled Skill. Claude lifecycle-hook acceptance is not claimed by this release.

**Grok Build:**

```sh
grok plugin marketplace add toolboxmd/marketplace
grok plugin install agentsmd --trust
```

Inspect Skills in a fresh session. The separately pinned `use-grok` Skill still
requires explicit invocation and an authenticated CLI. This setup grants no
new authentication, quota or credit authority.

Grok reads plugin hook output only on a tool call, so Project Direction arrives
with the first tool result of a session. Later tool calls stay silent until the
triad changes. Nothing arrives before that first tool result, so the explicit
reading fallback below covers the first response. Grok must also resolve
`agentsmd` to its own install: a same-named package without hooks in the Claude
marketplace clone wins instead and delivers no context.
[toolboxmd/marketplace#52](https://github.com/toolboxmd/marketplace/issues/52)
tracks that collision. Live Grok hook acceptance is not claimed by this release.

**OpenCode:** link the packaged Skills only into OpenCode's own global Skill
directory. Never link them into `~/.agents/skills`, `~/.claude/skills`, or
`~/.grok/skills`: Codex and Grok Build scan `~/.agents/skills`, and Grok scans
`~/.claude/skills`, so a host that already uses the plugin would list every
Skill twice. There is no AgentsMD OpenCode plugin.

```sh
"$AGENTSMD_DIR/bin/agentsmd-opencode" skills install --source "$AGENTSMD_DIR/skills"
opencode debug skill
```

The command creates one owned link per Skill under
`${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills` and never replaces an
existing entry; it preserves and reports each foreign entry, installs the rest
and exits 2. Inspect existing same-name Skills instead of overwriting them.
`skills status` and `skills uninstall` report and remove only those owned
links. OpenCode's bounded run adapter remains pinned to **1.18.29**; link setup
does not expand that run contract. See [OpenCode details](docs/opencode.md).

### 3. Link global instructions and initialize preferences

Run the following for each desired host, setting `AGENTSMD_HOST` to `codex`, `grok`,
`opencode`, or `claude`:

```sh
export AGENTSMD_HOST=codex
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/AGENTS.md"
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" install --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/AGENTS.md"
```

| Host | Default global path | Respected configuration directory |
| --- | --- | --- |
| Codex | `~/.codex/AGENTS.md` | `CODEX_HOME` |
| Grok Build | `~/.grok/AGENTS.md` | `GROK_HOME` |
| OpenCode | `~/.config/opencode/AGENTS.md` | `OPENCODE_CONFIG_DIR`, otherwise `XDG_CONFIG_HOME/opencode` |
| Claude Code | `~/.claude/CLAUDE.md` | `CLAUDE_CONFIG_DIR` |

All links resolve to the same stable `AGENTS.md`. Set `AGENTSMD_HOST` separately
for each host process: `codex`, `grok`, `opencode`, or `claude`. The loader's
`--host` option overrides that environment selection. Do not reuse a different
host's exported value. Legacy `project-direction hook` callers default to Codex
only when other configured native paths do not imply a conflicting source.
Conflicts report `source-ambiguous` and inject no preferences until selection is
explicit. No host identity is inferred from inherited Codex/Claude markers.
Export configuration-directory overrides consistently in installer and host environments.
Grok documents `GROK_HOME` in its [settings guide](https://docs.x.ai/build/settings);
unset or empty values retain the default `~/.grok` path. OpenCode documents a custom config
directory in its [configuration guide](https://opencode.ai/docs/config/).
Claude documents `CLAUDE_CONFIG_DIR` in its
[directory guide](https://code.claude.com/docs/en/claude-directory); verify its
actual instruction discovery in the installed version, because host bugs can
make documented path support differ from loaded context.

Inspection reports `missing`, `broken-link`, `cache-bound-link`,
`cache-bound-target`, `invalid-link-target`, or user-owned `non-symlink` targets.
With `--source`, a different stable source reports `divergent-link`, even when
its bytes match. Only a healthy matching link exits zero. Without `--source`,
`valid-stable-link` proves a stable destination, not the intended identity.

Existing targets are preserved unless you explicitly authorize replacement:

```sh
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" install --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/AGENTS.md" --replace
```

Replacement first creates a recoverable backup in the target's adjacent
`agentsmd-backups/` directory. `--backup-dir` selects another backup location.
`--target` remains available for deliberate non-default native paths; ordinary
setup should use the host's documented configuration override so the loader
finds the same path. Sources and targets inside `plugins/cache` are rejected.
The result records source and target SHA-256 digests; repeated setup reports
`unchanged` and creates no extra backup.

Setup copies tracked `PREFERENCES.example.md` to adjacent private
`PREFERENCES.md` only when absent. Existing contents survive all setup and update
commands, including OpenCode's ownership-safe lifecycle. Edit the private file
for personal defaults; never commit it. It is gitignored and excluded from Git
release archives. Keep credentials elsewhere. Explicit task instructions,
required project constraints, proof and authority boundaries take precedence.
Machine roles do not authorize deployment. Project commands belong in their
owning repository, not the shared contract.

OpenCode's existing `agentsmd-opencode install/status/update/uninstall`
interface retains its exact-link ownership checks and JSON reports. Use that
adapter for owned updates or removal, as described in [its guide](docs/opencode.md).
The common installer supplies the explicit backed-up migration path for a
user-owned OpenCode target. Neither command changes host settings or credentials.

### 4. Verify discovery and current context

```sh
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --host "$AGENTSMD_HOST" \
  --source "$AGENTSMD_DIR/AGENTS.md"
"$AGENTSMD_DIR/bin/project-direction" inspect --host "$AGENTSMD_HOST"
```

The first command verifies link identity. The second reads private preferences
from that source's directory, including outside Git and when invoked from a
plugin cache. It never reads project-local preferences or substitutes the
example. Its JSON contains private text: do not publish raw output.
`preferences.status` is `ready` with complete contents, `absent` for shared
defaults, or an explicit failure. Files over 8,192 bytes return `oversized`
and require an explicit full read; they are never silently truncated.

On supported Codex lifecycle boundaries, the existing Project Direction loader
also supplies canonical source path/hash and preferences. Unchanged prompts
stay silent. Source/content changes, deletion, startup, resume, clear,
root-task compaction and new workers refresh context. Private subagent
compaction still needs explicit reading. Combined serialized context is limited
to 14,000 UTF-8 bytes, conservatively below the 16,000-token hook allowance.
If JSON escaping or combined contents exceed that budget, `read_required`
retains file paths/hashes and requires complete explicit reads; no partial triad
or private contents are injected. Hooks cache only fingerprints, not
private contents. The increased hook context allowance requires renewed trust.

**Explicit reading fallback:** at task/worker start, after context loss and after
source changes, inspect the selected host's link, compare its source path/hash
with the full global instructions in context, and read current canonical
`AGENTS.md` when freshness is unproved. Read adjacent `PREFERENCES.md` in full
when present; report unreadable files and discard deleted preferences. Load
applicable project instructions and the complete Project Direction triad for
repository work. Keep Skill bodies on demand. A worker also needs the exact
Issue scope, authority, base and exclusive workspace in its task packet.

A valid link does not prove native discovery, complete model context or
behavioral compliance. Check each installed host separately:

- **Codex:** inspect `/hooks` and `/skills` in a fresh session. CLI 0.154.0's
  `codex debug prompt-input` provides a deterministic prompt inspection surface.
  Compare source paths and full known instruction bytes locally; do not publish
  raw prompts. Codex builds native guidance once per run, per its
  [discovery contract](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
  Existing desktop child context was observed to retain old global text even
  while a fresh CLI process loaded current text. The freshness boundary above
  addresses that limitation without repeated whole-contract hook injection.
- **Grok:** `grok inspect --json` exposes instruction sources and byte counts.
  Version 1.0.34 reports the global file; project discovery is trust-gated.
  Compare the native source and full expected byte count. Do not interpret an
  untrusted project's omitted files as proof of compatibility deduplication.
  Confirm the same output resolves `agentsmd` to Grok's own installed plugin
  with hooks, not to the hookless Claude marketplace clone
  ([toolboxmd/marketplace#52](https://github.com/toolboxmd/marketplace/issues/52)).
  Grok clips hook context at 10,000 characters, so the loader falls back to
  `read_required` paths and hashes above that cap and requires explicit reads.
- **OpenCode:** `opencode debug paths` and `opencode debug skill` inspect paths
  and Skills. Version 1.18.31 does not expose complete discovered native rule
  contents through `debug config`; settings output is not loaded-context proof.
  In a fresh session, verify native/project instruction composition manually.
  Its [rules](https://opencode.ai/docs/rules/) describe Claude files as fallbacks;
  avoid adding the same file through configured `instructions` as well.
- **Claude Code:** use `/context` in a fresh session to inspect memory files and
  confirm the native global path, including when `CLAUDE_CONFIG_DIR` is set.
  Full native discovery on version 2.1.276 remains unverified in this change.

When native and compatibility files coexist, verify each intended source appears
once with complete contents, and preserve project-specific rules. Deterministic
adapter regressions do not prove host-side duplicate suppression. Host discovery,
link correctness, preference loading and user behavioral Live Verification are
separate results. No paid model test is required.

### 5. Update and troubleshoot

Update the stable clone to the intended released revision while preserving
private preferences and user changes. Update the host plugin through its native
plugin manager, rerun link inspection, review changed hook trust and start a
fresh session. Do not point global links at disposable plugin caches.

If link inspection fails, inspect its exact status before using `--replace`.
If preferences report `source-unavailable`, repair the selected native link;
do not copy preferences into the current project. If a hook stays silent after
restoration, use the explicit reading fallback and check hook trust. If source
hashes changed during a long session, read the current source before continuing.
An installed plugin, a healthy link, loaded preferences and correct behavior each
need their own evidence.

The plugin does not place CLIs on the terminal `PATH`. If needed, link the
standalone version CLI after inspecting any existing destination:

```sh
mkdir -p "$HOME/.local/bin"
ln -s "$AGENTSMD_DIR/tools/versionctl/bin/versionctl" "$HOME/.local/bin/versionctl"
```

Ensure that directory is on `PATH`. Other hosts can use canonical instructions
and Active Skills with explicit reading; automatic hook parity is not claimed.

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

Read the policy before using it. Put personal defaults in private
`PREFERENCES.md`; change shared policy only when that is the intended outcome. Keep project-specific commands,
architecture, checks, and deployment rules inside each project.

## License

MIT. See `LICENSE`.

## Core and operating procedures

`AGENTS.md` keeps alignment, judgment, authority, task routing and truthful
reporting in the core. The model-invoked `operations` Skill holds seven linked
references for implementation, orchestration/dependencies, verification,
delivery, finalization, repository setup and legacy reconciliation. Agents load
only the procedures their next action needs and reuse unchanged context.

The main agent owns the outcome and delegates when it reduces total work or
provides required independence. Choose after simplifying the solution.
Exact approved prose retains the narrow review exception in verification.

Global instruction installation links only `AGENTS.md`. Resolve its symlink to
the canonical AgentsMD checkout and use `skills/operations/SKILL.md` there to
keep the core and modules coherent. Installed Skill discovery also supplies the
operations package; check compatibility before combining sources. Resolve
references from the actual selected Skill directory, never a target-project cwd
or the directory containing the global symlink. Missing modules block only the
action that requires them. No new runtime or configuration is needed.

Keep full current Project Direction in context; reuse unchanged contents on
follow-ups and reload after change or context loss. Existing loader hooks and
local Project Direction exceptions remain supported. One canonical Issue
handoff carries exact proof and delivery state, with links from the PR.
Behavioral token savings are unmeasured; user Live Verification remains pending.
