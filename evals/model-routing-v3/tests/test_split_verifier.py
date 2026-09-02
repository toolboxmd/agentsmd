from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

import split_verifier


class ProtocolTests(unittest.TestCase):
    def binding(self, task: str = "use-grok") -> split_verifier.Binding:
        return split_verifier.Binding(
            nonce="0" * 64,
            task=task,
            candidate_manifest_sha256="1" * 64,
            driver_sha256="2" * 64,
            worker_sha256="3" * 64,
            deadline_unix_ms=int(time.time() * 1000) + 10_000,
        )

    def request(self, binding: split_verifier.Binding, sequence: int = 0) -> dict[str, object]:
        return {
            "binding": binding.as_dict(),
            "kind": "request",
            "operation": "echo",
            "payload": {"value": "ok"},
            "protocol_version": 1,
            "request_id": 0,
            "sequence": sequence,
        }

    def test_canonical_frame_binds_nonce_identity_deadline_and_sequence(self) -> None:
        binding = self.binding()
        raw = split_verifier.canonical_line(self.request(binding))
        value = split_verifier.validate_frame(
            raw,
            source="driver",
            binding=binding,
            expected_sequence=0,
        )
        self.assertEqual(value["binding"], binding.as_dict())
        for mutation in (
            lambda item: item["binding"].__setitem__("nonce", "f" * 64),
            lambda item: item.__setitem__("sequence", 1),
        ):
            changed = json.loads(raw)
            mutation(changed)
            with self.assertRaises(split_verifier.ProtocolError):
                split_verifier.validate_frame(
                    split_verifier.canonical_line(changed),
                    source="driver",
                    binding=binding,
                    expected_sequence=0,
                )

    def test_rejects_noncanonical_wrong_direction_and_oversized_frames(self) -> None:
        binding = self.binding()
        request = self.request(binding)
        noncanonical = (json.dumps(request, sort_keys=False) + "\n").encode()
        with self.assertRaisesRegex(split_verifier.ProtocolError, "canonical"):
            split_verifier.validate_frame(
                noncanonical,
                source="driver",
                binding=binding,
                expected_sequence=0,
            )
        with self.assertRaisesRegex(split_verifier.ProtocolError, "worker transport"):
            split_verifier.validate_frame(
                split_verifier.canonical_line(request),
                source="worker",
                binding=binding,
                expected_sequence=0,
            )
        oversized = self.request(binding)
        oversized["payload"] = {"value": "x" * split_verifier.MAX_FRAME_BYTES}
        with self.assertRaisesRegex(split_verifier.ProtocolError, "byte bound"):
            split_verifier.canonical_line(oversized)

    def test_mediator_hashes_exact_transcript_and_only_driver_owns_output(self) -> None:
        binding = self.binding()
        driver_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='driver')
value = endpoint.request('echo', {'value': 'hello'})
print(value['value'])
"""
        worker_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='worker')
while True:
    request = endpoint.read_request()
    if request is None:
        break
    endpoint.respond(request['request_id'], result=request['payload'])
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            environment = {
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(PACKAGE_ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            paths = {
                name: root / name
                for name in (
                    "transcript",
                    "driver.stdout",
                    "driver.stderr",
                    "worker.stdout",
                    "worker.stderr",
                )
            }
            receipt = split_verifier.run_split_verifier(
                [sys.executable, "-B", "-c", driver_program],
                [sys.executable, "-B", "-c", worker_program],
                driver_cwd=root,
                worker_cwd=root,
                driver_environment=environment,
                worker_environment=environment,
                binding=binding,
                deadline_monotonic=time.monotonic() + 10,
                transcript_path=paths["transcript"],
                driver_stdout_path=paths["driver.stdout"],
                driver_stderr_path=paths["driver.stderr"],
                worker_stdout_path=paths["worker.stdout"],
                worker_stderr_path=paths["worker.stderr"],
            )
            self.assertTrue(receipt.passed, receipt.as_dict())
            self.assertEqual(paths["driver.stdout"].read_text(), "hello\n")
            self.assertEqual(paths["worker.stdout"].read_bytes(), b"")
            self.assertEqual(receipt.frame_count, 2)
            self.assertEqual(
                receipt.transcript_sha256,
                hashlib.sha256(paths["transcript"].read_bytes()).hexdigest(),
            )

    def test_node_sync_endpoint_roundtrip_uses_distinct_inherited_pipes(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        binding = self.binding()
        driver_program = r"""
const fs = require("node:fs");
const readFd = Number(process.env.ROUTING_SPLIT_READ_FD);
const writeFd = Number(process.env.ROUTING_SPLIT_WRITE_FD);
if (!Number.isSafeInteger(readFd) || !Number.isSafeInteger(writeFd) || readFd === writeFd) {
  throw new Error("split pipe descriptors are invalid");
}
if (process.env.ROUTING_SPLIT_PROTOCOL_FD !== undefined) {
  throw new Error("legacy duplex descriptor must not be present");
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
const binding = JSON.parse(process.env.ROUTING_SPLIT_BINDING);
const request = {
  binding,
  kind: "request",
  operation: "echo",
  payload: { value: "node-sync-ok" },
  protocol_version: 1,
  request_id: 0,
  sequence: 0,
};
fs.writeSync(writeFd, `${canonical(request)}\n`);
let buffered = Buffer.alloc(0);
while (buffered.indexOf(10) < 0) {
  const chunk = Buffer.alloc(65536);
  const count = fs.readSync(readFd, chunk, 0, chunk.length, null);
  if (count === 0) throw new Error("protocol response closed early");
  buffered = Buffer.concat([buffered, chunk.subarray(0, count)]);
}
const end = buffered.indexOf(10);
const raw = buffered.subarray(0, end).toString("utf8");
const response = JSON.parse(raw);
if (canonical(response) !== raw || response.result.value !== "node-sync-ok") {
  throw new Error("protocol response differs");
}
process.stdout.write(`${response.result.value}\n`);
"""
        worker_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='worker')
request = endpoint.read_request()
endpoint.respond(request['request_id'], result=request['payload'])
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            environment = {
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(PACKAGE_ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            paths = {
                name: root / name
                for name in (
                    "transcript",
                    "driver.stdout",
                    "driver.stderr",
                    "worker.stdout",
                    "worker.stderr",
                )
            }
            receipt = split_verifier.run_split_verifier(
                [node, "-e", driver_program],
                [sys.executable, "-B", "-c", worker_program],
                driver_cwd=root,
                worker_cwd=root,
                driver_environment=environment,
                worker_environment=environment,
                binding=binding,
                deadline_monotonic=time.monotonic() + 10,
                transcript_path=paths["transcript"],
                driver_stdout_path=paths["driver.stdout"],
                driver_stderr_path=paths["driver.stderr"],
                worker_stdout_path=paths["worker.stdout"],
                worker_stderr_path=paths["worker.stderr"],
            )
            self.assertTrue(receipt.passed, receipt.as_dict())
            self.assertEqual(paths["driver.stdout"].read_text(), "node-sync-ok\n")
            self.assertEqual(receipt.frame_count, 2)

    def sandboxed_node_test_roundtrip(
        self, *, use_test_runner: bool
    ) -> tuple[split_verifier.SplitReceipt, str, str, str]:
        node = shutil.which("node")
        sandbox = Path("/usr/bin/sandbox-exec")
        if node is None or not sandbox.is_file():
            self.skipTest("Node.js or sandbox-exec is unavailable")
        binding = self.binding(task="openbot-acp")
        driver_program = r"""
import fs from "node:fs";
import { test } from "node:test";
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonical(object[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
test("sandboxed test child roundtrip", () => {
  const readFd = Number(process.env.ROUTING_SPLIT_READ_FD);
  const writeFd = Number(process.env.ROUTING_SPLIT_WRITE_FD);
  const binding = JSON.parse(process.env.ROUTING_SPLIT_BINDING);
  const request = {
    binding,
    kind: "request",
    operation: "echo",
    payload: { value: "sandboxed-node-test-ok" },
    protocol_version: 1,
    request_id: 0,
    sequence: 0,
  };
  fs.writeSync(writeFd, `${canonical(request)}\n`);
  let buffered = Buffer.alloc(0);
  while (buffered.indexOf(10) < 0) {
    const chunk = Buffer.alloc(65536);
    const count = fs.readSync(readFd, chunk, 0, chunk.length, null);
    if (count === 0) throw new Error("protocol response closed early");
    buffered = Buffer.concat([buffered, chunk.subarray(0, count)]);
  }
  const raw = buffered.subarray(0, buffered.indexOf(10)).toString("utf8");
  const response = JSON.parse(raw);
  if (canonical(response) !== raw || response.result.value !== "sandboxed-node-test-ok") {
    throw new Error("protocol response differs");
  }
});
"""
        worker_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='worker')
request = endpoint.read_request()
endpoint.respond(request['request_id'], result=request['payload'])
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            driver_file = root / "driver.test.ts"
            driver_file.write_text(driver_program, encoding="utf-8")
            profile = (
                '(version 1)(deny default)(import "system.sb")'
                '(allow process*)(allow file-read*)'
                f'(allow file-write* (subpath {json.dumps(str(root.resolve()))}))'
            )
            environment = {
                "HOME": str(root),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "PYTHONPATH": str(PACKAGE_ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
                "TMPDIR": str(root),
            }
            paths = {
                name: root / name
                for name in (
                    "transcript",
                    "driver.stdout",
                    "driver.stderr",
                    "worker.stdout",
                    "worker.stderr",
                )
            }
            receipt = split_verifier.run_split_verifier(
                [
                    str(sandbox),
                    "-p",
                    profile,
                    node,
                    "--experimental-strip-types",
                    *(["--test"] if use_test_runner else []),
                    str(driver_file),
                ],
                [sys.executable, "-B", "-c", worker_program],
                driver_cwd=root,
                worker_cwd=root,
                driver_environment=environment,
                worker_environment=environment,
                binding=binding,
                deadline_monotonic=time.monotonic() + 10,
                transcript_path=paths["transcript"],
                driver_stdout_path=paths["driver.stdout"],
                driver_stderr_path=paths["driver.stderr"],
                worker_stdout_path=paths["worker.stdout"],
                worker_stderr_path=paths["worker.stderr"],
            )
            return (
                receipt,
                paths["driver.stdout"].read_text(),
                paths["driver.stderr"].read_text(),
                paths["worker.stderr"].read_text(),
            )

    def test_sandboxed_direct_node_test_roundtrip_preserves_protocol_fds(self) -> None:
        receipt, driver_stdout, driver_stderr, worker_stderr = (
            self.sandboxed_node_test_roundtrip(use_test_runner=False)
        )
        self.assertTrue(receipt.passed, {
            **receipt.as_dict(),
            "driver_stdout": driver_stdout,
            "driver_stderr": driver_stderr,
            "worker_stderr": worker_stderr,
        })
        self.assertIn("sandboxed test child roundtrip", driver_stdout)
        self.assertEqual(receipt.frame_count, 2)

    def test_node_test_runner_child_drops_protocol_fds_fail_closed(self) -> None:
        receipt, driver_stdout, _driver_stderr, _worker_stderr = (
            self.sandboxed_node_test_roundtrip(use_test_runner=True)
        )
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.driver_returncode, 1)
        self.assertEqual(receipt.frame_count, 0)
        self.assertRegex(driver_stdout, r"E(?:BADF|NXIO|ISDIR):")

    def test_openbot_worker_acknowledges_close_and_exits_after_driver_eof(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        binding = self.binding(task="openbot-acp")
        driver_program = """
from split_verifier import ProtocolEndpoint
endpoint = ProtocolEndpoint.from_environment(role='driver')
created = endpoint.request('create', {
    'amount': 0,
    'mode': 'healthy',
    'option': '',
    'timing': {'startDeadlineMs': 750, 'terminateGraceMs': 25},
})
pid = created['pid']
assert isinstance(pid, int) and pid > 1
closed = endpoint.request('close', {'client_id': created['client_id']})
assert closed is None
print('close-acknowledged')
"""
        candidate_program = r"""
import { spawn } from "node:child_process";

const signalProcess = process.kill.bind(process);

export class AcpClient {
  constructor() {
    this.child = spawn(process.execPath, [
      "-e",
      "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000);",
    ], { detached: true, stdio: "ignore" });
    this.child.unref();
    this.pid = this.child.pid;
  }

  close() {
    try {
      signalProcess(-this.pid, "SIGKILL");
    } catch (error) {
      if (error?.code !== "ESRCH") throw error;
    }
  }
}
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            candidate = root / "candidate.mjs"
            relay = root / "relay.mjs"
            candidate.write_text(candidate_program, encoding="utf-8")
            relay.write_text("// worker constructor stub does not execute this file\n", encoding="utf-8")
            environment = {
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(PACKAGE_ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            worker_environment = {
                **environment,
                "ROUTING_CANDIDATE_ACP": str(candidate),
                "ROUTING_CANDIDATE_ROOT": str(root),
                "ROUTING_OPENBOT_AGENT_RELAY": str(relay),
            }
            paths = {
                name: root / name
                for name in (
                    "transcript",
                    "driver.stdout",
                    "driver.stderr",
                    "worker.stdout",
                    "worker.stderr",
                )
            }
            receipt = split_verifier.run_split_verifier(
                [sys.executable, "-B", "-c", driver_program],
                [node, str(PACKAGE_ROOT / "verifiers/workers/openbot_acp_worker.mjs")],
                driver_cwd=root,
                worker_cwd=root,
                driver_environment=environment,
                worker_environment=worker_environment,
                binding=binding,
                deadline_monotonic=time.monotonic() + 10,
                transcript_path=paths["transcript"],
                driver_stdout_path=paths["driver.stdout"],
                driver_stderr_path=paths["driver.stderr"],
                worker_stdout_path=paths["worker.stdout"],
                worker_stderr_path=paths["worker.stderr"],
            )
            self.assertTrue(receipt.passed, {
                **receipt.as_dict(),
                "driver_stdout": paths["driver.stdout"].read_text(),
                "driver_stderr": paths["driver.stderr"].read_text(),
                "worker_stderr": paths["worker.stderr"].read_text(),
            })
            self.assertEqual(paths["driver.stdout"].read_text(), "close-acknowledged\n")


class SourceSeparationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (PACKAGE_ROOT / relative).read_text(encoding="utf-8")

    def test_python_sources_parse_without_importing_candidate_in_driver(self) -> None:
        driver = self.read("verifiers/hidden/v2_split_driver.py")
        worker = self.read("verifiers/workers/v2_command_worker.py")
        ast.parse(driver)
        ast.parse(worker)
        self.assertNotIn("subprocess", driver)
        self.assertNotIn("verify_use_grok", worker)
        self.assertNotIn("verify_karpathy_pointer", worker)
        self.assertNotIn("frozen-hidden", worker)

    def test_openbot_candidate_import_and_hidden_assertions_are_separate(self) -> None:
        driver = self.read("verifiers/hidden/openbot_acp_hidden_driver.test.ts")
        worker = self.read("verifiers/workers/openbot_acp_worker.mjs")
        relay = self.read("verifiers/workers/openbot_agent_relay.mjs")
        for peer in (driver, worker):
            self.assertIn("ROUTING_SPLIT_READ_FD", peer)
            self.assertIn("ROUTING_SPLIT_WRITE_FD", peer)
            self.assertNotIn("ROUTING_SPLIT_PROTOCOL_FD", peer)
        self.assertNotIn("ROUTING_CANDIDATE_ACP", driver)
        self.assertNotIn("pathToFileURL", driver)
        self.assertIn("ROUTING_WORKSPACE_ROOT", driver)
        self.assertNotIn("process.cwd()", driver)
        self.assertIn("process.kill(-groupId, 0)", driver)
        self.assertIn("process.kill(processId, 0)", driver)
        self.assertNotIn("SIGTERM", driver)
        self.assertNotIn("SIGKILL", driver)
        self.assertIn("ROUTING_CANDIDATE_ACP", worker)
        self.assertIn("pathToFileURL", worker)
        self.assertNotIn("observe_cleanup", driver)
        self.assertNotIn("observe_cleanup", worker)
        self.assertIn('transport.request("close", {', driver)
        self.assertIn('operation === "close"', worker)
        self.assertIn("await sleep(state.terminateGraceMs + 25);", worker)
        self.assertIn("if (maximumGraceMs > 0) await sleep(maximumGraceMs + 25);", worker)
        self.assertLess(
            worker.index("const closeDescriptor = fs.closeSync.bind(fs);"),
            worker.index("await import(pathToFileURL(resolvedCandidate).href)"),
        )
        self.assertIn("exitProcess(shutdownReturnCode);", worker)
        self.assertNotIn("node:assert", worker)
        self.assertNotIn("node:test", worker)
        self.assertNotIn("node:assert", relay)
        self.assertNotIn("node:test", relay)
        self.assertNotIn("ACP transport protocol error", worker)

    def test_protocol_schema_is_strict_and_has_no_final_worker_frame(self) -> None:
        schema = json.loads(self.read("schemas/hidden-protocol.schema.json"))
        self.assertEqual(schema["$defs"]["base"]["properties"]["kind"]["enum"], [
            "request",
            "response",
            "event",
        ])
        self.assertNotIn("final", json.dumps(schema))


if __name__ == "__main__":
    unittest.main()
