# ContextMD entries

These ContextMD pointer rules deny a matching command, such as `git commit`,
until the agent reads the operations procedure named in the entry's `target`.
Each `target` is relative to this folder, so it resolves in whichever AgentsMD
clone serves it.

To serve them on a machine, add this folder to
`~/.config/contextmd/serving.json`:

```json
{"exact_keys": ["~/dev/toolboxmd/agentsmd/contextmd"]}
```

ContextMD skips this README.
