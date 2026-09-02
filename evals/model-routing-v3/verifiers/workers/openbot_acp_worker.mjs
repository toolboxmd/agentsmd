#!/usr/bin/env node
"use strict";

// This is the only hidden-verifier process that imports the candidate module.
// It exposes generic AcpClient operations and never owns hidden assertions or
// the verifier's final result.

import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { setTimeout as sleep } from "node:timers/promises";
import { pathToFileURL } from "node:url";

const PROTOCOL_VERSION = 1;
const MAX_FRAME_BYTES = 16 * 1024 * 1024;
const protocolReadFd = Number(process.env.ROUTING_SPLIT_READ_FD);
const protocolWriteFd = Number(process.env.ROUTING_SPLIT_WRITE_FD);
if (!Number.isSafeInteger(protocolReadFd) || protocolReadFd < 0) {
  throw new Error("ROUTING_SPLIT_READ_FD must be a file descriptor");
}
if (!Number.isSafeInteger(protocolWriteFd) || protocolWriteFd < 0) {
  throw new Error("ROUTING_SPLIT_WRITE_FD must be a file descriptor");
}
if (protocolReadFd === protocolWriteFd) {
  throw new Error("protocol read and write descriptors must differ");
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

const bindingText = process.env.ROUTING_SPLIT_BINDING;
if (!bindingText) throw new Error("ROUTING_SPLIT_BINDING is required");
const binding = JSON.parse(bindingText);
if (canonical(binding) !== bindingText) throw new Error("split binding is not canonical JSON");
if (binding.task !== "openbot-acp") throw new Error("worker task differs from the binding");

// Candidate code shares this process, so bind worker shutdown primitives
// before loading it. The trusted driver owns cleanup assertions; this worker
// owns candidate lifecycle actions and deterministic protocol shutdown.
const closeDescriptor = fs.closeSync.bind(fs);
const exitProcess = process.exit.bind(process);

const candidatePath = process.env.ROUTING_CANDIDATE_ACP;
const relayPath = process.env.ROUTING_OPENBOT_AGENT_RELAY;
const candidateRoot = process.env.ROUTING_CANDIDATE_ROOT;
if (!candidatePath || !relayPath || !candidateRoot) {
  throw new Error("candidate, relay, and candidate root paths are required");
}
const resolvedCandidate = path.resolve(candidatePath);
const resolvedRelay = path.resolve(relayPath);
const resolvedRoot = path.resolve(candidateRoot);
if (!resolvedCandidate.startsWith(`${resolvedRoot}${path.sep}`)) {
  throw new Error("candidate module is outside the candidate root");
}
if (!fs.statSync(resolvedCandidate).isFile() || !fs.statSync(resolvedRelay).isFile()) {
  throw new Error("candidate module and ACP relay must be regular files");
}

const candidateModule = await import(pathToFileURL(resolvedCandidate).href);
const AcpClient = candidateModule.AcpClient;
if (typeof AcpClient !== "function") throw new Error("candidate does not export AcpClient");

let sendSequence = 0;
let receiveSequence = 0;
const clients = new Map();
let nextClientId = 0;

function send(frame) {
  const line = `${canonical(frame)}\n`;
  if (Buffer.byteLength(line) > MAX_FRAME_BYTES) throw new Error("protocol frame exceeds the byte bound");
  fs.writeSync(protocolWriteFd, line);
}

function respond(requestId, result, error = null) {
  send({
    binding,
    error,
    kind: "response",
    ok: error === null,
    protocol_version: PROTOCOL_VERSION,
    request_id: requestId,
    result: error === null ? result : null,
    sequence: sendSequence,
  });
  sendSequence += 1;
}

function event(requestId, name, payload) {
  send({
    binding,
    kind: "event",
    name,
    payload,
    protocol_version: PROTOCOL_VERSION,
    request_id: requestId,
    sequence: sendSequence,
  });
  sendSequence += 1;
}

function objectWithExactKeys(value, keys, name) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${name} must be an object`);
  }
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (canonical(actual) !== canonical(expected)) throw new Error(`${name} fields differ`);
}

function validateRequest(line) {
  if (Buffer.byteLength(line) + 1 > MAX_FRAME_BYTES) throw new Error("protocol frame exceeds the byte bound");
  const frame = JSON.parse(line);
  if (`${canonical(frame)}\n` !== `${line}\n`) throw new Error("protocol request is not canonical JSONL");
  objectWithExactKeys(
    frame,
    ["binding", "kind", "operation", "payload", "protocol_version", "request_id", "sequence"],
    "protocol request",
  );
  if (frame.protocol_version !== PROTOCOL_VERSION || frame.kind !== "request") {
    throw new Error("protocol request identity differs");
  }
  if (canonical(frame.binding) !== bindingText) throw new Error("protocol request binding differs");
  if (frame.sequence !== receiveSequence) throw new Error("protocol request sequence differs");
  if (!Number.isSafeInteger(frame.request_id) || frame.request_id < 0) throw new Error("request id is invalid");
  if (typeof frame.operation !== "string" || !frame.operation) throw new Error("operation is invalid");
  objectWithExactKeys(frame.payload, Object.keys(frame.payload), "request payload");
  if (Date.now() >= binding.deadline_unix_ms) throw new Error("shared deadline elapsed");
  receiveSequence += 1;
  return frame;
}

function record(clientId) {
  const value = clients.get(clientId);
  if (!value) throw new Error("unknown AcpClient id");
  return value;
}

async function settle() {
  await sleep(350);
  if (Date.now() >= binding.deadline_unix_ms) throw new Error("shared deadline elapsed");
}

async function dispatch(frame) {
  const { operation, payload, request_id: requestId } = frame;
  if (operation === "create") {
    objectWithExactKeys(payload, ["mode", "option", "amount", "timing"], "create payload");
    if (
      typeof payload.mode !== "string"
      || typeof payload.option !== "string"
      || !Number.isSafeInteger(payload.amount)
      || payload.amount < 0
    ) {
      throw new Error("create payload values are invalid");
    }
    objectWithExactKeys(payload.timing, ["startDeadlineMs", "terminateGraceMs"], "timing");
    if (payload.timing.startDeadlineMs !== 750 || payload.timing.terminateGraceMs !== 25) {
      throw new Error("AcpClient timing differs from the hidden contract");
    }
    const clientId = nextClientId;
    nextClientId += 1;
    const state = {
      client: null,
      eventRequestId: requestId,
      groupId: null,
      terminateGraceMs: payload.timing.terminateGraceMs,
    };
    const client = new AcpClient({
      command: process.execPath,
      args: [resolvedRelay, payload.mode, payload.option, String(payload.amount)],
      env: {
        HOME: process.env.HOME ?? resolvedRoot,
        LANG: "C",
        LC_ALL: "C",
        NO_COLOR: "1",
        PATH: "/usr/bin:/bin",
        TMPDIR: process.env.TMPDIR ?? "/tmp",
      },
    }, resolvedRoot, {
      onStderr(line) {
        event(state.eventRequestId, "stderr", { client_id: clientId, line });
      },
    }, payload.timing);
    state.client = client;
    state.groupId = Number.isSafeInteger(client.pid) && client.pid > 0 ? client.pid : null;
    clients.set(clientId, state);
    return { client_id: clientId, pid: state.groupId };
  }
  if (operation === "call") {
    objectWithExactKeys(payload, ["client_id", "method", "arguments"], "call payload");
    if (!Number.isSafeInteger(payload.client_id) || payload.client_id < 0) throw new Error("client id is invalid");
    if (!Array.isArray(payload.arguments)) throw new Error("call arguments must be an array");
    if (!["initialize", "newSession", "loadSession", "resumeSession", "prompt"].includes(payload.method)) {
      throw new Error("AcpClient method is not allowed");
    }
    const state = record(payload.client_id);
    state.eventRequestId = requestId;
    const result = await state.client[payload.method](...payload.arguments);
    await settle();
    return result === undefined ? null : result;
  }
  if (operation === "close") {
    objectWithExactKeys(payload, ["client_id"], "close payload");
    if (!Number.isSafeInteger(payload.client_id) || payload.client_id < 0) {
      throw new Error("client id is invalid");
    }
    const state = record(payload.client_id);
    state.eventRequestId = requestId;
    try {
      state.client.close();
      await sleep(state.terminateGraceMs + 25);
      return null;
    } finally {
      clients.delete(payload.client_id);
    }
  }
  throw new Error("OpenBot worker operation is not allowed");
}

const transport = fs.createReadStream(null, { fd: protocolReadFd, autoClose: false });
const lines = readline.createInterface({ input: transport, crlfDelay: Infinity });
let chain = Promise.resolve();
lines.on("line", (line) => {
  chain = chain.then(async () => {
    let frame;
    try {
      frame = validateRequest(line);
      const result = await dispatch(frame);
      respond(frame.request_id, result);
    } catch (error) {
      if (frame) respond(frame.request_id, null, String(error?.message ?? error));
      else throw error;
    }
  });
});
lines.once("close", () => {
  let shutdownReturnCode = 0;
  chain = chain.then(async () => {
    let maximumGraceMs = 0;
    for (const state of clients.values()) {
      state.client.close();
      maximumGraceMs = Math.max(maximumGraceMs, state.terminateGraceMs);
    }
    clients.clear();
    if (maximumGraceMs > 0) await sleep(maximumGraceMs + 25);
  }).catch((error) => {
    process.stderr.write(`${String(error?.stack ?? error)}\n`);
    shutdownReturnCode = 1;
  }).finally(() => {
    transport.destroy();
    try {
      closeDescriptor(protocolReadFd);
    } catch (error) {
      if (error?.code !== "EBADF") shutdownReturnCode = 1;
    }
    // process.exit closes the write descriptor atomically with worker exit, so
    // the mediator cannot mistake an orderly EOF for a still-live peer.
    exitProcess(shutdownReturnCode);
  });
});
