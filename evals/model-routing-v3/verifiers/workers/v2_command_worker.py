#!/usr/bin/env python3
"""Candidate-side command worker for the frozen v2 hidden verifier."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT))

from split_verifier import ProtocolEndpoint, ProtocolError  # noqa: E402


ALLOWED_EXECUTABLES = {"/bin/bash", "/usr/bin/python3"}
MAX_CAPTURE_BYTES = 4 * 1024 * 1024


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _run(
    payload: Any,
    *,
    roots: tuple[Path, ...],
    deadline_unix_ms: int,
    python_executable: Path,
    command_bin: Path,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "executable",
        "arguments",
        "cwd",
        "timeout_seconds",
    }:
        raise ProtocolError("run_command payload fields differ")
    executable = payload["executable"]
    arguments = payload["arguments"]
    cwd_value = payload["cwd"]
    timeout_seconds = payload["timeout_seconds"]
    if executable not in ALLOWED_EXECUTABLES:
        raise ProtocolError("run_command executable is not allowed")
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        raise ProtocolError("run_command arguments must be strings")
    if not isinstance(cwd_value, str):
        raise ProtocolError("run_command cwd must be a string")
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= 120
    ):
        raise ProtocolError("run_command timeout is outside the frozen verifier bound")
    cwd = Path(cwd_value).resolve(strict=True)
    if not cwd.is_dir() or not _inside(cwd, roots):
        raise ProtocolError("run_command cwd is outside the allowed roots")
    remaining = (deadline_unix_ms - int(time.time() * 1000)) / 1000
    if remaining <= 0:
        return {"returncode": None, "stdout": "", "stderr": "", "timed_out": True}
    runtime = Path(os.environ["HOME"]).resolve(strict=True)
    if not runtime.is_dir() or not _inside(runtime, roots):
        raise ProtocolError("worker runtime is outside the allowed roots")
    environment = {
        "PATH": f"{command_bin}:{python_executable.parent}:/usr/bin:/bin",
        "HOME": str(runtime),
        "TMPDIR": str(runtime),
        "LANG": "C",
        "LC_ALL": "C",
        "NO_COLOR": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    try:
        actual_executable = (
            str(python_executable)
            if executable == "/usr/bin/python3"
            else executable
        )
        completed = subprocess.run(
            [actual_executable, *arguments],
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            timeout=min(float(timeout_seconds), remaining),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "returncode": None,
            "stdout": stdout[-MAX_CAPTURE_BYTES:],
            "stderr": stderr[-MAX_CAPTURE_BYTES:],
            "timed_out": True,
        }
    if len(completed.stdout.encode("utf-8")) > MAX_CAPTURE_BYTES:
        raise ProtocolError("run_command stdout exceeds the capture bound")
    if len(completed.stderr.encode("utf-8")) > MAX_CAPTURE_BYTES:
        raise ProtocolError("run_command stderr exceeds the capture bound")
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowed-root", action="append", required=True, type=Path)
    parser.add_argument("--python-executable", required=True, type=Path)
    parser.add_argument("--command-bin", required=True, type=Path)
    arguments = parser.parse_args()
    roots = tuple(path.resolve(strict=True) for path in arguments.allowed_root)
    python_executable = arguments.python_executable.resolve(strict=True)
    if not python_executable.is_file():
        raise ProtocolError("pinned worker Python is not a regular file")
    command_bin = arguments.command_bin.resolve(strict=True)
    if not command_bin.is_dir():
        raise ProtocolError("worker command bin is not a real directory")
    endpoint = ProtocolEndpoint.from_environment(role="worker")
    while True:
        request = endpoint.read_request()
        if request is None:
            return 0
        try:
            if request["operation"] != "run_command":
                raise ProtocolError("v2 worker operation is not allowed")
            result = _run(
                request["payload"],
                roots=roots,
                deadline_unix_ms=endpoint.binding.deadline_unix_ms,
                python_executable=python_executable,
                command_bin=command_bin,
            )
            endpoint.respond(request["request_id"], result=result)
        except Exception as exc:
            endpoint.respond(
                request["request_id"],
                error=f"{type(exc).__name__}: {exc}",
            )


if __name__ == "__main__":
    raise SystemExit(main())
