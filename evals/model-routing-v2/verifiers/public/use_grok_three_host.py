#!/usr/bin/env python3
"""Verify the public use-grok 0.2.0 three-host release contract."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Any


EXPECTED_PORTABLE = {
    "name": "use-grok",
    "version": "0.2.0",
    "description": (
        "Delegate research, coding, and reviews to the local Grok Build CLI."
    ),
    "repository": "https://github.com/toolboxmd/use-grok",
    "license": "Apache-2.0",
}
PORTABLE_KEYS = set(EXPECTED_PORTABLE) | {"author"}
CODEX_ONLY_KEYS = {"homepage", "interface", "keywords", "skills"}
MANIFEST_PATHS = {
    "claude": ".claude-plugin/plugin.json",
    "codex": ".codex-plugin/plugin.json",
    "grok": ".grok-plugin/plugin.json",
}
EXPECTED_AUTHORS = {
    "claude": {"name": "lukaszmaj"},
    "codex": {
        "name": "lukaszmaj",
        "url": "https://github.com/toolboxmd",
    },
    "grok": {"name": "lukaszmaj"},
}


class VerificationError(Exception):
    """A concise public-verifier failure."""


def _regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise VerificationError(f"{label} is unavailable: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise VerificationError(f"{label} must be a regular file")


def _read_text(path: Path, label: str) -> str:
    _regular_file(path, label)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read {label}: {exc}") from exc
    if len(payload) > 256 * 1024:
        raise VerificationError(f"{label} exceeds 256 KiB")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"{label} is not UTF-8") from exc


def _read_manifest(workspace: Path, host: str) -> dict[str, Any]:
    relative = MANIFEST_PATHS[host]
    text = _read_text(workspace / relative, relative)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{relative} is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{relative} must contain a JSON object")
    return value


def _verify_semantics(workspace: Path) -> None:
    version = _read_text(workspace / "VERSION", "VERSION")
    if version.splitlines() != [EXPECTED_PORTABLE["version"]]:
        raise VerificationError("VERSION must contain exactly 0.2.0")

    manifests = {
        host: _read_manifest(workspace, host) for host in MANIFEST_PATHS
    }
    for host, manifest in manifests.items():
        for key, expected in EXPECTED_PORTABLE.items():
            if manifest.get(key) != expected:
                raise VerificationError(
                    f"{host} manifest {key} must equal {expected!r}"
                )
        if manifest.get("author") != EXPECTED_AUTHORS[host]:
            raise VerificationError(f"{host} manifest author is not release-exact")

    for host in ("claude", "grok"):
        keys = set(manifests[host])
        if keys != PORTABLE_KEYS:
            unexpected = sorted(keys - PORTABLE_KEYS)
            missing = sorted(PORTABLE_KEYS - keys)
            raise VerificationError(
                f"{host} manifest key scope differs; "
                f"missing={missing}, unexpected={unexpected}"
            )

    codex = manifests["codex"]
    missing_codex = sorted(CODEX_ONLY_KEYS - set(codex))
    if missing_codex:
        raise VerificationError(
            f"codex manifest is missing host-only keys: {missing_codex}"
        )
    if codex.get("homepage") != "https://github.com/toolboxmd/use-grok#readme":
        raise VerificationError("codex manifest homepage is not release-exact")
    if codex.get("skills") != "./skills/":
        raise VerificationError("codex manifest skills must equal './skills/'")
    if not isinstance(codex.get("keywords"), list) or not codex["keywords"]:
        raise VerificationError("codex manifest keywords must be a nonempty list")
    if not isinstance(codex.get("interface"), dict) or not codex["interface"]:
        raise VerificationError("codex manifest interface must be a nonempty object")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"FAIL: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2
    try:
        _verify_semantics(workspace)
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: use-grok 0.2.0 three-host public contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
