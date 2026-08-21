from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ExitCode, VersionCtlError
from .policy import Mirror
from .semver import SemVer


@dataclass(frozen=True)
class MirrorState:
    path: str
    pointer: str
    version: str | None
    consistent: bool
    normalization: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "pointer": self.pointer,
            "version": self.version,
            "consistent": self.consistent,
            "normalization": self.normalization,
        }


def read_version_file(path: Path, *, label: str = "repository version") -> SemVer:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise VersionCtlError(
            ExitCode.MISSING_VERSION,
            f"missing canonical version file: {path}",
            details={"path": str(path)},
        ) from exc
    except OSError as exc:
        raise VersionCtlError(ExitCode.IO_ERROR, f"cannot read {path}: {exc}") from exc
    value = raw.strip()
    if not value or len(raw.splitlines()) != 1:
        raise VersionCtlError(
            ExitCode.INVALID_VERSION,
            f"{path} must contain exactly one SemVer value",
            details={"value": raw},
        )
    return SemVer.parse(value, label=label)


def parse_version_text(raw: str | None, *, label: str) -> SemVer | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value or len(raw.splitlines()) != 1:
        raise VersionCtlError(
            ExitCode.INVALID_VERSION,
            f"{label} must contain exactly one SemVer value",
        )
    return SemVer.parse(value, label=label)


def _pointer_tokens(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise VersionCtlError(ExitCode.INVALID_POLICY, f"invalid pointer: {pointer}")
    raw_tokens = pointer[1:].split("/")
    if any(re.search(r"~(?![01])", token) for token in raw_tokens):
        raise VersionCtlError(ExitCode.INVALID_POLICY, f"invalid JSON Pointer escape: {pointer}")
    return [token.replace("~1", "/").replace("~0", "~") for token in raw_tokens]


def _lookup(value: Any, tokens: list[str], *, pointer: str) -> Any:
    current = value
    for token in tokens:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"mirror pointer does not exist: {pointer}",
                details={"pointer": pointer},
            )
    return current


def _assign(value: Any, tokens: list[str], new_value: str, *, pointer: str) -> None:
    if not tokens:
        raise VersionCtlError(ExitCode.INVALID_POLICY, "mirror pointer cannot target the document root")
    parent = _lookup(value, tokens[:-1], pointer=pointer) if len(tokens) > 1 else value
    token = tokens[-1]
    if isinstance(parent, dict) and token in parent:
        parent[token] = new_value
    elif isinstance(parent, list) and token.isdigit() and int(token) < len(parent):
        parent[int(token)] = new_value
    else:
        raise VersionCtlError(
            ExitCode.INVALID_POLICY,
            f"mirror pointer does not exist: {pointer}",
            details={"pointer": pointer},
        )


def read_mirror(root: Path, mirror: Mirror) -> str:
    path = root / mirror.path
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise VersionCtlError(
            ExitCode.STALE_MIRROR,
            f"cannot read version mirror {mirror.path}: {exc}",
            details=mirror.as_dict(),
        ) from exc
    return version_from_mirror_text(path, mirror.pointer, text)


def version_from_mirror_text(path: Path, pointer: str, text: str) -> str:
    tokens = _pointer_tokens(pointer)
    try:
        if path.suffix.lower() == ".json":
            document = json.loads(text)
        elif path.suffix.lower() == ".toml":
            document = tomllib.loads(text)
        else:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"unsupported mirror format: {path}",
                details={"supported": [".json", ".toml"]},
            )
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise VersionCtlError(
            ExitCode.STALE_MIRROR,
            f"cannot parse version mirror {path}: {exc}",
        ) from exc
    value = _lookup(document, tokens, pointer=pointer)
    if not isinstance(value, str):
        raise VersionCtlError(
            ExitCode.STALE_MIRROR,
            f"version mirror must point to a string: {path}{pointer}",
        )
    SemVer.parse(value, label=f"mirror {path}{pointer}")
    return value


def mirror_states(root: Path, mirrors: tuple[Mirror, ...], version: SemVer) -> list[MirrorState]:
    states: list[MirrorState] = []
    for mirror in mirrors:
        try:
            value = read_mirror(root, mirror)
            states.append(
                MirrorState(
                    path=mirror.path,
                    pointer=mirror.pointer,
                    version=value,
                    consistent=value == str(version),
                )
            )
        except VersionCtlError as exc:
            states.append(
                MirrorState(
                    path=mirror.path,
                    pointer=mirror.pointer,
                    version=None,
                    consistent=False,
                    normalization=exc.message,
                )
            )
    return states


def updated_mirror_text(path: Path, pointer: str, version: str) -> tuple[str, str | None]:
    text = path.read_text(encoding="utf-8")
    tokens = _pointer_tokens(pointer)
    suffix = path.suffix.lower()
    if suffix == ".json":
        document = json.loads(text)
        current = _lookup(document, tokens, pointer=pointer)
        if not isinstance(current, str):
            raise VersionCtlError(ExitCode.STALE_MIRROR, f"mirror target is not a string: {path}")
        _assign(document, tokens, version, pointer=pointer)
        indent_match = re.search(r"\n(?P<indent>[ \t]+)\S", text)
        indent: int | str = 2
        if indent_match:
            sample = indent_match.group("indent")
            indent = "\t" if "\t" in sample else len(sample)
        trailing = "\n" if text.endswith("\n") else ""
        return (
            json.dumps(document, indent=indent, ensure_ascii=False) + trailing,
            "JSON document reserialized with detected indentation",
        )
    if suffix == ".toml":
        return _updated_toml_text(text, tokens, pointer, version), None
    raise VersionCtlError(
        ExitCode.INVALID_POLICY,
        f"unsupported mirror format: {path}",
        details={"supported": [".json", ".toml"]},
    )


def _updated_toml_text(text: str, tokens: list[str], pointer: str, version: str) -> str:
    if not tokens or any(re.fullmatch(r"[A-Za-z0-9_-]+", token) is None for token in tokens):
        raise VersionCtlError(
            ExitCode.INVALID_POLICY,
            f"TOML mirror pointers support only bare section and key names: {pointer}",
        )
    document = tomllib.loads(text)
    current = _lookup(document, tokens, pointer=pointer)
    if not isinstance(current, str):
        raise VersionCtlError(ExitCode.STALE_MIRROR, f"TOML mirror target is not a string: {pointer}")

    wanted_section = ".".join(tokens[:-1])
    wanted_key = tokens[-1]
    current_section = ""
    matches = 0
    output: list[str] = []
    assignment = re.compile(
        rf"^(?P<lead>\s*{re.escape(wanted_key)}\s*=\s*)(?P<quote>['\"])(?P<value>.*?)(?P=quote)(?P<tail>\s*(?:#.*)?)$"
    )
    section = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        newline = line[len(body) :]
        section_match = section.match(body)
        if section_match:
            current_section = section_match.group(1).strip()
            output.append(line)
            continue
        match = assignment.match(body) if current_section == wanted_section else None
        if match:
            matches += 1
            body = (
                f"{match.group('lead')}{match.group('quote')}{version}"
                f"{match.group('quote')}{match.group('tail')}"
            )
            output.append(body + newline)
        else:
            output.append(line)
    if matches != 1:
        raise VersionCtlError(
            ExitCode.STALE_MIRROR,
            f"expected one TOML assignment for {pointer}, found {matches}",
        )
    return "".join(output)


def transactional_write(changes: dict[Path, str]) -> None:
    originals: dict[Path, bytes | None] = {}
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, text in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            originals[path] = path.read_bytes() if path.exists() else None
            mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
            descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            temp_path = Path(temp_name)
            temporary[path] = temp_path
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp_path, mode)
        for path, temp_path in temporary.items():
            os.replace(temp_path, path)
            replaced.append(path)
    except OSError as exc:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise VersionCtlError(
            ExitCode.IO_ERROR,
            f"version transaction failed and was rolled back: {exc}",
        ) from exc
    finally:
        for temp_path in temporary.values():
            temp_path.unlink(missing_ok=True)
