# Grok Build CLI reference

This is a working reference for Grok CLI 1.0.5. Read it only when the default invocation in `SKILL.md` is insufficient. If the installed version differs or an option fails, run `grok --help` and `grok models` and prefer the live interface.

## Built-in tools

The default invocation leaves these enabled.

| Tool | What it does |
|------|--------------|
| `read_file` | Read a file |
| `search_replace` | Line-precise edit |
| `grep` | Regex search with ripgrep |
| `list_dir` | List a directory |
| `run_terminal_command` | Shell, using this internal tool id rather than `bash` |
| `web_search` / `web_fetch` | Search the web or fetch a URL |
| `todo_write` | Task list |
| `spawn_subagent` | Child session |
| `memory_search` | Cross-session memory |

MCP tools from the user's Grok config also load. `--tools` is a headless allowlist and removes everything else. Do not pass it unless you intend to restrict Grok. `--disallowed-tools` removes named ids and wins over `--tools`.

## Subagents

Subagents are enabled by default. Do not pass `--no-subagents` unless the user asked to restrict Grok.

| Type | Role |
|------|------|
| `general-purpose` | Full child agent |
| `explore` | Search, read, and shell without editing |
| `plan` | Implementation planning without editing |

`--disallowed-tools Agent` blocks all spawning. `Agent(explore)` and `Agent(explore, plan)` block named types only.

## Flags

### Prompt

| Flag | Use |
|------|-----|
| `--prompt-file <path>` | Brief from a file, preferred |
| `-p, --single <text>` | Inline prompt for a short request |
| `--prompt-json <json>` | Content-block prompt |
| `--verbatim` | Send the prompt exactly |

### Workspace and model

| Flag | Use |
|------|-----|
| `--cwd <path>` | Grok's working directory |
| `-m, --model <id>` | Select a model; use `grok models` for the live list and default |
| `--reasoning-effort` / `--effort` | Select the available reasoning effort |
| `--max-turns <n>` | Cap model rounds in headless mode |
| `--rules <text>` | Extra system-prompt rules for this run |
| `--agent <name-or-file>` | Named agent or definition file |

### Permissions and sandbox

| Flag | Use |
|------|-----|
| `--always-approve` / `--yolo` | Auto-approve tools; intentional default for this skill |
| `--permission-mode` | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, or `plan` |
| `--allow <rule>` / `--deny <rule>` | Gate invocations; deny wins; repeatable |
| `--sandbox <profile>` | Kernel filesystem and network profile; do not pass unless asked |

Known sandbox profiles in 1.0.5: `off` is unrestricted; `workspace` reads anywhere and writes CWD, `~/.grok`, and temp; `read-only` reads anywhere without project writes; `strict` reads CWD and system paths and can write CWD.

Permission rules are not tool ids. Prefixes include `Bash(...)`, `Edit(...)`, `Write(...)`, `Read(...)`, `Grep(...)`, `WebFetch(...)`, and `MCPTool(...)`. `*` matches one path segment and `**` is recursive. A bare prefix matches all. Example: `--deny 'Bash(rm*)'`.

### Restricting tools

Use these only when the user asked to restrict Grok.

| Flag | Use |
|------|-----|
| `--tools <ids>` | Headless allowlist, comma-separated |
| `--disallowed-tools <ids>` | Remove built-ins in headless mode |
| `--no-subagents` | Disable child agents |
| `--disable-web-search` | Disable `web_search` and `web_fetch` |
| `--no-plan` | Disable plan mode |

### Sessions and output

| Flag | Use |
|------|-----|
| `--output-format json` | Single object after completion |
| `--output-format plain` | Human text on stdout |
| `--output-format streaming-json` | NDJSON ACP events |
| `--output-format streaming-messages-json` | NDJSON Messages API wire format |
| `--json-schema <schema>` | Constrain final output to JSON Schema; implies JSON output |
| `-r, --resume [<id-or-title>]` | Continue a session |
| `-c, --continue` | Continue the latest session in this cwd |
| `-s, --session-id <uuid>` | Force a new session id that does not already exist |
| `--fork-session` | Fork when resuming or continuing |

Headless `-p` and `--prompt-file` do not create a git worktree from `--worktree`.
