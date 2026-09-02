#!/usr/bin/env python3
"""Trusted subprocess wrapper for one split hidden-verifier invocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE_ROOT))

import split_verifier  # noqa: E402


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _load_config(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise split_verifier.ProtocolError("runner config is not valid JSON") from exc
    expected = {
        "binding",
        "deadline_monotonic",
        "driver_argv",
        "driver_cwd",
        "driver_environment",
        "output_paths",
        "worker_argv",
        "worker_cwd",
        "worker_environment",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise split_verifier.ProtocolError("runner config fields differ")
    if raw != _canonical_bytes(value):
        raise split_verifier.ProtocolError("runner config is not canonical JSON")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    arguments = parser.parse_args()
    value = _load_config(arguments.config.resolve(strict=True))
    deadline_monotonic = value["deadline_monotonic"]
    if (
        isinstance(deadline_monotonic, bool)
        or not isinstance(deadline_monotonic, (int, float))
        or deadline_monotonic <= time.monotonic()
    ):
        raise split_verifier.ProtocolError("runner deadline is invalid")
    binding = split_verifier.Binding.from_value(value["binding"])
    outputs = value["output_paths"]
    if not isinstance(outputs, dict) or set(outputs) != {
        "driver_stderr",
        "driver_stdout",
        "transcript",
        "worker_stderr",
        "worker_stdout",
    }:
        raise split_verifier.ProtocolError("runner output paths differ")
    receipt = split_verifier.run_split_verifier(
        value["driver_argv"],
        value["worker_argv"],
        driver_cwd=Path(value["driver_cwd"]).resolve(strict=True),
        worker_cwd=Path(value["worker_cwd"]).resolve(strict=True),
        driver_environment=value["driver_environment"],
        worker_environment=value["worker_environment"],
        binding=binding,
        deadline_monotonic=float(deadline_monotonic),
        transcript_path=Path(outputs["transcript"]),
        driver_stdout_path=Path(outputs["driver_stdout"]),
        driver_stderr_path=Path(outputs["driver_stderr"]),
        worker_stdout_path=Path(outputs["worker_stdout"]),
        worker_stderr_path=Path(outputs["worker_stderr"]),
    )
    sys.stdout.buffer.write(_canonical_bytes(receipt.as_dict()))
    return 0 if receipt.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
