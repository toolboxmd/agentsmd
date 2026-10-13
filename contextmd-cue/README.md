# ContextMD Cue entries

These ContextMD Cue entries point to AgentsMD procedures whose moment has no
trigger words, such as research or grilling. ContextMD's Cue scores each
entry's `name: applies` text against the conversation at every user message
and tool call. An entry that fires is served with its `applies` line first,
then a pointer to its `target`. Each `target` is relative to this folder, so
it resolves in whichever AgentsMD clone serves it.

The deployed Cue adapter was trained on these exact `name` and `applies`
texts. Changing either lowers Cue's accuracy until the adapter is retrained
(toolboxmd/contextmd#4), so change them only together with retraining. The
tests pin them.

To serve them on a machine, add this folder to the `cue` list in
`~/.config/contextmd/serving.json`, with the Cue service URL:

```json
{"cue": ["~/dev/toolboxmd/agentsmd/contextmd-cue"], "cue_url": "http://100.116.0.2:8710"}
```

Keep this folder out of the `exact_keys` list: each loader rejects the other's
entries. ContextMD skips this README.
