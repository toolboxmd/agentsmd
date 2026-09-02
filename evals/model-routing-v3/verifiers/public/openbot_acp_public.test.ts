import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { before, describe, test } from "node:test";

type AcpHandlers = {
  onStderr?: (line: string) => void;
};

type AcpClientLike = {
  readonly pid: number | undefined;
  initialize(): Promise<{ authMethods: unknown[] }>;
  newSession(cwd: string): Promise<string>;
  prompt(text: string): Promise<string>;
  close(): void;
};

type AcpClientConstructor = new (
  spec: { command: string; args: string[]; env: NodeJS.ProcessEnv },
  cwd: string,
  handlers?: AcpHandlers,
  timing?: { startDeadlineMs: number; terminateGraceMs: number },
) => AcpClientLike;

const candidatePath = process.env.ROUTING_CANDIDATE_ACP;
if (!candidatePath) throw new Error("ROUTING_CANDIDATE_ACP is required");
let AcpClient: AcpClientConstructor;
before(async () => {
  const candidateModule = await import(pathToFileURL(candidatePath).href);
  AcpClient = candidateModule.AcpClient as AcpClientConstructor;
  if (typeof AcpClient !== "function") throw new Error("candidate does not export AcpClient");
});

const HEALTHY_AGENT = String.raw`
const readline = require("node:readline");
const input = readline.createInterface({ input: process.stdin });
const send = (message) => process.stdout.write(JSON.stringify(message) + "\n");
input.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    send({ jsonrpc: "2.0", id: message.id, result: { authMethods: [] } });
  } else if (message.method === "session/new") {
    send({ jsonrpc: "2.0", id: message.id, result: { sessionId: "healthy-session" } });
  } else if (message.method === "session/prompt") {
    send({ jsonrpc: "2.0", id: message.id, result: { stopReason: "end_turn" } });
  }
});
`;

const FLOODING_AGENT = String.raw`
const readline = require("node:readline");
const input = readline.createInterface({ input: process.stdin });
const phase = process.argv[1];
const send = (message) => process.stdout.write(JSON.stringify(message) + "\n");
const flood = (done) => {
  const frames = [];
  for (let index = 0; index < 5000; index += 1) {
    frames.push(JSON.stringify({
      jsonrpc: "2.0",
      method: "future/progress",
      params: { index, payload: "aggregate-output" }
    }) + "\n");
  }
  process.stdout.write(frames.join(""), done);
};
process.on("SIGTERM", () => {});
input.on("line", (line) => {
  const message = JSON.parse(line);
  if (message.method === "initialize") {
    const done = () => send({ jsonrpc: "2.0", id: message.id, result: { authMethods: [] } });
    if (phase === "startup") flood(done); else done();
    return;
  }
  if (message.method === "session/new") {
    const done = () => send({
      jsonrpc: "2.0",
      id: message.id,
      result: { sessionId: "flood-session" }
    });
    if (phase === "attachment") flood(done); else done();
    return;
  }
  if (message.method === "session/prompt") {
    send({ jsonrpc: "2.0", id: message.id, result: { stopReason: "end_turn" } });
    if (phase === "idle") setTimeout(() => flood(() => {}), 50);
  }
});
setInterval(() => {}, 1000);
`;

async function within<T>(promise: Promise<T>, milliseconds = 2_000): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error("ACP check stayed pending")), milliseconds);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

function processGroupExists(groupId: number): boolean {
  try {
    process.kill(-groupId, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code !== "ESRCH";
  }
}

async function waitForProcessGroupGone(groupId: number, milliseconds = 2_000): Promise<void> {
  const deadline = Date.now() + milliseconds;
  while (processGroupExists(groupId) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.equal(processGroupExists(groupId), false, "ACP child process survived containment");
}

function client(source: string, args: string[] = []): AcpClientLike {
  return new AcpClient({
    command: process.execPath,
    args: ["-e", source, ...args],
    env: { ...process.env },
  }, process.cwd(), {}, { startDeadlineMs: 750, terminateGraceMs: 25 });
}

async function closeClient(acp: AcpClientLike): Promise<void> {
  const groupId = acp.pid;
  acp.close();
  if (groupId) await waitForProcessGroupGone(groupId);
}

async function assertSanitizedTransportFailure(action: Promise<unknown>): Promise<void> {
  await assert.rejects(within(action, 4_000), (error: unknown) => {
    assert.equal((error as Error).message, "ACP transport protocol error");
    assert.equal(String(error).includes("aggregate-output"), false);
    return true;
  });
}

async function proveFreshClientRecovery(): Promise<void> {
  const fresh = client(HEALTHY_AGENT);
  try {
    assert.deepEqual(await within(fresh.initialize()), { authMethods: [] });
    assert.equal(await within(fresh.newSession(process.cwd())), "healthy-session");
    assert.equal(await within(fresh.prompt("recover")), "");
  } finally {
    await closeClient(fresh);
  }
}

describe("AcpClient lifecycle output containment", () => {
  test("keeps a healthy client reusable", { skip: process.platform === "win32" }, async () => {
    const acp = client(HEALTHY_AGENT);
    try {
      assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
      assert.equal(await within(acp.newSession(process.cwd())), "healthy-session");
      assert.equal(await within(acp.prompt("first turn")), "");
      assert.equal(await within(acp.prompt("second turn")), "");
    } finally {
      await closeClient(acp);
    }
  });

  test("contains aggregate startup and attachment output", {
    skip: process.platform === "win32",
  }, async (t) => {
    for (const phase of ["startup", "attachment"] as const) {
      await t.test(phase, async () => {
        const acp = client(FLOODING_AGENT, [phase]);
        const groupId = acp.pid;
        assert.ok(groupId);
        try {
          if (phase === "startup") {
            await assertSanitizedTransportFailure(acp.initialize());
          } else {
            assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
            await assertSanitizedTransportFailure(acp.newSession(process.cwd()));
          }
          await waitForProcessGroupGone(groupId);
        } finally {
          await closeClient(acp);
        }
        await proveFreshClientRecovery();
      });
    }
  });

  test("contains aggregate idle output and refuses reuse", {
    skip: process.platform === "win32",
  }, async () => {
    const acp = client(FLOODING_AGENT, ["idle"]);
    const groupId = acp.pid;
    assert.ok(groupId);
    try {
      assert.deepEqual(await within(acp.initialize()), { authMethods: [] });
      assert.equal(await within(acp.newSession(process.cwd())), "flood-session");
      assert.equal(await within(acp.prompt("finish before idle output")), "");
      await waitForProcessGroupGone(groupId, 1_500);
      await assertSanitizedTransportFailure(acp.prompt("must not reuse"));
    } finally {
      await closeClient(acp);
    }
    await proveFreshClientRecovery();
  });
});
