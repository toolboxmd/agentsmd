import assert from "node:assert/strict";
import fs from "node:fs";
import { describe, test } from "node:test";

type AcpHandlers = {
  onStderr?: (line: string) => void;
};

type AcpClientLike = {
  readonly pid: number | undefined;
  initialize(): Promise<{ authMethods: unknown[] }>;
  newSession(cwd: string): Promise<string>;
  loadSession(sessionId: string): Promise<string>;
  resumeSession(sessionId: string): Promise<string>;
  prompt(text: string): Promise<string>;
  close(): void;
};

type Frame = Record<string, unknown> & {
  kind: "response" | "event";
  request_id: number;
  sequence: number;
};

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

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

const bindingText = process.env.ROUTING_SPLIT_BINDING;
if (!bindingText) throw new Error("ROUTING_SPLIT_BINDING is required");
const binding = JSON.parse(bindingText) as Record<string, unknown>;
if (canonical(binding) !== bindingText) throw new Error("split binding is not canonical JSON");
if (binding.task !== "openbot-acp") throw new Error("driver task differs from the binding");
const workspaceRoot = process.env.ROUTING_WORKSPACE_ROOT;
if (!workspaceRoot || !workspaceRoot.startsWith("/") || workspaceRoot.includes("\0")) {
  throw new Error("ROUTING_WORKSPACE_ROOT must be an absolute path");
}

class RpcTransport {
  private sendSequence = 0;
  private receiveSequence = 0;
  private nextRequestId = 0;
  private buffer = Buffer.alloc(0);

  request(
    operation: string,
    payload: Record<string, unknown>,
    onEvent?: (name: string, payload: Record<string, unknown>) => void,
  ): unknown {
    const requestId = this.nextRequestId;
    this.nextRequestId += 1;
    const frame = {
      binding,
      kind: "request",
      operation,
      payload,
      protocol_version: 1,
      request_id: requestId,
      sequence: this.sendSequence,
    };
    this.sendSequence += 1;
    const line = `${canonical(frame)}\n`;
    if (Buffer.byteLength(line) > MAX_FRAME_BYTES) throw new Error("protocol frame exceeds the byte bound");
    fs.writeSync(protocolWriteFd, line);
    while (true) {
      const response = this.readFrame();
      if (response.request_id !== requestId) throw new Error("worker frame request id differs");
      if (response.kind === "event") {
        const name = response.name;
        const eventPayload = response.payload;
        if (typeof name !== "string" || eventPayload === null || typeof eventPayload !== "object" || Array.isArray(eventPayload)) {
          throw new Error("worker event fields are invalid");
        }
        onEvent?.(name, eventPayload as Record<string, unknown>);
        continue;
      }
      if (response.ok === true) return response.result;
      if (typeof response.error !== "string") throw new Error("worker failure is invalid");
      throw new Error(response.error);
    }
  }

  private readFrame(): Frame {
    while (this.buffer.indexOf(10) < 0) {
      if (this.buffer.length >= MAX_FRAME_BYTES) throw new Error("protocol frame exceeds the byte bound");
      const chunk = Buffer.alloc(Math.min(65_536, MAX_FRAME_BYTES - this.buffer.length));
      const count = fs.readSync(protocolReadFd, chunk, 0, chunk.length, null);
      if (count === 0) throw new Error("protocol transport closed before a response");
      this.buffer = Buffer.concat([this.buffer, chunk.subarray(0, count)]);
    }
    const end = this.buffer.indexOf(10);
    const raw = this.buffer.subarray(0, end).toString("utf8");
    this.buffer = this.buffer.subarray(end + 1);
    const frame = JSON.parse(raw) as Frame;
    if (canonical(frame) !== raw) throw new Error("worker frame is not canonical JSONL");
    const expected = frame.kind === "response"
      ? ["binding", "error", "kind", "ok", "protocol_version", "request_id", "result", "sequence"]
      : ["binding", "kind", "name", "payload", "protocol_version", "request_id", "sequence"];
    assert.deepEqual(Object.keys(frame).sort(), expected.sort());
    assert.equal(frame.protocol_version, 1);
    assert.equal(canonical(frame.binding), bindingText);
    assert.equal(frame.sequence, this.receiveSequence);
    this.receiveSequence += 1;
    if (frame.kind !== "response" && frame.kind !== "event") throw new Error("worker frame kind is invalid");
    return frame;
  }
}

const transport = new RpcTransport();

function processGroupExists(groupId: number): boolean {
  try {
    process.kill(-groupId, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code !== "ESRCH";
  }
}

function processExists(processId: number): boolean {
  try {
    process.kill(processId, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code !== "ESRCH";
  }
}

async function waitForProcessGroupGone(
  groupId: number,
  milliseconds = 2_000,
): Promise<void> {
  const deadline = Date.now() + milliseconds;
  while (processGroupExists(groupId) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(processGroupExists(groupId), false, `ACP process group ${groupId} survived`);
}

async function waitForProcessGone(
  processId: number,
  milliseconds = 2_000,
): Promise<void> {
  const deadline = Date.now() + milliseconds;
  while (processExists(processId) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(processExists(processId), false, `ACP descendant ${processId} survived`);
}

class RemoteAcpClient implements AcpClientLike {
  readonly pid: number | undefined;
  private readonly clientId: number;
  private readonly handlers: AcpHandlers;
  private closed = false;

  constructor(mode: string, option: string, amount: number, handlers: AcpHandlers) {
    this.handlers = handlers;
    const value = transport.request("create", {
      amount,
      mode,
      option,
      timing: { startDeadlineMs: 750, terminateGraceMs: 25 },
    }) as { client_id: number; pid: number | null };
    if (!Number.isSafeInteger(value.client_id) || (value.pid !== null && !Number.isSafeInteger(value.pid))) {
      throw new Error("worker create result is invalid");
    }
    this.clientId = value.client_id;
    this.pid = value.pid ?? undefined;
  }

  private events = (name: string, payload: Record<string, unknown>): void => {
    if (name !== "stderr" || payload.client_id !== this.clientId || typeof payload.line !== "string") {
      throw new Error("worker AcpClient event is invalid");
    }
    this.handlers.onStderr?.(payload.line);
  };

  private async call<T>(method: string, args: unknown[]): Promise<T> {
    if (this.closed) throw new Error("ACP transport protocol error");
    return transport.request("call", {
      arguments: args,
      client_id: this.clientId,
      method,
    }, this.events) as T;
  }

  initialize(): Promise<{ authMethods: unknown[] }> {
    return this.call("initialize", []);
  }

  newSession(cwd: string): Promise<string> {
    return this.call("newSession", [cwd]);
  }

  loadSession(sessionId: string): Promise<string> {
    return this.call("loadSession", [sessionId]);
  }

  resumeSession(sessionId: string): Promise<string> {
    return this.call("resumeSession", [sessionId]);
  }

  prompt(text: string): Promise<string> {
    return this.call("prompt", [text]);
  }

  close(): void {
    if (this.closed) return;
    const value = transport.request("close", {
      client_id: this.clientId,
    }, this.events);
    assert.equal(value, null);
    this.closed = true;
  }
}

async function within<T>(promise: Promise<T>, milliseconds = 2_000): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error("ACP lifecycle regression stayed pending")), milliseconds);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

async function waitForCleanup(
  acp: AcpClientLike,
  milliseconds = 2_000,
  processId: number | null = null,
): Promise<void> {
  const groupId = acp.pid ?? null;
  assert.ok(groupId);
  await waitForProcessGroupGone(groupId, milliseconds);
  if (processId !== null) await waitForProcessGone(processId, milliseconds);
}

function client(
  mode: string,
  option = "",
  amount = 0,
  handlers: AcpHandlers = {},
): AcpClientLike {
  return new RemoteAcpClient(mode, option, amount, handlers);
}

async function closeClient(acp: AcpClientLike): Promise<void> {
  const groupId = acp.pid;
  acp.close();
  if (groupId) await waitForProcessGroupGone(groupId);
}

async function expectProtocolFailure(action: Promise<unknown>): Promise<void> {
  await assert.rejects(within(action, 5_000), (error: unknown) => {
    assert.equal((error as Error).message, "ACP transport protocol error");
    assert.doesNotMatch(String(error), /SENSITIVE-DELAYED-OUTPUT|idle-/);
    return true;
  });
}

async function initializeAndAttach(acp: AcpClientLike): Promise<void> {
  assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
  assert.equal(await within(acp.newSession(workspaceRoot)), "bounded-session");
}

describe("AcpClient exact lifecycle output bounds", () => {
  test("enforces exact item ceilings for startup and each attachment method", {
    skip: process.platform === "win32",
  }, async (t) => {
    const cases = [
      ["startup", (acp: AcpClientLike) => acp.initialize(), { authMethods: [] }],
      ["session/new", (acp: AcpClientLike) => acp.newSession(workspaceRoot), "bounded-session"],
      ["session/load", (acp: AcpClientLike) => acp.loadSession("saved-session"), "saved-session"],
      ["session/resume", (acp: AcpClientLike) => acp.resumeSession("saved-session"), "saved-session"],
    ] as const;
    for (const [phase, exercise, expected] of cases) {
      await t.test(phase, async () => {
        const allowed = client("phase-item", phase, 4095);
        try {
          if (phase !== "startup") assert.deepEqual(await within(allowed.initialize()), { authMethods: [] });
          assert.deepEqual(await within(exercise(allowed)), expected);
        } finally {
          await closeClient(allowed);
        }

        const overflowed = client("phase-item", phase, 4096);
        const groupId = overflowed.pid;
        assert.ok(groupId);
        try {
          if (phase !== "startup") {
            assert.deepEqual(await within(overflowed.initialize()), { authMethods: [] });
          }
          await expectProtocolFailure(exercise(overflowed));
          await waitForCleanup(overflowed);
        } finally {
          await closeClient(overflowed);
        }
      });
    }
  });

  test("enforces the exact aggregate wire ceiling", {
    skip: process.platform === "win32",
  }, async (t) => {
    const exactBytes = 16 * 1024 * 1024;
    for (const phase of ["startup", "attachment"] as const) {
      await t.test(phase, async () => {
        const allowed = client("phase-wire", phase, exactBytes);
        try {
          if (phase === "startup") {
            assert.deepEqual(await within(allowed.initialize(), 5_000), { authMethods: [] });
          } else {
            assert.deepEqual(await within(allowed.initialize()), { authMethods: [] });
            assert.equal(await within(allowed.newSession(workspaceRoot), 5_000), "bounded-session");
          }
        } finally {
          await closeClient(allowed);
        }

        const overflowed = client("phase-wire", phase, exactBytes + 1);
        try {
          if (phase === "attachment") {
            assert.deepEqual(await within(overflowed.initialize()), { authMethods: [] });
            await expectProtocolFailure(overflowed.newSession(workspaceRoot));
          } else {
            await expectProtocolFailure(overflowed.initialize());
          }
        } finally {
          await closeClient(overflowed);
        }
      });
    }
  });

  test("charges data after a same-chunk attachment response exactly once", {
    skip: process.platform === "win32",
  }, async () => {
    const acp = client("same-chunk");
    try {
      assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
      await expectProtocolFailure(acp.newSession(workspaceRoot));
    } finally {
      await closeClient(acp);
    }
  });

  test("keeps a split stdout item in its settled phase", {
    skip: process.platform === "win32",
  }, async (t) => {
    for (const phase of ["startup", "attachment"] as const) {
      await t.test(phase, async () => {
        const acp = client("split-stdout", phase);
        const groupId = acp.pid;
        assert.ok(groupId);
        try {
          if (phase === "startup") {
            assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
          } else {
            assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
            assert.equal(await within(acp.newSession(workspaceRoot)), "bounded-session");
          }
          await waitForCleanup(acp, 1_500);
          await expectProtocolFailure(acp.initialize());
        } finally {
          await closeClient(acp);
        }
      });
    }
  });

  test("keeps delayed CR and CRLF stderr items in the settled attachment phase", {
    skip: process.platform === "win32",
  }, async (t) => {
    for (const delimiter of ["cr", "crlf"] as const) {
      await t.test(delimiter, async () => {
        let stderrCallbacks = 0;
        const acp = client("delayed-stderr", delimiter, 0, {
          onStderr() { stderrCallbacks += 1; },
        });
        const groupId = acp.pid;
        assert.ok(groupId);
        try {
          assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
          assert.equal(await within(acp.newSession(workspaceRoot)), "bounded-session");
          await waitForCleanup(acp, 1_500);
          assert.equal(stderrCallbacks, 0);
          await expectProtocolFailure(acp.newSession(workspaceRoot));
        } finally {
          await closeClient(acp);
        }
      });
    }
  });

  test("preserves the established active-turn exact boundary", {
    skip: process.platform === "win32",
  }, async () => {
    const acp = client("active-turn");
    try {
      await initializeAndAttach(acp);
      assert.equal(await within(acp.prompt("exact active turn"), 5_000), "");
    } finally {
      await closeClient(acp);
    }
  });

  test("contains idle overflow, reaps descendants, refuses reuse, and permits recovery", {
    skip: process.platform === "win32",
  }, async () => {
    let exactCallbacks = 0;
    let resolveExact!: () => void;
    const exactDone = new Promise<void>((resolve) => { resolveExact = resolve; });
    const exact = client("idle", "", 4096, {
      onStderr(line) {
        exactCallbacks += 1;
        if (line === "IDLE-DONE") resolveExact();
      },
    });
    try {
      await initializeAndAttach(exact);
      assert.equal(await within(exact.prompt("enter exact idle phase")), "");
      await within(exactDone, 5_000);
      assert.equal(exactCallbacks, 4096);
      assert.equal(await within(exact.prompt("reuse exact idle phase")), "");
    } finally {
      await closeClient(exact);
    }

    let resolveDescendant!: (pid: number) => void;
    const descendantReady = new Promise<number>((resolve) => { resolveDescendant = resolve; });
    const overflowed = client("idle", "", 5000, {
      onStderr(line) {
        if (line.startsWith("descendant:")) resolveDescendant(Number(line.slice(11)));
      },
    });
    const groupId = overflowed.pid;
    assert.ok(groupId);
    let descendant: number | undefined;
    try {
      await initializeAndAttach(overflowed);
      assert.equal(await within(overflowed.prompt("finish before idle overflow")), "");
      descendant = await within(descendantReady, 5_000);
      assert.ok(Number.isSafeInteger(descendant) && descendant > 0);
      await waitForCleanup(overflowed, 1_500, descendant);
      await expectProtocolFailure(overflowed.prompt("do not reuse"));
    } finally {
      await closeClient(overflowed);
    }

    const fresh = client("healthy");
    try {
      await initializeAndAttach(fresh);
      assert.equal(await within(fresh.prompt("fresh recovery")), "");
    } finally {
      await closeClient(fresh);
    }
  });
});
