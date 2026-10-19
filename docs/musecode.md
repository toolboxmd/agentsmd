# Muse harness

AgentsMD supports the native plugin interface in **Muse Code 1.4.9**. Other
versions need compatibility proof before this support claim expands. The plugin
reuses the existing Project Direction loader, Elon gate and operations Skill.

## Instructions and Skill discovery

Muse's native global target is `$XDG_CONFIG_HOME/muse/AGENTS.md`, defaulting to
`~/.config/muse/AGENTS.md` when XDG is unset or empty. Custom `XDG_CONFIG_HOME`
is unsupported for Muse installation until hook environment propagation is
proven: Muse 1.4.9 hook tests omit it from child processes. Unset it before
installing and use the default root. The install command rejects any non-empty
value before writing; `inspect --harness muse` still reports the computed native
target, including a custom absolute XDG root.

Project `AGENTS.md` composes with the global file. The native global file wins
over the compatibility fallback `~/.claude/CLAUDE.md`. A lone Claude file can
supply Muse rules through that fallback, but it is not the Muse harness target:
`inspect --harness muse` reports the native path and can report it missing even
when the Claude fallback loads. Do not rely on the fallback for AgentsMD.
A project `AGENTS.md` also wins over a sibling `CLAUDE.md`.

The native plugin exposes `plugin:agentsmd:operations` from
`skills/operations/SKILL.md`. Muse also scans configuration, project and shared
Skill directories, including `~/.agents/skills`, `~/.codex/skills` and
`~/.claude/skills`. A user-scope `operations` in those shared directories
coexists with the plugin Skill; installing the plugin does not remove it.
Inspect `muse skills list --json` and remove any separate shared-directory
operations installation yourself after checking its owner. Do not create
AgentsMD Skill links in shared directories.

## Install and verify

Use a stable clone or extracted released artifact outside plugin caches for
`AGENTSMD_DIR`, as in the [shared setup](../README.md#install-boundary).
For the plugin source, use an extracted release artifact or a clean clone
checkout containing no private or untracked files: `muse plugins install`
copies the whole source tree into its local plugin cache. A live clone can
therefore copy private `PREFERENCES.md` and untracked files into that cache.
`muse plugins update` recopies the source tree; check it before each update.

```sh
muse plugins install "$AGENTSMD_DIR" --scope user --json
muse plugins inspect agentsmd --json
muse plugins approve agentsmd:hook:session-start --json
muse plugins approve agentsmd:hook:user-prompt-submit --json
muse plugins approve agentsmd:hook:subagent-start --json
muse plugins approve agentsmd:hook:pre-tool-use --json
muse plugins approve agentsmd:hook:operations-routing --json
muse plugins inspect agentsmd --json
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" install --harness muse \
  --source "$AGENTSMD_DIR/global/AGENTS.md"
"$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --harness muse \
  --source "$AGENTSMD_DIR/global/AGENTS.md"
"$AGENTSMD_DIR/bin/project-direction" inspect --harness muse
muse skills list --json
```

Review each hook definition before approving it. Every hook's
`runtime_capabilities[].status` must be `trusted_enabled` in the final plugin
inspection; skills activate without this review. List the trusted hook ids with:

```sh
muse plugins inspect agentsmd --json | jq -r '.runtime_capabilities[] | select(.status == "trusted_enabled") | .candidate.capability_id'
```

Check all five expected ids, then confirm `muse skills list --json` includes
`plugin:agentsmd:operations` and remove any separate user-scope operations copy.
Start a fresh session after installing.
`project-direction inspect` includes private preferences; do not publish its output.

The global-link installer preserves foreign files and links, rejects sources
and targets inside plugin caches, and initializes clone-root `PREFERENCES.md`
only when absent. `inspect` is the link's status command and exits zero only
for a healthy link to the supplied source. It never replaces an existing file
just because its contents match. These are the same ownership rules as the
other harnesses; the plugin cache supplies executables and the stable clone supplies
the global contract and private preferences.

## Update and uninstall

After updating the clone to the next released tag:

```sh
muse plugins update agentsmd --json
muse plugins inspect agentsmd --json
```

Changed hook definitions return to `review_needed`. Review and approve each
changed hook using the install commands, then verify `trusted_enabled`, the
global link and the plugin Skill identity again. Start a fresh session.

```sh
muse plugins remove agentsmd --json
muse plugins list --json
```

Removal uninstalls the cached plugin. The common global-link command currently
has no uninstall action. Inspect with the expected source, then remove only the
exact link path returned by that inspection when it is `valid-stable-link`.
This command refuses to remove missing, foreign, divergent or unhealthy entries:

```sh
if MUSE_LINK_TARGET="$("$AGENTSMD_DIR/bin/agentsmd-global-instructions" inspect --harness muse \
  --source "$AGENTSMD_DIR/global/AGENTS.md" | python3 -c '
import json, sys
report = json.load(sys.stdin)
if report.get("status") != "valid-stable-link" or not report.get("healthy"):
    sys.exit("Preserved: expected a healthy link to the supplied source")
print(report["target"])
')"; then
  rm -- "$MUSE_LINK_TARGET"
fi
```

Preserve foreign files, the clone and preferences.
For an authorized source-path migration, inspect first and use the common
installer's `--replace` option, which preserves a recoverable backup.

## Hooks and limits

| Event | Behavior |
| --- | --- |
| `SessionStart` | Deliver the complete loader block and a separate operations pointer |
| `UserPromptSubmit` | Deliver changed context; otherwise deliver only the conversation reminder |
| `SubagentStart` | Deliver the complete block for the new worker |
| `PreToolUse` | Run only the Elon gate; exit 2 with a stderr reason blocks non-compliant Issue and PR creation through `gh issue create`, `gh pr create`, or REST `gh api` POST requests to `repos/OWNER/REPO/issues` or `repos/OWNER/REPO/pulls` |

Every event uses a distinct Python wrapper because Muse rejects shared hook
source paths. The wrappers select the `--host muse` alias explicitly. Muse's hook-test
fixtures use `tool_input.command` for bash. The adapter parses JSON-string
tool_input objects, joins string-list commands with shell quoting, then maps a
string `tool_input.cmd` when command is not already a string. Unparseable inputs
and mixed-type lists pass through unchanged. The loader owns all command policy.
Event names normalize case and ignore underscores and hyphens for the four
supported events; unknown names reach the loader diagnostic. Muse has no
hook matcher, so
the gate receives every tool call and the loader selects candidate shell commands.
Malformed input retains the loader's diagnostic and exit behavior.

Muse caps hook stdout at **16,384 bytes**, including JSON framing. The loader
caps context at **10,000 UTF-8 bytes** and checks the complete encoded Muse
stdout against the 16,384-byte ceiling. Quote-dense content that exceeds the
encoded ceiling uses the existing `read_required` fallback. Nonce sections,
budgets and the initial session hash retain their existing semantics. Oversized direction is never injected partially.

`muse skills validate skills/operations --json` and
`muse plugins validate "$AGENTSMD_DIR" --json` validate the bundle without model
calls. In this multi-harness repository, `muse plugins validate` returns
`valid: true` with one expected `multiple-manifests` warning because it selects
the native manifest over the sibling Claude/Codex manifests.
Maintained tests in `tests/test_muse.py` exercise the real wrappers without
requiring Muse. Isolated CLI hook tests separately prove trust, injection and
blocking at the hook runner.

The loader currently ignores SessionStart `source` values: startup, resume,
clear, compact and other source values all take the same delivery path.
Per-source live re-delivery, SubagentStart routing into the child's context,
and the merge order of the two SessionStart contexts (direction and pointer)
remain pending live verification.

Skipped hook approval, a disabled plugin or missing `python3` removes Project
Direction delivery and the Elon gate with no model-visible error. Check plugin
status and Python availability yourself; the global contract's explicit reread
rule when no hook ran is the backstop.

PostCompact re-delivery is unproven. Read the complete triad explicitly after
compaction if context is missing. Live tool-call blocking remains proven only
at hook-test level until user-owned Live Verification through normal work.
Marketplace listing is pending separate publication authority; install from the
clone in the meantime. Native Muse tools and permissions remain Muse's responsibility.
