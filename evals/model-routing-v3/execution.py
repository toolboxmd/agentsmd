"""Coalition-bound process execution for routing benchmark v3."""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from coalition import CoalitionError, CoalitionIds, CoalitionMember, MacOSCoalitionInspector


MAX_PROMPT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_CONTROL_OUTPUT_BYTES = 256 * 1024
MAX_OBSERVED_EXECUTABLES = 2048
LAUNCHCTL = Path("/bin/launchctl")
RUNNER = Path(__file__).resolve().with_name("launchd_stage_runner.py")
KNOWN_INDEPENDENT_BROKERS = frozenset(
    {"/bin/launchctl", "/usr/bin/open", "/usr/bin/osascript"}
)
CONTAINMENT_SCOPE = (
    "same-user launchd coalition containment; intentional same-user service "
    "broker escape is outside the threat model and only known broker paths "
    "are observed on a best-effort polling basis"
)


class ExecutionError(RuntimeError):
    """The controller could not execute or bind a process safely."""


@dataclass(frozen=True)
class ProcessReceipt:
    argv: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    started_at: str
    finished_at: str
    duration_seconds: float
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str
    survivor_pids: tuple[int, ...]
    service_label: str
    service_domain: str
    runner_pid: int
    target_pid: int | None
    resource_coalition_id: int
    jetsam_coalition_id: int
    coalition_binding_verified: bool
    bootout_returncode: int
    terminated_member_pids: tuple[int, ...]
    terminal_member_pids: tuple[int, ...]
    service_registration_absent: bool
    resource_coalition_reaped: bool
    jetsam_coalition_absent: bool
    terminal_process_state: bool
    marker_identity_used: bool
    observed_executable_paths: tuple[str, ...]
    broker_usage_observed: bool
    broker_executables: tuple[str, ...]
    launch_observation_complete: bool
    runner_handshake_sha256: str
    runner_result_sha256: str | None
    containment_scope: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _TeardownReceipt:
    bootout_returncode: int
    terminated_member_pids: tuple[int, ...]
    terminal_member_pids: tuple[int, ...]
    service_registration_absent: bool
    resource_coalition_reaped: bool
    jetsam_coalition_absent: bool
    terminal_process_state: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def run_bounded_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdin_bytes: bytes,
    stdout_path: Path,
    stderr_path: Path,
    deadline_monotonic: float,
    run_marker: str,
    grace_seconds: float = 1.0,
) -> ProcessReceipt:
    """Run one process in a unique transient launchd coalition.

    ``run_marker`` remains in the call signature for receipt compatibility but
    is never used for process identity, discovery, or cleanup.  The target may
    clear its environment, call setsid, fork repeatedly, or ignore SIGTERM
    without leaving the kernel coalition used as the terminal identity.
    """

    normalized_argv = _validate_inputs(
        argv=argv,
        cwd=cwd,
        environment=environment,
        stdin_bytes=stdin_bytes,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        deadline_monotonic=deadline_monotonic,
    )
    del run_marker
    try:
        inspector = MacOSCoalitionInspector()
    except CoalitionError as exc:
        raise ExecutionError(str(exc)) from exc

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_hex(24)
    label = f"com.toolboxmd.routing-v3.{nonce}"
    domain = f"gui/{os.getuid()}"
    service_target = f"{domain}/{label}"
    control_root = stdout_path.parent / f".launchd-stage-{nonce}"
    control_root.mkdir(mode=0o700)
    stdin_path = control_root / "stdin.bin"
    config_path = control_root / "config.json"
    plist_path = control_root / "service.plist"
    ready_path = control_root / "ready.json"
    release_path = control_root / "release.json"
    result_path = control_root / "result.json"
    try:
        config_hash = _prepare_launch_files(
            stdin_path=stdin_path,
            config_path=config_path,
            plist_path=plist_path,
            stdin_bytes=stdin_bytes,
            nonce=nonce,
            argv=normalized_argv,
            cwd=cwd,
            environment=environment,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            ready_path=ready_path,
            release_path=release_path,
            result_path=result_path,
            deadline_monotonic=deadline_monotonic,
            label=label,
        )
    except BaseException:
        shutil.rmtree(control_root)
        raise

    started_at = utc_now()
    started = time.monotonic()
    registered = False
    bootstrap_attempted = False
    runner_pid: int | None = None
    coalition_ids: CoalitionIds | None = None
    target_pid: int | None = None
    returncode: int | None = None
    timed_out = False
    runner_handshake_hash: str | None = None
    runner_result_hash: str | None = None
    observed_paths: set[str] = {normalized_argv[0]}
    broker_paths: set[str] = (
        {normalized_argv[0]}
        if normalized_argv[0] in KNOWN_INDEPENDENT_BROKERS
        else set()
    )
    survivor_pids: set[int] = set()
    monitor_error: ExecutionError | None = None
    teardown: _TeardownReceipt | None = None
    try:
        bootstrap_attempted = True
        bootstrap = _launchctl(
            ("bootstrap", domain, str(plist_path)),
            deadline_monotonic=deadline_monotonic,
        )
        if bootstrap.returncode != 0:
            raise ExecutionError(
                "launchctl bootstrap failed: " + _control_failure(bootstrap)
            )
        registered = True
        kickstart = _launchctl(
            ("kickstart", "-p", service_target),
            deadline_monotonic=deadline_monotonic,
        )
        if kickstart.returncode != 0:
            raise ExecutionError(
                "launchctl kickstart failed: " + _control_failure(kickstart)
            )
        runner_pid = _parse_pid(kickstart.stdout)
        ready = _wait_for_json(
            ready_path,
            deadline_monotonic=deadline_monotonic,
            alternate=result_path,
        )
        _require_exact_keys(
            ready,
            {
                "schema_version",
                "nonce",
                "pid",
                "config_sha256",
                "stdout_device",
                "stdout_inode",
                "stderr_device",
                "stderr_inode",
            },
            "ready",
        )
        if (
            ready.get("schema_version") != 1
            or ready.get("nonce") != nonce
            or ready.get("pid") != runner_pid
            or ready.get("config_sha256") != config_hash
            or not all(
                isinstance(ready.get(name), int) and ready[name] > 0
                for name in (
                    "stdout_device",
                    "stdout_inode",
                    "stderr_device",
                    "stderr_inode",
                )
            )
        ):
            raise ExecutionError("launchd runner handshake binding differs from config")
        runner_handshake_hash = _sha256_file(ready_path)
        first_binding = inspector.coalition_for_pid(runner_pid)
        second_binding = inspector.coalition_for_pid(runner_pid)
        if first_binding is None or first_binding != second_binding:
            raise ExecutionError("launchd runner coalition binding was not stable")
        coalition_ids = first_binding
        controller_ids = inspector.coalition_for_pid(os.getpid())
        if (
            coalition_ids.resource <= 0
            or coalition_ids.jetsam <= 0
            or controller_ids is None
            or coalition_ids.resource == controller_ids.resource
            or coalition_ids.jetsam == controller_ids.jetsam
        ):
            raise ExecutionError("launchd did not create a distinct coalition pair")
        _write_json_exclusive(
            release_path,
            {
                "schema_version": 1,
                "nonce": nonce,
                "resource_coalition_id": coalition_ids.resource,
                "jetsam_coalition_id": coalition_ids.jetsam,
            },
        )

        next_observation = 0.0
        while not result_path.exists():
            if time.monotonic() >= deadline_monotonic:
                timed_out = True
                break
            if time.monotonic() >= next_observation:
                _observe_process_launches(
                    inspector,
                    coalition_ids,
                    observed_paths=observed_paths,
                    broker_paths=broker_paths,
                )
                next_observation = time.monotonic() + 0.1
            time.sleep(min(0.01, max(0.0, deadline_monotonic - time.monotonic())))
        if result_path.exists():
            result = _read_json_file(result_path)
            _require_exact_keys(
                result,
                {
                    "schema_version",
                    "nonce",
                    "target_pid",
                    "returncode",
                    "runner_error",
                    "resource_coalition_id",
                    "jetsam_coalition_id",
                },
                "result",
            )
            if (
                result.get("schema_version") != 1
                or result.get("nonce") != nonce
                or result.get("resource_coalition_id") != coalition_ids.resource
                or result.get("jetsam_coalition_id") != coalition_ids.jetsam
                or result.get("runner_error") is not None
                or not isinstance(result.get("target_pid"), int)
                or result["target_pid"] <= 0
                or not isinstance(result.get("returncode"), int)
            ):
                raise ExecutionError("launchd runner result binding is invalid")
            target_pid = int(result["target_pid"])
            returncode = int(result["returncode"])
            runner_result_hash = _sha256_file(result_path)

        _observe_process_launches(
            inspector,
            coalition_ids,
            observed_paths=observed_paths,
            broker_paths=broker_paths,
        )
        for member in inspector.matching_members(coalition_ids):
            if member.pid not in {runner_pid, target_pid}:
                survivor_pids.add(member.pid)
    except (CoalitionError, OSError, ValueError) as exc:
        monitor_error = ExecutionError(f"coalition-bound execution failed: {exc}")
    except ExecutionError as exc:
        monitor_error = exc
    finally:
        if registered:
            if coalition_ids is None:
                bootout = _launchctl_cleanup(("bootout", service_target))
                if bootout.returncode != 0:
                    bootout_error = ExecutionError(
                        "launchctl bootout failed before coalition binding: "
                        + _control_failure(bootout)
                    )
                    monitor_error = (
                        bootout_error
                        if monitor_error is None
                        else ExecutionError(f"{monitor_error}; {bootout_error}")
                    )
                if _launchctl_cleanup(("print", service_target)).returncode == 0:
                    leftover = ExecutionError(
                        "launchd service remained registered before coalition binding"
                    )
                    monitor_error = (
                        leftover
                        if monitor_error is None
                        else ExecutionError(f"{monitor_error}; {leftover}")
                    )
            else:
                try:
                    teardown = _teardown_coalition(
                        inspector,
                        service_target=service_target,
                        expected=coalition_ids,
                        grace_seconds=grace_seconds,
                    )
                except (CoalitionError, ExecutionError, OSError) as exc:
                    if monitor_error is None:
                        monitor_error = ExecutionError(
                            f"coalition terminal proof failed: {exc}"
                        )
                    else:
                        monitor_error = ExecutionError(
                            f"{monitor_error}; coalition terminal proof also failed: {exc}"
                        )
        elif bootstrap_attempted:
            _launchctl_cleanup(("bootout", service_target))
            if _launchctl_cleanup(("print", service_target)).returncode == 0:
                leftover = ExecutionError(
                    "launchd service remained registered after failed bootstrap"
                )
                monitor_error = leftover if monitor_error is None else ExecutionError(
                    f"{monitor_error}; {leftover}"
                )
        try:
            shutil.rmtree(control_root)
        except OSError as exc:
            cleanup_error = ExecutionError(f"cannot remove launch control directory: {exc}")
            monitor_error = cleanup_error if monitor_error is None else ExecutionError(
                f"{monitor_error}; {cleanup_error}"
            )

    if teardown is not None and not teardown.terminal_process_state:
        failure = ExecutionError(
            "coalition terminal state is unproved: "
            f"bootout={teardown.bootout_returncode} "
            f"members={teardown.terminal_member_pids} "
            f"service_absent={teardown.service_registration_absent} "
            f"resource_reaped={teardown.resource_coalition_reaped} "
            f"jetsam_absent={teardown.jetsam_coalition_absent}"
        )
        monitor_error = failure if monitor_error is None else ExecutionError(
            f"{monitor_error}; {failure}"
        )
    if monitor_error is not None:
        raise monitor_error
    if (
        runner_pid is None
        or coalition_ids is None
        or runner_handshake_hash is None
        or teardown is None
    ):
        raise ExecutionError("coalition execution ended without a complete receipt")
    _require_bound_output(
        stdout_path,
        expected_device=int(ready["stdout_device"]),
        expected_inode=int(ready["stdout_inode"]),
    )
    _require_bound_output(
        stderr_path,
        expected_device=int(ready["stderr_device"]),
        expected_inode=int(ready["stderr_inode"]),
    )
    if stdout_path.stat().st_size > MAX_OUTPUT_BYTES or stderr_path.stat().st_size > MAX_OUTPUT_BYTES:
        raise ExecutionError("stage output exceeded its fixed byte bound")

    finished = time.monotonic()
    return ProcessReceipt(
        argv=normalized_argv,
        returncode=returncode,
        timed_out=timed_out,
        started_at=started_at,
        finished_at=utc_now(),
        duration_seconds=finished - started,
        stdout_bytes=stdout_path.stat().st_size,
        stderr_bytes=stderr_path.stat().st_size,
        stdout_sha256=_sha256_file(stdout_path),
        stderr_sha256=_sha256_file(stderr_path),
        survivor_pids=tuple(sorted(survivor_pids)),
        service_label=label,
        service_domain=domain,
        runner_pid=runner_pid,
        target_pid=target_pid,
        resource_coalition_id=coalition_ids.resource,
        jetsam_coalition_id=coalition_ids.jetsam,
        coalition_binding_verified=True,
        bootout_returncode=teardown.bootout_returncode,
        terminated_member_pids=teardown.terminated_member_pids,
        terminal_member_pids=teardown.terminal_member_pids,
        service_registration_absent=teardown.service_registration_absent,
        resource_coalition_reaped=teardown.resource_coalition_reaped,
        jetsam_coalition_absent=teardown.jetsam_coalition_absent,
        terminal_process_state=teardown.terminal_process_state,
        marker_identity_used=False,
        observed_executable_paths=tuple(sorted(observed_paths)),
        broker_usage_observed=bool(broker_paths),
        broker_executables=tuple(sorted(broker_paths)),
        launch_observation_complete=True,
        runner_handshake_sha256=runner_handshake_hash,
        runner_result_sha256=runner_result_hash,
        containment_scope=CONTAINMENT_SCOPE,
    )


def _validate_inputs(
    *,
    argv: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdin_bytes: bytes,
    stdout_path: Path,
    stderr_path: Path,
    deadline_monotonic: float,
) -> tuple[str, ...]:
    normalized = tuple(str(item) for item in argv)
    if (
        not normalized
        or not Path(normalized[0]).is_absolute()
        or any(not item or "\0" in item for item in normalized)
    ):
        raise ExecutionError("executable and argv must be nonempty absolute-safe values")
    if not cwd.is_absolute() or not cwd.is_dir():
        raise ExecutionError("working directory must be an existing absolute directory")
    if len(stdin_bytes) > MAX_PROMPT_BYTES:
        raise ExecutionError("stdin exceeds the benchmark prompt bound")
    if not stdout_path.is_absolute() or not stderr_path.is_absolute():
        raise ExecutionError("output paths must be absolute")
    if stdout_path == stderr_path or stdout_path.exists() or stderr_path.exists():
        raise ExecutionError("output paths must be distinct and absent")
    for name, value in environment.items():
        if (
            not isinstance(name, str)
            or not name
            or "=" in name
            or "\0" in name
            or not isinstance(value, str)
            or "\0" in value
        ):
            raise ExecutionError("environment contains an invalid entry")
    if time.monotonic() >= deadline_monotonic:
        raise ExecutionError("shared deadline elapsed before process start")
    if not LAUNCHCTL.is_file() or not RUNNER.is_file() or not Path(sys.executable).is_absolute():
        raise ExecutionError("pinned launchd execution prerequisites are unavailable")
    return normalized


def _prepare_launch_files(
    *,
    stdin_path: Path,
    config_path: Path,
    plist_path: Path,
    stdin_bytes: bytes,
    nonce: str,
    argv: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    ready_path: Path,
    release_path: Path,
    result_path: Path,
    deadline_monotonic: float,
    label: str,
) -> str:
    _write_exclusive(stdin_path, stdin_bytes)
    config = {
        "schema_version": 1,
        "nonce": nonce,
        "argv": list(argv),
        "cwd": str(cwd),
        "environment": dict(environment),
        "stdin_path": str(stdin_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "ready_path": str(ready_path),
        "release_path": str(release_path),
        "result_path": str(result_path),
        "deadline_monotonic": deadline_monotonic,
    }
    payload = _canonical_json(config)
    if len(payload) > 4 * 1024 * 1024:
        raise ExecutionError("launchd runner config exceeds its fixed byte bound")
    _write_exclusive(config_path, payload)
    config_hash = hashlib.sha256(payload).hexdigest()
    _write_plist_exclusive(
        plist_path,
        {
            "Label": label,
            "ProgramArguments": [sys.executable, str(RUNNER), str(config_path)],
            "WorkingDirectory": str(cwd),
            "EnvironmentVariables": {
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            "RunAtLoad": False,
            "KeepAlive": False,
            "AbandonProcessGroup": False,
            "ExitTimeOut": 1,
            "ThrottleInterval": 1,
            "StandardOutPath": "/dev/null",
            "StandardErrorPath": "/dev/null",
        },
    )
    return config_hash


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        written = 0
        while written < len(payload):
            written += os.write(descriptor, payload[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _write_json_exclusive(path: Path, value: Mapping[str, object]) -> str:
    payload = _canonical_json(value)
    _write_exclusive(path, payload)
    return hashlib.sha256(payload).hexdigest()


def _write_plist_exclusive(path: Path, value: Mapping[str, object]) -> None:
    payload = plistlib.dumps(dict(value), fmt=plistlib.FMT_XML, sort_keys=True)
    _write_exclusive(path, payload)


def _remaining_timeout(deadline_monotonic: float) -> float:
    remaining = deadline_monotonic - time.monotonic()
    if remaining <= 0:
        raise ExecutionError("shared deadline elapsed during launchd control")
    return max(0.001, remaining)


def _launchctl(
    arguments: Sequence[str], *, deadline_monotonic: float
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [str(LAUNCHCTL), *arguments],
            cwd="/",
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=_remaining_timeout(deadline_monotonic),
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionError("launchctl exceeded the shared deadline") from exc


def _launchctl_cleanup(arguments: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            [str(LAUNCHCTL), *arguments],
            cwd="/",
            env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5.0,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            [str(LAUNCHCTL), *arguments], 124, b"", b"cleanup timeout"
        )


def _control_failure(result: subprocess.CompletedProcess[bytes]) -> str:
    stdout = result.stdout[:MAX_CONTROL_OUTPUT_BYTES].decode("utf-8", "replace").strip()
    stderr = result.stderr[:MAX_CONTROL_OUTPUT_BYTES].decode("utf-8", "replace").strip()
    return f"returncode={result.returncode} stdout={stdout!r} stderr={stderr!r}"


def _parse_pid(raw: bytes) -> int:
    if len(raw) > 64:
        raise ExecutionError("launchctl kickstart PID output exceeds its bound")
    try:
        value = int(raw.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ExecutionError("launchctl kickstart did not return one PID") from exc
    if value <= 0:
        raise ExecutionError("launchctl kickstart returned a nonpositive PID")
    return value


def _wait_for_json(
    path: Path, *, deadline_monotonic: float, alternate: Path | None = None
) -> Mapping[str, object]:
    while time.monotonic() < deadline_monotonic:
        if path.exists():
            return _read_json_file(path)
        if alternate is not None and alternate.exists():
            raise ExecutionError("launchd runner exited before publishing readiness")
        time.sleep(min(0.005, max(0.0, deadline_monotonic - time.monotonic())))
    raise ExecutionError("shared deadline elapsed before launchd runner readiness")


def _read_json_file(path: Path) -> Mapping[str, object]:
    raw = path.read_bytes()
    if len(raw) > 64 * 1024:
        raise ExecutionError(f"runner control file exceeds its bound: {path.name}")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutionError(f"runner control file is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise ExecutionError(f"runner control file is not an object: {path.name}")
    return value


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], description: str
) -> None:
    if set(value) != expected:
        raise ExecutionError(f"launchd runner {description} fields differ from schema 1")


def _observe_process_launches(
    inspector: MacOSCoalitionInspector,
    expected: CoalitionIds,
    *,
    observed_paths: set[str],
    broker_paths: set[str],
) -> None:
    for member in inspector.matching_members(expected):
        path = inspector.executable_path(member.pid, allow_missing=True)
        if path is None:
            continue
        observed_paths.add(path)
        if len(observed_paths) > MAX_OBSERVED_EXECUTABLES:
            raise ExecutionError("process launch observation exceeded its fixed bound")
        if path in KNOWN_INDEPENDENT_BROKERS:
            broker_paths.add(path)


def _signal_if_still_owned(
    inspector: MacOSCoalitionInspector,
    member: CoalitionMember,
    expected: CoalitionIds,
    signal_number: int,
) -> bool:
    current = inspector.coalition_for_pid(member.pid, allow_missing=True)
    if current is None:
        return False
    if current.resource != expected.resource and current.jetsam != expected.jetsam:
        return False
    try:
        os.kill(member.pid, signal_number)
    except ProcessLookupError:
        return False
    return True


def _teardown_coalition(
    inspector: MacOSCoalitionInspector,
    *,
    service_target: str,
    expected: CoalitionIds,
    grace_seconds: float,
) -> _TeardownReceipt:
    bootout = _launchctl_cleanup(("bootout", service_target))
    cleanup_deadline = time.monotonic() + max(1.0, grace_seconds)
    terminated: set[int] = set()
    members: tuple[CoalitionMember, ...] = ()
    resource_reaped = False
    jetsam_absent = False
    while time.monotonic() < cleanup_deadline:
        members = inspector.matching_members(expected)
        for member in members:
            if _signal_if_still_owned(inspector, member, expected, signal.SIGSTOP):
                terminated.add(member.pid)
        for member in members:
            if _signal_if_still_owned(inspector, member, expected, signal.SIGKILL):
                terminated.add(member.pid)
        resource_reaped = inspector.resource_coalition_reaped(expected.resource)
        jetsam_absent = inspector.jetsam_coalition_absent(expected.jetsam)
        if not members and resource_reaped and jetsam_absent:
            break
        time.sleep(0.01)
    terminal_members = inspector.matching_members(expected)
    resource_reaped = inspector.resource_coalition_reaped(expected.resource)
    jetsam_absent = inspector.jetsam_coalition_absent(expected.jetsam)
    service_registration_absent = (
        _launchctl_cleanup(("print", service_target)).returncode != 0
    )
    terminal = (
        bootout.returncode == 0
        and not terminal_members
        and service_registration_absent
        and resource_reaped
        and jetsam_absent
    )
    return _TeardownReceipt(
        bootout_returncode=bootout.returncode,
        terminated_member_pids=tuple(sorted(terminated)),
        terminal_member_pids=tuple(member.pid for member in terminal_members),
        service_registration_absent=service_registration_absent,
        resource_coalition_reaped=resource_reaped,
        jetsam_coalition_absent=jetsam_absent,
        terminal_process_state=terminal,
    )


def _require_bound_output(
    path: Path, *, expected_device: int, expected_inode: int
) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ExecutionError(f"trusted runner output is unavailable: {path}") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_dev != expected_device
        or metadata.st_ino != expected_inode
    ):
        raise ExecutionError(f"trusted runner output identity changed: {path}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
