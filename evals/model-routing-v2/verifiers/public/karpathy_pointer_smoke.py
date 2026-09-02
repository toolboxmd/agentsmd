#!/usr/bin/env python3
"""Smoke-test pointer exclusion through Karpathy wiki discovery and indexing."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class VerificationError(Exception):
    """A concise public-verifier failure."""


def _regular_file(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise VerificationError(f"{label} is unavailable: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise VerificationError(f"{label} must be a regular file")


def _run(
    command: list[str], *, workspace: Path, label: str, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    environment = {
        key: os.environ[key]
        for key in (
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "NO_COLOR",
            "PYTHONDONTWRITEBYTECODE",
            "PYTHONNOUSERSITE",
        )
        if key in os.environ
    }
    environment["PATH"] = "/usr/bin:/bin"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VerificationError(f"{label} timed out") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        tail = detail[-1][:300] if detail else "no diagnostic"
        raise VerificationError(f"{label} failed: {tail}")
    return result


def _discover(workspace: Path, script: Path, wiki: Path) -> dict[str, Any]:
    result = _run(
        [sys.executable, "-B", str(script), "--wiki-root", str(wiki)],
        workspace=workspace,
        label="wiki-discover",
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VerificationError(
            f"wiki-discover returned invalid JSON: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise VerificationError("wiki-discover output must be a JSON object")
    return value


def _page(*, title: str, tags: str, summary: str, body: str) -> bytes:
    return (
        "---\n"
        f'title: "{title}"\n'
        "type: concepts\n"
        f"tags: {tags}\n"
        "sources: []\n"
        f'summary: "{summary}"\n'
        "---\n"
        f"{body}\n"
    ).encode("utf-8")


def _write_fixture(wiki: Path) -> dict[Path, bytes]:
    concepts = wiki / "concepts"
    nested = concepts / "nested"
    deeper = nested / "deeper"
    deeper.mkdir(parents=True)

    files = {
        concepts / "ordinary.md": _page(
            title="Ordinary Root",
            tags="[ordinary]",
            summary="Visible root ordinary page.",
            body="ORDINARY_ROOT_VISIBLE",
        ),
        concepts / "case-pointer.md": _page(
            title="Case And Whitespace Pointer",
            tags='["  PoInTeR  ", reference]',
            summary="This pointer must not enter an index.",
            body="POINTER_SHOULD_NOT_APPEAR_CASE",
        ),
        nested / "ordinary-nested.md": _page(
            title="Nested Ordinary",
            tags="[ordinary]",
            summary="Visible nested ordinary page.",
            body="ORDINARY_NESTED_VISIBLE",
        ),
        deeper / "deep-pointer.md": _page(
            title="Deep Pointer",
            tags="[pointer]",
            summary="This deep pointer must not change depth.",
            body="POINTER_SHOULD_NOT_APPEAR_DEEP",
        ),
    }
    for path, payload in files.items():
        path.write_bytes(payload)
    return {
        path: payload
        for path, payload in files.items()
        if "pointer" in path.name
    }


def _assert_pointer_bytes(pointer_bytes: dict[Path, bytes], stage: str) -> None:
    for path, expected in pointer_bytes.items():
        try:
            actual = path.read_bytes()
        except OSError as exc:
            raise VerificationError(
                f"pointer missing after {stage}: {path.name}"
            ) from exc
        if actual != expected:
            raise VerificationError(f"pointer bytes changed after {stage}: {path.name}")


def _assert_discovery(value: dict[str, Any], stage: str) -> None:
    if value.get("categories") != ["concepts"]:
        raise VerificationError(f"{stage} categories must equal ['concepts']")
    if value.get("counts") != {"concepts": 2}:
        raise VerificationError(f"{stage} must count exactly two ordinary pages")
    if value.get("depths") != {"concepts": 2}:
        raise VerificationError(f"{stage} depth must be two, excluding deep pointer")
    serialized = json.dumps(value, sort_keys=True)
    for marker in ("case-pointer", "deep-pointer", "Pointer"):
        if marker in serialized:
            raise VerificationError(
                f"{stage} discovery leaked pointer marker {marker!r}"
            )


def _read_generated(path: Path, label: str) -> str:
    _regular_file(path, label)
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VerificationError(f"cannot read generated {label}") from exc


def _assert_indexes(wiki: Path) -> None:
    root = _read_generated(wiki / "index.md", "index.md")
    concepts = _read_generated(wiki / "concepts/_index.md", "concepts/_index.md")
    nested = _read_generated(
        wiki / "concepts/nested/_index.md", "concepts/nested/_index.md"
    )
    deeper = _read_generated(
        wiki / "concepts/nested/deeper/_index.md",
        "concepts/nested/deeper/_index.md",
    )
    combined = "\n".join((root, concepts, nested, deeper))
    for marker in (
        "Case And Whitespace Pointer",
        "Deep Pointer",
        "case-pointer.md",
        "deep-pointer.md",
        "POINTER_SHOULD_NOT_APPEAR",
    ):
        if marker in combined:
            raise VerificationError(f"generated index leaked pointer marker {marker!r}")

    if "[Ordinary Root](ordinary.md)" not in concepts:
        raise VerificationError("root ordinary page is missing from category rows")
    if "[Nested Ordinary](ordinary-nested.md)" not in nested:
        raise VerificationError("nested ordinary page is missing from nested rows")
    if "[nested/](nested/_index.md)" not in concepts or "1 pages" not in concepts:
        raise VerificationError(
            "nested ordinary page is missing from category preview count"
        )
    if "Nested Ordinary" not in concepts:
        raise VerificationError(
            "nested ordinary title is missing from category preview"
        )
    if "[deeper/](deeper/_index.md)" not in nested or "0 pages" not in nested:
        raise VerificationError("deep pointer was not excluded from subtree count")
    if not re.search(
        r"\[Concepts\]\(concepts/_index\.md\).*2 pages, 2 levels deep",
        root,
    ):
        raise VerificationError(
            "root index count or depth is not exactly 2 pages at depth 2"
        )


def _verify(workspace: Path) -> None:
    discover = workspace / "scripts/wiki-discover.py"
    build = workspace / "scripts/wiki-build-index.py"
    _regular_file(discover, "scripts/wiki-discover.py")
    _regular_file(build, "scripts/wiki-build-index.py")

    with tempfile.TemporaryDirectory(prefix="karpathy-pointer-public-") as temp:
        wiki = Path(temp) / "wiki"
        wiki.mkdir()
        pointer_bytes = _write_fixture(wiki)

        before = _discover(workspace, discover, wiki)
        _assert_discovery(before, "pre-build")
        _assert_pointer_bytes(pointer_bytes, "discovery")

        _run(
            [
                sys.executable,
                "-B",
                str(build),
                "--wiki-root",
                str(wiki),
                "--rebuild-all",
            ],
            workspace=workspace,
            label="wiki-build-index",
        )
        _assert_pointer_bytes(pointer_bytes, "index build")

        after = _discover(workspace, discover, wiki)
        _assert_discovery(after, "post-build")
        _assert_pointer_bytes(pointer_bytes, "post-build discovery")
        _assert_indexes(wiki)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"FAIL: workspace is not a directory: {workspace}", file=sys.stderr)
        return 2
    try:
        _verify(workspace)
    except VerificationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("PASS: Karpathy pointer discovery and index smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
