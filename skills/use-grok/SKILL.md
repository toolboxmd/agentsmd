---
name: use-grok
description: Delegate to the local Grok Build CLI when the user explicitly asks to ask, send, pass, delegate to, or consult Grok for research, coding, implementation, review, or a second opinion. Do not use unless the user asked to consult Grok.
license: Apache-2.0
compatibility: Requires a local shell and the Grok Build CLI (grok) on PATH, authenticated with grok login or XAI_API_KEY. Hosted environments work only when they provide that executable.
metadata:
  short-description: Consult local Grok Build CLI
---

# Consult Grok

Run the local `grok` CLI as a full agent. Grok can read and edit the repo, run a shell, search the web, and spawn subagents. Its answer is a proposal unless the user asked it to implement.

Invoke with `/use-grok` in Claude Code or Grok, `$use-grok` in Codex, or select the skill with `@` in ChatGPT. The host may also invoke it automatically when the user asks to consult Grok. Invocation arguments are the question; put them in the brief. Do not run unless the user asked to consult Grok.

A path in the brief is a hint. Grok sees the workspace because `--cwd` points at it, not because a path was named.

## Default invocation

Always start from this. Unrestricted permissions are intentional: this skill delegates to Grok as a full agent. Do **not** add `--no-subagents`, `--disable-web-search`, `--tools`, `--disallowed-tools`, or `--sandbox` unless the user asked to restrict Grok.

```bash
grok \
  --prompt-file "<brief-path>" \
  --verbatim \
  --cwd "<workspace>" \
  --always-approve \
  --output-format json
```

`--always-approve` is `--yolo` and `--permission-mode bypassPermissions`. Tools run without prompts. Prefer `--prompt-file` plus `--verbatim` over `-p` so the brief is not smashed by the shell.

`<workspace>` is the repo (or subproject) Grok should work in. `<brief-path>` is a file you write; keep it outside this skill directory.

Missing `grok` on PATH: tell the user to install Grok Build. Auth failure: `grok login` or `XAI_API_KEY`.

## When Grok is done

`grok --prompt-file` is headless and **blocking**. The consult is over when that process exits. Do not poll, background it, or wait for a second signal. Subagents finish (or get torn down) before the parent exits.

1. Wait for the shell command to return.
2. Read the exit code.
3. Parse JSON stdout (`--output-format json`).
4. Treat `.text` as Grok's final answer (or the JSON string if you passed `--json-schema`).
5. Reconcile with the repo and the original task. Exit 0 does not mean the work is correct; it only means Grok stopped on its own. Do not silently replace a plan or merge edits unread.

| Exit | Meaning |
|------|---------|
| `0` | Process finished; read `.stopReason` next |
| `1` | Failed to run. Stdout is `{"type":"error","message":"..."}` |
| `130` | SIGINT. Session saved through the last finished tool call; disk edits are **not** rolled back |
| `143` | SIGTERM. Same persistence rules as `130` |

`.stopReason` (on exit 0):

| Value | Grok is... | What you do |
|-------|----------|-------------|
| `end_turn` | Done with this prompt | Use `.text`. Keep `.sessionId` if you might continue |
| `max_tokens` | Cut off mid-answer | Resume with `--resume "<sessionId>"` or tell the user it was incomplete |
| `max_turn_requests` | Hit `--max-turns` | Same: incomplete. Raise `--max-turns` or narrow the brief |
| `cancelled` / `refusal` | Did not complete | Report `.text` / the error; do not pretend it finished |

JSON fields you actually use: `text`, `stopReason`, `sessionId`, `num_turns`. For `implement`, also look at the workspace because Grok may have edited files before exiting.

The brief's `Done when:` line is Grok's *goal*, not a protocol. The protocol is: process exit + `stopReason`. If the answer looks unfinished despite `end_turn`, send a follow-up with `--resume "<sessionId>"`.

## Brief

Write a short file. Do not dump the repo. Do not paste `.env`, keys, or secrets.

```text
Goal: <research | implement | review | second-opinion>
Question: <what Grok should do>
Workspace: <absolute path; same as --cwd>
Look at: <paths or symbols worth opening first>
Constraints: <tests to run, files not to touch, deadline>
Done when: <acceptance>
```

## Optional CLI details

The default invocation above needs no additional catalog lookup. For non-default flags, tool restrictions, subagent types, models, sandbox profiles, or session controls, read [references/grok-cli.md](references/grok-cli.md). That reference records the Grok CLI 1.0.5 interface. If the installed version differs or a documented option fails, check the live `grok --help` and `grok models` output before proceeding.

## Recipes

Same default command. Change the brief (and flags only where noted).

### Research

Goal `research`. Tell Grok to search the repo and the web, cite paths and URLs, and not edit files. It will use `web_search`, `web_fetch`, `grep`, and `explore` subagents on its own.

```text
Goal: research
Question: <what to find out>
Look at: <starting paths>
Do not modify files.
Cite file paths and URLs.
Done when: you can answer the question or say what is still unknown.
```

Optional: `--max-turns 30`. Add `--sandbox read-only` only when the user explicitly asks to restrict Grok.

### Implement / coding

Goal `implement`. Tell Grok to make the change, run the relevant tests, and report what it did. Leave tools and sandbox unrestricted.

```text
Goal: implement
Question: <behavior to add or fix>
Look at: <paths>
Constraints: <tests, style, files not to touch>
Done when: <test or repro that must pass>
```

Optional: `--max-turns 30`. Follow up in the same Grok session with `--resume "<sessionId>"`.

### Review / second opinion

Goal `review` or `second-opinion`. Tell Grok to inspect the named paths or the current plan and **not** edit. Ask for overengineering, gaps, risks, and a minimum change.

```text
Goal: review
Question: <plan or change to judge>
Look at: <paths>
Do not modify files.
Answer with: verdict (proceed / proceed with changes / replan / needs a human);
overengineering; missing; risks; minimum change; decisions that are still the user's.
```

Optional structured stdout:

```bash
--json-schema '{"type":"object","additionalProperties":false,"required":["verdict","overengineering","missing","risks","minimum_plan_delta","user_decisions"],"properties":{"verdict":{"type":"string","enum":["PROCEED","PROCEED WITH CHANGES","REPLAN","NEEDS HUMAN DECISION"]},"overengineering":{"type":"array","items":{"type":"string"}},"missing":{"type":"array","items":{"type":"string"}},"risks":{"type":"array","items":{"type":"string"}},"minimum_plan_delta":{"type":"array","items":{"type":"string"}},"user_decisions":{"type":"array","items":{"type":"string"}}}}'
```

If `--json-schema` is set, the review is in the JSON object (`.text` may be the JSON string). Reconcile; do not silently replace the plan. Add `--sandbox read-only` only when the user explicitly asks to restrict Grok.

### Continue a prior consult

```bash
grok --prompt-file "<brief-path>" --verbatim --cwd "<workspace>" --always-approve --output-format json --resume "<sessionId>"
```
