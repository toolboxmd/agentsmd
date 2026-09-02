#!/usr/bin/env python3
"""Trusted driver for the exact frozen v2 hidden-verifier semantics."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE_ROOT))

from split_verifier import ProtocolEndpoint, ProtocolError  # noqa: E402


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_frozen_hidden(path: Path, expected_sha256: str) -> ModuleType:
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or resolved.is_symlink():
        raise ProtocolError("frozen hidden verifier must be a regular file")
    if _sha256_file(resolved) != expected_sha256:
        raise ProtocolError("frozen hidden verifier hash differs")
    spec = importlib.util.spec_from_file_location("routing_v2_frozen_hidden", resolved)
    if spec is None or spec.loader is None:
        raise ProtocolError("cannot load the frozen hidden verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _failure(task: str, exc: Exception) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": task,
        "status": "FAIL",
        "checks": [],
        "failures": [
            {
                "name": "verifier setup",
                "passed": False,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        ],
        "failed_count": 1,
        "timed_out_commands": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True, choices=("use-grok", "karpathy-pointer"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--frozen-hidden", required=True, type=Path)
    parser.add_argument("--expected-hidden-sha256", required=True)
    arguments = parser.parse_args()

    try:
        workspace = arguments.workspace.resolve(strict=True)
        if not workspace.is_dir():
            raise NotADirectoryError(workspace)
        endpoint = ProtocolEndpoint.from_environment(role="driver")
        if endpoint.binding.task != arguments.task:
            raise ProtocolError("driver task differs from the protocol binding")
        module = _load_frozen_hidden(
            arguments.frozen_hidden,
            arguments.expected_hidden_sha256,
        )

        def run_command(
            executable: str,
            command_arguments: Sequence[str],
            cwd: Path,
            timeout_seconds: int = 120,
        ) -> Any:
            value = endpoint.request(
                "run_command",
                {
                    "executable": executable,
                    "arguments": list(command_arguments),
                    "cwd": str(cwd.resolve(strict=True)),
                    "timeout_seconds": timeout_seconds,
                },
            )
            if not isinstance(value, dict) or set(value) != {
                "returncode",
                "stdout",
                "stderr",
                "timed_out",
            }:
                raise ProtocolError("v2 worker result fields differ")
            if value["returncode"] is not None and (
                not isinstance(value["returncode"], int)
                or isinstance(value["returncode"], bool)
            ):
                raise ProtocolError("v2 worker returncode is invalid")
            if not isinstance(value["stdout"], str) or not isinstance(value["stderr"], str):
                raise ProtocolError("v2 worker output is invalid")
            if not isinstance(value["timed_out"], bool):
                raise ProtocolError("v2 worker timeout flag is invalid")
            return module.CommandResult(
                value["returncode"],
                value["stdout"],
                value["stderr"],
                value["timed_out"],
            )

        # Preserve the exact frozen checks. Only their process executor crosses
        # into the candidate-side worker.
        module.run_command = run_command
        result = (
            module.verify_use_grok(workspace)
            if arguments.task == "use-grok"
            else module.verify_karpathy_pointer(workspace)
        )
    except Exception as exc:
        result = _failure(arguments.task, exc)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
