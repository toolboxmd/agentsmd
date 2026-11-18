/**
 * Deliver AgentsMD Project Direction to OpenCode through the system prompt.
 *
 * The plugin transports the canonical loader's payload without adding policy.
 * It runs `bin/project-direction hook --host opencode` beside this file with a
 * synthetic SessionStart input and appends the emitted context to the system
 * prompt. Any failure leaves the system prompt unchanged and logs one line.
 * It also appends the pointer to the operations Skill from
 * `bin/operations-routing`, because OpenCode does not always load it on its own.
 *
 * One default export serves both plugin APIs. OpenCode 1.x loads `{id, server}`
 * and calls `server`; OpenCode 2.x loads `{id, setup}`, calls `setup` and
 * ignores `server`.
 */

import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// The OpenCode versions this plugin was proved on. The 1.x hooks are
// experimental and the bounded run adapter pins 1.18.32. The plugin context
// exposes no harness version, so the list is documentation, not a runtime gate.
const SUPPORTED_OPENCODE_VERSIONS = Object.freeze(["1.18.32", "1.19.6", "2.3.2"]);
const PLUGIN_ID = "agentsmd-project-direction";

const LOG_PREFIX = "agentsmd-project-direction:";
const LOADER = ["bin", "project-direction"];
const ROUTING = ["bin", "operations-routing"];
const MAX_OUTPUT_BYTES = 1048576;

let reported = false;

function report(detail) {
  if (reported) {
    return;
  }
  reported = true;
  process.stderr.write(
    `${LOG_PREFIX} Project Direction was not loaded (${detail}). Read VISION.md, MISSION.md and OBJECTIVE.md explicitly and in full.\n`,
  );
}

function loaderPath(command = LOADER) {
  // realpath resolves the owned installed link back to its canonical clone,
  // so the plugin always runs the loader of the same AgentsMD revision.
  const self = realpathSync(fileURLToPath(import.meta.url));
  return join(dirname(dirname(self)), ...command);
}

let routing = null;
let routingReported = false;

function loadRouting() {
  if (routing || routingReported) {
    return routing;
  }
  try {
    const result = spawnSync(loaderPath(ROUTING), [], {
      encoding: "utf8",
      maxBuffer: MAX_OUTPUT_BYTES,
    });
    const context = JSON.parse(result.stdout).hookSpecificOutput.additionalContext;
    if (typeof context === "string" && context) {
      routing = context;
    }
  } catch (error) {
    routingReported = true;
    process.stderr.write(
      `${LOG_PREFIX} the operations pointer was not loaded (${error && error.message}).\n`,
    );
  }
  return routing;
}

function sessionKey(given, directory) {
  return typeof given === "string" && given.trim()
    ? given
    : `agentsmd-opencode:${directory}`;
}

function loadContext(directory, sessionID) {
  let result;
  try {
    result = spawnSync(loaderPath(), ["hook", "--host", "opencode"], {
      input: JSON.stringify({
        hook_event_name: "SessionStart",
        cwd: directory,
        session_id: sessionID,
      }),
      encoding: "utf8",
      maxBuffer: MAX_OUTPUT_BYTES,
    });
  } catch (error) {
    report(`loader unavailable: ${error && error.message}`);
    return null;
  }
  if (result.error) {
    report(`loader unavailable: ${result.error.message}`);
    return null;
  }
  if (result.status !== 0) {
    report(`loader exited with status ${result.status}`);
    return null;
  }
  let output;
  try {
    output = JSON.parse(result.stdout);
  } catch (error) {
    report("loader output was not valid JSON");
    return null;
  }
  const specific = output && output.hookSpecificOutput;
  const context = specific && specific.additionalContext;
  if (typeof context !== "string" || !context) {
    report("loader emitted no additional context");
    return null;
  }
  return context;
}

// A coarse filter; the loader parses the shell command and decides.
const MAY_CREATE = /\bgh\b[\s\S]*\b(?:create|api)\b/;

// The loader owns the Elon gate; the plugin only forwards possible gh create
// calls to it and turns its exit status 2 into a thrown error, which blocks the
// tool. A loader that cannot run blocks too, so the gate never fails open.
function elonGate(directory, sessionID, tool, args) {
  const text = JSON.stringify(args ?? {});
  if (!MAY_CREATE.test(text)) {
    return null;
  }
  let result;
  try {
    result = spawnSync(loaderPath(), ["hook", "--host", "opencode"], {
      input: JSON.stringify({
        hook_event_name: "PreToolUse",
        cwd: directory,
        session_id: sessionID,
        tool_name: tool,
        tool_input: args ?? {},
      }),
      encoding: "utf8",
      maxBuffer: MAX_OUTPUT_BYTES,
    });
  } catch (error) {
    return `AgentsMD could not run its Elon check (${error && error.message}); fix the AgentsMD install before creating Issues or PRs.`;
  }
  if (result.error || result.status === null) {
    return `AgentsMD could not run its Elon check (${result.error ? result.error.message : "loader was killed"}); fix the AgentsMD install before creating Issues or PRs.`;
  }
  if (result.status === 2) {
    return (result.stderr || "AgentsMD blocked this call: add the Elon record.").trim();
  }
  return null;
}

function systemEntries(directory, sessionID) {
  const entries = [];
  const loaded = loadContext(directory, sessionID);
  if (loaded) {
    entries.push(loaded);
  }
  const table = loadRouting();
  if (table) {
    entries.push(table);
  }
  return entries;
}

// OpenCode 1.x: hooks returned from `server`.
async function server(context) {
  const directory =
    (context && (context.directory || context.worktree)) || process.cwd();
  return {
    "experimental.chat.system.transform": async (input, output) => {
      if (!output || !Array.isArray(output.system)) {
        return;
      }
      output.system.push(
        ...systemEntries(directory, sessionKey(input && input.sessionID, directory)),
      );
    },
    "tool.execute.before": async (input, output) => {
      const blocked = elonGate(
        directory,
        sessionKey(input && input.sessionID, directory),
        input && input.tool,
        output && output.args,
      );
      if (blocked) {
        throw new Error(blocked);
      }
    },
  };
}

// OpenCode 2.x: hooks registered from `setup`. The `context` hook edits each
// primary model request; a throw in `execute.before` fails the tool call
// before it runs. OpenCode 1.x also calls `setup`, with a context that has no
// session or tool hooks; `server` already covers 1.x, so setup does nothing.
async function setup(context) {
  const session = context && context.session;
  const tool = context && context.tool;
  if (
    !session || typeof session.hook !== "function" ||
    !tool || typeof tool.hook !== "function"
  ) {
    return;
  }
  const location = context.location;
  const directory = (location && location.directory) || process.cwd();
  await session.hook("context", (input) => {
    if (!input || !Array.isArray(input.system)) {
      return;
    }
    for (const text of systemEntries(directory, sessionKey(input.sessionID, directory))) {
      input.system.push({ type: "text", text });
    }
  });
  await tool.hook("execute.before", (input) => {
    const blocked = elonGate(
      directory,
      sessionKey(input && input.sessionID, directory),
      input && input.tool,
      input && input.input,
    );
    if (blocked) {
      throw new Error(blocked);
    }
  });
}

export default {
  id: PLUGIN_ID,
  server,
  setup,
  supportedOpenCodeVersions: SUPPORTED_OPENCODE_VERSIONS,
};
