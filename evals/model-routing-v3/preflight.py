"""Native, no-model permission-profile preflight for routing benchmark v3.

This seam deliberately uses ``codex sandbox`` and ``codex debug prompt-input``.
It never invokes ``codex exec`` and therefore cannot spend model quota. Every
denial is paired with an unsandboxed positive control against the exact same
file, endpoint, socket, or environment name.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import stat
import subprocess
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ElementTree
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import isolation


POLICY_DENIED_EXIT = 77
VALID_CATEGORIES = frozenset({"success", "policy_denied", "timeout", "error"})
HEX_LENGTH = 64
COMMAND_LINE_TOOLS_ROOT = Path("/Library/Developer/CommandLineTools")
SHORT_SOCKET_PARENT = Path("/private/tmp")


class PreflightError(RuntimeError):
    """The no-model boundary could not be proven exactly."""


@dataclass(frozen=True)
class Operation:
    name: str
    arguments: tuple[str, ...]
    expected_category: str
    positive_arguments: tuple[str, ...] | None = None
    timeout_seconds: float = 4.0


@dataclass(frozen=True)
class CommandResult:
    category: str
    returncode: int | None
    elapsed_seconds: float
    stdout_sha256: str
    stderr_sha256: str
    payload: Mapping[str, Any] | None


@dataclass(frozen=True)
class PreflightBindings:
    package_sha256: str
    fixture_sha256: Mapping[str, str]

    def normalized(self) -> "PreflightBindings":
        return PreflightBindings(
            package_sha256=_sha(self.package_sha256, "package_sha256"),
            fixture_sha256={
                _identifier(name, "fixture name"): _sha(value, f"fixture {name}")
                for name, value in sorted(self.fixture_sha256.items())
            },
        )


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receipt_sha256(receipt: Mapping[str, Any]) -> str:
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_definition(
    path: Path, bindings: PreflightBindings, expected_codex_sha256: str
) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError("definition is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise PreflightError("definition must be a JSON object")
    pinned = value.get("pinned_runtime")
    tasks = value.get("tasks")
    if not isinstance(pinned, dict) or not isinstance(tasks, dict) or not tasks:
        raise PreflightError("definition lacks pinned_runtime or tasks")
    if pinned.get("codex_cli_version") != isolation.CODEX_VERSION:
        raise PreflightError("definition Codex version does not match isolation pin")
    if pinned.get("codex_native_sha256") != expected_codex_sha256:
        raise PreflightError("definition Codex binary hash does not match requested pin")
    if set(bindings.fixture_sha256) != set(tasks):
        raise PreflightError("fixture hash names do not match definition tasks")
    return value


def sandbox_command(
    codex_executable: Path | str,
    paths: isolation.CodexPaths,
    probe_executable: Path | str,
    arguments: Sequence[str],
) -> list[str]:
    normalized = paths.normalized()
    probe = Path(probe_executable).expanduser().resolve(strict=True)
    return [
        str(Path(codex_executable).expanduser().resolve(strict=True)),
        "sandbox",
        "-P",
        isolation.PROFILE_CANDIDATE,
        "-C",
        str(normalized.candidate_root),
        "--",
        str(probe),
        *map(str, arguments),
    ]


def _parse_probe(stdout: bytes, returncode: int) -> tuple[str, Mapping[str, Any] | None]:
    try:
        text = stdout.decode("utf-8", errors="strict")
        lines = text.splitlines()
        if len(lines) != 1:
            return "error", None
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("category") not in VALID_CATEGORIES:
            return "error", None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "error", None
    category = payload["category"]
    if category == "success" and returncode == 0:
        return category, payload
    if (
        category == "policy_denied"
        and returncode == POLICY_DENIED_EXIT
        and payload.get("errno") in {1, 13}
    ):
        return category, payload
    return "error", payload


def run_probe_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path | str,
    timeout_seconds: float,
) -> CommandResult:
    started = time.monotonic()
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd),
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        isolation.terminate_process_group(process)
        stdout, stderr = process.communicate()
        category, payload = "timeout", None
    else:
        category, payload = _parse_probe(stdout, process.returncode)
    return CommandResult(
        category=category,
        returncode=process.returncode,
        elapsed_seconds=time.monotonic() - started,
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        payload=payload,
    )


class _TcpServer:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(8)
        self.socket.settimeout(0.1)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)

    @property
    def endpoint(self) -> tuple[str, int]:
        host, port = self.socket.getsockname()
        return str(host), int(port)

    def __enter__(self) -> "_TcpServer":
        self.thread.start()
        return self

    def _serve(self) -> None:
        while not self.stop.is_set():
            try:
                connection, _ = self.socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            connection.close()

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.socket.close()
        self.thread.join(timeout=1)


class _UnixServer:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def __enter__(self) -> "_UnixServer":
        self.path.unlink(missing_ok=True)
        self.socket.bind(str(self.path))
        self.socket.listen(8)
        self.socket.settimeout(0.1)
        self.thread.start()
        return self

    def _serve(self) -> None:
        while not self.stop.is_set():
            try:
                connection, _ = self.socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            connection.close()

    def __exit__(self, *_: object) -> None:
        self.stop.set()
        self.socket.close()
        self.thread.join(timeout=1)
        self.path.unlink(missing_ok=True)


def _marker_pids(marker: str) -> list[int]:
    result = subprocess.run(
        ["/bin/ps", "eww", "-axo", "pid=,command="],
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    if result.returncode:
        raise PreflightError("cannot scan for breakaway descendants")
    own_pid = os.getpid()
    found: list[int] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) == 2 and marker in fields[1]:
            pid = int(fields[0])
            if pid != own_pid:
                found.append(pid)
    return found


def _kill_pids(pids: Iterable[int]) -> None:
    unique = sorted(set(pids))
    for pid in unique:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(0.1)
    for pid in unique:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _version(codex: Path, environment: Mapping[str, str], cwd: Path) -> str:
    result = subprocess.run(
        [str(codex), "--version"],
        cwd=str(cwd),
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1:] or result.stdout.strip().splitlines()[-1:]
        suffix = f": {detail[0]}" if detail else ""
        raise PreflightError("pinned Codex binary did not report a version" + suffix)
    value = result.stdout.strip()
    if value not in {isolation.CODEX_VERSION, f"codex-cli {isolation.CODEX_VERSION}"}:
        raise PreflightError(f"unexpected Codex version: {value!r}")
    return value


def _debug_prompt_input(
    codex: Path, environment: Mapping[str, str], candidate: Path
) -> dict[str, Any]:
    result = subprocess.run(
        [str(codex), "debug", "prompt-input", "routing-v3-no-model-preflight"],
        cwd=str(candidate),
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if result.returncode:
        raise PreflightError("codex debug prompt-input rejected the isolated config")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError("codex debug prompt-input did not return JSON") from exc
    evidence = _parse_prompt_input(payload, candidate)
    evidence["stdout_sha256"] = hashlib.sha256(
        result.stdout.encode("utf-8")
    ).hexdigest()
    return evidence


def _parse_prompt_input(payload: Any, candidate: Path) -> dict[str, Any]:
    """Validate the model-visible Codex 0.149.1 environment context.

    ``codex debug prompt-input`` returns an array of Responses input items.  It
    does not expose the configured permission-profile ID.  The selected ID is
    instead bound by the config receipt and by the explicit ``codex sandbox
    -P`` invocations.  This parser proves only the effective managed-profile
    semantics that the debug command actually makes model-visible.
    """

    if not isinstance(payload, list) or not payload:
        raise PreflightError("prompt input root must be a nonempty JSON array")
    texts: list[str] = []
    for item in payload:
        if not isinstance(item, dict):
            raise PreflightError("prompt input array contains a non-object item")
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise PreflightError("prompt input message content must be an array")
        for part in content:
            if not isinstance(part, dict):
                raise PreflightError("prompt input message contains a non-object part")
            if part.get("type") != "input_text":
                continue
            text = part.get("text")
            if not isinstance(text, str):
                raise PreflightError("prompt input_text must contain text")
            texts.append(text)

    joined = "\n".join(texts)
    forbidden = ("<skills_instructions>", "## Skills\n", "/skills/.system/")
    leaked = [needle for needle in forbidden if needle in joined]
    if leaked:
        raise PreflightError("prompt input contains a Skills injection: " + ", ".join(leaked))

    contexts = [
        text.strip()
        for text in texts
        if text.lstrip().startswith("<environment_context>")
    ]
    if len(contexts) != 1:
        raise PreflightError("prompt input must contain exactly one environment_context")
    try:
        context = ElementTree.fromstring(contexts[0])
    except ElementTree.ParseError as exc:
        raise PreflightError("prompt input environment_context is not valid XML") from exc
    if context.tag != "environment_context":
        raise PreflightError("prompt input environment_context root is invalid")

    resolved_candidate = candidate.expanduser().resolve(strict=True)
    write_root = (resolved_candidate / ".runner-tmp").resolve(strict=True)
    cwd_nodes = context.findall("cwd")
    if len(cwd_nodes) != 1 or (cwd_nodes[0].text or "").strip() != str(resolved_candidate):
        raise PreflightError("prompt input does not bind the exact candidate cwd")
    filesystem_nodes = context.findall("filesystem")
    if len(filesystem_nodes) != 1:
        raise PreflightError("prompt input must contain exactly one filesystem context")
    filesystem = filesystem_nodes[0]
    workspace_nodes = filesystem.findall("workspace_roots")
    if len(workspace_nodes) != 1:
        raise PreflightError("prompt input must contain exactly one workspace_roots context")
    workspace_roots = [
        (node.text or "").strip() for node in list(workspace_nodes[0]) if node.tag == "root"
    ]
    if len(list(workspace_nodes[0])) != 1 or workspace_roots != [str(resolved_candidate)]:
        raise PreflightError("prompt input does not bind the exact candidate workspace root")

    profile_nodes = filesystem.findall("permission_profile")
    if len(profile_nodes) != 1 or profile_nodes[0].attrib != {"type": "managed"}:
        raise PreflightError("prompt input does not expose a managed permission profile")
    file_system_nodes = profile_nodes[0].findall("file_system")
    if len(file_system_nodes) != 1 or file_system_nodes[0].attrib != {"type": "restricted"}:
        raise PreflightError("prompt input does not expose restricted filesystem semantics")

    parsed_entries: list[tuple[str, str, str, Mapping[str, str]]] = []
    for entry in list(file_system_nodes[0]):
        children = list(entry)
        if entry.tag != "entry" or len(children) != 1 or children[0].tag not in {"path", "special"}:
            raise PreflightError("prompt input contains an invalid filesystem entry")
        access = entry.attrib.get("access")
        if access not in {"read", "write", "deny"}:
            raise PreflightError("prompt input contains an invalid filesystem access")
        value = (children[0].text or "").strip()
        if not value:
            raise PreflightError("prompt input contains an empty filesystem entry")
        parsed_entries.append((children[0].tag, value, access, dict(entry.attrib)))

    writes = [value for kind, value, access, _ in parsed_entries if access == "write" and kind == "path"]
    if any(access == "write" and kind != "path" for kind, _, access, _ in parsed_entries):
        raise PreflightError("prompt input contains a non-path write grant")
    if writes != [str(write_root)]:
        raise PreflightError("prompt input does not expose the exact sole candidate write root")
    candidate_reads = [
        entry
        for entry in parsed_entries
        if entry[0:3] == ("path", str(resolved_candidate), "read")
    ]
    if len(candidate_reads) != 1:
        raise PreflightError("prompt input does not expose candidate workspace read access")

    expected_specials = {
        ":minimal": {"access": "read"},
        ":root": {"access": "deny", "escalatable": "false"},
        ":slash_tmp": {"access": "deny", "escalatable": "false"},
    }
    for special, attributes in expected_specials.items():
        matching = [
            entry
            for entry in parsed_entries
            if entry[0] == "special" and entry[1] == special
        ]
        if len(matching) != 1 or matching[0][3] != attributes:
            raise PreflightError(f"prompt input does not expose exact {special} semantics")

    return {
        "response_item_array": True,
        "environment_context_xml": True,
        "candidate_cwd_bound": True,
        "workspace_roots": [str(resolved_candidate)],
        "write_roots": [str(write_root)],
        "candidate_read_bound": True,
        "effective_permission_profile_type": "managed",
        "effective_filesystem_type": "restricted",
        "minimal_special_access": "read",
        "root_special_access": "deny",
        "slash_tmp_special_access": "deny",
        "named_permission_profile_id_exposed": False,
        "skills_injected": False,
    }


def _protected_read_files(
    values: Mapping[str, Path | str], candidate: Path
) -> dict[str, Path]:
    if not isinstance(values, Mapping) or not values:
        raise PreflightError("protected_read_paths must be a nonempty mapping")
    protected: dict[str, Path] = {}
    observed: set[Path] = set()
    for raw_name, raw_path in sorted(values.items()):
        name = _identifier(raw_name, "protected read name")
        try:
            supplied = Path(raw_path).expanduser()
        except TypeError as exc:
            raise PreflightError(f"protected read path {name} is invalid") from exc
        if not supplied.is_absolute() or supplied.is_symlink():
            raise PreflightError(f"protected read path {name} must be an absolute ordinary file")
        try:
            path = supplied.resolve(strict=True)
        except OSError as exc:
            raise PreflightError(f"protected read path {name} does not exist") from exc
        state = path.lstat()
        if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
            raise PreflightError(f"protected read path {name} must be an ordinary single-link file")
        if _within(path, candidate):
            raise PreflightError(f"protected read path {name} must be outside the candidate")
        if path in observed:
            raise PreflightError("protected_read_paths must resolve to distinct files")
        observed.add(path)
        protected[name] = path
    return protected


def _external_target(candidates: Sequence[tuple[str, int]]) -> tuple[str, int]:
    for host, port in candidates:
        try:
            with socket.create_connection((host, port), timeout=1.5):
                return host, port
        except OSError:
            continue
    raise PreflightError("no pre-established reachable external TCP target")


def _record(result: CommandResult) -> dict[str, Any]:
    return {
        "category": result.category,
        "returncode": result.returncode,
        "elapsed_seconds": round(result.elapsed_seconds, 6),
        "stdout_sha256": result.stdout_sha256,
        "stderr_sha256": result.stderr_sha256,
    }


def run_native_preflight(
    *,
    codex_executable: Path | str,
    probe_executable: Path | str,
    definition_path: Path | str,
    paths: isolation.CodexPaths,
    bindings: PreflightBindings,
    real_memory_marker: Path | str,
    expected_codex_sha256: str,
    protected_read_paths: Mapping[str, Path | str],
    external_candidates: Sequence[tuple[str, int]] = (("1.1.1.1", 443), ("8.8.8.8", 53)),
    runtime_roots: Sequence[Path | str] = (),
) -> dict[str, Any]:
    """Run the real Codex 0.149.1 native preflight and return a bound receipt."""

    normalized = paths.normalized()
    bound = bindings.normalized()
    codex = Path(codex_executable).expanduser().resolve(strict=True)
    probe = Path(probe_executable).expanduser().resolve(strict=True)
    definition = Path(definition_path).expanduser().resolve(strict=True)
    memory_marker = Path(real_memory_marker).expanduser().resolve(strict=True)
    if not memory_marker.is_file() or not _within(memory_marker, normalized.memory_root):
        raise PreflightError("real memory marker must be a file under memory_root")
    protected_reads = _protected_read_files(
        protected_read_paths, normalized.candidate_root
    )
    expected_binary = _sha(expected_codex_sha256, "expected_codex_sha256")
    _validate_definition(definition, bound, expected_binary)
    if sha256_file(codex) != expected_binary:
        raise PreflightError("pinned Codex binary hash mismatch")

    if normalized.tmpdir.exists() or normalized.tmpdir.is_symlink():
        raise PreflightError("native preflight requires a fresh candidate temp directory")
    for directory in (
        normalized.candidate_root,
        normalized.controller_root,
        normalized.home,
        normalized.codex_home,
        normalized.codex_sqlite_home,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    normalized.tmpdir.mkdir(parents=True)
    if normalized.auth_target.exists() and not normalized.auth_target.is_file():
        raise PreflightError("auth target must be a readable file")
    if not normalized.auth_target.exists():
        normalized.auth_target.write_text("preflight-auth-marker\n", encoding="utf-8")
    auth_link = normalized.codex_home / "auth.json"
    if auth_link.exists() or auth_link.is_symlink():
        auth_link.unlink()
    auth_link.symlink_to(normalized.auth_target)

    markers = {
        "allowed_read": normalized.tmpdir / "allowed-read.marker",
        "allowed_write": normalized.tmpdir / "allowed-write.marker",
        "undeclared_write": normalized.candidate_root / ".routing-denied-write.marker",
        "codex": normalized.codex_home / "preflight.marker",
        "controller": normalized.controller_root / "preflight.marker",
    }
    for marker in markers.values():
        marker.write_text("routing-v3-preflight-marker\n", encoding="utf-8")
    escape = normalized.tmpdir / "controller-escape.marker"
    escape.unlink(missing_ok=True)
    escape.symlink_to(markers["controller"])

    run_marker = "routingv3-" + uuid.uuid4().hex
    config_path, config_hash = isolation.write_permission_profile(
        normalized,
        child_environment={"ROUTING_RUN_MARKER": run_marker},
        writable_paths=(".runner-tmp",),
        runtime_roots=(*runtime_roots, probe, COMMAND_LINE_TOOLS_ROOT),
    )
    environment = isolation.build_clean_environment(normalized)
    secret_name = "ROUTING_PREFLIGHT_SECRET"
    launch_environment = dict(environment)
    launch_environment[secret_name] = "presence-only-marker"
    launch_environment["ROUTING_RUN_MARKER"] = run_marker
    version = _version(codex, environment, normalized.candidate_root)
    prompt_input = _debug_prompt_input(codex, environment, normalized.candidate_root)
    external_host, external_port = _external_target(external_candidates)

    results: dict[str, Any] = {}
    breakaway: dict[str, Any] = {}
    socket_path: Path | None = None
    try:
        with ExitStack() as stack:
            if not SHORT_SOCKET_PARENT.is_dir():
                raise PreflightError("short Unix socket parent is unavailable")
            socket_directory = Path(
                stack.enter_context(
                    tempfile.TemporaryDirectory(
                        prefix="routing-v3-socket-", dir=SHORT_SOCKET_PARENT
                    )
                )
            )
            socket_path = socket_directory / "probe.sock"
            if len(os.fsencode(socket_path)) >= 104:
                raise PreflightError("synthetic Unix socket path exceeds the macOS limit")
            tcp_server = stack.enter_context(_TcpServer())
            stack.enter_context(_UnixServer(socket_path))
            loopback_host, loopback_port = tcp_server.endpoint
            operations = (
                Operation("allowed_candidate_read", ("read", str(markers["allowed_read"])), "success"),
                Operation("allowed_candidate_write", ("write", str(markers["allowed_write"])), "success"),
                Operation("denied_undeclared_write", ("write", str(markers["undeclared_write"])), "policy_denied"),
                Operation("denied_codex_home_marker", ("read", str(markers["codex"])), "policy_denied"),
                Operation("denied_auth_link", ("read", str(auth_link)), "policy_denied"),
                Operation("denied_auth_target", ("read", str(normalized.auth_target)), "policy_denied"),
                Operation("denied_controller_marker", ("read", str(markers["controller"])), "policy_denied"),
                Operation("denied_real_memory", ("read", str(memory_marker)), "policy_denied"),
                *(
                    Operation(
                        f"denied_protected_read_{name}",
                        ("read", str(path)),
                        "policy_denied",
                    )
                    for name, path in protected_reads.items()
                ),
                Operation("denied_external_tcp", ("tcp", external_host, str(external_port)), "policy_denied"),
                Operation("denied_live_loopback", ("tcp", loopback_host, str(loopback_port)), "policy_denied"),
                Operation("denied_live_unix_socket", ("unix", str(socket_path)), "policy_denied"),
                Operation("denied_symlink_escape", ("read", str(escape)), "policy_denied"),
                Operation(
                    "environment_not_leaked",
                    ("env-absent", secret_name),
                    "success",
                    positive_arguments=("env-present", secret_name),
                ),
            )
            for operation in operations:
                control_arguments = operation.positive_arguments or operation.arguments
                control = run_probe_command(
                    [str(probe), *control_arguments],
                    environment=launch_environment,
                    cwd=normalized.candidate_root,
                    timeout_seconds=operation.timeout_seconds,
                )
                sandboxed = run_probe_command(
                    sandbox_command(codex, normalized, probe, operation.arguments),
                    environment=launch_environment,
                    cwd=normalized.candidate_root,
                    timeout_seconds=operation.timeout_seconds,
                )
                results[operation.name] = {
                    "positive_control": _record(control),
                    "sandboxed": _record(sandboxed),
                    "expected_category": operation.expected_category,
                    "passed": control.category == "success" and sandboxed.category == operation.expected_category,
                }

            breakaway_environment = dict(launch_environment)
            timed = run_probe_command(
                sandbox_command(codex, normalized, probe, ("breakaway",)),
                environment=breakaway_environment,
                cwd=normalized.candidate_root,
                timeout_seconds=0.75,
            )
            survivors = _marker_pids(run_marker)
            _kill_pids(survivors)
            time.sleep(0.1)
            remaining = _marker_pids(run_marker)
            _kill_pids(remaining)
            breakaway = {
                "sandboxed": _record(timed),
                "detected_count": len(survivors),
                "remaining_count": len(remaining),
                "passed": timed.category == "timeout" and bool(survivors) and not remaining,
            }
    finally:
        escape.unlink(missing_ok=True)
        markers["allowed_read"].unlink(missing_ok=True)
        markers["allowed_write"].unlink(missing_ok=True)
        markers["undeclared_write"].unlink(missing_ok=True)
        normalized.tmpdir.rmdir()
    if socket_path is None:
        raise PreflightError("synthetic Unix socket probe did not initialize")

    definition_hash = sha256_file(definition)
    passed = all(item["passed"] for item in results.values()) and breakaway.get("passed") is True
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "status": "PASS" if passed else "FAIL",
        "no_model_calls": True,
        "codex": {
            "path": str(codex),
            "version": version,
            "sha256": sha256_file(codex),
        },
        "config": {
            "path": str(config_path),
            "sha256": config_hash,
            "permission_profile": isolation.PROFILE_CANDIDATE,
        },
        "definition_sha256": definition_hash,
        "package_sha256": bound.package_sha256,
        "fixture_sha256": dict(bound.fixture_sha256),
        "protected_reads": {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "operation": f"denied_protected_read_{name}",
            }
            for name, path in protected_reads.items()
        },
        "prompt_input": prompt_input,
        "external_target": {"host": external_host, "port": external_port, "positive_control": "success"},
        "unix_socket_target": {
            "path": str(socket_path),
            "positive_control": "success",
        },
        "operations": results,
        "breakaway": breakaway,
    }
    receipt["receipt_sha256"] = receipt_sha256(receipt)
    return receipt


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise PreflightError(f"{field} must be a nonempty identifier")
    return value


def _sha(value: str, field: str) -> str:
    if not isinstance(value, str) or len(value) != HEX_LENGTH:
        raise PreflightError(f"{field} must be a SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise PreflightError(f"{field} must be a SHA-256") from exc
    return value.lower()
