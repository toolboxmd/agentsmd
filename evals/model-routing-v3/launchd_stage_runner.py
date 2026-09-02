#!/usr/bin/env python3
"""Trusted launchd service wrapper for one benchmark stage.

The wrapper remains the launchd service leader, publishes its PID before any
candidate code runs, waits for the controller to bind both coalition IDs, and
then forks exactly one target process.  The target receives the exact supplied
environment through execve rather than inheriting launchd's environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import resource
import stat
import sys
import time
from pathlib import Path
from typing import Any, Mapping


MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_CONTROL_BYTES = 16 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


class RunnerError(RuntimeError):
    """The trusted stage runner rejected its controller input."""


def _read_exact_json(path: Path, *, maximum: int) -> Mapping[str, Any]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RunnerError(f"control path is not a regular file: {path}")
        raw = os.read(descriptor, maximum + 1)
        if len(raw) > maximum:
            raise RunnerError(f"control JSON exceeds its byte bound: {path}")
        if os.read(descriptor, 1):
            raise RunnerError(f"control JSON exceeds its byte bound: {path}")
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"control JSON is invalid: {path}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"control JSON is not an object: {path}")
    return value


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _publish_json(path: Path, value: Mapping[str, Any]) -> str:
    payload = _canonical_bytes(value)
    prepared = path.with_name(path.name + f".prepared-{os.getpid()}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(prepared, flags, 0o600)
    try:
        written = 0
        while written < len(payload):
            written += os.write(descriptor, payload[written:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(prepared, path)
    finally:
        prepared.unlink(missing_ok=True)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return hashlib.sha256(payload).hexdigest()


def _required_path(value: object, name: str) -> Path:
    if not isinstance(value, str) or not value or "\0" in value:
        raise RunnerError(f"{name} is invalid")
    path = Path(value)
    if not path.is_absolute():
        raise RunnerError(f"{name} must be absolute")
    return path


def _validate_config(value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "schema_version",
        "nonce",
        "argv",
        "cwd",
        "environment",
        "stdin_path",
        "stdout_path",
        "stderr_path",
        "ready_path",
        "release_path",
        "result_path",
        "deadline_monotonic",
    }
    if set(value) != expected or value.get("schema_version") != 1:
        raise RunnerError("runner config fields differ from schema 1")
    nonce = value.get("nonce")
    if (
        not isinstance(nonce, str)
        or len(nonce) < 32
        or not all(character in "0123456789abcdef" for character in nonce)
    ):
        raise RunnerError("runner nonce is invalid")
    argv = value.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item and "\0" not in item for item in argv)
        or not Path(argv[0]).is_absolute()
    ):
        raise RunnerError("runner argv is invalid")
    environment = value.get("environment")
    if not isinstance(environment, dict):
        raise RunnerError("runner environment is invalid")
    for name, item in environment.items():
        if (
            not isinstance(name, str)
            or not name
            or "=" in name
            or "\0" in name
            or not isinstance(item, str)
            or "\0" in item
        ):
            raise RunnerError("runner environment contains an invalid entry")
    deadline = value.get("deadline_monotonic")
    if not isinstance(deadline, (int, float)) or not deadline > 0:
        raise RunnerError("runner deadline is invalid")
    return {
        **value,
        "argv": list(argv),
        "environment": dict(environment),
        "deadline_monotonic": float(deadline),
        "cwd": _required_path(value.get("cwd"), "cwd"),
        "stdin_path": _required_path(value.get("stdin_path"), "stdin_path"),
        "stdout_path": _required_path(value.get("stdout_path"), "stdout_path"),
        "stderr_path": _required_path(value.get("stderr_path"), "stderr_path"),
        "ready_path": _required_path(value.get("ready_path"), "ready_path"),
        "release_path": _required_path(value.get("release_path"), "release_path"),
        "result_path": _required_path(value.get("result_path"), "result_path"),
    }


def _open_target_files(config: Mapping[str, Any]) -> tuple[int, int, int]:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    stdin_descriptor = os.open(config["stdin_path"], os.O_RDONLY | nofollow)
    try:
        output_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow
        stdout_descriptor = os.open(config["stdout_path"], output_flags, 0o600)
        try:
            stderr_descriptor = os.open(config["stderr_path"], output_flags, 0o600)
        except Exception:
            os.close(stdout_descriptor)
            raise
    except Exception:
        os.close(stdin_descriptor)
        raise
    return stdin_descriptor, stdout_descriptor, stderr_descriptor


def _apply_limits() -> None:
    _, file_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    file_soft = (
        MAX_OUTPUT_BYTES
        if file_hard == resource.RLIM_INFINITY
        else min(MAX_OUTPUT_BYTES, file_hard)
    )
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_soft, file_hard))
    _, nofile_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    nofile_soft = 256 if nofile_hard == resource.RLIM_INFINITY else min(256, nofile_hard)
    resource.setrlimit(resource.RLIMIT_NOFILE, (nofile_soft, nofile_hard))


def _wait_for_release(config: Mapping[str, Any]) -> Mapping[str, Any]:
    while time.monotonic() < config["deadline_monotonic"]:
        try:
            release = _read_exact_json(config["release_path"], maximum=MAX_CONTROL_BYTES)
        except FileNotFoundError:
            time.sleep(0.005)
            continue
        expected = {"schema_version", "nonce", "resource_coalition_id", "jetsam_coalition_id"}
        if set(release) != expected or release.get("schema_version") != 1:
            raise RunnerError("runner release fields differ from schema 1")
        if release.get("nonce") != config["nonce"]:
            raise RunnerError("runner release nonce does not match")
        if not all(
            isinstance(release.get(name), int) and release[name] > 0
            for name in ("resource_coalition_id", "jetsam_coalition_id")
        ):
            raise RunnerError("runner release coalition IDs are invalid")
        return release
    raise RunnerError("shared deadline elapsed before coalition release")


def _wait_status_returncode(status: int) -> int:
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    raise RunnerError("target wait status was neither exited nor signaled")


def run(config_path: Path) -> int:
    raw_config = _read_exact_json(config_path, maximum=MAX_CONFIG_BYTES)
    config = _validate_config(raw_config)
    config_payload = _canonical_bytes(raw_config)
    config_hash = hashlib.sha256(config_payload).hexdigest()
    _apply_limits()
    stdin_descriptor, stdout_descriptor, stderr_descriptor = _open_target_files(config)
    stdout_metadata = os.fstat(stdout_descriptor)
    stderr_metadata = os.fstat(stderr_descriptor)
    _publish_json(
        config["ready_path"],
        {
            "schema_version": 1,
            "nonce": config["nonce"],
            "pid": os.getpid(),
            "config_sha256": config_hash,
            "stdout_device": stdout_metadata.st_dev,
            "stdout_inode": stdout_metadata.st_ino,
            "stderr_device": stderr_metadata.st_dev,
            "stderr_inode": stderr_metadata.st_ino,
        },
    )
    try:
        release = _wait_for_release(config)
        child = os.fork()
        if child == 0:
            try:
                os.chdir(config["cwd"])
                os.dup2(stdin_descriptor, 0)
                os.dup2(stdout_descriptor, 1)
                os.dup2(stderr_descriptor, 2)
                for descriptor in (stdin_descriptor, stdout_descriptor, stderr_descriptor):
                    if descriptor > 2:
                        os.close(descriptor)
                os.execve(config["argv"][0], config["argv"], config["environment"])
            except BaseException:
                os._exit(127)
        for descriptor in (stdin_descriptor, stdout_descriptor, stderr_descriptor):
            os.close(descriptor)
        while True:
            try:
                _, status = os.waitpid(child, 0)
                break
            except InterruptedError:
                continue
        returncode = _wait_status_returncode(status)
        _publish_json(
            config["result_path"],
            {
                "schema_version": 1,
                "nonce": config["nonce"],
                "target_pid": child,
                "returncode": returncode,
                "runner_error": None,
                "resource_coalition_id": release["resource_coalition_id"],
                "jetsam_coalition_id": release["jetsam_coalition_id"],
            },
        )
        return 0
    except BaseException:
        for descriptor in (stdin_descriptor, stdout_descriptor, stderr_descriptor):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 64
    try:
        return run(Path(argv[1]))
    except BaseException:
        # Do not emit config, paths, environment, or exception text.  The
        # controller classifies an absent result as a trusted-runner failure.
        return 70


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
