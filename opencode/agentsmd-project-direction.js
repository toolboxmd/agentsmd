/**
 * Deliver AgentsMD Project Direction to OpenCode through the system prompt.
 *
 * The plugin transports the canonical loader's payload without adding policy.
 * It runs `bin/project-direction hook --host opencode` beside this file with a
 * synthetic SessionStart input and appends the emitted context to the system
 * prompt. Any failure leaves the system prompt unchanged and logs one line.
 */

import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// `experimental.chat.system.transform` is experimental in this OpenCode
// version, which the bounded run adapter pins as well. The plugin context
// exposes no host version, so the pin is documentation, not a runtime gate.
export const SUPPORTED_OPENCODE_VERSION = "1.18.29";

const LOG_PREFIX = "agentsmd-project-direction:";
const LOADER = ["bin", "project-direction"];
const MAX_OUTPUT_BYTES = 1048576;

let reported = false;

function report(detail) {
  if (reported) {
    return;
  }
  reported = true;
  process.stderr.write(
    `${LOG_PREFIX} Project Direction was not loaded (${detail}). Read VISION.md, MISSION.md and OBJECTIVE.md explicitly.\n`,
  );
}

function loaderPath() {
  // realpath resolves the owned installed link back to its canonical clone,
  // so the plugin always runs the loader of the same AgentsMD revision.
  const self = realpathSync(fileURLToPath(import.meta.url));
  return join(dirname(dirname(self)), ...LOADER);
}

function sessionKey(input, directory) {
  const given = input && input.sessionID;
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

export default async function agentsmdProjectDirection(context) {
  const directory =
    (context && (context.directory || context.worktree)) || process.cwd();
  return {
    "experimental.chat.system.transform": async (input, output) => {
      if (!output || !Array.isArray(output.system)) {
        return;
      }
      const loaded = loadContext(directory, sessionKey(input, directory));
      if (loaded) {
        output.system.push(loaded);
      }
    },
  };
}
