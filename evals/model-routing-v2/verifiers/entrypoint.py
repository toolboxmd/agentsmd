#!/usr/bin/env python3
"""Bind the container-visible workspace manifest before running a verifier."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import runpy
import shutil
import stat
import sys
import tempfile
from typing import Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
VERIFIER_ROOT = PACKAGE_ROOT / "verifiers"
sys.path.insert(0, str(PACKAGE_ROOT))
from tree_manifest import TreeManifestError, build_tree_manifest  # noqa: E402


def _verifier_path(relative: str) -> Path:
    candidate = (PACKAGE_ROOT / relative).resolve()
    try:
        candidate.relative_to(VERIFIER_ROOT)
    except ValueError as error:
        raise ValueError("verifier path escapes the trusted verifier directory") from error
    if not candidate.is_file():
        raise ValueError("trusted verifier is unavailable")
    return candidate


def _run_verifier(verifier: Path, arguments: Sequence[str]) -> int:
    previous = sys.argv
    sys.argv = [str(verifier), *arguments]
    try:
        try:
            runpy.run_path(str(verifier), run_name="__main__")
        except SystemExit as exit_signal:
            if exit_signal.code is None:
                return 0
            if isinstance(exit_signal.code, int):
                return exit_signal.code
            print(str(exit_signal.code), file=sys.stderr)
            return 1
        return 0
    finally:
        sys.argv = previous


def _copy_regular_no_follow(source: str, destination: str) -> str:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    source_fd = os.open(source, flags)
    destination_fd: int | None = None
    try:
        before = os.fstat(source_fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError("snapshot source is not a single-link regular file")
        destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        destination_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        destination_fd = os.open(destination, destination_flags, 0o600)
        while True:
            chunk = os.read(source_fd, 1024 * 1024)
            if not chunk:
                break
            view = memoryview(chunk)
            while view:
                written = os.write(destination_fd, view)
                if written <= 0:
                    raise OSError("short write while creating verifier snapshot")
                view = view[written:]
        after = os.fstat(source_fd)
        stable = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if not stable:
            raise ValueError("snapshot source changed while copied")
        os.fchmod(destination_fd, stat.S_IMODE(before.st_mode) & 0o777)
    finally:
        if destination_fd is not None:
            os.close(destination_fd)
        os.close(source_fd)
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--verifier", required=True)
    parser.add_argument("--task")
    args = parser.parse_args(argv)

    if re.fullmatch(r"[0-9a-f]{64}", args.expected_manifest_sha256) is None:
        print("ERROR: expected workspace manifest is not a SHA-256", file=sys.stderr)
        return 2
    try:
        verifier = _verifier_path(args.verifier)
        with tempfile.TemporaryDirectory(prefix="routing-verifier-snapshot-") as raw:
            snapshot = Path(raw) / args.workspace.name
            shutil.copytree(
                args.workspace,
                snapshot,
                symlinks=True,
                copy_function=_copy_regular_no_follow,
            )
            observed = build_tree_manifest(snapshot)
            if observed["sha256"] != args.expected_manifest_sha256:
                print(
                    "ERROR: container workspace snapshot differs from expected evidence",
                    file=sys.stderr,
                )
                return 2
            verifier_arguments = ["--workspace", str(snapshot)]
            if args.task is not None:
                verifier_arguments.extend(["--task", args.task])
            return _run_verifier(verifier, verifier_arguments)
    except (OSError, shutil.Error, TreeManifestError, ValueError) as error:
        print(f"ERROR: cannot bind verifier workspace: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
