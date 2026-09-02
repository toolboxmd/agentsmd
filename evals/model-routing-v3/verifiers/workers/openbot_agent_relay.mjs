#!/usr/bin/env node
"use strict";

// Candidate-visible ACP peer. It supplies inputs and transport behavior only;
// hidden expectations and assertions remain in the trusted driver.

import { spawn } from "node:child_process";
import readline from "node:readline";

const input = readline.createInterface({ input: process.stdin });
const mode = process.argv[2];
const option = process.argv[3] ?? "";
const amount = Number(process.argv[4] ?? 0);
const send = (message) => process.stdout.write(`${JSON.stringify(message)}\n`);
const responseFor = (message) => `${JSON.stringify({
  jsonrpc: "2.0",
  id: message.id,
  result: message.method === "initialize"
    ? { authMethods: [] }
    : message.method === "session/prompt"
      ? { stopReason: "end_turn" }
      : message.method === "session/new"
        ? { sessionId: "bounded-session" }
        : {},
})}\n`;
const progress = (kind, index, padding = "") => `${JSON.stringify({
  jsonrpc: "2.0",
  method: `future/${kind}`,
  params: { index, padding },
})}\n`;
const itemFlood = (message, count) => {
  const frames = [];
  for (let index = 0; index < count; index += 1) frames.push(progress("item", index));
  frames.push(responseFor(message));
  process.stdout.write(frames.join(""));
};
const exactJsonLines = (totalBytes, count, kind) => {
  const targets = Array.from({ length: count }, (_value, index) => (
    Math.floor(totalBytes / count) + (index < totalBytes % count ? 1 : 0)
  ));
  return targets.map((targetBytes, index) => {
    const empty = progress(kind, index);
    return progress(kind, index, "w".repeat(targetBytes - Buffer.byteLength(empty)));
  });
};
const wireFlood = (message, bytes) => {
  const response = responseFor(message);
  const frames = exactJsonLines(bytes - Buffer.byteLength(response), 64, "wire");
  frames.push(response);
  process.stdout.write(frames.join(""));
};

process.on("SIGTERM", () => {});
input.on("line", (line) => {
  const message = JSON.parse(line);
  if (mode === "healthy") {
    send(JSON.parse(responseFor(message)));
    return;
  }
  if (mode === "phase-item") {
    const selected = option === "startup" ? "initialize" : option;
    if (message.method === selected) itemFlood(message, amount);
    else send(JSON.parse(responseFor(message)));
    return;
  }
  if (mode === "phase-wire") {
    const selected = option === "startup" ? "initialize" : "session/new";
    if (message.method === selected) wireFlood(message, amount);
    else send(JSON.parse(responseFor(message)));
    return;
  }
  if (mode === "same-chunk") {
    if (message.method === "initialize") {
      itemFlood(message, 4095);
      return;
    }
    if (message.method === "session/new") {
      const entries = [];
      for (let index = 0; index < 4094; index += 1) {
        entries.push({ jsonrpc: "2.0", method: "future/same_chunk", params: { index } });
      }
      entries.push({ jsonrpc: "2.0", id: message.id, result: { sessionId: "bounded-session" } });
      entries.push({ jsonrpc: "2.0", method: "future/after_response", params: {} });
      process.stdout.write(`${JSON.stringify(entries)}\n`);
    }
    return;
  }
  if (mode === "split-stdout") {
    const selected = option === "startup" ? "initialize" : "session/new";
    if (message.method !== selected) {
      send(JSON.parse(responseFor(message)));
      return;
    }
    const frames = [];
    for (let index = 0; index < 4095; index += 1) frames.push(progress("split", index));
    frames.push(responseFor(message));
    const partial = JSON.stringify({
      jsonrpc: "2.0",
      method: "future/split_after_response",
      params: {},
    });
    process.stdout.write(frames.join("") + partial, () => {
      setTimeout(() => process.stdout.write("\n"), 150);
    });
    return;
  }
  if (mode === "delayed-stderr") {
    if (message.method === "initialize") {
      send(JSON.parse(responseFor(message)));
      return;
    }
    if (message.method === "session/new") {
      process.stderr.write("SENSITIVE-DELAYED-OUTPUT", () => {
        setTimeout(() => {
          const frames = [];
          for (let index = 0; index < 4095; index += 1) frames.push(progress("delayed", index));
          frames.push(responseFor(message));
          process.stdout.write(frames.join(""), () => {
            setTimeout(() => process.stderr.write("\r", () => {
              if (option === "crlf") setTimeout(() => process.stderr.write("\n"), 20);
            }), 150);
          });
        }, 150);
      });
    }
    return;
  }
  if (mode === "idle") {
    if (message.method !== "session/prompt") {
      send(JSON.parse(responseFor(message)));
      return;
    }
    send(JSON.parse(responseFor(message)));
    if (amount === 0) return;
    setTimeout(() => {
      const lines = [];
      if (amount > 4096) {
        const descendant = spawn(process.execPath, [
          "-e",
          "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);",
        ], { stdio: "ignore" });
        lines.push(`descendant:${descendant.pid}\n`);
      }
      for (let index = lines.length; index < amount; index += 1) {
        lines.push(`${index === amount - 1 ? "IDLE-DONE" : `idle-${index}`}\n`);
      }
      process.stderr.write(lines.join(""));
    }, 75);
    return;
  }
  if (mode === "active-turn") {
    if (message.method === "session/prompt") itemFlood(message, 4095);
    else send(JSON.parse(responseFor(message)));
  }
});
setInterval(() => {}, 1000);
