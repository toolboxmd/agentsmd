# agentsmd

A small, opinionated, speed-first policy pack for coding agents. It keeps the
same global working agreements and long-running Goal contract across supported
agent harnesses.

## Files

- `AGENTS.md`: portable global working agreements.
- `GOAL_TEMPLATE.md`: harness-neutral `GOAL.md` and `STATUS.md` contract for
  work that must continue across sessions.

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

### Codex

```sh
mkdir -p "$HOME/.codex"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.codex/AGENTS.md"
ln -s "$AGENTSMD_DIR/GOAL_TEMPLATE.md" "$HOME/.codex/GOAL_TEMPLATE.md"
```

Codex officially reads global guidance from `AGENTS.md` in `CODEX_HOME`, which
defaults to `~/.codex`. It rebuilds the instruction chain on each new run or
TUI session.

### Grok Build CLI

```sh
mkdir -p "$HOME/.grok"
ln -s "$AGENTSMD_DIR/AGENTS.md" "$HOME/.grok/AGENTS.md"
ln -s "$AGENTSMD_DIR/GOAL_TEMPLATE.md" "$HOME/.grok/GOAL_TEMPLATE.md"
```

Verified with Grok Build CLI 1.0.5. Grok loads the global `AGENTS.md`
automatically. It reads `GOAL_TEMPLATE.md` on demand when the Goal rule applies.

### Other harnesses

Configure `AGENTS.md` as global instructions and make `GOAL_TEMPLATE.md`
available beside them. The Goal files remain useful even without a native Goal
feature because Git stores the approved contract and current status.

## Customize

Read the policy before using it. Fork the repository or edit your local copy if
its assumptions do not match your workflow. Keep project-specific commands,
architecture, checks, and deployment rules inside each project.

## License

MIT. See `LICENSE`.
