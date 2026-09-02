"""Trusted-driver and candidate-worker transport for hidden verification.

The mediator owns neither hidden assertions nor candidate execution. It gives
each process separate inherited read and write pipes, validates every canonical
JSONL frame, forwards only typed RPC traffic, and treats only the driver's
stdout as final verifier output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from typing import Any, Callable, Mapping, Sequence


PROTOCOL_VERSION = 1
MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_TRANSCRIPT_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 20_000
PROTOCOL_READ_FD_ENV = "ROUTING_SPLIT_READ_FD"
PROTOCOL_WRITE_FD_ENV = "ROUTING_SPLIT_WRITE_FD"
BINDING_ENV = "ROUTING_SPLIT_BINDING"


class ProtocolError(RuntimeError):
    """A peer violated the hidden-verifier protocol."""


@dataclass(frozen=True)
class Binding:
    """Immutable identity and deadline repeated in full on every frame."""

    nonce: str
    task: str
    candidate_manifest_sha256: str
    driver_sha256: str
    worker_sha256: str
    deadline_unix_ms: int

    def __post_init__(self) -> None:
        for name in (
            "nonce",
            "candidate_manifest_sha256",
            "driver_sha256",
            "worker_sha256",
        ):
            value = getattr(self, name)
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ProtocolError(f"binding {name} must be a lowercase SHA-256 value")
        if self.task not in {"use-grok", "karpathy-pointer", "openbot-acp"}:
            raise ProtocolError("binding task is not a benchmark task")
        if not isinstance(self.deadline_unix_ms, int) or isinstance(self.deadline_unix_ms, bool):
            raise ProtocolError("binding deadline_unix_ms must be an integer")
        if self.deadline_unix_ms <= 0:
            raise ProtocolError("binding deadline_unix_ms must be positive")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_value(cls, value: Any) -> "Binding":
        if not isinstance(value, dict) or set(value) != {
            "nonce",
            "task",
            "candidate_manifest_sha256",
            "driver_sha256",
            "worker_sha256",
            "deadline_unix_ms",
        }:
            raise ProtocolError("binding fields differ from the protocol")
        return cls(**value)


@dataclass(frozen=True)
class SplitReceipt:
    driver_returncode: int | None
    worker_returncode: int | None
    timed_out: bool
    protocol_error: str | None
    frame_count: int
    transcript_bytes: int
    transcript_sha256: str
    driver_stdout_bytes: int
    driver_stdout_sha256: str
    driver_stderr_bytes: int
    driver_stderr_sha256: str
    worker_stdout_bytes: int
    worker_stdout_sha256: str
    worker_stderr_bytes: int
    worker_stderr_sha256: str

    @property
    def passed(self) -> bool:
        return (
            not self.timed_out
            and self.protocol_error is None
            and self.driver_returncode == 0
            and self.worker_returncode == 0
            and self.worker_stdout_bytes == 0
        )

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["passed"] = self.passed
        return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_line(value: Any) -> bytes:
    encoded = canonical_bytes(value) + b"\n"
    if len(encoded) > MAX_FRAME_BYTES:
        raise ProtocolError("protocol frame exceeds the byte bound")
    return encoded


def binding_from_environment() -> Binding:
    raw = os.environ.get(BINDING_ENV)
    if raw is None:
        raise ProtocolError(f"{BINDING_ENV} is required")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError("split binding is not valid JSON") from exc
    binding = Binding.from_value(value)
    if raw.encode("utf-8") != canonical_bytes(binding.as_dict()):
        raise ProtocolError("split binding is not canonical JSON")
    return binding


def _frame_fields(kind: str) -> set[str]:
    common = {"protocol_version", "binding", "kind", "sequence"}
    if kind == "request":
        return common | {"request_id", "operation", "payload"}
    if kind == "response":
        return common | {"request_id", "ok", "result", "error"}
    if kind == "event":
        return common | {"request_id", "name", "payload"}
    raise ProtocolError("protocol frame kind is not allowed")


def validate_frame(
    raw_line: bytes,
    *,
    source: str,
    binding: Binding,
    expected_sequence: int,
) -> dict[str, Any]:
    """Validate one exact canonical line and its direction authority."""

    if not raw_line.endswith(b"\n") or b"\n" in raw_line[:-1]:
        raise ProtocolError("protocol input must contain exactly one JSON line")
    if len(raw_line) > MAX_FRAME_BYTES:
        raise ProtocolError("protocol frame exceeds the byte bound")
    try:
        value = json.loads(raw_line)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("protocol frame is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError("protocol frame root must be an object")
    if raw_line != canonical_line(value):
        raise ProtocolError("protocol frame is not canonical JSONL")
    kind = value.get("kind")
    if set(value) != _frame_fields(kind):
        raise ProtocolError("protocol frame fields differ from its kind")
    if value["protocol_version"] != PROTOCOL_VERSION:
        raise ProtocolError("protocol version differs")
    if value["binding"] != binding.as_dict():
        raise ProtocolError("protocol frame binding differs")
    if value["sequence"] != expected_sequence:
        raise ProtocolError("protocol frame sequence differs")
    if source == "driver" and kind != "request":
        raise ProtocolError("driver transport may emit only requests")
    if source == "worker" and kind not in {"response", "event"}:
        raise ProtocolError("worker transport may emit only responses and events")
    request_id = value.get("request_id")
    if not isinstance(request_id, int) or isinstance(request_id, bool) or request_id < 0:
        raise ProtocolError("protocol request_id must be a non-negative integer")
    if kind == "request":
        if not isinstance(value["operation"], str) or not value["operation"]:
            raise ProtocolError("protocol operation must be a non-empty string")
        if not isinstance(value["payload"], dict):
            raise ProtocolError("protocol request payload must be an object")
    elif kind == "response":
        if not isinstance(value["ok"], bool):
            raise ProtocolError("protocol response ok must be boolean")
        if value["ok"]:
            if value["error"] is not None:
                raise ProtocolError("successful response cannot contain an error")
        else:
            if value["result"] is not None or not isinstance(value["error"], str):
                raise ProtocolError("failed response fields are invalid")
    else:
        if not isinstance(value["name"], str) or not value["name"]:
            raise ProtocolError("protocol event name must be a non-empty string")
        if not isinstance(value["payload"], dict):
            raise ProtocolError("protocol event payload must be an object")
    return value


class ProtocolEndpoint:
    """Blocking endpoint used by a trusted driver or candidate worker."""

    def __init__(
        self,
        read_fd: int,
        write_fd: int,
        *,
        role: str,
        binding: Binding,
    ) -> None:
        if role not in {"driver", "worker"}:
            raise ProtocolError("endpoint role must be driver or worker")
        if read_fd == write_fd:
            raise ProtocolError("protocol read and write descriptors must differ")
        self.read_fd = read_fd
        self.write_fd = write_fd
        self.role = role
        self.binding = binding
        self.send_sequence = 0
        self.receive_sequence = 0
        self.next_request_id = 0
        self.buffer = bytearray()

    @classmethod
    def from_environment(cls, *, role: str) -> "ProtocolEndpoint":
        raw_read_fd = os.environ.get(PROTOCOL_READ_FD_ENV)
        raw_write_fd = os.environ.get(PROTOCOL_WRITE_FD_ENV)
        if raw_read_fd is None or not raw_read_fd.isdigit():
            raise ProtocolError(f"{PROTOCOL_READ_FD_ENV} must be a file descriptor")
        if raw_write_fd is None or not raw_write_fd.isdigit():
            raise ProtocolError(f"{PROTOCOL_WRITE_FD_ENV} must be a file descriptor")
        return cls(
            int(raw_read_fd),
            int(raw_write_fd),
            role=role,
            binding=binding_from_environment(),
        )

    def _send(self, value: Mapping[str, Any]) -> None:
        line = canonical_line(value)
        view = memoryview(line)
        while view:
            written = os.write(self.write_fd, view)
            if written <= 0:
                raise ProtocolError("protocol transport closed during write")
            view = view[written:]

    def _read(self) -> dict[str, Any]:
        while b"\n" not in self.buffer:
            if len(self.buffer) >= MAX_FRAME_BYTES:
                raise ProtocolError("protocol frame exceeds the byte bound")
            chunk = os.read(
                self.read_fd,
                min(65536, MAX_FRAME_BYTES - len(self.buffer)),
            )
            if not chunk:
                raise ProtocolError("protocol transport closed before a complete frame")
            self.buffer.extend(chunk)
        end = self.buffer.index(10) + 1
        raw = bytes(self.buffer[:end])
        del self.buffer[:end]
        source = "worker" if self.role == "driver" else "driver"
        value = validate_frame(
            raw,
            source=source,
            binding=self.binding,
            expected_sequence=self.receive_sequence,
        )
        self.receive_sequence += 1
        return value

    def request(
        self,
        operation: str,
        payload: Mapping[str, Any],
        *,
        on_event: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> Any:
        if self.role != "driver":
            raise ProtocolError("only a driver endpoint may send requests")
        request_id = self.next_request_id
        self.next_request_id += 1
        self._send(
            {
                "binding": self.binding.as_dict(),
                "kind": "request",
                "operation": operation,
                "payload": dict(payload),
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "sequence": self.send_sequence,
            }
        )
        self.send_sequence += 1
        while True:
            frame = self._read()
            if frame["request_id"] != request_id:
                raise ProtocolError("worker frame request_id differs from active request")
            if frame["kind"] == "event":
                if on_event is not None:
                    on_event(frame["name"], frame["payload"])
                continue
            if frame["ok"]:
                return frame["result"]
            raise ProtocolError(f"worker operation failed: {frame['error']}")

    def read_request(self) -> dict[str, Any] | None:
        if self.role != "worker":
            raise ProtocolError("only a worker endpoint may read requests")
        try:
            return self._read()
        except ProtocolError as exc:
            if str(exc) == "protocol transport closed before a complete frame" and not self.buffer:
                return None
            raise

    def respond(self, request_id: int, *, result: Any = None, error: str | None = None) -> None:
        if self.role != "worker":
            raise ProtocolError("only a worker endpoint may send responses")
        ok = error is None
        self._send(
            {
                "binding": self.binding.as_dict(),
                "error": None if ok else error,
                "kind": "response",
                "ok": ok,
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "result": result if ok else None,
                "sequence": self.send_sequence,
            }
        )
        self.send_sequence += 1

    def event(self, request_id: int, name: str, payload: Mapping[str, Any]) -> None:
        if self.role != "worker":
            raise ProtocolError("only a worker endpoint may send events")
        self._send(
            {
                "binding": self.binding.as_dict(),
                "kind": "event",
                "name": name,
                "payload": dict(payload),
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "sequence": self.send_sequence,
            }
        )
        self.send_sequence += 1


def run_split_verifier(
    driver_argv: Sequence[str],
    worker_argv: Sequence[str],
    *,
    driver_cwd: Path,
    worker_cwd: Path,
    driver_environment: Mapping[str, str],
    worker_environment: Mapping[str, str],
    binding: Binding,
    deadline_monotonic: float,
    transcript_path: Path,
    driver_stdout_path: Path,
    driver_stderr_path: Path,
    worker_stdout_path: Path,
    worker_stderr_path: Path,
) -> SplitReceipt:
    """Run separately sandboxable peers under one absolute deadline."""

    if not driver_argv or not worker_argv:
        raise ProtocolError("driver and worker commands are required")
    if time.monotonic() >= deadline_monotonic:
        raise ProtocolError("shared deadline elapsed before split verifier start")
    monotonic_remaining = deadline_monotonic - time.monotonic()
    wall_remaining = binding.deadline_unix_ms / 1000 - time.time()
    if abs(monotonic_remaining - wall_remaining) > 1.0:
        raise ProtocolError("binding and mediator deadlines differ")
    outputs = (
        transcript_path,
        driver_stdout_path,
        driver_stderr_path,
        worker_stdout_path,
        worker_stderr_path,
    )
    for path in outputs:
        if path.exists():
            raise ProtocolError(f"split verifier output already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    driver_output_read, driver_output_write = os.pipe()
    driver_input_read, driver_input_write = os.pipe()
    worker_output_read, worker_output_write = os.pipe()
    worker_input_read, worker_input_write = os.pipe()
    all_pipe_fds = {
        driver_output_read,
        driver_output_write,
        driver_input_read,
        driver_input_write,
        worker_output_read,
        worker_output_write,
        worker_input_read,
        worker_input_write,
    }
    binding_text = canonical_bytes(binding.as_dict()).decode("utf-8")
    driver_env = {
        **driver_environment,
        PROTOCOL_READ_FD_ENV: str(driver_input_read),
        PROTOCOL_WRITE_FD_ENV: str(driver_output_write),
        BINDING_ENV: binding_text,
    }
    worker_env = {
        **worker_environment,
        PROTOCOL_READ_FD_ENV: str(worker_input_read),
        PROTOCOL_WRITE_FD_ENV: str(worker_output_write),
        BINDING_ENV: binding_text,
    }
    driver: subprocess.Popen[bytes] | None = None
    worker: subprocess.Popen[bytes] | None = None
    selector: selectors.BaseSelector | None = None
    timed_out = False
    protocol_error: str | None = None
    frame_count = 0
    transcript_bytes = 0
    sequences = {"driver": 0, "worker": 0}
    buffers = {"driver": bytearray(), "worker": bytearray()}

    with (
        transcript_path.open("xb") as transcript,
        driver_stdout_path.open("xb") as driver_stdout,
        driver_stderr_path.open("xb") as driver_stderr,
        worker_stdout_path.open("xb") as worker_stdout,
        worker_stderr_path.open("xb") as worker_stderr,
    ):
        try:
            worker = subprocess.Popen(
                list(worker_argv),
                cwd=worker_cwd,
                env=worker_env,
                stdin=subprocess.DEVNULL,
                stdout=worker_stdout,
                stderr=worker_stderr,
                pass_fds=(worker_input_read, worker_output_write),
                start_new_session=True,
            )
            driver = subprocess.Popen(
                list(driver_argv),
                cwd=driver_cwd,
                env=driver_env,
                stdin=subprocess.DEVNULL,
                stdout=driver_stdout,
                stderr=driver_stderr,
                pass_fds=(driver_input_read, driver_output_write),
                start_new_session=True,
            )
            for child_fd in (
                driver_input_read,
                driver_output_write,
                worker_input_read,
                worker_output_write,
            ):
                os.close(child_fd)
                all_pipe_fds.remove(child_fd)
            for parent_fd in (
                driver_output_read,
                driver_input_write,
                worker_output_read,
                worker_input_write,
            ):
                os.set_blocking(parent_fd, False)
            selector = selectors.DefaultSelector()
            readers = {
                "driver": driver_output_read,
                "worker": worker_output_read,
            }
            writers = {
                "driver": driver_input_write,
                "worker": worker_input_write,
            }
            for source, read_fd in readers.items():
                selector.register(read_fd, selectors.EVENT_READ, ("read", source))
            pending = {"driver": bytearray(), "worker": bytearray()}
            source_closed = {"driver": False, "worker": False}
            writer_open = {"driver": True, "worker": True}
            writer_registered: set[str] = set()

            def close_writer(target: str) -> None:
                if not writer_open[target]:
                    return
                if target in writer_registered:
                    selector.unregister(writers[target])
                    writer_registered.remove(target)
                os.close(writers[target])
                all_pipe_fds.remove(writers[target])
                writer_open[target] = False

            def queue_frame(target: str, raw: bytes) -> None:
                if not writer_open[target]:
                    raise ProtocolError(f"{target} transport closed before forwarding")
                pending[target].extend(raw)
                if target not in writer_registered:
                    selector.register(
                        writers[target],
                        selectors.EVENT_WRITE,
                        ("write", target),
                    )
                    writer_registered.add(target)

            while selector.get_map():
                if time.monotonic() >= deadline_monotonic:
                    timed_out = True
                    break
                events = selector.select(min(0.1, deadline_monotonic - time.monotonic()))
                for key, _mask in events:
                    operation, peer = key.data
                    if operation == "write":
                        try:
                            written = os.write(writers[peer], pending[peer])
                        except BlockingIOError:
                            continue
                        if written <= 0:
                            raise ProtocolError(
                                f"{peer} transport closed during forwarding"
                            )
                        del pending[peer][:written]
                        if not pending[peer]:
                            selector.unregister(writers[peer])
                            writer_registered.remove(peer)
                            source = "worker" if peer == "driver" else "driver"
                            if source_closed[source]:
                                close_writer(peer)
                        continue

                    source = peer
                    try:
                        chunk = os.read(readers[source], 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        if buffers[source]:
                            raise ProtocolError(f"{source} closed with an incomplete frame")
                        selector.unregister(readers[source])
                        os.close(readers[source])
                        all_pipe_fds.remove(readers[source])
                        source_closed[source] = True
                        target = "worker" if source == "driver" else "driver"
                        if not pending[target]:
                            close_writer(target)
                        continue
                    buffers[source].extend(chunk)
                    if len(buffers[source]) > MAX_FRAME_BYTES and b"\n" not in buffers[source]:
                        raise ProtocolError(f"{source} frame exceeds the byte bound")
                    while b"\n" in buffers[source]:
                        end = buffers[source].index(10) + 1
                        raw = bytes(buffers[source][:end])
                        del buffers[source][:end]
                        validate_frame(
                            raw,
                            source=source,
                            binding=binding,
                            expected_sequence=sequences[source],
                        )
                        sequences[source] += 1
                        frame_count += 1
                        if frame_count > MAX_FRAMES:
                            raise ProtocolError("protocol frame count exceeds the bound")
                        prefix = b"D" if source == "driver" else b"W"
                        record = prefix + len(raw).to_bytes(4, "big") + raw
                        transcript_bytes += len(record)
                        if transcript_bytes > MAX_TRANSCRIPT_BYTES:
                            raise ProtocolError("protocol transcript exceeds the byte bound")
                        transcript.write(record)
                        target = "worker" if source == "driver" else "driver"
                        queue_frame(target, raw)
            transcript.flush()
            os.fsync(transcript.fileno())
        except (OSError, ProtocolError) as exc:
            protocol_error = f"{type(exc).__name__}: {exc}"
        finally:
            if selector is not None:
                selector.close()
            for child in (driver, worker):
                if child is not None and child.poll() is None:
                    _terminate_process_group(child)
            for child in (driver, worker):
                if child is not None:
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        _kill_process_group(child.pid)
                        child.wait(timeout=2)
            for pipe_fd in tuple(all_pipe_fds):
                try:
                    os.close(pipe_fd)
                except OSError:
                    pass
                all_pipe_fds.discard(pipe_fd)

    worker_stdout_bytes = worker_stdout_path.stat().st_size
    if worker_stdout_bytes and protocol_error is None:
        protocol_error = "ProtocolError: worker wrote unauthorized final output"
    return SplitReceipt(
        driver_returncode=None if driver is None else driver.returncode,
        worker_returncode=None if worker is None else worker.returncode,
        timed_out=timed_out,
        protocol_error=protocol_error,
        frame_count=frame_count,
        transcript_bytes=transcript_bytes,
        transcript_sha256=_sha256_file(transcript_path),
        driver_stdout_bytes=driver_stdout_path.stat().st_size,
        driver_stdout_sha256=_sha256_file(driver_stdout_path),
        driver_stderr_bytes=driver_stderr_path.stat().st_size,
        driver_stderr_sha256=_sha256_file(driver_stderr_path),
        worker_stdout_bytes=worker_stdout_bytes,
        worker_stdout_sha256=_sha256_file(worker_stdout_path),
        worker_stderr_bytes=worker_stderr_path.stat().st_size,
        worker_stderr_sha256=_sha256_file(worker_stderr_path),
    )


def _terminate_process_group(child: subprocess.Popen[bytes]) -> None:
    pid = child.pid
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        child.poll()
        return
    except PermissionError:
        if child.poll() is not None:
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                return
        raise
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        child.poll()
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    _kill_process_group(pid, child=child)


def _kill_process_group(
    pid: int, *, child: subprocess.Popen[bytes] | None = None
) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if child is None or child.poll() is None:
            raise
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
