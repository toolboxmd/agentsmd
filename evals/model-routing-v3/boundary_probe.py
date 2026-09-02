#!/usr/bin/python3
"""Tiny no-model process used to classify native sandbox operations.

The probe never prints file contents or environment values. A denied result is
reported only when the operating system returns EACCES or EPERM. The controller
therefore cannot mistake a missing path, refused connection, or probe defect
for a working policy boundary.
"""

from __future__ import annotations

import errno
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


EXIT_POLICY_DENIED = 77
POLICY_ERRNOS = frozenset({errno.EACCES, errno.EPERM})


def _emit(category: str, operation: str, **details: object) -> int:
    payload = {"category": category, "operation": operation, **details}
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if category == "success" else EXIT_POLICY_DENIED if category == "policy_denied" else 1


def _read(path: str) -> None:
    with Path(path).open("rb") as handle:
        handle.read(1)


def _write(path: str) -> None:
    target = Path(path)
    with target.open("ab") as handle:
        handle.write(b"p")
        handle.flush()


def _tcp(host: str, port: str) -> None:
    with socket.create_connection((host, int(port)), timeout=1.5):
        pass


def _unix(path: str) -> None:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(1.5)
    try:
        client.connect(path)
    finally:
        client.close()


def _env_present(names: list[str]) -> None:
    missing = [name for name in names if name not in os.environ]
    if missing:
        raise RuntimeError("expected environment names are absent: " + ",".join(missing))


def _env_absent(names: list[str]) -> None:
    present = [name for name in names if name in os.environ]
    if present:
        raise RuntimeError("environment names leaked: " + ",".join(present))


def _breakaway() -> None:
    marker = os.environ.get("ROUTING_RUN_MARKER")
    if not marker:
        raise RuntimeError("ROUTING_RUN_MARKER is required")
    code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)"
    subprocess.Popen(
        ["/usr/bin/python3", "-c", code],
        env=dict(os.environ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    while True:
        time.sleep(30)


def _coalition_breakaway() -> None:
    """Clear marker state and detach twice while ignoring graceful teardown."""

    first = os.fork()
    if first == 0:
        os.setsid()
        second = os.fork()
        if second > 0:
            os._exit(0)
        os.environ.clear()
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(30)
    os.waitpid(first, 0)


def _broker_observation() -> None:
    """Exercise a read-only known broker command long enough for observation."""

    domain = f"gui/{os.getuid()}"
    deadline = time.monotonic() + 0.4
    while time.monotonic() < deadline:
        subprocess.run(
            ["/bin/launchctl", "print-disabled", domain],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return _emit("error", "missing", error="operation is required")
    operation, arguments = argv[1], argv[2:]
    actions = {
        "read": lambda: _read(arguments[0]),
        "write": lambda: _write(arguments[0]),
        "tcp": lambda: _tcp(arguments[0], arguments[1]),
        "unix": lambda: _unix(arguments[0]),
        "env-present": lambda: _env_present(arguments),
        "env-absent": lambda: _env_absent(arguments),
        "breakaway": _breakaway,
        "coalition-breakaway": _coalition_breakaway,
        "broker-observation": _broker_observation,
    }
    action = actions.get(operation)
    if action is None:
        return _emit("error", operation, error="unknown operation")
    try:
        action()
    except OSError as exc:
        category = "policy_denied" if exc.errno in POLICY_ERRNOS else "error"
        return _emit(category, operation, errno=exc.errno, error=type(exc).__name__)
    except (IndexError, RuntimeError, ValueError) as exc:
        return _emit("error", operation, error=str(exc))
    return _emit("success", operation)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
