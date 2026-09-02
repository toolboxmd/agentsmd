#!/usr/bin/env python3
"""Fail-closed side-effecting controller for model-routing benchmark v3.

The public CLI intentionally exposes one preflight, one canary command, and
one exact-next command.  It has no batch runner, arbitrary cell selector,
retry, repair, or rereview surface.
"""

from __future__ import annotations

import argparse
import base64
import errno
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence


PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
DEFINITION_PATH = PACKAGE_ROOT / "definition.json"
DEFAULT_STATE_ROOT = Path.home() / ".codex" / "routing-benchmark-v3"
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
OPENAI_STRICT_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "additionalProperties",
        "anyOf",
        "description",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "items",
        "maximum",
        "maxItems",
        "minimum",
        "minItems",
        "multipleOf",
        "pattern",
        "properties",
        "required",
        "type",
    }
)
OPENAI_STRICT_SCHEMA_TYPES = frozenset(
    {"array", "boolean", "integer", "null", "number", "object", "string"}
)
OPENAI_STRICT_STRING_FORMATS = frozenset(
    {"date", "date-time", "duration", "email", "hostname", "ipv4", "ipv6", "time", "uuid"}
)
CODEX_AUTH_FIELD_NAMES = frozenset(
    {
        "access_token",
        "account_id",
        "api_key",
        "id_token",
        "password",
        "refresh_token",
        "secret",
        "token",
    }
)
MAX_CODEX_AUTH_BYTES = 4 * 1024 * 1024
MAX_CODEX_STATE_ENTRIES = 100_000
MAX_EVALUATOR_AUTH_BYTES = 4 * 1024 * 1024
EVALUATOR_RUN_EVIDENCE_NAMES = frozenset(
    {
        "after-usage.json",
        "before-usage.json",
        "result.json",
        "run-receipt.json",
        "stderr.raw",
        "stdout.raw",
    }
)
SAFE_ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C", "NO_COLOR": "1"}
COMMAND_LINE_TOOLS = Path("/Library/Developer/CommandLineTools")
NODE_OPENSSL_CONFIG = Path("/System/Library/OpenSSL/openssl.cnf")
SPLIT_PYTHON = (
    COMMAND_LINE_TOOLS
    / "Library/Frameworks/Python3.framework/Versions/3.9/bin/python3"
)
SEATBELT_READ_PROBE = """import json,sys
try:
    with open(sys.argv[1], 'rb') as handle:
        handle.read(1)
except OSError as exc:
    denied = exc.errno in (1, 13)
    print(json.dumps({'category': 'policy_denied' if denied else 'error', 'errno': exc.errno}, sort_keys=True, separators=(',', ':')))
    raise SystemExit(77 if denied else 1)
print(json.dumps({'category': 'success', 'errno': None}, sort_keys=True, separators=(',', ':')))
"""
SEATBELT_SIGNAL_ZERO_PROBE = """import json,os,sys
target_pid = int(sys.argv[1])
target_kind = sys.argv[2]
if target_kind not in ('pid', 'pgid'):
    raise SystemExit(2)
target = target_pid if target_kind == 'pid' else -target_pid
try:
    os.kill(target, 0)
except OSError as exc:
    denied = exc.errno in (1, 13)
    print(json.dumps({'category': 'policy_denied' if denied else 'error', 'errno': exc.errno, 'target_kind': target_kind}, sort_keys=True, separators=(',', ':')))
    raise SystemExit(77 if denied else 1)
print(json.dumps({'category': 'success', 'errno': None, 'target_kind': target_kind}, sort_keys=True, separators=(',', ':')))
"""
SEATBELT_CHILD_SIGNAL_PROBE = """import errno,json,os,signal,subprocess,sys,time
group_ledger = sys.argv[1]
descendant_file = sys.argv[2]
children = []
payload = {'category': 'error', 'descendant_after_errno': None, 'descendant_observed_after_leader_exit': False, 'errno': None, 'group_after_errno': None, 'group_leader_pid': None, 'group_leader_returncode': None, 'group_observed_after_leader_exit': False, 'group_signal': 'SIGKILL', 'inherited_descendant_pid': None, 'pid_after_errno': None, 'pid_child_pid': None, 'pid_returncode': None}
exit_code = 1
def target_errno(target):
    try:
        os.kill(target, 0)
    except OSError as exc:
        return exc.errno
    return None
try:
    pid_child = subprocess.Popen(['/bin/sleep', '30'], start_new_session=True)
    children.append(pid_child)
    group_leader_source = "import json,os,subprocess,sys; child=subprocess.Popen(['/bin/sleep','30'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); payload={'inherited_descendant_pid':child.pid}; handle=open(sys.argv[1],'xb'); handle.write(json.dumps(payload,sort_keys=True,separators=(',',':')).encode('ascii')); handle.flush(); os.fsync(handle.fileno()); handle.close()"
    group_leader = subprocess.Popen([sys.executable, '-I', '-B', '-c', group_leader_source, descendant_file], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    children.append(group_leader)
    ledger = {'group_leader_pgid': group_leader.pid, 'pid_child_pgid': pid_child.pid}
    with open(group_ledger, 'xb') as handle:
        handle.write(json.dumps(ledger, sort_keys=True, separators=(',', ':')).encode('ascii'))
        handle.flush()
        os.fsync(handle.fileno())
    group_leader_returncode = group_leader.wait(timeout=2)
    if group_leader_returncode != 0:
        raise RuntimeError('group leader did not exit cleanly')
    with open(descendant_file, 'rb') as handle:
        descendant_bytes = handle.read()
    descendant_record = json.loads(descendant_bytes)
    if descendant_bytes != json.dumps(descendant_record, sort_keys=True, separators=(',', ':')).encode('ascii') or set(descendant_record) != {'inherited_descendant_pid'}:
        raise RuntimeError('descendant record differs')
    inherited_descendant_pid = descendant_record['inherited_descendant_pid']
    if not isinstance(inherited_descendant_pid, int) or isinstance(inherited_descendant_pid, bool) or inherited_descendant_pid <= 1:
        raise RuntimeError('descendant PID differs')
    payload['pid_child_pid'] = pid_child.pid
    payload['group_leader_pid'] = group_leader.pid
    payload['group_leader_returncode'] = group_leader_returncode
    payload['inherited_descendant_pid'] = inherited_descendant_pid
    os.kill(pid_child.pid, 0)
    os.kill(-group_leader.pid, 0)
    payload['group_observed_after_leader_exit'] = True
    os.kill(inherited_descendant_pid, 0)
    payload['descendant_observed_after_leader_exit'] = True
    os.kill(pid_child.pid, signal.SIGTERM)
    payload['pid_returncode'] = pid_child.wait(timeout=2)
    os.kill(-group_leader.pid, signal.SIGKILL)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        payload['pid_after_errno'] = target_errno(pid_child.pid)
        payload['group_after_errno'] = target_errno(-group_leader.pid)
        payload['descendant_after_errno'] = target_errno(inherited_descendant_pid)
        if payload['pid_after_errno'] == errno.ESRCH and payload['group_after_errno'] == errno.ESRCH and payload['descendant_after_errno'] == errno.ESRCH:
            break
        time.sleep(0.01)
    if payload['pid_returncode'] != -signal.SIGTERM or payload['pid_after_errno'] != errno.ESRCH or payload['group_after_errno'] != errno.ESRCH or payload['descendant_after_errno'] != errno.ESRCH:
        raise RuntimeError('signaled child exit status differs')
    payload['category'] = 'success'
    exit_code = 0
except OSError as exc:
    payload['errno'] = exc.errno
    if exc.errno in (1, 13):
        payload['category'] = 'policy_denied'
        exit_code = 77
except (json.JSONDecodeError, RuntimeError, subprocess.TimeoutExpired, ValueError):
    pass
for child in children:
    try:
        os.kill(-child.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
print(json.dumps(payload, sort_keys=True, separators=(',', ':')))
raise SystemExit(exit_code)
"""
SEATBELT_SIGNAL_CONTROL = """import json,os,sys,time
ready_file = sys.argv[1]
payload = {'process_group_id': os.getpgrp(), 'process_id': os.getpid()}
with open(ready_file, 'xb') as handle:
    handle.write(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('ascii'))
    handle.flush()
    os.fsync(handle.fileno())
time.sleep(30)
"""


def _reject_import_bytecode(root: Path) -> None:
    """Reject executable Python cache state before importing package modules."""

    for path in root.rglob("*"):
        if path.name == "__pycache__" or path.suffix == ".pyc":
            raise RuntimeError(f"benchmark package contains Python bytecode: {path}")


_reject_import_bytecode(PACKAGE_ROOT)
sys.path.insert(0, str(PACKAGE_ROOT))
import execution  # noqa: E402
import evaluator  # noqa: E402
import fixtures  # noqa: E402
import isolation  # noqa: E402
import lifecycle  # noqa: E402
import split_verifier  # noqa: E402
import telemetry  # noqa: E402


class ControllerError(RuntimeError):
    """A benchmark command cannot proceed without weakening evidence."""


class TerminalControllerError(ControllerError):
    """A classified controller-side failure that terminalizes the active cell."""

    terminal_status = "CONTROLLER_ERROR"

    def __init__(self, message: str, *, evidence: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.evidence = dict(evidence) if evidence is not None else None


class BoundaryFailure(TerminalControllerError):
    terminal_status = "BOUNDARY_FAILURE"


class TelemetryFailure(TerminalControllerError):
    terminal_status = "TELEMETRY_FAILURE"


class ProviderUnavailable(TerminalControllerError):
    terminal_status = "PROVIDER_UNAVAILABLE"


class QuotaExhausted(TerminalControllerError):
    terminal_status = "QUOTA_EXHAUSTED"


class StageTimeout(ControllerError):
    """The exact bounded stage reached its shared inclusive deadline."""


@dataclass(frozen=True, slots=True)
class ControllerConfig:
    state_root: Path
    use_grok_repo: Path
    karpathy_repo: Path
    openbot_repo: Path
    openbot_runtime_source: Path
    codex_executable: Path
    codex_launcher: Path
    node_executable: Path
    auth_source: Path
    codexbar_executable: Path = Path("/opt/homebrew/bin/codexbar")
    memory_root: Path = Path.home() / ".codex" / "memories"

    def normalized(self) -> "ControllerConfig":
        values = {
            name: Path(getattr(self, name)).expanduser().resolve(strict=False)
            for name in self.__dataclass_fields__
        }
        root = values["state_root"]
        if _overlap(root, REPOSITORY_ROOT.resolve()):
            raise ControllerError("controller state must be outside the repository")
        if root in {Path("/tmp"), Path("/private/tmp"), Path("/")}:
            raise ControllerError("controller state root is too broad or disposable")
        return ControllerConfig(**values)


@dataclass(slots=True)
class ControllerHooks:
    """Narrow test seams. Production leaves every hook unset."""

    preflight: Callable[..., Mapping[str, Any]] | None = None
    quota: Callable[[], Mapping[str, Any]] | None = None
    verifier: Callable[[str, Path, float], Mapping[str, Any]] | None = None
    codex_stage: Callable[..., Mapping[str, Any]] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_openai_strict_output_schema(
    value: Any, *, label: str, root: bool = True
) -> frozenset[str]:
    """Validate the narrow Structured Outputs subset used by Codex stages.

    This is deliberately an allowlist. A newly introduced schema keyword must
    be reviewed and added explicitly before it can reach a provider request.
    Value constraints that Structured Outputs can express are still checked
    semantically after generation by the controller.
    """

    if not isinstance(value, Mapping):
        raise ControllerError(f"{label} is not a JSON Schema object")
    unknown = set(value) - OPENAI_STRICT_SCHEMA_KEYWORDS
    if unknown:
        raise ControllerError(
            f"{label} uses unsupported strict-schema keywords: {sorted(unknown)}"
        )
    if not root and "$schema" in value:
        raise ControllerError(f"{label} declares $schema below the root")

    type_value = value.get("type")
    if isinstance(type_value, str):
        types = {type_value}
    elif isinstance(type_value, list):
        if (
            len(type_value) != 2
            or not all(isinstance(item, str) for item in type_value)
            or len(set(type_value)) != 2
            or "null" not in type_value
        ):
            raise ControllerError(f"{label} has an invalid nullable type union")
        types = set(type_value)
    elif type_value is None and "anyOf" in value:
        types = set()
    else:
        raise ControllerError(f"{label} has no valid type")
    if not types.issubset(OPENAI_STRICT_SCHEMA_TYPES):
        raise ControllerError(f"{label} uses an unsupported schema type")
    if root and (types != {"object"} or "anyOf" in value):
        raise ControllerError(f"{label} root must be one object schema")

    seen = set(value)
    if "object" in types:
        properties = value.get("properties")
        required = value.get("required")
        if (
            not isinstance(properties, Mapping)
            or value.get("additionalProperties") is not False
            or not isinstance(required, list)
            or not all(isinstance(item, str) for item in required)
            or len(required) != len(set(required))
            or set(required) != set(properties)
        ):
            raise ControllerError(
                f"{label} object must require every property and deny additional properties"
            )
        for name, child in properties.items():
            if not isinstance(name, str) or not name:
                raise ControllerError(f"{label} has an invalid property name")
            seen.update(
                validate_openai_strict_output_schema(
                    child, label=f"{label}.properties[{name!r}]", root=False
                )
            )
    elif any(key in value for key in ("properties", "required", "additionalProperties")):
        raise ControllerError(f"{label} has object keywords on a non-object schema")

    if "array" in types:
        if "items" not in value:
            raise ControllerError(f"{label} array has no item schema")
        seen.update(
            validate_openai_strict_output_schema(
                value["items"], label=f"{label}.items", root=False
            )
        )
    elif any(key in value for key in ("items", "minItems", "maxItems")):
        raise ControllerError(f"{label} has array keywords on a non-array schema")

    if "anyOf" in value:
        alternatives = value["anyOf"]
        if not isinstance(alternatives, list) or not alternatives:
            raise ControllerError(f"{label} has an invalid anyOf")
        for index, child in enumerate(alternatives):
            seen.update(
                validate_openai_strict_output_schema(
                    child, label=f"{label}.anyOf[{index}]", root=False
                )
            )

    if "pattern" in value:
        if "string" not in types or not isinstance(value["pattern"], str):
            raise ControllerError(f"{label} has an invalid string pattern")
        try:
            re.compile(value["pattern"])
        except re.error as exc:
            raise ControllerError(f"{label} has an invalid string pattern") from exc
    if "format" in value and (
        "string" not in types
        or not isinstance(value["format"], str)
        or value["format"] not in OPENAI_STRICT_STRING_FORMATS
    ):
        raise ControllerError(f"{label} has an unsupported string format")

    for keyword in (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
    ):
        constraint = value.get(keyword)
        if keyword in value and (
            not ({"integer", "number"} & types)
            or isinstance(constraint, bool)
            or not isinstance(constraint, (int, float))
        ):
            raise ControllerError(f"{label} has an invalid numeric constraint")
    for keyword in ("minItems", "maxItems"):
        constraint = value.get(keyword)
        if keyword in value and (
            isinstance(constraint, bool)
            or not isinstance(constraint, int)
            or constraint < 0
        ):
            raise ControllerError(f"{label} has an invalid array constraint")
    return frozenset(seen)


def openai_strict_output_schema_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerError(f"model output schema is invalid JSON: {path}") from exc
    keywords = validate_openai_strict_output_schema(value, label=path.name)
    try:
        relative = path.resolve(strict=True).relative_to(PACKAGE_ROOT.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ControllerError("model output schema is outside the benchmark package") from exc
    return {
        "path": relative.as_posix(),
        "sha256": sha256_file(path),
        "keywords": sorted(keywords),
    }


def _classified_codex_failure(stdout_path: Path) -> type[TerminalControllerError] | None:
    """Classify only exact machine-readable provider error codes.

    Human text and percentage observations are deliberately ignored. Unknown
    nonzero exits remain controller errors instead of being guessed into a
    quota or provider category.
    """

    quota_codes = {
        "insufficient_quota",
        "quota_exhausted",
        "usage_limit_reached",
    }
    provider_codes = {
        "provider_unavailable",
        "service_unavailable",
        "upstream_unavailable",
    }
    try:
        lines = stdout_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, Mapping):
            continue
        candidates: list[Any] = [event]
        for key in ("error", "details", "payload"):
            nested = event.get(key)
            if isinstance(nested, Mapping):
                candidates.append(nested)
        for record in candidates:
            if not isinstance(record, Mapping):
                continue
            codes = {
                record.get("code"),
                record.get("error_code"),
            }
            if codes & quota_codes:
                return QuotaExhausted
            if codes & provider_codes:
                return ProviderUnavailable
    return None


def strict_package_sha256(root: Path = PACKAGE_ROOT) -> str:
    """Hash all durable v3 package inputs and reject aliases or special files."""

    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            raise ControllerError(f"Python bytecode is forbidden in the package: {relative}")
        state = path.lstat()
        record: dict[str, Any] = {"path": relative.as_posix(), "mode": stat.S_IMODE(state.st_mode)}
        if stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode):
            record["kind"] = "directory"
        elif stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
            record.update(kind="file", size=state.st_size, sha256=sha256_file(path))
        else:
            raise ControllerError(f"special, linked, or aliased package entry: {relative}")
        entries.append(record)
    return sha256_bytes(canonical_bytes({"schema_version": 1, "entries": entries}))


def strict_tree_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        state = path.lstat()
        if stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode):
            entries.append({"path": relative, "kind": "directory", "mode": stat.S_IMODE(state.st_mode)})
        elif stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
            entries.append({"path": relative, "kind": "file", "mode": stat.S_IMODE(state.st_mode), "size": state.st_size, "sha256": sha256_file(path)})
        else:
            raise ControllerError(f"candidate contains a special, linked, or aliased entry: {relative}")
    payload = {"schema_version": 1, "entries": entries}
    payload["sha256"] = sha256_bytes(canonical_bytes(payload))
    return payload


def _entry_map(manifest: Mapping[str, Any]) -> dict[str, tuple[Any, ...]]:
    return {
        str(item["path"]): (
            item.get("kind"),
            item.get("mode"),
            item.get("size"),
            item.get("sha256"),
        )
        for item in manifest["entries"]
    }


def _file_map(manifest: Mapping[str, Any]) -> dict[str, tuple[Any, ...]]:
    return {
        path: (entry[1], entry[2], entry[3])
        for path, entry in _entry_map(manifest).items()
        if entry[0] == "file"
    }


def _changed_paths(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    old, new = _entry_map(before), _entry_map(after)
    return sorted(path for path in set(old) | set(new) if old.get(path) != new.get(path))


def _scope_receipt(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    declared: Any,
    allowed_paths: Sequence[str],
) -> dict[str, Any]:
    """Evaluate file and directory changes against the exact production scope."""

    old = _entry_map(before)
    new = _entry_map(after)
    changed = _changed_paths(before, after)
    changed_files = sorted(
        path
        for path in changed
        if (old.get(path) or new.get(path) or (None,))[0] == "file"
        or (new.get(path) or old.get(path) or (None,))[0] == "file"
    )
    changed_directories = sorted(
        path
        for path in changed
        if (old.get(path) or (None,))[0] == "directory"
        or (new.get(path) or (None,))[0] == "directory"
    )
    declared_valid = (
        isinstance(declared, list)
        and all(isinstance(item, str) and item for item in declared)
        and len(declared) == len(set(declared))
    )
    allowed = set(allowed_paths)
    created_allowed_files = {
        path
        for path in changed_files
        if path in allowed and old.get(path) is None and new.get(path, (None,))[0] == "file"
    }
    allowed_created_ancestors: set[str] = set()
    for path in created_allowed_files:
        parent = Path(path).parent
        while parent != Path("."):
            allowed_created_ancestors.add(parent.as_posix())
            parent = parent.parent
    directory_safe = all(
        old.get(path) is None
        and new.get(path, (None,))[0] == "directory"
        and path in allowed_created_ancestors
        for path in changed_directories
    )
    safe = (
        declared_valid
        and sorted(declared) == changed_files
        and set(changed_files).issubset(allowed)
        and directory_safe
    )
    return {
        "safe": safe,
        "declared_paths": list(declared) if declared_valid else None,
        "changed_paths": changed,
        "changed_file_paths": changed_files,
        "changed_directory_paths": changed_directories,
        "allowed_created_directory_paths": sorted(allowed_created_ancestors),
    }


def _review_range_side(
    root: Path, path: str, entry: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    """Encode one immutable manifest entry and exact regular-file bytes."""

    if entry is None:
        return None
    metadata = {key: value for key, value in entry.items() if key != "path"}
    result: dict[str, Any] = {"entry": metadata, "content_base64": None}
    if entry.get("kind") != "file":
        return result
    target = root / path
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as exc:
        raise ControllerError(f"review range file cannot be opened safely: {path}") from exc
    try:
        state_before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(state_before.st_mode)
            or state_before.st_nlink != 1
            or stat.S_IMODE(state_before.st_mode) != entry.get("mode")
            or state_before.st_size != entry.get("size")
        ):
            raise ControllerError(f"review range file identity differs: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        content = b"".join(chunks)
        state_after = os.fstat(descriptor)
        if (
            state_after.st_dev != state_before.st_dev
            or state_after.st_ino != state_before.st_ino
            or state_after.st_mode != state_before.st_mode
            or state_after.st_nlink != 1
            or state_after.st_size != len(content)
            or sha256_bytes(content) != entry.get("sha256")
        ):
            raise ControllerError(f"review range file changed while reading: {path}")
    finally:
        os.close(descriptor)
    result["content_base64"] = base64.b64encode(content).decode("ascii")
    return result


def _build_review_range(
    baseline_root: Path,
    artifact_root: Path,
    *,
    baseline_manifest_sha256: str,
    artifact_manifest_sha256: str,
    scope: Mapping[str, Any],
    allowed_paths: Sequence[str],
) -> dict[str, Any]:
    """Build the canonical Luna range from immutable snapshots only."""

    baseline_before = strict_tree_manifest(baseline_root)
    artifact_before = strict_tree_manifest(artifact_root)
    if (
        baseline_before["sha256"] != baseline_manifest_sha256
        or artifact_before["sha256"] != artifact_manifest_sha256
    ):
        raise ControllerError("review range snapshot manifest differs")
    expected_scope = _scope_receipt(
        baseline_before,
        artifact_before,
        scope.get("declared_paths"),
        allowed_paths,
    )
    if expected_scope != dict(scope) or expected_scope["safe"] is not True:
        raise ControllerError("review range does not match the safe artifact scope")
    changed_paths = list(expected_scope["changed_paths"])
    if changed_paths != sorted(set(changed_paths)):
        raise ControllerError("review range changed paths are not sorted and unique")
    baseline_entries = {
        str(entry["path"]): entry for entry in baseline_before["entries"]
    }
    artifact_entries = {
        str(entry["path"]): entry for entry in artifact_before["entries"]
    }
    changes = [
        {
            "path": path,
            "before": _review_range_side(
                baseline_root, path, baseline_entries.get(path)
            ),
            "after": _review_range_side(
                artifact_root, path, artifact_entries.get(path)
            ),
        }
        for path in changed_paths
    ]
    baseline_after = strict_tree_manifest(baseline_root)
    artifact_after = strict_tree_manifest(artifact_root)
    if (
        baseline_after["sha256"] != baseline_manifest_sha256
        or artifact_after["sha256"] != artifact_manifest_sha256
    ):
        raise ControllerError("review range snapshot changed while reading")
    return {
        "schema_version": 1,
        "baseline_manifest_sha256": baseline_manifest_sha256,
        "artifact_manifest_sha256": artifact_manifest_sha256,
        "artifact_scope_sha256": sha256_bytes(canonical_bytes(scope)),
        "changed_paths": changed_paths,
        "changes": changes,
    }


def _copy_ordinary(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ControllerError(f"destination already exists: {destination}")
    source_state = source.lstat()
    if not stat.S_ISDIR(source_state.st_mode) or stat.S_ISLNK(source_state.st_mode):
        raise ControllerError(f"copy source is not a real directory: {source}")
    destination.mkdir(parents=True, mode=stat.S_IMODE(source_state.st_mode))
    for path in sorted(source.rglob("*"), key=lambda item: item.relative_to(source).as_posix()):
        relative, state = path.relative_to(source), path.lstat()
        target = destination / relative
        if stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode):
            target.mkdir(mode=stat.S_IMODE(state.st_mode))
        elif stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            target.chmod(stat.S_IMODE(state.st_mode))
        else:
            raise ControllerError(f"copy source contains a linked or special entry: {path}")


def _copy_bound_snapshot(
    source: Path, destination: Path, *, expected_manifest_sha256: str
) -> dict[str, Any]:
    """Copy an ordinary private artifact snapshot while proving source stability."""

    before = strict_tree_manifest(source)
    if before["sha256"] != expected_manifest_sha256:
        raise ControllerError("candidate changed before artifact snapshot")
    _copy_ordinary(source, destination)
    copied = strict_tree_manifest(destination)
    after = strict_tree_manifest(source)
    if (
        copied["sha256"] != expected_manifest_sha256
        or after["sha256"] != expected_manifest_sha256
    ):
        raise ControllerError("candidate changed while artifact snapshot was copied")
    return copied


def _seatbelt_profile(
    *,
    read_paths: Sequence[Path],
    write_paths: Sequence[Path],
    allow_legacy_bash_heredoc: bool = False,
    signal_scope: str = "none",
) -> tuple[str, str]:
    """Build one exact default-deny native profile for a verifier peer."""

    if signal_scope not in {"none", "children", "same-sandbox", "all"}:
        raise ValueError("Seatbelt signal scope is invalid")

    def clause(path: Path) -> str:
        resolved = path.resolve(strict=True)
        operator = "subpath" if resolved.is_dir() else "literal"
        return f"({operator} {json.dumps(str(resolved))})"

    system_runtime_roots = (
        Path("/System"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/Library"),
        Path("/private/etc"),
    )
    reads = sorted({clause(path) for path in (*system_runtime_roots, *read_paths)})
    writes = sorted({clause(path) for path in write_paths})
    metadata_paths: set[Path] = {Path("/")}
    for path in (*system_runtime_roots, *read_paths, *write_paths):
        resolved = path.resolve(strict=True)
        metadata_paths.update(resolved.parents)
    if allow_legacy_bash_heredoc:
        heredoc_root = Path("/private/var/tmp").resolve(strict=True)
        metadata_paths.add(heredoc_root)
        metadata_paths.update(heredoc_root.parents)
        metadata_paths.update((Path("/var"), Path("/var/tmp")))
    metadata = sorted(
        f"(literal {json.dumps(str(path))})" for path in metadata_paths
    )
    clauses = [
            "(version 1)",
            "(deny default)",
            '(import "system.sb")',
            "(allow process*)",
            "(allow file-read* ",
            " ".join(reads),
            ")",
            "(allow file-read-metadata ",
            " ".join(metadata),
            ")",
            "(allow file-write* ",
            " ".join(writes),
            ")",
    ]
    if signal_scope == "children":
        clauses.append("(allow signal (target children))")
    elif signal_scope == "same-sandbox":
        clauses.append("(allow signal (target same-sandbox))")
    elif signal_scope == "all":
        clauses.append("(allow signal)")
    if allow_legacy_bash_heredoc:
        clauses.append(
            '(allow file-read* file-write* '
            '(regex #"sh-thd-[0-9]+$"))'
        )
    profile = "".join(clauses)
    return profile, sha256_bytes(profile.encode("utf-8"))


def _evaluator_sandbox_profile(
    *,
    executable: Path,
    readable_files: Sequence[Path],
    writable_roots: Sequence[Path],
    metadata_only_paths: Sequence[Path],
) -> tuple[str, str]:
    """Build the exact tool-free evaluator Seatbelt policy projection."""

    executable = executable.resolve(strict=True)
    reads = {executable, *(path.resolve(strict=True) for path in readable_files)}
    writes = {path.resolve(strict=True) for path in writable_roots}
    metadata: set[Path] = {Path("/")}
    for path in (*reads, *writes, *metadata_only_paths):
        absolute = path.absolute()
        metadata.add(absolute)
        metadata.update(absolute.parents)

    literals = lambda paths: " ".join(
        f"(literal {json.dumps(str(path))})" for path in sorted(paths)
    )
    subpaths = " ".join(
        f"(subpath {json.dumps(str(path))})" for path in sorted(writes)
    )
    profile = "".join(
        (
            "(version 1)",
            "(deny default)",
            '(import "system.sb")',
            "(system-network)",
            '(allow network-outbound (literal "/private/var/run/mDNSResponder"))',
            "(allow network-outbound (require-all ",
            '(remote tcp "*:443") ',
            '(require-not (remote ip "localhost:*"))))',
            "(deny network-inbound)",
            '(deny network-outbound (remote tcp "localhost:*"))',
            '(deny network-outbound (literal "/private/var/run/syslog"))',
            "(allow process-info* (target self))",
            "(allow process-exec (literal ",
            json.dumps(str(executable)),
            "))",
            "(allow file-map-executable (literal ",
            json.dumps(str(executable)),
            "))",
            "(allow file-read* ",
            literals(reads),
            " ",
            subpaths,
            ")",
            "(allow file-read-metadata ",
            literals(metadata),
            ")",
            "(allow file-write* ",
            subpaths,
            ")",
        )
    )
    if "process-fork" in profile or "(allow process*)" in profile:
        raise ControllerError("evaluator profile unexpectedly grants process creation")
    return profile, sha256_bytes(profile.encode("utf-8"))


def _write_private_file(path: Path, data: bytes, *, mode: int) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        written = 0
        while written < len(data):
            count = os.write(descriptor, data[written:])
            if count <= 0:
                raise OSError("private file write made no progress")
            written += count
        os.fsync(descriptor)
        os.close(descriptor)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            raise ControllerError(
                "private file creation failed and cleanup failed"
            ) from cleanup_exc
        raise
    return sha256_bytes(data)


def _read_owned_single_link_file(
    path: Path, *, label: str, maximum_bytes: int, required_mode: int | None = None
) -> bytes:
    """Read one owner-controlled ordinary file without following aliases."""

    if not path.is_absolute() or not hasattr(os, "O_NOFOLLOW"):
        raise BoundaryFailure(
            f"{label} cannot be read with an absolute no-follow boundary"
        )
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
    except OSError as exc:
        raise BoundaryFailure(f"{label} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        mode = stat.S_IMODE(before.st_mode)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or (required_mode is not None and mode != required_mode)
            or before.st_size > maximum_bytes
        ):
            raise BoundaryFailure(
                f"{label} is not an admissible private ordinary file"
            )
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(
                descriptor, min(1024 * 1024, maximum_bytes + 1 - size)
            )
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum_bytes:
                raise BoundaryFailure(f"{label} exceeds its fixed byte bound")
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (
                after.st_dev,
                after.st_ino,
                after.st_mode,
                after.st_nlink,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            )
            != (
                before.st_dev,
                before.st_ino,
                before.st_mode,
                before.st_nlink,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            or len(content) != before.st_size
        ):
            raise BoundaryFailure(f"{label} changed while it was read")
        return content
    finally:
        os.close(descriptor)


def _codex_auth_markers(content: bytes) -> tuple[bytes, ...]:
    """Return secret-bearing byte sequences retained evidence must not contain."""

    markers: set[bytes] = set()
    if len(content) >= 16:
        markers.add(content)
        markers.add(base64.b64encode(content))
        markers.add(base64.urlsafe_b64encode(content))
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundaryFailure("Codex auth source is not valid JSON") from exc
    if not isinstance(document, Mapping) or not isinstance(
        document.get("tokens"), Mapping
    ):
        raise BoundaryFailure("Codex auth source has no OAuth token record")
    required_tokens = {"access_token", "account_id", "id_token", "refresh_token"}
    tokens = document["tokens"]
    if any(
        not isinstance(tokens.get(name), str) or not tokens[name]
        for name in required_tokens
    ):
        raise BoundaryFailure("Codex auth source has an incomplete OAuth token record")
    markers.add(canonical_bytes(document))

    def add_scalar(value: str) -> None:
        encoded = value.encode("utf-8")
        if len(encoded) < 8:
            return
        markers.add(encoded)
        markers.add(json.dumps(value, ensure_ascii=False).encode("utf-8"))
        markers.add(base64.b64encode(encoded))
        markers.add(base64.urlsafe_b64encode(encoded))

    def visit(value: Any, *, inside_tokens: bool = False) -> None:
        if isinstance(value, Mapping):
            for raw_key, nested in value.items():
                key = str(raw_key).lower()
                nested_inside_tokens = inside_tokens or key == "tokens"
                sensitive = (
                    key in CODEX_AUTH_FIELD_NAMES
                    or key.endswith("_token")
                    or key.endswith("_key")
                    or key.endswith("_password")
                    or key.endswith("_secret")
                )
                if sensitive:
                    markers.add(
                        json.dumps(str(raw_key), ensure_ascii=False).encode("utf-8")
                    )
                if isinstance(nested, str) and (sensitive or nested_inside_tokens):
                    add_scalar(nested)
                visit(nested, inside_tokens=nested_inside_tokens)
        elif isinstance(value, list):
            for nested in value:
                visit(nested, inside_tokens=inside_tokens)

    visit(document)
    return tuple(sorted(marker for marker in markers if len(marker) >= 8))


def _remove_exact_controller_entry(path: Path) -> bool:
    """Remove one exact controller-owned entry without following an alias."""

    try:
        state = path.lstat()
    except FileNotFoundError:
        return False
    if stat.S_ISDIR(state.st_mode) and not stat.S_ISLNK(state.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def _exact_controller_entry_absent(path: Path) -> bool:
    """Check exact-entry absence without following a broken or replaced alias."""

    try:
        path.lstat()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return False


def _snapshot_codex_rollout(
    codex_home: Path, destination: Path, *, required: bool
) -> tuple[Path | None, bytes | None]:
    """Copy the sole rollout out of disposable Codex state before cleanup."""

    try:
        root_state = codex_home.lstat()
    except OSError as exc:
        raise BoundaryFailure("fresh Codex state root cannot be inspected") from exc
    if (
        not stat.S_ISDIR(root_state.st_mode)
        or stat.S_ISLNK(root_state.st_mode)
        or root_state.st_uid != os.geteuid()
    ):
        raise BoundaryFailure("fresh Codex state root is not a private directory")
    sessions = codex_home / "sessions"
    try:
        sessions_state = sessions.lstat()
    except FileNotFoundError:
        if required:
            raise TelemetryFailure("successful stage did not persist a session tree")
        return None, None
    except OSError as exc:
        raise BoundaryFailure("fresh Codex session tree cannot be inspected") from exc
    if (
        not stat.S_ISDIR(sessions_state.st_mode)
        or stat.S_ISLNK(sessions_state.st_mode)
        or sessions_state.st_uid != os.geteuid()
    ):
        raise BoundaryFailure("fresh Codex session tree is not a private directory")

    rollouts: list[Path] = []
    pending = [sessions]
    observed_entries = 0
    while pending:
        directory = pending.pop()
        try:
            directory_state = directory.lstat()
            if (
                not stat.S_ISDIR(directory_state.st_mode)
                or stat.S_ISLNK(directory_state.st_mode)
                or directory_state.st_uid != os.geteuid()
            ):
                raise BoundaryFailure(
                    "fresh Codex session subtree is not a private directory"
                )
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    observed_entries += 1
                    if observed_entries > MAX_CODEX_STATE_ENTRIES:
                        raise BoundaryFailure(
                            "fresh Codex session tree exceeds its entry bound"
                        )
                    try:
                        entry_state = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise BoundaryFailure(
                            "fresh Codex session entry cannot be inspected"
                        ) from exc
                    path = Path(entry.path)
                    if stat.S_ISLNK(entry_state.st_mode):
                        raise BoundaryFailure(
                            "fresh Codex session tree contains an alias"
                        )
                    if stat.S_ISDIR(entry_state.st_mode):
                        if entry_state.st_uid != os.geteuid():
                            raise BoundaryFailure(
                                "fresh Codex session subtree has a foreign owner"
                            )
                        pending.append(path)
                    elif stat.S_ISREG(entry_state.st_mode):
                        if path.name.endswith(".jsonl"):
                            rollouts.append(path)
                    else:
                        raise BoundaryFailure(
                            "fresh Codex session tree contains a special entry"
                        )
        except BoundaryFailure:
            raise
        except OSError as exc:
            raise BoundaryFailure(
                "fresh Codex session subtree cannot be read completely"
            ) from exc
    rollouts.sort()
    if not rollouts:
        if required:
            raise TelemetryFailure("successful stage did not persist a rollout")
        return None, None
    if len(rollouts) != 1:
        raise BoundaryFailure(
            f"fresh stage persisted an ambiguous rollout set: {len(rollouts)}"
        )
    try:
        content = _read_owned_single_link_file(
            rollouts[0],
            label="Codex rollout",
            maximum_bytes=execution.MAX_OUTPUT_BYTES,
        )
        copied_hash = _write_private_file(destination, content, mode=0o600)
    except (OSError, ControllerError) as exc:
        destination.unlink(missing_ok=True)
        if isinstance(exc, BoundaryFailure):
            raise
        raise BoundaryFailure("Codex rollout cannot be retained safely") from exc
    if copied_hash != sha256_bytes(content):
        destination.unlink(missing_ok=True)
        raise BoundaryFailure("copied Codex rollout differs from its source bytes")
    return destination, content


def _cleanup_codex_stage_runtime(
    *,
    stage_root: Path,
    paths: isolation.CodexPaths,
    retained_paths: Sequence[Path],
    auth_markers: Sequence[bytes],
) -> dict[str, Any]:
    """Discard runtime state and admit only credential-free evidence files."""

    violations: list[str] = []
    stage_root_safe = False
    try:
        stage_state = stage_root.lstat()
        stage_root_safe = (
            stat.S_ISDIR(stage_state.st_mode)
            and not stat.S_ISLNK(stage_state.st_mode)
            and stage_state.st_uid == os.geteuid()
        )
        if not stage_root_safe:
            _remove_exact_controller_entry(stage_root)
            violations.append("stage evidence root was replaced by a special entry")
        elif stat.S_IMODE(stage_state.st_mode) != 0o700:
            stage_root.chmod(0o700)
            violations.append("stage evidence root lost its private mode")
    except OSError:
        violations.append("stage evidence root cannot be inspected safely")

    if stage_root_safe:
        auth_targets = (paths.codex_home / "auth.json", paths.auth_target)
        runtime_roots = (
            ("HOME", paths.home),
            ("CODEX_HOME", paths.codex_home),
            ("CODEX_SQLITE_HOME", paths.codex_sqlite_home),
        )
    else:
        auth_targets = ()
        runtime_roots = ()
    for target in auth_targets:
        try:
            _remove_exact_controller_entry(target)
        except OSError:
            violations.append("authentication cleanup failed")
    for label, root in runtime_roots:
        try:
            if root.exists() or root.is_symlink():
                state = root.lstat()
                if not stat.S_ISDIR(state.st_mode) or stat.S_ISLNK(state.st_mode):
                    violations.append(f"{label} was replaced by a special entry")
                _remove_exact_controller_entry(root)
        except OSError:
            violations.append(f"{label} cleanup failed")
    try:
        if paths.tmpdir.exists() or paths.tmpdir.is_symlink():
            temporary_state = paths.tmpdir.lstat()
            if not stat.S_ISDIR(temporary_state.st_mode) or stat.S_ISLNK(
                temporary_state.st_mode
            ):
                violations.append("TMPDIR was replaced by a special entry")
            _remove_exact_controller_entry(paths.tmpdir)
    except OSError:
        violations.append("TMPDIR cleanup failed")

    allowed = {path.name: path for path in retained_paths}
    if stage_root_safe:
        try:
            entries = list(stage_root.iterdir())
        except OSError:
            entries = []
            violations.append("stage evidence root cannot be inspected")
    else:
        entries = []
    for entry in entries:
        if entry.name in allowed and entry == allowed[entry.name]:
            continue
        try:
            _remove_exact_controller_entry(entry)
        except OSError:
            violations.append("unexpected stage entry cleanup failed")
        else:
            violations.append("unexpected stage entry was discarded")

    admitted: list[Path] = []
    admitted_artifacts: list[dict[str, Any]] = []
    for path in retained_paths if stage_root_safe else ():
        if not path.exists() and not path.is_symlink():
            continue
        try:
            content = _read_owned_single_link_file(
                path,
                label="retained Codex evidence",
                maximum_bytes=execution.MAX_OUTPUT_BYTES,
            )
            path.chmod(0o600, follow_symlinks=False)
        except (OSError, ControllerError):
            try:
                _remove_exact_controller_entry(path)
            except OSError:
                pass
            violations.append("retained evidence is not a safe ordinary file")
            continue
        admitted.append(path)
        admitted_artifacts.append(
            {
                "name": path.name,
                "bytes": len(content),
                "sha256": sha256_bytes(content),
            }
        )
        if any(marker in content for marker in auth_markers):
            violations.append("retained evidence contains authentication material")

    if violations:
        for path in admitted:
            try:
                _remove_exact_controller_entry(path)
            except OSError:
                violations.append("retained evidence cleanup failed")
        admitted = []
        admitted_artifacts = []

    if violations:
        raise BoundaryFailure(
            "Codex stage evidence retention boundary failed: "
            + "; ".join(sorted(set(violations)))
        )
    return {
        "status": "PASS",
        "exact_allowlist_satisfied": True,
        "retained_files": sorted(path.name for path in admitted),
        "retained_artifacts": sorted(
            admitted_artifacts, key=lambda artifact: artifact["name"]
        ),
        "discarded_runtime_roots": ["home", "codex-home", "sqlite", ".runner-tmp"],
        "runtime_roots_absent": True,
        "auth_destination_absent": True,
        "retained_artifacts_scanned": sorted(path.name for path in admitted),
        "auth_material_scan": "PASS",
    }


def _stage_evidence_binding(
    *, attempt: Path, stage_root: Path, retention: Mapping[str, Any]
) -> dict[str, Any]:
    """Bind every admitted direct stage artifact without rereading raw bytes."""

    artifacts = retention.get("retained_artifacts")
    if not isinstance(artifacts, list):
        raise BoundaryFailure("stage retention receipt has no artifact bindings")
    files: list[dict[str, Any]] = []
    for artifact in artifacts:
        if (
            not isinstance(artifact, Mapping)
            or set(artifact) != {"name", "bytes", "sha256"}
            or not isinstance(artifact.get("name"), str)
            or Path(artifact["name"]).name != artifact["name"]
            or isinstance(artifact.get("bytes"), bool)
            or not isinstance(artifact.get("bytes"), int)
            or artifact["bytes"] < 0
            or not isinstance(artifact.get("sha256"), str)
            or HASH_RE.fullmatch(artifact["sha256"]) is None
        ):
            raise BoundaryFailure("stage retention artifact binding is invalid")
        files.append(
            {
                "path": (stage_root / artifact["name"])
                .relative_to(attempt)
                .as_posix(),
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
            }
        )
    return {
        "stage": stage_root.name,
        "retention": dict(retention),
        "files": sorted(files, key=lambda item: item["path"]),
    }


def _evaluator_auth_markers(content: bytes) -> tuple[bytes, ...]:
    """Return in-memory forms of token-sized Grok auth document values."""

    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerError("Grok auth source is not valid JSON") from exc
    if not isinstance(document, Mapping) or not document:
        raise ControllerError("Grok auth source must contain a non-empty object")
    markers: set[bytes] = set()

    def add_bytes(value: bytes) -> None:
        if len(value) < 8:
            return
        markers.add(value)
        markers.add(base64.b64encode(value))
        markers.add(base64.urlsafe_b64encode(value))

    def add_text(value: str) -> None:
        encoded = value.encode("utf-8")
        add_bytes(encoded)
        add_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            for raw_key, nested in value.items():
                add_text(str(raw_key))
                if isinstance(nested, str):
                    add_text(nested)
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    add_bytes(content)
    add_bytes(canonical_bytes(document))
    visit(document)
    return tuple(sorted(markers))


def _read_evaluator_auth_source(
    source: Path, *, minimum_valid_seconds: float | None
) -> tuple[bytes, str, tuple[int, ...], str]:
    if not source.is_absolute():
        raise ControllerError("Grok auth source must be an absolute file")
    if not hasattr(os, "O_NOFOLLOW"):
        raise ControllerError("this host cannot enforce no-follow Grok auth copying")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        raise ControllerError("Grok auth source cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
        ):
            raise ControllerError(
                "Grok auth source must be an owner-owned 0600 regular single-link file"
            )
        if before.st_size > MAX_EVALUATOR_AUTH_BYTES:
            raise ControllerError("Grok auth source exceeds its fixed size limit")
        chunks: list[bytes] = []
        observed_bytes = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            observed_bytes += len(chunk)
            if observed_bytes > MAX_EVALUATOR_AUTH_BYTES:
                raise ControllerError("Grok auth source exceeds its fixed size limit")
            chunks.append(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            (after.st_dev, after.st_ino, after.st_mode, after.st_nlink, after.st_size)
            != (before.st_dev, before.st_ino, before.st_mode, before.st_nlink, before.st_size)
            or after.st_size != len(content)
        ):
            raise ControllerError("Grok auth source changed while it was copied")
    finally:
        os.close(descriptor)
    digest = sha256_bytes(content)
    admission = "stability_recheck"
    if minimum_valid_seconds is not None:
        try:
            document = json.loads(content)
            records = [
                record for record in document.values() if isinstance(record, Mapping)
            ]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControllerError("Grok auth source has no valid expiry record") from exc
        expirations: list[float] = []
        for record in records:
            if not isinstance(record.get("expires_at"), str):
                continue
            try:
                expirations.append(
                    datetime.fromisoformat(
                        str(record["expires_at"]).replace("Z", "+00:00")
                    ).timestamp()
                )
            except ValueError:
                continue
        minimum_expiry = time.time() + minimum_valid_seconds
        fresh_access = bool(expirations and max(expirations) > minimum_expiry)
        refresh_capable = any(
            isinstance(record.get("refresh_token"), str)
            and bool(record["refresh_token"])
            for record in records
        )
        if not fresh_access and not refresh_capable:
            raise ControllerError(
                "Grok auth is neither deadline-fresh nor refresh-capable"
            )
        admission = "fresh_access" if fresh_access else "refresh_capable"
    identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
    )
    return content, digest, identity, admission


def _copy_evaluator_auth(
    source: Path, destination: Path, *, minimum_valid_seconds: float
) -> tuple[str, tuple[int, ...], str, tuple[bytes, ...]]:
    """Copy one explicit owner-only Grok auth file without following aliases."""

    content, digest, identity, admission = _read_evaluator_auth_source(
        source, minimum_valid_seconds=minimum_valid_seconds
    )
    markers = _evaluator_auth_markers(content)
    created = False
    try:
        copied_digest = _write_private_file(destination, content, mode=0o600)
        created = True
        copied = destination.lstat()
        if (
            copied_digest != digest
            or not stat.S_ISREG(copied.st_mode)
            or copied.st_nlink != 1
            or copied.st_uid != os.geteuid()
            or stat.S_IMODE(copied.st_mode) != 0o600
        ):
            raise ControllerError("copied Grok auth file does not preserve byte identity")
    except BaseException:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return digest, identity, admission, markers


def _assert_evaluator_auth_source_stable(
    source: Path, *, digest: str, identity: tuple[int, ...]
) -> None:
    _content, observed_digest, observed_identity, _admission = _read_evaluator_auth_source(
        source, minimum_valid_seconds=None
    )
    if observed_digest != digest or observed_identity != identity:
        raise BoundaryFailure("Grok auth source changed during evaluator execution")


def _admit_evaluator_run_evidence(
    run_root: Path, auth_markers: Sequence[bytes]
) -> dict[str, Any]:
    """Admit the exact evaluator run subset or delete it without following aliases."""

    try:
        root_state = run_root.lstat()
    except FileNotFoundError:
        return {
            "status": "PASS",
            "run_directory_present": False,
            "exact_allowlist_satisfied": True,
            "auth_material_scan": "PASS" if auth_markers else "NOT_REQUIRED",
            "files": [],
        }
    except OSError:
        raise BoundaryFailure("evaluator run evidence cannot be inspected") from None
    violation = (
        not stat.S_ISDIR(root_state.st_mode)
        or stat.S_ISLNK(root_state.st_mode)
        or root_state.st_uid != os.geteuid()
        or stat.S_IMODE(root_state.st_mode) != 0o700
    )
    artifacts: list[dict[str, Any]] = []
    observed_entries = 0
    if not violation:
        try:
            with os.scandir(run_root) as entries:
                for entry in entries:
                    observed_entries += 1
                    if (
                        observed_entries > len(EVALUATOR_RUN_EVIDENCE_NAMES)
                        or entry.name not in EVALUATOR_RUN_EVIDENCE_NAMES
                    ):
                        violation = True
                        break
                    path = run_root / entry.name
                    try:
                        content = _read_owned_single_link_file(
                            path,
                            label="retained evaluator evidence",
                            maximum_bytes=execution.MAX_OUTPUT_BYTES,
                        )
                    except (OSError, ControllerError):
                        violation = True
                        break
                    if any(marker in content for marker in auth_markers):
                        violation = True
                        break
                    artifacts.append(
                        {
                            "path": f"run/{path.name}",
                            "bytes": len(content),
                            "sha256": sha256_bytes(content),
                        }
                    )
        except OSError:
            violation = True
    if violation:
        try:
            _remove_exact_controller_entry(run_root)
        except OSError:
            raise BoundaryFailure(
                "evaluator run evidence failed its retention boundary"
            ) from None
        if not _exact_controller_entry_absent(run_root):
            raise BoundaryFailure(
                "evaluator run evidence failed its retention boundary"
            ) from None
        raise BoundaryFailure(
            "evaluator run evidence failed its retention boundary"
        ) from None
    return {
        "status": "PASS",
        "run_directory_present": True,
        "exact_allowlist_satisfied": True,
        "auth_material_scan": "PASS" if auth_markers else "NOT_REQUIRED",
        "files": sorted(artifacts, key=lambda artifact: artifact["path"]),
    }


def _validate_evaluator_success_retention(
    outcome: evaluator.EvaluatorOutcome, retention: Mapping[str, Any]
) -> None:
    """Reconcile every admitted success artifact with the evaluator outcome."""

    receipt = outcome.run_receipt
    if not isinstance(receipt, Mapping):
        raise BoundaryFailure("successful evaluator receipt is not an object")
    receipt_payload = dict(receipt)
    receipt_payload_sha256 = receipt_payload.pop("receipt_payload_sha256", None)
    receipt_bytes = canonical_bytes(dict(receipt))
    result_bytes = canonical_bytes(outcome.result)
    if (
        receipt_payload_sha256 != sha256_bytes(canonical_bytes(receipt_payload))
        or outcome.run_receipt_sha256 != sha256_bytes(receipt_bytes)
        or outcome.result_sha256 != sha256_bytes(result_bytes)
        or receipt.get("result_file") != "result.json"
        or receipt.get("result_sha256") != outcome.result_sha256
    ):
        raise BoundaryFailure("successful evaluator result bindings differ")

    usage = receipt.get("usage_evidence")
    raw = receipt.get("raw_evidence")
    if not isinstance(usage, Mapping) or not isinstance(raw, Mapping):
        raise BoundaryFailure("successful evaluator evidence bindings are missing")
    expected: dict[str, dict[str, Any]] = {
        "run/result.json": {
            "bytes": len(result_bytes),
            "sha256": outcome.result_sha256,
        },
        "run/run-receipt.json": {
            "bytes": len(receipt_bytes),
            "sha256": outcome.run_receipt_sha256,
        },
    }
    for label in ("before", "after"):
        value = usage.get(label)
        value_bytes = canonical_bytes(value)
        value_sha256 = sha256_bytes(value_bytes)
        if usage.get(f"{label}_sha256") != value_sha256:
            raise BoundaryFailure("successful evaluator usage bindings differ")
        expected[f"run/{label}-usage.json"] = {
            "bytes": len(value_bytes),
            "sha256": value_sha256,
        }
    for label in ("stdout", "stderr"):
        path = raw.get(f"{label}_file")
        size = raw.get(f"{label}_bytes")
        digest = raw.get(f"{label}_sha256")
        if (
            path != f"{label}.raw"
            or isinstance(size, bool)
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or HASH_RE.fullmatch(digest) is None
        ):
            raise BoundaryFailure("successful evaluator raw bindings differ")
        expected[f"run/{path}"] = {"bytes": size, "sha256": digest}

    files = retention.get("files")
    if (
        retention.get("status") != "PASS"
        or retention.get("run_directory_present") is not True
        or retention.get("exact_allowlist_satisfied") is not True
        or retention.get("auth_material_scan") != "PASS"
        or not isinstance(files, list)
        or len(files) != len(EVALUATOR_RUN_EVIDENCE_NAMES)
    ):
        raise BoundaryFailure("successful evaluator retention is incomplete")
    observed: dict[str, dict[str, Any]] = {}
    for artifact in files:
        if (
            not isinstance(artifact, Mapping)
            or set(artifact) != {"path", "bytes", "sha256"}
            or not isinstance(artifact.get("path"), str)
            or artifact["path"] in observed
        ):
            raise BoundaryFailure("successful evaluator retention is invalid")
        observed[artifact["path"]] = {
            "bytes": artifact.get("bytes"),
            "sha256": artifact.get("sha256"),
        }
    if observed != expected:
        raise BoundaryFailure("successful evaluator retained artifacts differ")


def _build_evaluator_probe(destination: Path) -> dict[str, Any]:
    source = PACKAGE_ROOT / "evaluator_probe.c"
    compiler = Path("/usr/bin/clang")
    if not compiler.is_file() or not source.is_file():
        raise ControllerError("evaluator probe build inputs are unavailable")
    command = [
        str(compiler),
        "-std=c11",
        "-O2",
        "-Wall",
        "-Wextra",
        "-Werror",
        str(source),
        "-o",
        str(destination),
    ]
    completed = subprocess.run(
        command,
        cwd=str(PACKAGE_ROOT),
        env=SAFE_ENV,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ControllerError("evaluator probe compilation failed")
    destination.chmod(0o500)
    state = destination.lstat()
    if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
        raise ControllerError("evaluator probe is not an ordinary private executable")
    return {
        "source_sha256": sha256_file(source),
        "executable_sha256": sha256_file(destination),
        "compiler": str(compiler),
        "argv_sha256": sha256_bytes(canonical_bytes(command)),
    }


def _split_package_paths() -> dict[str, Path]:
    """Return every active source path in the split-verifier package."""

    return {
        "protocol": PACKAGE_ROOT / "split_verifier.py",
        "runner": PACKAGE_ROOT / "split_verifier_runner.py",
        "v2_driver": PACKAGE_ROOT / "verifiers" / "hidden" / "v2_split_driver.py",
        "openbot_driver": (
            PACKAGE_ROOT
            / "verifiers"
            / "hidden"
            / "openbot_acp_hidden_driver.test.ts"
        ),
        "hidden_package": PACKAGE_ROOT / "verifiers" / "hidden" / "package.json",
        "v2_worker": PACKAGE_ROOT / "verifiers" / "workers" / "v2_command_worker.py",
        "openbot_worker": (
            PACKAGE_ROOT / "verifiers" / "workers" / "openbot_acp_worker.mjs"
        ),
        "openbot_relay": (
            PACKAGE_ROOT / "verifiers" / "workers" / "openbot_agent_relay.mjs"
        ),
    }


def _v2_split_profiles(
    *,
    candidate: Path,
    shared: Path,
    hidden: Path,
    driver_runtime: Path,
    worker_runtime: Path,
) -> dict[str, tuple[str, str]]:
    """Build the exact v2 driver and worker profiles used in production."""

    paths = _split_package_paths()
    return {
        "driver": _seatbelt_profile(
            read_paths=(
                COMMAND_LINE_TOOLS,
                candidate,
                shared,
                hidden,
                paths["v2_driver"],
                driver_runtime,
            ),
            write_paths=(shared,),
        ),
        "worker": _seatbelt_profile(
            read_paths=(
                COMMAND_LINE_TOOLS,
                candidate,
                shared,
                paths["v2_worker"],
                worker_runtime,
            ),
            write_paths=(shared,),
            allow_legacy_bash_heredoc=True,
        ),
    }


def _openbot_split_profiles(
    *,
    node: Path,
    candidate: Path,
    shared: Path,
) -> dict[str, tuple[str, str]]:
    """Build exact OpenBot profiles while hiding candidate code from the driver."""

    paths = _split_package_paths()
    return {
        "driver": _seatbelt_profile(
            read_paths=(
                node,
                shared,
                paths["openbot_driver"],
                paths["hidden_package"],
            ),
            write_paths=(shared,),
            signal_scope="all",
        ),
        "worker": _seatbelt_profile(
            read_paths=(
                node,
                candidate,
                shared,
                paths["openbot_worker"],
                paths["openbot_relay"],
            ),
            write_paths=(shared,),
            signal_scope="same-sandbox",
        ),
    }


def _openbot_driver_argv(
    *, sandbox: Path, profile: str, node: Path, driver: Path
) -> list[str]:
    """Launch node:test in-process with pinned Node native type stripping."""

    return [
        str(sandbox),
        "-p",
        profile,
        str(node),
        "--experimental-strip-types",
        str(driver),
    ]


def _remove_runner_tmp(candidate: Path) -> None:
    target = candidate / ".runner-tmp"
    if not target.exists() and not target.is_symlink():
        return
    state = target.lstat()
    if not stat.S_ISDIR(state.st_mode) or stat.S_ISLNK(state.st_mode):
        raise ControllerError("candidate temporary root is not a real directory")
    shutil.rmtree(target)


def _atomic_json(path: Path, value: Any) -> str:
    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_bytes(data)


def _exclusive_json(path: Path, value: Any) -> str:
    """Publish one canonical JSON object without any overwrite surface."""

    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ControllerError(f"evidence already exists and cannot be replaced: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return sha256_bytes(data)


def _load_canonical(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ControllerError(f"invalid JSON object {path}: {exc}") from exc
    if not isinstance(value, dict) or raw != canonical_bytes(value):
        raise ControllerError(f"JSON evidence is not one canonical object: {path}")
    return value


def validate_package_review(review: Mapping[str, Any], *, definition_sha256: str, package_sha256: str) -> None:
    try:
        lifecycle.validate_package_review(
            review,
            definition_sha256=definition_sha256,
            package_sha256=package_sha256,
        )
    except lifecycle.LifecycleError as exc:
        raise ControllerError(f"package review is invalid: {exc}") from exc


class Controller:
    def __init__(self, config: ControllerConfig, hooks: ControllerHooks | None = None) -> None:
        self.config = config.normalized()
        self.hooks = hooks or ControllerHooks()
        self.definition, self.definition_sha256 = lifecycle.read_definition(DEFINITION_PATH)
        self.package_sha256 = strict_package_sha256()
        self.root = self.config.state_root
        self.state_path = self.root / "state.json"
        self.fixtures_path = self.root / "fixtures.json"

    def _assert_pins(self) -> None:
        pinned = self.definition["pinned_runtime"]
        checks = (
            (self.config.codex_executable, pinned["codex_native_sha256"], "Codex native binary"),
            (self.config.codex_launcher, pinned["codex_launcher_sha256"], "Codex launcher"),
            (self.config.node_executable, pinned["node_sha256"], "Node binary"),
            (self.config.codexbar_executable, pinned["codexbar_sha256"], "CodexBar observer"),
        )
        for path, expected, label in checks:
            if not path.is_file() or sha256_file(path) != expected:
                raise ControllerError(f"{label} does not match its exact pin: {path}")
        python_executable = Path(sys.executable).resolve(strict=True)
        python_version = ".".join(str(part) for part in sys.version_info[:3])
        if (
            sha256_file(python_executable) != pinned["controller_python_sha256"]
            or python_version != pinned["controller_python_version"]
        ):
            raise ControllerError(
                f"controller Python does not match its exact pin: {python_executable}"
            )
        if not self.config.auth_source.is_file():
            raise ControllerError("authenticated Codex source is missing")
        try:
            codexbar_version = subprocess.run(
                [str(self.config.codexbar_executable), "--version"],
                cwd=str(REPOSITORY_ROOT),
                env=SAFE_ENV,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
                text=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ControllerError(f"cannot inspect pinned CodexBar observer: {exc}") from exc
        if (
            codexbar_version.returncode != 0
            or codexbar_version.stdout.strip() != pinned["codexbar_version"]
        ):
            raise ControllerError("CodexBar observer version does not match its exact pin")
        self._assert_split_python_pin(ControllerError)

    def _assert_split_python_pin(
        self, failure: type[ControllerError]
    ) -> None:
        """Recheck the split Python byte and version pin at its use boundary."""

        pinned = self.definition["pinned_runtime"]
        try:
            matches_bytes = (
                SPLIT_PYTHON.is_file()
                and sha256_file(SPLIT_PYTHON) == pinned["split_python_sha256"]
            )
        except OSError as exc:
            raise failure(
                f"cannot inspect pinned split-verifier Python: {exc}"
            ) from exc
        if not matches_bytes:
            raise failure(
                f"split-verifier Python does not match its exact byte pin: {SPLIT_PYTHON}"
            )
        try:
            version = subprocess.run(
                [str(SPLIT_PYTHON), "--version"],
                cwd=str(REPOSITORY_ROOT),
                env=SAFE_ENV,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=10,
                text=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise failure(f"cannot inspect pinned split-verifier Python: {exc}") from exc
        if (
            version.returncode != 0
            or version.stdout.strip() != pinned["split_python_version"]
        ):
            raise failure(
                "split-verifier Python version does not match its exact pin"
            )

    def _assert_grok_pin(self, executable: Path) -> tuple[Path, dict[str, Any]]:
        pinned = self.definition["pinned_runtime"]
        try:
            resolved = executable.expanduser().resolve(strict=True)
            expected = Path(pinned["grok_executable"]).resolve(strict=True)
        except OSError as exc:
            raise ControllerError(f"pinned Grok executable is unavailable: {exc}") from exc
        if (
            resolved != expected
            or not resolved.is_file()
            or not os.access(resolved, os.X_OK)
            or sha256_file(resolved) != pinned["grok_executable_sha256"]
        ):
            raise ControllerError("Grok executable does not match its exact path and byte pin")
        return resolved, {
            "path": str(resolved),
            "sha256": pinned["grok_executable_sha256"],
            "expected_isolated_version": pinned["grok_isolated_cli_version"],
        }

    def _runtime_node(self, *, create: bool = False) -> Path:
        runtime_bin = self.root / "runtime" / "bin"
        node = runtime_bin / "node"
        expected = self.definition["pinned_runtime"]["node_sha256"]
        if create and not node.exists():
            runtime_bin.mkdir(parents=True, exist_ok=True)
            with self.config.node_executable.open("rb") as source, node.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            node.chmod(0o500)
        if not node.is_file() or sha256_file(node) != expected:
            raise ControllerError("dedicated copied Node runtime does not match its pin")
        if [path.name for path in runtime_bin.iterdir()] != ["node"]:
            raise ControllerError("dedicated runtime bin contains an unexpected executable")
        return node

    def _command_path(self) -> tuple[Path, ...]:
        return (self._runtime_node().parent, Path("/usr/bin"), Path("/bin"), Path("/usr/sbin"), Path("/sbin"))

    def _profile_runtime_roots(self) -> tuple[Path, ...]:
        if not COMMAND_LINE_TOOLS.is_dir():
            raise ControllerError("exact CommandLineTools runtime root is unavailable")
        expected_openssl = self.definition["pinned_runtime"]["openssl_config_sha256"]
        if (
            not NODE_OPENSSL_CONFIG.is_file()
            or sha256_file(NODE_OPENSSL_CONFIG) != expected_openssl
        ):
            raise ControllerError("Node OpenSSL configuration does not match its exact pin")
        return (self._runtime_node(), COMMAND_LINE_TOOLS, NODE_OPENSSL_CONFIG)

    @contextmanager
    def _locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "controller.lock").open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _load_state(self) -> dict[str, Any]:
        return lifecycle.load_state(
            self.state_path,
            self.definition,
            expected_definition_sha256=self.definition_sha256,
            expected_package_sha256=self.package_sha256,
        )

    def _save_state(self, state: Mapping[str, Any]) -> None:
        lifecycle.save_state(self.state_path, state, self.definition)

    def _require_package_review(self) -> None:
        review = _load_canonical(self.root / "package-review.json")
        validate_package_review(review, definition_sha256=self.definition_sha256, package_sha256=self.package_sha256)

    def _model_output_schema_compatibility(self) -> dict[str, Any]:
        schemas = {
            "implementation": PACKAGE_ROOT / "schemas" / "implementation.schema.json",
            "review": PACKAGE_ROOT / self.definition["reviewer"]["schema"],
        }
        return {
            "status": "PASS",
            "profile": "openai-structured-outputs-subset-2026-09-01",
            "schemas": {
                name: openai_strict_output_schema_receipt(path)
                for name, path in schemas.items()
            },
        }

    def preflight(self) -> dict[str, Any]:
        """Build and discriminate every fixture, then prove the native boundary."""

        self._assert_pins()
        self._require_package_review()
        schema_compatibility = self._model_output_schema_compatibility()
        with self._locked():
            if self.state_path.exists() or self.fixtures_path.exists():
                raise ControllerError("preflight is single-use for this state root")
            state = lifecycle.create_state(self.definition, definition_sha256=self.definition_sha256, package_sha256=self.package_sha256)
            self._runtime_node(create=True)
            fixture_root = self.root / "fixtures"
            sources = {
                "use-grok": self.config.use_grok_repo,
                "karpathy-pointer": self.config.karpathy_repo,
                "openbot-acp": self.config.openbot_repo,
            }
            built = fixtures.build_fixtures(
                definition=self.definition,
                sources=sources,
                controller_root=fixture_root,
                openbot_runtime_source=self.config.openbot_runtime_source,
                package_root=PACKAGE_ROOT,
            )
            fixture_hashes = {task: str(receipt["candidate_manifest"]["sha256"]) for task, receipt in built.items()}
            discrimination: dict[str, Any] = {}
            deadline = time.monotonic() + 900
            for task, receipt in built.items():
                baseline = self._verify(task, Path(receipt["paths"]["candidate"]), deadline)
                known = self._verify(task, Path(receipt["paths"]["known_good"]), deadline)
                if baseline.get("public") == "PASS" or baseline.get("hidden") == "PASS":
                    raise ControllerError(f"baseline unexpectedly passes a verifier: {task}")
                if known.get("public") != "PASS" or known.get("hidden") != "PASS":
                    raise ControllerError(f"known-good fixture does not pass both verifiers: {task}")
                discrimination[task] = {"baseline": baseline, "known_good": known}

            expected_bindings = self._expected_preflight_bindings(built)
            before_bindings = self._observe_preflight_bindings(built)
            if before_bindings != expected_bindings:
                raise ControllerError("fixture or package binding changed before native preflight")
            probe_receipt = self._native_preflight(built, fixture_hashes)
            split_separation = self._split_separation_preflight(built)
            self._validate_split_separation_receipt(split_separation)
            after_bindings = self._observe_preflight_bindings(built)
            if after_bindings != expected_bindings:
                raise ControllerError("fixture or package binding changed during native preflight")
            telemetry_compatibility: dict[str, Any]
            quota_compatibility: dict[str, Any]
            try:
                telemetry_compatibility = {
                    "status": "PASS",
                    "receipt": telemetry.telemetry_compatibility_receipt(),
                }
            except Exception as exc:
                telemetry_compatibility = {
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            try:
                quota_snapshot = self._quota()
                telemetry.validate_normalized_quota_snapshot(quota_snapshot)
                quota_compatibility = {
                    "status": "PASS",
                    "snapshot": dict(quota_snapshot),
                    "observer": self._quota_observer_receipt(),
                }
            except Exception as exc:
                quota_compatibility = {
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            receipt = {
                "status": (
                    "PASS"
                    if probe_receipt.get("status") == "PASS"
                    and split_separation.get("status") == "PASS"
                    and schema_compatibility["status"] == "PASS"
                    and telemetry_compatibility["status"] == "PASS"
                    and quota_compatibility["status"] == "PASS"
                    else "FAIL"
                ),
                "probe_receipt": probe_receipt,
                "split_separation": split_separation,
                "controller_binding_recheck": {
                    "expected": expected_bindings,
                    "before": before_bindings,
                    "after": after_bindings,
                    "matched": True,
                },
            }
            status = receipt["status"]
            combined = {
                "schema_version": 1,
                "status": status,
                "no_model_calls": True,
                "definition_sha256": self.definition_sha256,
                "package_sha256": self.package_sha256,
                "fixture_sha256": fixture_hashes,
                "discrimination": discrimination,
                "native": receipt,
                "model_output_schema_compatibility": schema_compatibility,
                "telemetry_compatibility": telemetry_compatibility,
                "quota_compatibility": quota_compatibility,
            }
            receipt_hash = _atomic_json(self.root / "preflight-receipt.json", combined)
            _atomic_json(self.fixtures_path, built)
            state = lifecycle.record_preflight(
                state,
                self.definition,
                status=status,
                receipt_sha256=receipt_hash,
                observed_definition_sha256=self.definition_sha256,
                observed_package_sha256=self.package_sha256,
            )
            self._save_state(state)
            if status != "PASS":
                raise ControllerError("native preflight failed")
            return combined

    def _expected_preflight_bindings(self, built: Mapping[str, Any]) -> dict[str, Any]:
        trees: dict[str, dict[str, str]] = {}
        manifest_keys = {
            "base_export": "base_export_manifest",
            "historical_export": "historical_export_manifest",
            "candidate": "candidate_manifest",
            "known_good": "known_good_manifest",
        }
        for task_id, record in built.items():
            trees[task_id] = {
                label: str(record[manifest_key]["sha256"])
                for label, manifest_key in manifest_keys.items()
            }
        return {"package_sha256": self.package_sha256, "fixture_trees": trees}

    def _observe_preflight_bindings(self, built: Mapping[str, Any]) -> dict[str, Any]:
        frozen = fixtures.load_frozen_v2(self.definition, package_root=PACKAGE_ROOT)
        trees: dict[str, dict[str, str]] = {}
        for task_id, record in built.items():
            trees[task_id] = {
                label: str(
                    frozen.tree_manifest.build_tree_manifest(
                        Path(record["paths"][label])
                    )["sha256"]
                )
                for label in ("base_export", "historical_export", "candidate", "known_good")
            }
        return {"package_sha256": strict_package_sha256(), "fixture_trees": trees}

    def _native_preflight(self, built: Mapping[str, Any], fixture_hashes: Mapping[str, str]) -> Mapping[str, Any]:
        if self.hooks.preflight is not None:
            return self.hooks.preflight(built=built, fixture_hashes=fixture_hashes)
        try:
            module = importlib.import_module("preflight")
        except ImportError as exc:
            raise ControllerError("native preflight module is unavailable") from exc
        if not hasattr(module, "run_native_preflight"):
            raise ControllerError("native preflight module lacks run_native_preflight")
        probe_root = self.root / "native-preflight"
        candidate = Path(built["use-grok"]["paths"]["candidate"])
        paths = isolation.CodexPaths(
            candidate_root=candidate,
            home=probe_root / "home",
            codex_home=probe_root / "codex-home",
            codex_sqlite_home=probe_root / "sqlite",
            tmpdir=candidate / ".runner-tmp",
            auth_target=probe_root / "auth-target.json",
            controller_root=probe_root,
            memory_root=self.config.memory_root,
        )
        memory_markers = sorted(path for path in self.config.memory_root.rglob("*") if path.is_file())
        if not memory_markers:
            raise ControllerError("no real memory marker exists for the native denial probe")
        frozen_v2 = (PACKAGE_ROOT.parent / "model-routing-v2").resolve(strict=True)
        protected_read_paths: dict[str, Path] = {
            "hidden_v2": frozen_v2 / "verifiers" / "hidden.py",
            **{
                f"split_{name}": path
                for name, path in _split_package_paths().items()
            },
        }
        for task_id, record in built.items():
            changed = record.get("changed_paths")
            if not isinstance(changed, list) or not changed:
                raise ControllerError(f"fixture lacks a protected answer path: {task_id}")
            answer_path = str(changed[0])
            protected_read_paths[f"known_good_{task_id.replace('-', '_')}"] = Path(record["paths"]["known_good"]) / answer_path
            protected_read_paths[f"historical_{task_id.replace('-', '_')}"] = Path(record["paths"]["historical_export"]) / answer_path
        return module.run_native_preflight(
            codex_executable=self.config.codex_executable,
            probe_executable=PACKAGE_ROOT / "boundary_probe.py",
            definition_path=DEFINITION_PATH,
            paths=paths,
            bindings=module.PreflightBindings(package_sha256=self.package_sha256, fixture_sha256=fixture_hashes),
            real_memory_marker=memory_markers[0],
            expected_codex_sha256=self.definition["pinned_runtime"]["codex_native_sha256"],
            runtime_roots=self._profile_runtime_roots(),
            protected_read_paths=protected_read_paths,
        )

    def _run_seatbelt_read_probe(
        self,
        *,
        target: Path,
        cwd: Path,
        expected_category: str,
        profile: str | None,
    ) -> dict[str, Any]:
        """Read one byte without printing it and classify the exact OS result."""

        if expected_category not in {"success", "policy_denied"}:
            raise ValueError("seatbelt probe expectation is invalid")
        command = [
            str(SPLIT_PYTHON),
            "-I",
            "-B",
            "-c",
            SEATBELT_READ_PROBE,
            str(target.resolve(strict=True)),
        ]
        if profile is not None:
            sandbox = Path("/usr/bin/sandbox-exec")
            if not sandbox.is_file():
                raise BoundaryFailure("native sandbox-exec is unavailable")
            command = [str(sandbox), "-p", profile, *command]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd.resolve(strict=True)),
                env={
                    **SAFE_ENV,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BoundaryFailure(f"Seatbelt separation probe failed: {exc}") from exc
        try:
            payload = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundaryFailure("Seatbelt separation probe output is malformed") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"category", "errno"}
            or completed.stdout != canonical_bytes(payload)
        ):
            raise BoundaryFailure("Seatbelt separation probe output fields differ")
        if expected_category == "success":
            valid = (
                completed.returncode == 0
                and payload == {"category": "success", "errno": None}
            )
        else:
            valid = (
                completed.returncode == 77
                and payload.get("category") == "policy_denied"
                and payload.get("errno") in {1, 13}
            )
        if not valid:
            raise BoundaryFailure(
                "Seatbelt separation probe did not produce the required OS result",
                evidence={
                    "expected_category": expected_category,
                    "returncode": completed.returncode,
                    "payload": payload,
                    "stderr_sha256": sha256_bytes(completed.stderr),
                },
            )
        return {
            "category": expected_category,
            "errno": payload["errno"],
            "returncode": completed.returncode,
            "elapsed_seconds": time.monotonic() - started,
            "stdout_sha256": sha256_bytes(completed.stdout),
            "stderr_sha256": sha256_bytes(completed.stderr),
        }

    def _prove_seatbelt_denial(
        self, *, profile: str, target: Path, control: Path, cwd: Path
    ) -> dict[str, Any]:
        """Pair each policy denial with content-free exact-path controls."""

        resolved_target = target.resolve(strict=True)
        resolved_control = control.resolve(strict=True)
        return {
            "target": str(resolved_target),
            "target_sha256": sha256_file(resolved_target),
            "control": str(resolved_control),
            "control_sha256": sha256_file(resolved_control),
            "unsandboxed_target_control": self._run_seatbelt_read_probe(
                target=resolved_target,
                cwd=cwd,
                expected_category="success",
                profile=None,
            ),
            "sandboxed_allowed_control": self._run_seatbelt_read_probe(
                target=resolved_control,
                cwd=cwd,
                expected_category="success",
                profile=profile,
            ),
            "sandboxed_target": self._run_seatbelt_read_probe(
                target=resolved_target,
                cwd=cwd,
                expected_category="policy_denied",
                profile=profile,
            ),
        }

    def _prove_seatbelt_read(
        self, *, profile: str, target: Path, cwd: Path
    ) -> dict[str, Any]:
        resolved_target = target.resolve(strict=True)
        return {
            "target": str(resolved_target),
            "target_sha256": sha256_file(resolved_target),
            "unsandboxed": self._run_seatbelt_read_probe(
                target=resolved_target,
                cwd=cwd,
                expected_category="success",
                profile=None,
            ),
            "sandboxed": self._run_seatbelt_read_probe(
                target=resolved_target,
                cwd=cwd,
                expected_category="success",
                profile=profile,
            ),
        }

    def _run_seatbelt_signal_zero_probe(
        self,
        *,
        target_pid: int,
        target_kind: str,
        cwd: Path,
        expected_category: str,
        profile: str | None,
    ) -> dict[str, Any]:
        """Observe one exact PID or process group with signal 0."""

        if target_pid <= 1 or target_kind not in {"pid", "pgid"}:
            raise ValueError("Seatbelt signal probe target is invalid")
        if expected_category not in {"success", "policy_denied"}:
            raise ValueError("Seatbelt signal probe expectation is invalid")
        command = [
            str(SPLIT_PYTHON),
            "-I",
            "-B",
            "-c",
            SEATBELT_SIGNAL_ZERO_PROBE,
            str(target_pid),
            target_kind,
        ]
        if profile is not None:
            sandbox = Path("/usr/bin/sandbox-exec")
            if not sandbox.is_file():
                raise BoundaryFailure("native sandbox-exec is unavailable")
            command = [str(sandbox), "-p", profile, *command]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd.resolve(strict=True)),
                env={
                    **SAFE_ENV,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BoundaryFailure(f"Seatbelt signal probe failed: {exc}") from exc
        try:
            payload = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundaryFailure("Seatbelt signal probe output is malformed") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"category", "errno", "target_kind"}
            or completed.stdout != canonical_bytes(payload)
            or payload["target_kind"] != target_kind
        ):
            raise BoundaryFailure("Seatbelt signal probe output fields differ")
        if expected_category == "success":
            valid = (
                completed.returncode == 0
                and payload["category"] == "success"
                and payload["errno"] is None
            )
        else:
            valid = (
                completed.returncode == 77
                and payload["category"] == "policy_denied"
                and payload["errno"] in {1, 13}
            )
        if not valid:
            raise BoundaryFailure(
                "Seatbelt signal probe did not produce the required OS result",
                evidence={
                    "expected_category": expected_category,
                    "returncode": completed.returncode,
                    "payload": payload,
                    "stderr_sha256": sha256_bytes(completed.stderr),
                },
            )
        return {
            "category": expected_category,
            "elapsed_seconds": time.monotonic() - started,
            "errno": payload["errno"],
            "returncode": completed.returncode,
            "stderr_sha256": sha256_bytes(completed.stderr),
            "stdout_sha256": sha256_bytes(completed.stdout),
            "target_kind": target_kind,
            "target_pid": target_pid,
        }

    def _run_seatbelt_child_signal_probe(
        self, *, profile: str, cwd: Path
    ) -> dict[str, Any]:
        """Prove the worker can signal a direct PID and reparented child group."""

        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.is_file():
            raise BoundaryFailure("native sandbox-exec is unavailable")
        resolved_cwd = cwd.resolve(strict=True)
        group_ledger = resolved_cwd / "worker-child-signal-groups.json"
        descendant_file = resolved_cwd / "worker-child-signal-descendant.json"
        if any(path.exists() or path.is_symlink() for path in (group_ledger, descendant_file)):
            raise BoundaryFailure("worker child signal probe is not single-use")
        command = [
            str(sandbox),
            "-p",
            profile,
            str(SPLIT_PYTHON),
            "-I",
            "-B",
            "-c",
            SEATBELT_CHILD_SIGNAL_PROBE,
            str(group_ledger),
            str(descendant_file),
        ]
        started = time.monotonic()
        completed: subprocess.CompletedProcess[bytes] | None = None
        group_ids: dict[str, int] = {}
        descendant_pid: int | None = None

        def load_record(path: Path, fields: set[str]) -> dict[str, int]:
            if not path.is_file() or path.is_symlink():
                return {}
            raw = path.read_bytes()
            loaded = json.loads(raw)
            if (
                not isinstance(loaded, dict)
                or set(loaded) != fields
                or any(
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value <= 1
                    for value in loaded.values()
                )
                or raw
                != json.dumps(loaded, sort_keys=True, separators=(",", ":")).encode(
                    "ascii"
                )
            ):
                return {}
            return loaded

        try:
            completed = subprocess.run(
                command,
                cwd=str(resolved_cwd),
                env={
                    **SAFE_ENV,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
            group_ids = load_record(
                group_ledger, {"group_leader_pgid", "pid_child_pgid"}
            )
            descendant = load_record(descendant_file, {"inherited_descendant_pid"})
            descendant_pid = descendant.get("inherited_descendant_pid")
        except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundaryFailure(f"Seatbelt child signal probe failed: {exc}") from exc
        finally:
            if not group_ids:
                try:
                    group_ids = load_record(
                        group_ledger, {"group_leader_pgid", "pid_child_pgid"}
                    )
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    group_ids = {}
            for group_id in group_ids.values():
                try:
                    os.killpg(group_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if completed is None:
            raise BoundaryFailure("Seatbelt child signal probe did not complete")
        try:
            payload = json.loads(completed.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundaryFailure("Seatbelt child signal probe output is malformed") from exc
        expected_fields = {
            "category",
            "descendant_after_errno",
            "descendant_observed_after_leader_exit",
            "errno",
            "group_after_errno",
            "group_leader_pid",
            "group_leader_returncode",
            "group_observed_after_leader_exit",
            "group_signal",
            "inherited_descendant_pid",
            "pid_after_errno",
            "pid_child_pid",
            "pid_returncode",
        }
        if (
            not isinstance(payload, dict)
            or set(payload) != expected_fields
            or completed.stdout != canonical_bytes(payload)
            or group_ids.get("pid_child_pgid") != payload.get("pid_child_pid")
            or group_ids.get("group_leader_pgid")
            != payload.get("group_leader_pid")
            or descendant_pid != payload.get("inherited_descendant_pid")
        ):
            raise BoundaryFailure("Seatbelt child signal probe output fields differ")
        if not (
            completed.returncode == 0
            and payload["category"] == "success"
            and payload["errno"] is None
            and payload["pid_returncode"] == -signal.SIGTERM
            and payload["group_leader_returncode"] == 0
            and payload["group_signal"] == "SIGKILL"
            and payload["group_observed_after_leader_exit"] is True
            and payload["descendant_observed_after_leader_exit"] is True
            and payload["pid_after_errno"] == errno.ESRCH
            and payload["group_after_errno"] == errno.ESRCH
            and payload["descendant_after_errno"] == errno.ESRCH
            and len(
                {
                    payload["pid_child_pid"],
                    payload["group_leader_pid"],
                    payload["inherited_descendant_pid"],
                }
            )
            == 3
        ):
            raise BoundaryFailure(
                "worker profile could not signal its inherited child process group",
                evidence={
                    "returncode": completed.returncode,
                    "payload": payload,
                    "stderr_sha256": sha256_bytes(completed.stderr),
                },
            )
        return {
            **payload,
            "elapsed_seconds": time.monotonic() - started,
            "returncode": completed.returncode,
            "stderr_sha256": sha256_bytes(completed.stderr),
            "stdout_sha256": sha256_bytes(completed.stdout),
        }

    def _prove_openbot_signal_scope(
        self, *, driver_profile: str, worker_profile: str, cwd: Path
    ) -> dict[str, Any]:
        """Prove exact observer, same-sandbox, and unrelated signal scopes."""

        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.is_file():
            raise BoundaryFailure("native sandbox-exec is unavailable")
        resolved_cwd = cwd.resolve(strict=True)
        ready_file = resolved_cwd / "worker-unrelated-sandbox-control.json"
        if ready_file.exists() or ready_file.is_symlink():
            raise BoundaryFailure("unrelated signal control probe is not single-use")
        control: subprocess.Popen[bytes] | None = None
        try:
            control = subprocess.Popen(
                [
                    str(sandbox),
                    "-p",
                    worker_profile,
                    str(SPLIT_PYTHON),
                    "-I",
                    "-B",
                    "-c",
                    SEATBELT_SIGNAL_CONTROL,
                    str(ready_file),
                ],
                cwd=str(resolved_cwd),
                env={
                    **SAFE_ENV,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            ready_payload: dict[str, Any] | None = None
            ready_deadline = time.monotonic() + 2
            while time.monotonic() < ready_deadline:
                if control.poll() is not None:
                    raise BoundaryFailure(
                        "separate-sandbox signal control exited before readiness"
                    )
                if ready_file.is_file() and not ready_file.is_symlink():
                    try:
                        raw_ready = ready_file.read_bytes()
                        candidate_ready = json.loads(raw_ready)
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                        pass
                    else:
                        if raw_ready == json.dumps(
                            candidate_ready, sort_keys=True, separators=(",", ":")
                        ).encode("ascii"):
                            ready_payload = candidate_ready
                            break
                time.sleep(0.01)
            if (
                not isinstance(ready_payload, dict)
                or set(ready_payload) != {"process_group_id", "process_id"}
                or ready_payload["process_id"] != control.pid
                or ready_payload["process_group_id"] != control.pid
            ):
                raise BoundaryFailure(
                    "separate-sandbox signal control readiness differs"
                )
            if control.poll() is not None:
                raise BoundaryFailure("unrelated signal control did not remain live")
            signal_checks = {
                "control": {
                    "alive_after": False,
                    "alive_before": True,
                    "launch": "separate_sandbox_exec_invocation",
                    "process_group_id": control.pid,
                    "process_id": control.pid,
                    "worker_profile_sha256": sha256_bytes(
                        worker_profile.encode("utf-8")
                    ),
                },
                "driver_pgid_observation": self._run_seatbelt_signal_zero_probe(
                    target_pid=control.pid,
                    target_kind="pgid",
                    cwd=cwd,
                    expected_category="success",
                    profile=driver_profile,
                ),
                "driver_pid_observation": self._run_seatbelt_signal_zero_probe(
                    target_pid=control.pid,
                    target_kind="pid",
                    cwd=cwd,
                    expected_category="success",
                    profile=driver_profile,
                ),
                "worker_same_sandbox_signaling": self._run_seatbelt_child_signal_probe(
                    profile=worker_profile,
                    cwd=cwd,
                ),
                "worker_unrelated_pgid_denial": self._run_seatbelt_signal_zero_probe(
                    target_pid=control.pid,
                    target_kind="pgid",
                    cwd=cwd,
                    expected_category="policy_denied",
                    profile=worker_profile,
                ),
                "worker_unrelated_pid_denial": self._run_seatbelt_signal_zero_probe(
                    target_pid=control.pid,
                    target_kind="pid",
                    cwd=cwd,
                    expected_category="policy_denied",
                    profile=worker_profile,
                ),
            }
            signal_checks["control"]["alive_after"] = control.poll() is None
            if signal_checks["control"]["alive_after"] is not True:
                raise BoundaryFailure("signal scope probe changed the unrelated control")
            return signal_checks
        except OSError as exc:
            raise BoundaryFailure(f"cannot run OpenBot signal scope probe: {exc}") from exc
        finally:
            if control is not None and control.poll() is None:
                try:
                    os.killpg(control.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if control is not None:
                try:
                    control.wait(timeout=2)
                except subprocess.TimeoutExpired as exc:
                    raise BoundaryFailure(
                        "unrelated signal control survived cleanup"
                    ) from exc

    def _validate_split_separation_receipt(
        self, receipt: Mapping[str, Any]
    ) -> None:
        """Reject incomplete or weak separation evidence before preflight PASS."""

        def validate_probe(value: Any, expected: str) -> None:
            if not isinstance(value, Mapping) or set(value) != {
                "category",
                "errno",
                "returncode",
                "elapsed_seconds",
                "stdout_sha256",
                "stderr_sha256",
            }:
                raise BoundaryFailure("split separation probe receipt fields differ")
            elapsed = value["elapsed_seconds"]
            if (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, (int, float))
                or elapsed < 0
                or not HASH_RE.fullmatch(str(value["stdout_sha256"]))
                or not HASH_RE.fullmatch(str(value["stderr_sha256"]))
            ):
                raise BoundaryFailure("split separation probe receipt values differ")
            if expected == "success":
                valid = (
                    value["category"] == "success"
                    and value["errno"] is None
                    and value["returncode"] == 0
                )
            else:
                valid = (
                    value["category"] == "policy_denied"
                    and value["errno"] in {1, 13}
                    and value["returncode"] == 77
                )
            if not valid:
                raise BoundaryFailure("split separation probe result is invalid")

        def validate_target(value: Mapping[str, Any], prefix: str) -> None:
            path_value = value.get(prefix)
            digest = value.get(f"{prefix}_sha256")
            if not isinstance(path_value, str) or not HASH_RE.fullmatch(str(digest)):
                raise BoundaryFailure("split separation target binding is invalid")
            try:
                path = Path(path_value).resolve(strict=True)
            except OSError as exc:
                raise BoundaryFailure(
                    "split separation target is unavailable"
                ) from exc
            if str(path) != path_value or not path.is_file() or sha256_file(path) != digest:
                raise BoundaryFailure("split separation target binding differs")

        def validate_denial(value: Any) -> None:
            if not isinstance(value, Mapping) or set(value) != {
                "target",
                "target_sha256",
                "control",
                "control_sha256",
                "unsandboxed_target_control",
                "sandboxed_allowed_control",
                "sandboxed_target",
            }:
                raise BoundaryFailure("split separation denial receipt fields differ")
            validate_target(value, "target")
            validate_target(value, "control")
            validate_probe(value["unsandboxed_target_control"], "success")
            validate_probe(value["sandboxed_allowed_control"], "success")
            validate_probe(value["sandboxed_target"], "policy_denied")

        def validate_read(value: Any) -> None:
            if not isinstance(value, Mapping) or set(value) != {
                "target",
                "target_sha256",
                "unsandboxed",
                "sandboxed",
            }:
                raise BoundaryFailure("split separation read receipt fields differ")
            validate_target(value, "target")
            validate_probe(value["unsandboxed"], "success")
            validate_probe(value["sandboxed"], "success")

        def validate_signal_zero(value: Any, expected: str, target_kind: str) -> None:
            if not isinstance(value, Mapping) or set(value) != {
                "category",
                "elapsed_seconds",
                "errno",
                "returncode",
                "stderr_sha256",
                "stdout_sha256",
                "target_kind",
                "target_pid",
            }:
                raise BoundaryFailure("split signal-zero receipt fields differ")
            validate_probe(
                {
                    key: value[key]
                    for key in (
                        "category",
                        "elapsed_seconds",
                        "errno",
                        "returncode",
                        "stderr_sha256",
                        "stdout_sha256",
                    )
                },
                expected,
            )
            if (
                value["target_kind"] != target_kind
                or not isinstance(value["target_pid"], int)
                or isinstance(value["target_pid"], bool)
                or value["target_pid"] <= 1
            ):
                raise BoundaryFailure("split signal-zero target differs")

        def validate_child_signal(value: Any) -> None:
            if not isinstance(value, Mapping) or set(value) != {
                "category",
                "descendant_after_errno",
                "descendant_observed_after_leader_exit",
                "elapsed_seconds",
                "errno",
                "group_after_errno",
                "group_leader_pid",
                "group_leader_returncode",
                "group_observed_after_leader_exit",
                "group_signal",
                "inherited_descendant_pid",
                "pid_after_errno",
                "pid_child_pid",
                "pid_returncode",
                "returncode",
                "stderr_sha256",
                "stdout_sha256",
            }:
                raise BoundaryFailure("split child signal receipt fields differ")
            if (
                value["category"] != "success"
                or value["errno"] is not None
                or value["returncode"] != 0
                or value["pid_returncode"] != -signal.SIGTERM
                or value["group_leader_returncode"] != 0
                or value["group_signal"] != "SIGKILL"
                or value["group_observed_after_leader_exit"] is not True
                or value["descendant_observed_after_leader_exit"] is not True
                or value["pid_after_errno"] != errno.ESRCH
                or value["group_after_errno"] != errno.ESRCH
                or value["descendant_after_errno"] != errno.ESRCH
                or any(
                    not isinstance(value[name], int)
                    or isinstance(value[name], bool)
                    or value[name] <= 1
                    for name in (
                        "pid_child_pid",
                        "group_leader_pid",
                        "inherited_descendant_pid",
                    )
                )
                or len(
                    {
                        value["pid_child_pid"],
                        value["group_leader_pid"],
                        value["inherited_descendant_pid"],
                    }
                )
                != 3
                or isinstance(value["elapsed_seconds"], bool)
                or not isinstance(value["elapsed_seconds"], (int, float))
                or value["elapsed_seconds"] < 0
                or not HASH_RE.fullmatch(str(value["stdout_sha256"]))
                or not HASH_RE.fullmatch(str(value["stderr_sha256"]))
            ):
                raise BoundaryFailure("split child signal receipt values differ")

        if not isinstance(receipt, Mapping) or set(receipt) != {
            "status",
            "no_model_calls",
            "accepted_denial_errnos",
            "tasks",
        }:
            raise BoundaryFailure("split separation receipt fields differ")
        if (
            receipt["status"] != "PASS"
            or receipt["no_model_calls"] is not True
            or receipt["accepted_denial_errnos"] != [1, 13]
        ):
            raise BoundaryFailure("split separation receipt cannot authorize preflight")
        tasks = receipt["tasks"]
        if not isinstance(tasks, Mapping) or set(tasks) != {
            "use-grok",
            "karpathy-pointer",
            "openbot-acp",
        }:
            raise BoundaryFailure("split separation task receipts differ")
        common_denials = {
            "v2_hidden_driver",
            "openbot_hidden_driver",
            "hidden_package",
            "protocol_source",
            "runner_source",
        }
        for task_id, task_receipt in tasks.items():
            if not isinstance(task_receipt, Mapping) or set(task_receipt) != {
                "status",
                "driver_profile_sha256",
                "worker_profile_sha256",
                "worker_denials",
                "driver_checks",
                "peer_source_checks",
                "signal_checks",
            }:
                raise BoundaryFailure("split separation task receipt fields differ")
            if (
                task_receipt["status"] != "PASS"
                or not HASH_RE.fullmatch(str(task_receipt["driver_profile_sha256"]))
                or not HASH_RE.fullmatch(str(task_receipt["worker_profile_sha256"]))
            ):
                raise BoundaryFailure("split separation task receipt values differ")
            worker_denials = task_receipt["worker_denials"]
            expected_denials = set(common_denials)
            if task_id != "openbot-acp":
                expected_denials.add("frozen_hidden_source")
            if not isinstance(worker_denials, Mapping) or set(worker_denials) != expected_denials:
                raise BoundaryFailure("split worker denial receipts differ")
            for denial in worker_denials.values():
                validate_denial(denial)
            driver_checks = task_receipt["driver_checks"]
            if task_id == "openbot-acp":
                if not isinstance(driver_checks, Mapping) or set(driver_checks) != {
                    "candidate_acp",
                    "candidate_tsx_loader",
                }:
                    raise BoundaryFailure("OpenBot driver separation checks differ")
                for denial in driver_checks.values():
                    validate_denial(denial)
            else:
                if not isinstance(driver_checks, Mapping) or set(driver_checks) != {
                    "candidate_read_is_intentionally_allowed",
                    "candidate_command_execution_owner",
                }:
                    raise BoundaryFailure("v2 driver separation checks differ")
                if driver_checks["candidate_command_execution_owner"] != "worker":
                    raise BoundaryFailure("v2 candidate command owner differs")
                validate_read(driver_checks["candidate_read_is_intentionally_allowed"])
            peer_checks = task_receipt["peer_source_checks"]
            if not isinstance(peer_checks, Mapping) or set(peer_checks) != {
                "driver",
                "worker",
            }:
                raise BoundaryFailure("split peer source checks differ")
            validate_read(peer_checks["driver"])
            validate_read(peer_checks["worker"])
            signal_checks = task_receipt["signal_checks"]
            if task_id != "openbot-acp":
                if signal_checks is not None:
                    raise BoundaryFailure("v2 split task unexpectedly grants signal")
                continue
            if not isinstance(signal_checks, Mapping) or set(signal_checks) != {
                "control",
                "driver_pgid_observation",
                "driver_pid_observation",
                "worker_same_sandbox_signaling",
                "worker_unrelated_pgid_denial",
                "worker_unrelated_pid_denial",
            }:
                raise BoundaryFailure("OpenBot signal separation checks differ")
            control = signal_checks["control"]
            if not isinstance(control, Mapping) or set(control) != {
                "alive_after",
                "alive_before",
                "launch",
                "process_group_id",
                "process_id",
                "worker_profile_sha256",
            }:
                raise BoundaryFailure("OpenBot signal control fields differ")
            control_pid = control["process_id"]
            if (
                control["alive_before"] is not True
                or control["alive_after"] is not True
                or not isinstance(control_pid, int)
                or isinstance(control_pid, bool)
                or control_pid <= 1
                or control["process_group_id"] != control_pid
                or control["launch"] != "separate_sandbox_exec_invocation"
                or control["worker_profile_sha256"]
                != task_receipt["worker_profile_sha256"]
            ):
                raise BoundaryFailure("OpenBot signal control values differ")
            for name, expected, target_kind in (
                ("driver_pid_observation", "success", "pid"),
                ("driver_pgid_observation", "success", "pgid"),
                ("worker_unrelated_pid_denial", "policy_denied", "pid"),
                ("worker_unrelated_pgid_denial", "policy_denied", "pgid"),
            ):
                validate_signal_zero(signal_checks[name], expected, target_kind)
                if signal_checks[name]["target_pid"] != control_pid:
                    raise BoundaryFailure("OpenBot signal probe target binding differs")
            validate_child_signal(signal_checks["worker_same_sandbox_signaling"])

    @staticmethod
    def _existing_candidate_answer(candidate: Path, changed: Any) -> Path:
        """Select one changed ordinary file that already exists in the baseline."""

        if not isinstance(changed, list) or not changed:
            raise BoundaryFailure("split preflight fixture lacks an answer path")
        resolved_candidate = candidate.resolve(strict=True)
        for value in changed:
            if not isinstance(value, str) or not value:
                raise BoundaryFailure("split preflight answer path is invalid")
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise BoundaryFailure("split preflight answer path escapes the fixture")
            target = resolved_candidate / relative
            try:
                state = target.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
                return target
        raise BoundaryFailure(
            "split preflight fixture has no existing changed answer file"
        )

    def _split_separation_preflight(
        self, built: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Prove the production peer profiles separate answers from workers."""

        self._assert_split_python_pin(BoundaryFailure)
        package_paths = _split_package_paths()
        for name, path in package_paths.items():
            if not path.is_file() or path.is_symlink():
                raise BoundaryFailure(f"split package path is unavailable: {name}")
        root = self.root / "split-separation-preflight"
        try:
            root.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise BoundaryFailure("split separation preflight is not single-use") from exc
        frozen = fixtures.load_frozen_v2(self.definition, package_root=PACKAGE_ROOT)
        frozen_hidden = frozen.root / "verifiers" / "hidden.py"
        common_worker_denials = {
            "v2_hidden_driver": package_paths["v2_driver"],
            "openbot_hidden_driver": package_paths["openbot_driver"],
            "hidden_package": package_paths["hidden_package"],
            "protocol_source": package_paths["protocol"],
            "runner_source": package_paths["runner"],
        }
        tasks: dict[str, Any] = {}
        for task_id in ("use-grok", "karpathy-pointer", "openbot-acp"):
            record = built.get(task_id)
            if not isinstance(record, Mapping):
                raise BoundaryFailure(f"split preflight fixture is missing: {task_id}")
            candidate = Path(str(record["paths"]["candidate"])).resolve(strict=True)
            task_root = root / task_id
            shared = task_root / "shared"
            driver_runtime = task_root / "driver-runtime"
            worker_runtime = task_root / "worker-runtime"
            for path in (shared, driver_runtime, worker_runtime):
                path.mkdir(parents=True, mode=0o700)
            control = shared / "content-free-positive-control"
            control.write_bytes(b"p")
            if task_id in {"use-grok", "karpathy-pointer"}:
                profiles = _v2_split_profiles(
                    candidate=candidate,
                    shared=shared,
                    hidden=frozen_hidden,
                    driver_runtime=driver_runtime,
                    worker_runtime=worker_runtime,
                )
                worker_denials = {
                    **common_worker_denials,
                    "frozen_hidden_source": frozen_hidden,
                }
                changed = record.get("changed_paths")
                candidate_read = self._existing_candidate_answer(candidate, changed)
                driver_checks = {
                    "candidate_read_is_intentionally_allowed": (
                        self._prove_seatbelt_read(
                            profile=profiles["driver"][0],
                            target=candidate_read,
                            cwd=shared,
                        )
                    ),
                    "candidate_command_execution_owner": "worker",
                }
                signal_checks = None
            else:
                profiles = _openbot_split_profiles(
                    node=self._runtime_node(),
                    candidate=candidate,
                    shared=shared,
                )
                worker_denials = dict(common_worker_denials)
                candidate_acp = candidate / "daemon" / "src" / "acp.ts"
                loader = candidate / "node_modules" / "tsx" / "dist" / "loader.mjs"
                driver_checks = {
                    "candidate_acp": self._prove_seatbelt_denial(
                        profile=profiles["driver"][0],
                        target=candidate_acp,
                        control=control,
                        cwd=shared,
                    ),
                    "candidate_tsx_loader": self._prove_seatbelt_denial(
                        profile=profiles["driver"][0],
                        target=loader,
                        control=control,
                        cwd=shared,
                    ),
                }
                signal_checks = self._prove_openbot_signal_scope(
                    driver_profile=profiles["driver"][0],
                    worker_profile=profiles["worker"][0],
                    cwd=shared,
                )
            worker_checks = {
                name: self._prove_seatbelt_denial(
                    profile=profiles["worker"][0],
                    target=path,
                    control=control,
                    cwd=shared,
                )
                for name, path in worker_denials.items()
            }
            peer_source_checks = {
                "driver": self._prove_seatbelt_read(
                    profile=profiles["driver"][0],
                    target=(
                        package_paths["openbot_driver"]
                        if task_id == "openbot-acp"
                        else package_paths["v2_driver"]
                    ),
                    cwd=shared,
                ),
                "worker": self._prove_seatbelt_read(
                    profile=profiles["worker"][0],
                    target=(
                        package_paths["openbot_worker"]
                        if task_id == "openbot-acp"
                        else package_paths["v2_worker"]
                    ),
                    cwd=shared,
                ),
            }
            tasks[task_id] = {
                "status": "PASS",
                "driver_profile_sha256": profiles["driver"][1],
                "worker_profile_sha256": profiles["worker"][1],
                "worker_denials": worker_checks,
                "driver_checks": driver_checks,
                "peer_source_checks": peer_source_checks,
                "signal_checks": signal_checks,
            }
        return {
            "status": "PASS",
            "no_model_calls": True,
            "accepted_denial_errnos": [1, 13],
            "tasks": tasks,
        }

    def _reserve(self, canary: bool) -> tuple[dict[str, Any], str, Path]:
        self._assert_pins()
        self._require_package_review()
        with self._locked():
            state = self._load_state()
            now = time.monotonic_ns()
            reserved = lifecycle.authorize_canary(state, self.definition, now_monotonic_ns=now) if canary else lifecycle.authorize_next(state, self.definition, now_monotonic_ns=now)
            cell_id = str(reserved["active_cell"]["cell_id"])
            attempt = self.root / "attempts" / cell_id
            attempt.parent.mkdir(parents=True, exist_ok=True)
            try:
                attempt.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise ControllerError(f"attempt already reserved; retry is forbidden: {cell_id}") from exc
            reservation = {"cell_id": cell_id, "attempt": 1, "definition_sha256": self.definition_sha256, "package_sha256": self.package_sha256, "reserved_at": utc_now()}
            _atomic_json(attempt / "reservation.json", reservation)
            self._save_state(reserved)
            return reserved, cell_id, attempt

    def run_canary(self) -> dict[str, Any]:
        state, cell_id, attempt = self._reserve(True)
        return self._run_reserved_fail_closed(state, cell_id, attempt)

    def run_next(self) -> dict[str, Any]:
        state, cell_id, attempt = self._reserve(False)
        return self._run_reserved_fail_closed(state, cell_id, attempt)

    def _run_reserved_fail_closed(self, state: dict[str, Any], cell_id: str, attempt: Path) -> dict[str, Any]:
        try:
            return self._run_reserved_cell(state, cell_id, attempt)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            with self._locked():
                current = self._load_state()
            active = current.get("active_cell")
            if not isinstance(active, Mapping) or active.get("cell_id") != cell_id:
                raise ControllerError(f"reserved cell failed after losing its active state: {error}") from exc
            now = time.monotonic_ns()
            deadline_ns = int(active["deadline_monotonic_ns"])
            status = (
                exc.terminal_status
                if isinstance(exc, TerminalControllerError)
                else "CONTROLLER_ERROR"
            )
            expected_artifact_sha256 = (
                active.get("implementation", {}).get("artifact_sha256")
                if isinstance(active.get("implementation"), Mapping)
                else None
            )
            artifact_error: ControllerError | None = None
            try:
                artifact, artifact_hash = self._load_attempt_artifact(
                    attempt,
                    expected_sha256=expected_artifact_sha256,
                )
            except ControllerError as evidence_error:
                artifact_error = evidence_error
                artifact = None
                artifact_hash = None
                status = "CONTROLLER_ERROR"
                error = f"{error}; artifact evidence failure: {evidence_error}"
            implementation_receipt = self._load_optional_receipt(
                attempt / "implementation-receipt.json"
            )
            verification_receipt = self._load_optional_receipt(
                attempt / "verification-receipt.json"
            )
            review_receipt = self._load_optional_receipt(
                attempt / "review-receipt.json"
            )
            attached_evidence = getattr(exc, "evidence", None)
            failure_evidence = (
                dict(attached_evidence)
                if isinstance(attached_evidence, Mapping)
                else {}
            )
            if artifact_error is not None:
                failure_evidence["artifact_evidence_error"] = str(artifact_error)
            timed_out = (
                artifact_error is None and isinstance(exc, StageTimeout)
            ) or (
                now >= deadline_ns
                and status not in lifecycle.HARD_STOP_STATUSES
            )
            terminal_status = "TIMEOUT" if timed_out else status
            result = self._terminal_payload(
                cell_id,
                terminal_status,
                implementation_receipt,
                verification_receipt,
                review_receipt,
                artifact=artifact,
                artifact_sha256=artifact_hash,
                error=error,
                failure_evidence=(
                    failure_evidence if failure_evidence else None
                ),
            )
            if terminal_status == "TIMEOUT":
                result_hash = sha256_bytes(canonical_bytes(result))
                terminal = lifecycle.expire_active_cell(current, self.definition, cell_id=cell_id, result_sha256=result_hash, now_monotonic_ns=max(now, deadline_ns))
            else:
                result_hash = sha256_bytes(canonical_bytes(result))
                terminal = lifecycle.record_active_failure(
                    current,
                    self.definition,
                    cell_id=cell_id,
                    status=terminal_status,
                    result_sha256=result_hash,
                    reason=error,
                    now_monotonic_ns=now,
                )
            return self._finish_attempt(terminal, attempt, result)

    def _checkpoint(self, state: Mapping[str, Any]) -> None:
        with self._locked():
            current = self._load_state()
            active = current.get("active_cell")
            replacement = state.get("active_cell")
            if not isinstance(active, Mapping) or not isinstance(replacement, Mapping) or active.get("cell_id") != replacement.get("cell_id"):
                raise ControllerError("active lifecycle state changed before checkpoint")
            self._save_state(state)

    def _copy_bound_fixture(
        self,
        state: Mapping[str, Any],
        task_id: str,
        destination: Path,
    ) -> tuple[Mapping[str, Any], dict[str, Any]]:
        preflight_path = self.root / "preflight-receipt.json"
        preflight = _load_canonical(preflight_path)
        if sha256_file(preflight_path) != state["preflight"]["receipt_sha256"]:
            raise ControllerError("preflight receipt no longer binds lifecycle state")
        fixtures_record = _load_canonical(self.fixtures_path)
        fixture = fixtures_record.get(task_id)
        if not isinstance(fixture, Mapping):
            raise ControllerError(f"fixture record is missing: {task_id}")
        expected = preflight.get("fixture_sha256", {}).get(task_id)
        candidate_manifest = fixture.get("candidate_manifest")
        if (
            not isinstance(expected, str)
            or not isinstance(candidate_manifest, Mapping)
            or candidate_manifest.get("sha256") != expected
        ):
            raise ControllerError("fixture record differs from preflight binding")
        source = Path(fixture["paths"]["candidate"])
        frozen = fixtures.load_frozen_v2(self.definition, package_root=PACKAGE_ROOT)
        source_before = frozen.tree_manifest.build_tree_manifest(source)["sha256"]
        if source_before != expected:
            raise ControllerError("fixture source drifted after preflight")
        _copy_ordinary(source, destination)
        copied = frozen.tree_manifest.build_tree_manifest(destination)["sha256"]
        source_after = frozen.tree_manifest.build_tree_manifest(source)["sha256"]
        if copied != expected or source_after != expected:
            raise ControllerError("fixture source changed while the scored baseline was copied")
        return fixture, {
            "preflight_receipt_sha256": state["preflight"]["receipt_sha256"],
            "expected_candidate_manifest_sha256": expected,
            "source_before_sha256": source_before,
            "copied_sha256": copied,
            "source_after_sha256": source_after,
        }

    def _run_reserved_cell(self, state: dict[str, Any], cell_id: str, attempt: Path) -> dict[str, Any]:
        active = state["active_cell"]
        deadline_ns = int(active["deadline_monotonic_ns"])
        deadline = deadline_ns / 1_000_000_000
        cell = self.definition["cells"][cell_id]
        task_id = cell["task"]
        candidate = attempt / "candidate"
        _fixture, fixture_binding = self._copy_bound_fixture(
            state, task_id, candidate
        )
        baseline = strict_tree_manifest(candidate)
        baseline_snapshot = attempt / "baseline-snapshot"
        baseline_snapshot_manifest = _copy_bound_snapshot(
            candidate,
            baseline_snapshot,
            expected_manifest_sha256=baseline["sha256"],
        )
        task = self.definition["tasks"][task_id]
        implementation_receipt = self._codex_stage(
            attempt=attempt,
            stage="implementation",
            task_id=task_id,
            candidate=candidate,
            model=cell["model"],
            effort=cell["effort"],
            schema=PACKAGE_ROOT / "schemas" / "implementation.schema.json",
            prompt=(candidate / "TASK.md").read_text(encoding="utf-8")
            + "\nImplement the task now. Return only the required structured result.\n",
            reviewer=False,
            writable_paths=tuple(task["allowed_paths"]) + (".runner-tmp",),
            deadline=deadline,
        )
        response = implementation_receipt["response"]
        implementation_hash = _exclusive_json(
            attempt / "implementation-receipt.json", implementation_receipt
        )

        now = time.monotonic_ns()
        if now >= deadline_ns or implementation_receipt.get("process", {}).get("timed_out"):
            result = self._terminal_payload(cell_id, "TIMEOUT", implementation_receipt, None, None)
            state = lifecycle.expire_active_cell(state, self.definition, cell_id=cell_id, result_sha256=sha256_bytes(canonical_bytes(result)), now_monotonic_ns=max(now, deadline_ns))
            return self._finish_attempt(state, attempt, result)
        if response.get("status") == "blocked":
            result = self._terminal_payload(
                cell_id,
                "IMPLEMENTATION_FAILED",
                implementation_receipt,
                None,
                None,
                error=str(response.get("blocker") or "implementation reported blocked"),
            )
            result_hash = sha256_bytes(canonical_bytes(result))
            state = lifecycle.record_implementation_failure(state, self.definition, cell_id=cell_id, result_sha256=result_hash, reason="single implementation attempt did not complete", now_monotonic_ns=now)
            return self._finish_attempt(state, attempt, result)
        if response.get("status") != "completed":
            raise ControllerError("implementation response has no valid terminal status")

        _remove_runner_tmp(candidate)
        after = strict_tree_manifest(candidate)
        scope = _scope_receipt(
            baseline,
            after,
            response.get("changed_paths"),
            task["allowed_paths"],
        )
        artifact_snapshot = attempt / "artifact-snapshot"
        snapshot_manifest = _copy_bound_snapshot(
            candidate,
            artifact_snapshot,
            expected_manifest_sha256=after["sha256"],
        )
        artifact = self._artifact_receipt(
            cell_id=cell_id,
            task_id=task_id,
            before=baseline,
            after=after,
            baseline_snapshot=baseline_snapshot_manifest,
            snapshot=snapshot_manifest,
            scope=scope,
            fixture_binding=fixture_binding,
        )
        artifact_hash = _exclusive_json(attempt / "artifact.json", artifact)
        now = time.monotonic_ns()
        scope_safe = bool(scope["safe"])
        if not scope_safe and now >= deadline_ns:
            raise BoundaryFailure(
                "unsafe allowed-path scope discovered at or after the inclusive deadline",
                evidence={"scope": scope},
            )
        if now >= deadline_ns:
            result = self._terminal_payload(
                cell_id,
                "TIMEOUT",
                implementation_receipt,
                None,
                None,
                artifact=artifact,
                artifact_sha256=artifact_hash,
            )
            state = lifecycle.expire_active_cell(
                state,
                self.definition,
                cell_id=cell_id,
                result_sha256=sha256_bytes(canonical_bytes(result)),
                now_monotonic_ns=max(now, deadline_ns),
            )
            return self._finish_attempt(state, attempt, result)
        state = lifecycle.record_implementation_complete(state, self.definition, cell_id=cell_id, artifact_sha256=artifact_hash, receipt_sha256=implementation_hash, now_monotonic_ns=now)
        self._checkpoint(state)

        if not scope_safe:
            verification_receipt = {
                "scope_safe": False,
                "telemetry_safe": True,
                "scope": scope,
                "public": "NOT_RUN",
                "hidden": "NOT_RUN",
                "reason": "unsafe allowed-path scope",
                "artifact_manifest_sha256": snapshot_manifest["sha256"],
            }
            verification_hash = sha256_bytes(canonical_bytes(verification_receipt))
            persisted_verification_hash = _exclusive_json(
                attempt / "verification-receipt.json", verification_receipt
            )
            if persisted_verification_hash != verification_hash:
                raise ControllerError("verification receipt changed while persisting")
            unsafe_payload = self._terminal_payload(
                cell_id,
                "UNSAFE_SCOPE",
                implementation_receipt,
                verification_receipt,
                None,
                artifact=artifact,
                artifact_sha256=artifact_hash,
            )
            state = lifecycle.record_verification(
                state,
                self.definition,
                cell_id=cell_id,
                public_passed=False,
                hidden_passed=False,
                scope_safe=False,
                telemetry_safe=True,
                receipt_sha256=verification_hash,
                now_monotonic_ns=time.monotonic_ns(),
                unsafe_result_sha256=sha256_bytes(canonical_bytes(unsafe_payload)),
            )
            return self._finish_attempt(state, attempt, unsafe_payload)

        try:
            review_range = _build_review_range(
                baseline_snapshot,
                artifact_snapshot,
                baseline_manifest_sha256=baseline_snapshot_manifest["sha256"],
                artifact_manifest_sha256=snapshot_manifest["sha256"],
                scope=scope,
                allowed_paths=task["allowed_paths"],
            )
        except ControllerError as exc:
            raise BoundaryFailure(
                f"canonical Luna review range could not be built: {exc}"
            ) from exc
        review_range_hash = _exclusive_json(
            attempt / "review-range.json", review_range
        )

        snapshot_before_verification = strict_tree_manifest(artifact_snapshot)["sha256"]
        if snapshot_before_verification != snapshot_manifest["sha256"]:
            raise BoundaryFailure("artifact snapshot drifted before verification")
        verification_workspace = attempt / "verification-workspace"
        verification_workspace_manifest = _copy_bound_snapshot(
            artifact_snapshot,
            verification_workspace,
            expected_manifest_sha256=snapshot_manifest["sha256"],
        )
        verification = self._verify(task_id, verification_workspace, deadline)
        _remove_runner_tmp(verification_workspace)
        verification_workspace_after = strict_tree_manifest(verification_workspace)["sha256"]
        snapshot_after_verification = strict_tree_manifest(artifact_snapshot)["sha256"]
        if (
            verification_workspace_after != verification_workspace_manifest["sha256"]
            or snapshot_after_verification != snapshot_manifest["sha256"]
        ):
            raise BoundaryFailure("artifact bytes changed during deterministic verification")
        verification_receipt = {
            "scope_safe": True,
            "telemetry_safe": True,
            "scope": scope,
            "artifact_manifest_sha256": snapshot_manifest["sha256"],
            "verification_workspace_before_sha256": verification_workspace_manifest["sha256"],
            "verification_workspace_after_sha256": verification_workspace_after,
            "artifact_before_sha256": snapshot_before_verification,
            "artifact_after_sha256": snapshot_after_verification,
            **verification,
        }
        verification_hash = _exclusive_json(
            attempt / "verification-receipt.json", verification_receipt
        )
        state = lifecycle.record_verification(
            state,
            self.definition,
            cell_id=cell_id,
            public_passed=verification.get("public") == "PASS",
            hidden_passed=verification.get("hidden") == "PASS",
            scope_safe=True,
            telemetry_safe=True,
            receipt_sha256=verification_hash,
            now_monotonic_ns=time.monotonic_ns(),
        )
        self._checkpoint(state)

        baseline_before_review = strict_tree_manifest(baseline_snapshot)["sha256"]
        snapshot_before_review = strict_tree_manifest(artifact_snapshot)["sha256"]
        if (
            baseline_before_review != baseline_snapshot_manifest["sha256"]
            or snapshot_before_review != snapshot_manifest["sha256"]
            or sha256_file(attempt / "artifact.json") != artifact_hash
            or sha256_file(attempt / "review-range.json") != review_range_hash
        ):
            raise BoundaryFailure("review inputs drifted before review")
        review_workspace = attempt / "review-workspace"
        review_workspace_artifact_manifest = _copy_bound_snapshot(
            artifact_snapshot,
            review_workspace,
            expected_manifest_sha256=snapshot_manifest["sha256"],
        )
        review_workspace_range = (
            review_workspace / ".benchmark" / "review-range.json"
        )
        review_workspace_range_hash = _exclusive_json(
            review_workspace_range, review_range
        )
        if (
            review_workspace_range_hash != review_range_hash
            or review_workspace_range.read_bytes()
            != (attempt / "review-range.json").read_bytes()
        ):
            raise BoundaryFailure("review workspace range bytes differ")
        review_workspace_before = strict_tree_manifest(review_workspace)["sha256"]
        raw_review_receipt: Mapping[str, Any] | None = None
        review_error: str | None = None
        review_failure: Exception | None = None
        try:
            review_prompt = (
                "Review the completed implementation of TASK.md read-only. "
                f"Artifact SHA-256: {artifact_hash}. "
                f"Review range SHA-256: {review_range_hash}. "
                "Use .benchmark/review-range.json as the exact baseline-to-artifact "
                "change range. Echo both hashes exactly. Report every correctness, "
                "regression, scope, or test finding. Return only the required "
                "structured result."
            )
            raw_review_receipt = self._codex_stage(
                attempt=attempt,
                stage="review",
                task_id=task_id,
                candidate=review_workspace,
                model=self.definition["reviewer"]["model"],
                effort=self.definition["reviewer"]["effort"],
                schema=PACKAGE_ROOT / self.definition["reviewer"]["schema"],
                prompt=review_prompt,
                reviewer=True,
                writable_paths=(),
                deadline=deadline,
            )
        except Exception as exc:
            review_failure = exc
            review_error = f"{type(exc).__name__}: {exc}"
        _remove_runner_tmp(review_workspace)
        review_workspace_after = strict_tree_manifest(review_workspace)["sha256"]
        baseline_after_review = strict_tree_manifest(baseline_snapshot)["sha256"]
        snapshot_after_review = strict_tree_manifest(artifact_snapshot)["sha256"]
        if (
            review_workspace_after != review_workspace_before
            or baseline_after_review != baseline_snapshot_manifest["sha256"]
            or snapshot_after_review != snapshot_manifest["sha256"]
            or sha256_file(attempt / "artifact.json") != artifact_hash
            or sha256_file(attempt / "review-range.json") != review_range_hash
            or sha256_file(review_workspace_range) != review_range_hash
            or review_workspace_range.read_bytes()
            != (attempt / "review-range.json").read_bytes()
        ):
            raise BoundaryFailure("review inputs changed during read-only review")
        if review_failure is not None:
            raise review_failure
        review_binding = {
            "artifact_evidence_sha256": artifact_hash,
            "baseline_manifest_sha256": baseline_snapshot_manifest["sha256"],
            "artifact_manifest_sha256": snapshot_manifest["sha256"],
            "review_range_sha256": review_range_hash,
            "review_workspace_range_sha256": review_workspace_range_hash,
            "review_workspace_artifact_manifest_sha256": (
                review_workspace_artifact_manifest["sha256"]
            ),
            "review_workspace_before_sha256": review_workspace_before,
            "review_workspace_after_sha256": review_workspace_after,
            "baseline_before_sha256": baseline_before_review,
            "baseline_after_sha256": baseline_after_review,
            "artifact_before_sha256": snapshot_before_review,
            "artifact_after_sha256": snapshot_after_review,
        }
        review_receipt = {
            **(
                dict(raw_review_receipt)
                if raw_review_receipt is not None
                else {"error": review_error or "invalid review"}
            ),
            "artifact_binding": review_binding,
        }
        now = time.monotonic_ns()
        if now >= deadline_ns:
            result = self._terminal_payload(
                cell_id,
                "TIMEOUT",
                implementation_receipt,
                verification_receipt,
                review_receipt,
                artifact=artifact,
                artifact_sha256=artifact_hash,
                error=review_error,
            )
            state = lifecycle.expire_active_cell(state, self.definition, cell_id=cell_id, result_sha256=sha256_bytes(canonical_bytes(result)), now_monotonic_ns=max(now, deadline_ns))
            return self._finish_attempt(state, attempt, result)
        review = raw_review_receipt.get("response") if raw_review_receipt else None
        valid_review = (
            isinstance(review, Mapping)
            and set(review)
            == {
                "status",
                "artifact_sha256",
                "review_range_sha256",
                "summary",
                "findings",
            }
            and review.get("artifact_sha256") == artifact_hash
            and review.get("review_range_sha256") == review_range_hash
            and review.get("status") in {"PASS", "BLOCKED"}
            and isinstance(review.get("findings"), list)
        )
        status = str(review.get("status")) if valid_review else "BLOCKED"
        findings = list(review.get("findings", [])) if valid_review else [{"reason": review_error or "invalid review evidence"}]
        if findings:
            status = "BLOCKED"
        persisted_review = review_receipt
        review_hash = _exclusive_json(
            attempt / "review-receipt.json", persisted_review
        )
        review_receipt = persisted_review
        result_status = "ACCEPTED" if status == "PASS" and not findings and verification["public"] == "PASS" and verification["hidden"] == "PASS" else "REVIEW_BLOCKED" if status != "PASS" or findings else "VERIFICATION_FAILED"
        result = self._terminal_payload(
            cell_id,
            result_status,
            implementation_receipt,
            verification_receipt,
            review_receipt,
            artifact=artifact,
            artifact_sha256=artifact_hash,
            error=review_error,
        )
        result_hash = sha256_bytes(canonical_bytes(result))
        state = lifecycle.record_review(
            state,
            self.definition,
            cell_id=cell_id,
            status=status,
            finding_count=len(findings),
            artifact_sha256=artifact_hash,
            review_range_sha256=review_range_hash,
            receipt_sha256=review_hash,
            result_sha256=result_hash,
            now_monotonic_ns=now,
        )
        return self._finish_attempt(state, attempt, result)

    def _artifact_receipt(
        self,
        *,
        cell_id: str,
        task_id: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        baseline_snapshot: Mapping[str, Any],
        snapshot: Mapping[str, Any],
        scope: Mapping[str, Any],
        fixture_binding: Mapping[str, Any],
    ) -> dict[str, Any]:
        files = _file_map(after)
        changed = list(scope["changed_paths"])
        return {
            "schema_version": 1,
            "cell_id": cell_id,
            "task_id": task_id,
            "fixture_binding": dict(fixture_binding),
            "before_manifest_sha256": before["sha256"],
            "after_manifest_sha256": after["sha256"],
            "baseline_snapshot_manifest_sha256": baseline_snapshot["sha256"],
            "snapshot_manifest_sha256": snapshot["sha256"],
            "scope": dict(scope),
            "changed_paths": changed,
            "changed_files": {path: ({"mode": files[path][0], "size": files[path][1], "sha256": files[path][2]} if path in files else None) for path in changed},
        }

    def _load_attempt_artifact(
        self, attempt: Path, *, expected_sha256: str | None = None
    ) -> tuple[dict[str, Any] | None, str | None]:
        path = attempt / "artifact.json"
        if not path.is_file():
            if expected_sha256 is not None:
                raise ControllerError(
                    "expected artifact evidence is absent from the attempt"
                )
            return None, expected_sha256
        artifact = _load_canonical(path)
        observed = sha256_file(path)
        if expected_sha256 is not None and observed != expected_sha256:
            raise ControllerError("artifact evidence no longer matches lifecycle state")
        return artifact, observed

    def _rebuild_attempt_review_range(
        self, attempt: Path, artifact: Mapping[str, Any]
    ) -> tuple[dict[str, Any], str, dict[str, Any], dict[str, Any]]:
        """Rebuild one exact Luna range without consulting the mutable candidate."""

        task_id = artifact.get("task_id")
        if task_id not in self.definition["tasks"]:
            raise ControllerError("artifact task identity is invalid")
        baseline = strict_tree_manifest(attempt / "baseline-snapshot")
        snapshot = strict_tree_manifest(attempt / "artifact-snapshot")
        if (
            artifact.get("before_manifest_sha256") != baseline["sha256"]
            or artifact.get("baseline_snapshot_manifest_sha256")
            != baseline["sha256"]
            or artifact.get("after_manifest_sha256") != snapshot["sha256"]
            or artifact.get("snapshot_manifest_sha256") != snapshot["sha256"]
        ):
            raise ControllerError("artifact snapshot manifests do not bind the review range")
        scope = artifact.get("scope")
        if not isinstance(scope, Mapping):
            raise ControllerError("artifact scope is missing from the review range")
        rebuilt = _build_review_range(
            attempt / "baseline-snapshot",
            attempt / "artifact-snapshot",
            baseline_manifest_sha256=baseline["sha256"],
            artifact_manifest_sha256=snapshot["sha256"],
            scope=scope,
            allowed_paths=self.definition["tasks"][task_id]["allowed_paths"],
        )
        persisted = _load_canonical(attempt / "review-range.json")
        workspace_range = _load_canonical(
            attempt / "review-workspace" / ".benchmark" / "review-range.json"
        )
        if persisted != rebuilt or workspace_range != rebuilt:
            raise ControllerError("persisted Luna review range differs from its snapshots")
        review_range_sha256 = sha256_bytes(canonical_bytes(rebuilt))
        if (
            sha256_file(attempt / "review-range.json") != review_range_sha256
            or sha256_file(
                attempt
                / "review-workspace"
                / ".benchmark"
                / "review-range.json"
            )
            != review_range_sha256
        ):
            raise ControllerError("Luna review range hash differs from its snapshots")
        return rebuilt, review_range_sha256, baseline, snapshot

    @staticmethod
    def _load_optional_receipt(path: Path) -> dict[str, Any] | None:
        return _load_canonical(path) if path.is_file() else None

    def _terminal_payload(
        self,
        cell_id: str,
        status: str,
        implementation_receipt: Any,
        verification: Any,
        review: Any,
        *,
        artifact: Mapping[str, Any] | None = None,
        artifact_sha256: str | None = None,
        error: str | None = None,
        failure_evidence: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "cell_id": cell_id,
            "status": status,
            "definition_sha256": self.definition_sha256,
            "package_sha256": self.package_sha256,
            "implementation": implementation_receipt,
            "verification": verification,
            "review": review,
            "artifact": dict(artifact) if artifact is not None else None,
            "artifact_evidence_file": "artifact.json" if artifact is not None else None,
            "artifact_sha256": artifact_sha256,
            "artifact_snapshot": "artifact-snapshot" if artifact is not None else None,
            "artifact_snapshot_manifest_sha256": (
                artifact.get("snapshot_manifest_sha256")
                if artifact is not None
                else None
            ),
            "failure_evidence": (
                dict(failure_evidence) if failure_evidence is not None else None
            ),
            "error": error,
        }

    def _finish_attempt(self, state: Mapping[str, Any], attempt: Path, result: Mapping[str, Any]) -> dict[str, Any]:
        expected_hash = sha256_bytes(canonical_bytes(result))
        if expected_hash != state["terminal_cells"][-1]["terminal"]["result_sha256"]:
            raise ControllerError("persisted terminal result does not match lifecycle state")
        result_hash = _exclusive_json(attempt / "result.json", result)
        if result_hash != expected_hash:
            raise ControllerError("terminal result changed while it was persisted")
        with self._locked():
            current = self._load_state()
            terminal = state["terminal_cells"][-1]
            active = current.get("active_cell")
            if (
                not isinstance(active, Mapping)
                or active.get("cell_id") != terminal.get("cell_id")
                or len(current.get("terminal_cells", [])) + 1 != len(state.get("terminal_cells", []))
            ):
                raise ControllerError("lifecycle state changed during the reserved attempt")
            self._save_state(state)
        return dict(result)

    def _quota(self) -> Mapping[str, Any]:
        if self.hooks.quota is not None:
            value = self.hooks.quota()
            if not isinstance(value, Mapping):
                raise TelemetryFailure("quota hook did not return an object")
            try:
                telemetry.validate_normalized_quota_snapshot(value)
            except telemetry.TelemetryError as exc:
                raise TelemetryFailure(
                    f"quota hook returned an invalid snapshot: {exc}"
                ) from exc
            return dict(value)
        executable = self.config.codexbar_executable
        if not executable.is_file():
            raise TelemetryFailure("CodexBar quota executable is unavailable")
        try:
            profile, _profile_hash = self._quota_sandbox_profile()
        except ControllerError as exc:
            raise TelemetryFailure(str(exc)) from exc
        observer_environment = {
            **SAFE_ENV,
            "HOME": str(self.config.auth_source.parent.parent),
            "CODEX_HOME": str(self.config.auth_source.parent),
        }
        try:
            result = subprocess.run(
                [
                    "/usr/bin/sandbox-exec",
                    "-p",
                    profile,
                    str(executable),
                    "usage",
                    "--provider",
                    "codex",
                    "--source",
                    "oauth",
                    "--format",
                    "json",
                    "--no-color",
                ],
                cwd=str(self.root),
                env=observer_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TelemetryFailure(f"CodexBar quota observation failed: {exc}") from exc
        if result.returncode:
            raise TelemetryFailure("CodexBar quota observation failed")
        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TelemetryFailure("CodexBar quota output is malformed") from exc
        try:
            snapshot = telemetry.normalize_codexbar_snapshot(raw, captured_at=utc_now())
            telemetry.validate_normalized_quota_snapshot(snapshot)
        except telemetry.TelemetryError as exc:
            raise TelemetryFailure(
                f"CodexBar quota output is incompatible: {exc}"
            ) from exc
        return snapshot

    def _quota_sandbox_profile(self) -> tuple[str, str]:
        executable = self.config.codexbar_executable
        bundle = next(
            (parent for parent in (executable, *executable.parents) if parent.suffix == ".app"),
            None,
        )
        if bundle is None:
            raise ControllerError("CodexBar observer is not inside a pinned app bundle")
        profile = "".join(
            (
                "(version 1)",
                "(deny default)",
                '(import "system.sb")',
                "(allow process*)",
                "(allow file-read* ",
                f"(subpath {json.dumps(str(bundle))}) ",
                f"(literal {json.dumps(str(self.config.auth_source))}))",
                "(allow network-outbound)",
            )
        )
        return profile, sha256_bytes(profile.encode("utf-8"))

    def _quota_observer_receipt(self) -> dict[str, Any]:
        if self.hooks.quota is not None:
            return {"mode": "test_hook"}
        profile, profile_hash = self._quota_sandbox_profile()
        return {
            "mode": "pinned_sandboxed_codexbar",
            "executable_sha256": sha256_file(self.config.codexbar_executable),
            "version": self.definition["pinned_runtime"]["codexbar_version"],
            "sandbox_profile_sha256": profile_hash,
            "sandbox_profile_bytes": len(profile.encode("utf-8")),
            "auth_material_present_in_stage": False,
        }

    def _codex_stage(
        self,
        *,
        attempt: Path,
        stage: str,
        task_id: str,
        candidate: Path,
        model: str,
        effort: str,
        schema: Path,
        prompt: str,
        reviewer: bool,
        writable_paths: Sequence[str],
        deadline: float,
    ) -> Mapping[str, Any]:
        openai_strict_output_schema_receipt(schema)
        if self.hooks.codex_stage is not None:
            return self.hooks.codex_stage(
                attempt=attempt,
                stage=stage,
                task_id=task_id,
                candidate=candidate,
                model=model,
                effort=effort,
                schema=schema,
                prompt=prompt,
                reviewer=reviewer,
                writable_paths=writable_paths,
                deadline=deadline,
            )
        if time.monotonic() >= deadline:
            raise StageTimeout("inclusive cell deadline elapsed before model stage")
        stage_root = attempt / stage
        stage_root.mkdir(mode=0o700)
        paths = isolation.CodexPaths(
            candidate_root=candidate,
            home=stage_root / "home",
            codex_home=stage_root / "codex-home",
            codex_sqlite_home=stage_root / "sqlite",
            tmpdir=candidate / ".runner-tmp",
            auth_target=stage_root / "auth-target.json",
            controller_root=stage_root,
            memory_root=self.config.memory_root,
        )
        last_message = stage_root / "last-message.json"
        stdout = stage_root / "exec.jsonl"
        stderr = stage_root / "stderr.txt"
        rollout_snapshot: Path | None = None
        auth_content = b""
        auth_markers: tuple[bytes, ...] = ()
        runtime_cleaned = False
        try:
            paths.home.mkdir(parents=True)
            paths.codex_home.mkdir(parents=True)
            paths.codex_sqlite_home.mkdir(parents=True)
            paths.tmpdir.mkdir(parents=True, exist_ok=True)
            runtime_roots = self._profile_runtime_roots()
            marker = f"routing-v3-{secrets.token_hex(16)}"
            child_environment = {"ROUTING_RUN_MARKER": marker}
            if task_id == "openbot-acp":
                candidate_acp = candidate / "daemon" / "src" / "acp.ts"
                if not candidate_acp.is_file():
                    raise ControllerError("OpenBot candidate ACP source is missing")
                child_environment["ROUTING_CANDIDATE_ACP"] = str(candidate_acp)
            _, config_hash = isolation.write_permission_profile(
                paths,
                reviewer=reviewer,
                reasoning_effort=effort,
                child_environment=child_environment,
                writable_paths=writable_paths,
                runtime_roots=runtime_roots,
                command_path=self._command_path(),
            )
            environment = isolation.build_clean_environment(
                paths,
                command_path=self._command_path(),
                extra=child_environment,
            )
            command = isolation.build_codex_command(
                codex_executable=self.config.codex_executable,
                paths=paths,
                model=model,
                output_schema=schema,
                last_message_path=last_message,
            )
            before = self._quota()
            auth_content = _read_owned_single_link_file(
                self.config.auth_source,
                label="Codex auth source",
                maximum_bytes=MAX_CODEX_AUTH_BYTES,
                required_mode=0o600,
            )
            auth_markers = _codex_auth_markers(auth_content)
            _write_private_file(paths.auth_target, auth_content, mode=0o600)
            (paths.codex_home / "auth.json").symlink_to(paths.auth_target)
            process_error: Exception | None = None
            process = None
            try:
                process = execution.run_bounded_process(
                    command,
                    cwd=candidate,
                    environment=environment,
                    stdin_bytes=prompt.encode("utf-8"),
                    stdout_path=stdout,
                    stderr_path=stderr,
                    deadline_monotonic=deadline,
                    run_marker=marker,
                )
            except Exception as exc:
                process_error = (
                    BoundaryFailure(
                        f"stage process containment failed: {exc}"
                    )
                    if isinstance(exc, execution.ExecutionError)
                    else exc
                )
            finally:
                (paths.codex_home / "auth.json").unlink(missing_ok=True)
                paths.auth_target.unlink(missing_ok=True)
            after_error: Exception | None = None
            after: Mapping[str, Any] | None = None
            try:
                after = self._quota()
            except Exception as exc:
                after_error = exc
            rollout_snapshot, rollout_bytes = _snapshot_codex_rollout(
                paths.codex_home,
                stage_root / "rollout.jsonl",
                required=(
                    process is not None
                    and not process.timed_out
                    and process.returncode == 0
                ),
            )
            if process_error is not None:
                raise process_error
            assert process is not None
            if process.timed_out:
                raise StageTimeout("Codex stage reached the shared deadline")
            if process.survivor_pids:
                raise BoundaryFailure(
                    "Codex stage retained a process after terminal cleanup",
                    evidence={"process": process.as_dict()},
                )
            if process.returncode != 0:
                classified = _classified_codex_failure(stdout)
                if classified is not None:
                    raise classified(
                        "Codex stage returned a classified provider error",
                        evidence={"process": process.as_dict()},
                    )
                raise ControllerError(
                    "Codex stage exited nonzero without a classified provider code"
                )
            if after_error is not None:
                if isinstance(after_error, TerminalControllerError):
                    raise after_error
                raise TelemetryFailure(
                    f"post-stage quota observation failed: {after_error}"
                ) from after_error
            assert after is not None
            try:
                last_message_bytes = _read_owned_single_link_file(
                    last_message,
                    label="Codex last message",
                    maximum_bytes=execution.MAX_OUTPUT_BYTES,
                )
                response = json.loads(last_message_bytes)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ControllerError("Codex last message is not structured JSON") from exc
            self._validate_stage_response(response, reviewer=reviewer)
            if rollout_snapshot is None or rollout_bytes is None:
                raise TelemetryFailure("fresh Codex rollout was not retained")
            try:
                exec_text = _read_owned_single_link_file(
                    stdout,
                    label="Codex exec JSONL",
                    maximum_bytes=execution.MAX_OUTPUT_BYTES,
                ).decode("utf-8")
                rollout_text = rollout_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TelemetryFailure("model-stage telemetry is not UTF-8") from exc
            try:
                receipt = telemetry.build_telemetry_receipt(
                    exec_text,
                    rollout_text,
                    planned_model=model,
                    planned_effort=effort,
                    planned_permission_profile=isolation.PROFILE_REVIEWER if reviewer else isolation.PROFILE_CANDIDATE,
                )
            except telemetry.TelemetryError as exc:
                raise TelemetryFailure(
                    f"model-stage telemetry is not attributable: {exc}"
                ) from exc
            result = {
                "stage": stage,
                "model": model,
                "effort": effort,
                "config_sha256": config_hash,
                "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
                "schema_sha256": sha256_file(schema),
                "process": process.as_dict(),
                "telemetry": receipt,
                "quota": telemetry.quota_movement(before, after),
                "quota_observer": self._quota_observer_receipt(),
                "response": response,
                "response_sha256": sha256_bytes(canonical_bytes(response)),
                "evidence_files": {
                    "exec_jsonl": stdout.relative_to(attempt).as_posix(),
                    "rollout_jsonl": rollout_snapshot.relative_to(attempt).as_posix(),
                    "stderr": stderr.relative_to(attempt).as_posix(),
                    "last_message": last_message.relative_to(attempt).as_posix(),
                },
            }
            retention = _cleanup_codex_stage_runtime(
                stage_root=stage_root,
                paths=paths,
                retained_paths=(stdout, rollout_snapshot, stderr, last_message),
                auth_markers=auth_markers,
            )
            runtime_cleaned = True
            result["evidence_retention"] = retention
            return result
        except Exception as stage_error:
            if not runtime_cleaned:
                retention = _cleanup_codex_stage_runtime(
                    stage_root=stage_root,
                    paths=paths,
                    retained_paths=tuple(
                        path
                        for path in (stdout, rollout_snapshot, stderr, last_message)
                        if path is not None
                    ),
                    auth_markers=auth_markers,
                )
                runtime_cleaned = True
                existing = getattr(stage_error, "evidence", None)
                failure_evidence = dict(existing) if isinstance(existing, Mapping) else {}
                failure_evidence["stage_evidence"] = _stage_evidence_binding(
                    attempt=attempt,
                    stage_root=stage_root,
                    retention=retention,
                )
                stage_error.evidence = failure_evidence
            raise
        finally:
            if not runtime_cleaned:
                _cleanup_codex_stage_runtime(
                    stage_root=stage_root,
                    paths=paths,
                    retained_paths=tuple(
                        path
                        for path in (stdout, rollout_snapshot, stderr, last_message)
                        if path is not None
                    ),
                    auth_markers=auth_markers,
                )

    @staticmethod
    def _validate_stage_response(value: Any, *, reviewer: bool) -> None:
        if not isinstance(value, dict):
            raise ControllerError("Codex last message root is not an object")
        if reviewer:
            if set(value) != {
                "status",
                "artifact_sha256",
                "review_range_sha256",
                "summary",
                "findings",
            }:
                raise ControllerError("review result fields differ from the schema")
            findings = value.get("findings")
            if (
                value.get("status") not in {"PASS", "BLOCKED"}
                or not isinstance(value.get("artifact_sha256"), str)
                or HASH_RE.fullmatch(value["artifact_sha256"]) is None
                or not isinstance(value.get("review_range_sha256"), str)
                or HASH_RE.fullmatch(value["review_range_sha256"]) is None
                or not isinstance(value.get("summary"), str)
                or not isinstance(findings, list)
            ):
                raise ControllerError("review result values are invalid")
            for finding in findings:
                if not isinstance(finding, dict) or set(finding) != {
                    "severity",
                    "path",
                    "line_start",
                    "line_end",
                    "reason",
                }:
                    raise ControllerError("review finding fields differ from the schema")
                line_start = finding.get("line_start")
                line_end = finding.get("line_end")
                if (
                    finding.get("severity") not in {"P1", "P2", "P3"}
                    or not isinstance(finding.get("path"), str)
                    or not finding["path"]
                    or isinstance(line_start, bool)
                    or not isinstance(line_start, int)
                    or line_start < 1
                    or isinstance(line_end, bool)
                    or not isinstance(line_end, int)
                    or line_end < line_start
                    or not isinstance(finding.get("reason"), str)
                    or not finding["reason"]
                ):
                    raise ControllerError("review finding values are invalid")
        else:
            if set(value) != {"status", "summary", "changed_paths", "public_verifier", "blocker"}:
                raise ControllerError("implementation result fields differ from the schema")
            status = value.get("status")
            changed_paths = value.get("changed_paths")
            blocker = value.get("blocker")
            if (
                status not in {"completed", "blocked"}
                or not isinstance(value.get("summary"), str)
                or not isinstance(changed_paths, list)
                or not all(isinstance(path, str) and path for path in changed_paths)
                or len(changed_paths) != len(set(changed_paths))
                or value.get("public_verifier")
                not in {"passed", "failed", "not_run"}
                or not (blocker is None or isinstance(blocker, str))
                or (status == "completed" and blocker is not None)
                or (status == "blocked" and not blocker)
            ):
                raise ControllerError("implementation result values are invalid")

    def _split_hidden_verifier(
        self, task_id: str, candidate: Path, deadline: float
    ) -> dict[str, Any]:
        if task_id not in {"use-grok", "karpathy-pointer", "openbot-acp"}:
            raise ControllerError("split hidden verifier received an unknown task")
        self._assert_split_python_pin(BoundaryFailure)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StageTimeout("shared deadline elapsed before hidden verification")
        source_candidate = candidate
        source_manifest = strict_tree_manifest(source_candidate)
        stage = candidate.parent / f"split-hidden-{secrets.token_hex(8)}"
        stage.mkdir(mode=0o700)
        candidate = stage / "workspaces" / self.definition["tasks"][task_id]["workspace_name"]
        candidate_view_manifest = _copy_bound_snapshot(
            source_candidate,
            candidate,
            expected_manifest_sha256=source_manifest["sha256"],
        )
        shared = stage / "shared"
        shared.mkdir(mode=0o700)
        driver_home = shared / "driver-home"
        worker_home = shared / "worker-home"
        driver_home.mkdir(mode=0o700)
        worker_home.mkdir(mode=0o700)
        protocol_source = PACKAGE_ROOT / "split_verifier.py"
        driver_runtime = stage / "driver-runtime"
        worker_runtime = stage / "worker-runtime"
        for runtime in (driver_runtime, worker_runtime):
            runtime.mkdir(mode=0o700)
            target = runtime / "split_verifier.py"
            with protocol_source.open("rb") as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            target.chmod(0o400)
            if sha256_file(target) != sha256_file(protocol_source):
                raise BoundaryFailure("split protocol runtime copy differs")
            runtime.chmod(0o500)
        worker_runtime.chmod(0o700)
        mktemp_wrapper = worker_runtime / "mktemp"
        mktemp_wrapper.write_text(
            "#!"
            + str(SPLIT_PYTHON.resolve(strict=True))
            + "\n"
            + "import os,secrets,sys\n"
            + "if sys.argv[1:] != ['-d']: raise SystemExit(2)\n"
            + "root=os.environ.get('TMPDIR')\n"
            + "if not root: raise SystemExit(2)\n"
            + "for _ in range(128):\n"
            + " p=os.path.join(root,'tmp.'+secrets.token_hex(8))\n"
            + " try: os.mkdir(p,0o700); print(p); raise SystemExit(0)\n"
            + " except FileExistsError: pass\n"
            + "raise SystemExit(1)\n",
            encoding="utf-8",
        )
        mktemp_wrapper.chmod(0o500)
        worker_runtime.chmod(0o500)
        driver_stdout = stage / "driver.stdout"
        driver_stderr = stage / "driver.stderr"
        worker_stdout = stage / "worker.stdout"
        worker_stderr = stage / "worker.stderr"
        transcript = stage / "transcript.bin"
        runner_stdout = stage / "runner.stdout"
        runner_stderr = stage / "runner.stderr"
        python_executable = SPLIT_PYTHON.resolve(strict=True)
        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.is_file():
            raise BoundaryFailure("native sandbox-exec is unavailable")

        component_hashes: dict[str, str]
        heredoc_temp_before: tuple[str, ...] | None = None
        if task_id in {"use-grok", "karpathy-pointer"}:
            heredoc_temp_before = tuple(
                sorted(path.name for path in Path("/private/var/tmp").glob("sh-thd-*") if path.is_file())
            )
            frozen = fixtures.load_frozen_v2(self.definition, package_root=PACKAGE_ROOT)
            hidden = frozen.root / "verifiers" / "hidden.py"
            driver = PACKAGE_ROOT / "verifiers" / "hidden" / "v2_split_driver.py"
            worker = PACKAGE_ROOT / "verifiers" / "workers" / "v2_command_worker.py"
            profiles = _v2_split_profiles(
                candidate=candidate,
                shared=shared,
                hidden=hidden,
                driver_runtime=driver_runtime,
                worker_runtime=worker_runtime,
            )
            driver_profile, driver_profile_hash = profiles["driver"]
            worker_profile, worker_profile_hash = profiles["worker"]
            driver_argv = [
                str(sandbox),
                "-p",
                driver_profile,
                str(python_executable),
                "-B",
                str(driver),
                "--task",
                task_id,
                "--workspace",
                str(candidate),
                "--frozen-hidden",
                str(hidden),
                "--expected-hidden-sha256",
                sha256_file(hidden),
            ]
            worker_argv = [
                str(sandbox),
                "-p",
                worker_profile,
                str(python_executable),
                "-B",
                str(worker),
                "--allowed-root",
                str(candidate),
                "--allowed-root",
                str(shared),
                "--python-executable",
                str(python_executable),
                "--command-bin",
                str(worker_runtime),
            ]
            driver_environment = {
                **SAFE_ENV,
                "HOME": str(driver_home),
                "TMPDIR": str(shared),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(driver_runtime),
            }
            worker_environment = {
                **SAFE_ENV,
                "HOME": str(worker_home),
                "TMPDIR": str(shared),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
                "PYTHONPATH": str(worker_runtime),
            }
            component_hashes = {
                "driver": sha256_file(driver),
                "worker": sha256_file(worker),
                "frozen_hidden": sha256_file(hidden),
                "protocol": sha256_file(protocol_source),
                "mktemp_wrapper": sha256_file(mktemp_wrapper),
            }
        else:
            driver = (
                PACKAGE_ROOT
                / "verifiers"
                / "hidden"
                / "openbot_acp_hidden_driver.test.ts"
            )
            worker = (
                PACKAGE_ROOT
                / "verifiers"
                / "workers"
                / "openbot_acp_worker.mjs"
            )
            relay = (
                PACKAGE_ROOT
                / "verifiers"
                / "workers"
                / "openbot_agent_relay.mjs"
            )
            driver_package = driver.parent / "package.json"
            node = self._runtime_node()
            loader = candidate / "node_modules" / "tsx" / "dist" / "loader.mjs"
            profiles = _openbot_split_profiles(
                node=node,
                candidate=candidate,
                shared=shared,
            )
            driver_profile, driver_profile_hash = profiles["driver"]
            worker_profile, worker_profile_hash = profiles["worker"]
            driver_argv = _openbot_driver_argv(
                sandbox=sandbox,
                profile=driver_profile,
                node=node,
                driver=driver,
            )
            worker_argv = [
                str(sandbox),
                "-p",
                worker_profile,
                str(node),
                "--import",
                str(loader),
                str(worker),
            ]
            driver_environment = {
                **SAFE_ENV,
                "HOME": str(driver_home),
                "ROUTING_WORKSPACE_ROOT": str(candidate),
                "TMPDIR": str(shared),
                "TSX_DISABLE_CACHE": "1",
            }
            worker_environment = {
                **SAFE_ENV,
                "HOME": str(worker_home),
                "TMPDIR": str(shared),
                "TSX_DISABLE_CACHE": "1",
                "ROUTING_CANDIDATE_ACP": str(
                    candidate / "daemon" / "src" / "acp.ts"
                ),
                "ROUTING_CANDIDATE_ROOT": str(candidate),
                "ROUTING_OPENBOT_AGENT_RELAY": str(relay),
            }
            component_hashes = {
                "driver": sha256_file(driver),
                "driver_package": sha256_file(driver_package),
                "worker": sha256_file(worker),
                "relay": sha256_file(relay),
                "loader": sha256_file(loader),
            }

        worker_binding_hash = sha256_bytes(
            canonical_bytes(
                {
                    key: component_hashes[key]
                    for key in sorted(component_hashes)
                    if key != "driver"
                }
            )
        )
        binding = split_verifier.Binding(
            nonce=secrets.token_hex(32),
            task=task_id,
            candidate_manifest_sha256=strict_tree_manifest(candidate)["sha256"],
            driver_sha256=component_hashes["driver"],
            worker_sha256=worker_binding_hash,
            deadline_unix_ms=int((time.time() + remaining) * 1000),
        )
        config = {
            "binding": binding.as_dict(),
            "deadline_monotonic": deadline,
            "driver_argv": driver_argv,
            "driver_cwd": str(candidate),
            "driver_environment": driver_environment,
            "output_paths": {
                "driver_stderr": str(driver_stderr),
                "driver_stdout": str(driver_stdout),
                "transcript": str(transcript),
                "worker_stderr": str(worker_stderr),
                "worker_stdout": str(worker_stdout),
            },
            "worker_argv": worker_argv,
            "worker_cwd": str(candidate),
            "worker_environment": worker_environment,
        }
        config_path = stage / "runner-config.json"
        config_hash = _exclusive_json(config_path, config)
        marker = f"routing-v3-split-{secrets.token_hex(16)}"
        try:
            process = execution.run_bounded_process(
                [
                    sys.executable,
                    "-B",
                    str(PACKAGE_ROOT / "split_verifier_runner.py"),
                    str(config_path),
                ],
                cwd=PACKAGE_ROOT,
                environment={
                    **SAFE_ENV,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "ROUTING_RUN_MARKER": marker,
                },
                stdin_bytes=b"",
                stdout_path=runner_stdout,
                stderr_path=runner_stderr,
                deadline_monotonic=deadline,
                run_marker=marker,
            )
        except execution.ExecutionError as exc:
            raise BoundaryFailure(
                f"split hidden verifier containment failed: {exc}"
            ) from exc
        if process.timed_out:
            raise StageTimeout("split hidden verifier reached the shared deadline")
        if process.survivor_pids:
            raise BoundaryFailure(
                "split hidden verifier retained a process",
                evidence={"process": process.as_dict()},
            )
        try:
            raw_receipt = runner_stdout.read_bytes()
            receipt_value = json.loads(raw_receipt)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BoundaryFailure("split hidden verifier receipt is malformed") from exc
        receipt_fields = set(split_verifier.SplitReceipt.__dataclass_fields__)
        if (
            not isinstance(receipt_value, dict)
            or set(receipt_value) != receipt_fields | {"passed"}
            or raw_receipt != canonical_bytes(receipt_value)
        ):
            raise BoundaryFailure("split hidden verifier receipt fields differ")
        receipt = split_verifier.SplitReceipt(
            **{field: receipt_value[field] for field in receipt_fields}
        )
        if receipt_value["passed"] != receipt.passed:
            raise BoundaryFailure("split hidden verifier pass flag is inconsistent")
        if receipt.protocol_error is not None or receipt.worker_stdout_bytes:
            raise BoundaryFailure(
                "split hidden verifier protocol boundary failed",
                evidence={"split": receipt.as_dict(), "process": process.as_dict()},
            )
        if process.returncode != (0 if receipt.passed else 1):
            raise BoundaryFailure("split hidden verifier runner status is inconsistent")
        heredoc_temp_after = (
            tuple(
                sorted(path.name for path in Path("/private/var/tmp").glob("sh-thd-*") if path.is_file())
            )
            if heredoc_temp_before is not None
            else None
        )
        if heredoc_temp_before != heredoc_temp_after:
            raise BoundaryFailure(
                "legacy Bash heredoc temporary-file state changed during verification"
            )
        evidence = {
            "status": (
                "PASS"
                if receipt.passed
                else "FAIL"
                if receipt.driver_returncode == 1
                else "ERROR"
            ),
            "binding": binding.as_dict(),
            "component_sha256": component_hashes,
            "source_candidate_manifest_sha256": source_manifest["sha256"],
            "candidate_view_manifest_sha256": candidate_view_manifest["sha256"],
            "legacy_bash_heredoc_temp_scope": (
                {
                    "seatbelt_regex": "sh-thd-[0-9]+$",
                    "observed_root": "/private/var/tmp",
                    "before_names": list(heredoc_temp_before),
                    "after_names": list(heredoc_temp_after),
                    "unchanged": True,
                }
                if heredoc_temp_before is not None
                else None
            ),
            "driver_profile_sha256": driver_profile_hash,
            "worker_profile_sha256": worker_profile_hash,
            "runner_config_sha256": config_hash,
            "runner_sha256": sha256_file(PACKAGE_ROOT / "split_verifier_runner.py"),
            "split_receipt": receipt.as_dict(),
            "process": process.as_dict(),
            "evidence_files": {
                name: path.relative_to(stage).as_posix()
                for name, path in {
                    "driver_stdout": driver_stdout,
                    "driver_stderr": driver_stderr,
                    "worker_stdout": worker_stdout,
                    "worker_stderr": worker_stderr,
                    "transcript": transcript,
                    "runner_stdout": runner_stdout,
                    "runner_stderr": runner_stderr,
                }.items()
            },
        }
        if task_id in {"use-grok", "karpathy-pointer"}:
            try:
                driver_result = json.loads(driver_stdout.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BoundaryFailure("v2 hidden driver result is malformed") from exc
            evidence["driver_result"] = driver_result
        if (
            strict_tree_manifest(source_candidate)["sha256"]
            != source_manifest["sha256"]
            or strict_tree_manifest(candidate)["sha256"]
            != candidate_view_manifest["sha256"]
        ):
            raise BoundaryFailure("candidate bytes changed during split verification")
        return evidence

    def _verify(self, task_id: str, candidate: Path, deadline: float) -> Mapping[str, Any]:
        if self.hooks.verifier is not None:
            return self.hooks.verifier(task_id, candidate, deadline)
        if time.monotonic() >= deadline:
            raise ControllerError("inclusive cell deadline elapsed before verification")
        return self._verify_openbot(candidate, deadline) if task_id == "openbot-acp" else self._verify_v2(task_id, candidate, deadline)

    def _verify_v2(self, task_id: str, candidate: Path, deadline: float) -> Mapping[str, Any]:
        frozen = fixtures.load_frozen_v2(self.definition, package_root=PACKAGE_ROOT)
        v2_definition = json.loads((frozen.root / "definition.json").read_text(encoding="utf-8"))
        manifest = frozen.tree_manifest.build_tree_manifest(candidate)
        task = self.definition["tasks"][task_id]
        public = (PACKAGE_ROOT / task["public_verifier_source"]).resolve()
        public_run = self._v2_public_docker_verifier(
            frozen,
            v2_definition,
            public,
            candidate,
            task_id,
            manifest["sha256"],
            deadline,
        )
        hidden_run = self._split_hidden_verifier(task_id, candidate, deadline)
        return {"public": public_run["status"], "hidden": hidden_run["status"], "public_receipt": public_run, "hidden_receipt": hidden_run}

    def _v2_public_docker_verifier(
        self,
        frozen: Any,
        definition: Mapping[str, Any],
        verifier: Path,
        candidate: Path,
        task_id: str,
        manifest_sha256: str,
        deadline: float,
    ) -> dict[str, Any]:
        docker = Path("/usr/local/bin/docker")
        if not docker.is_file() or time.monotonic() >= deadline:
            raise ControllerError("pinned Docker verifier runtime is unavailable or out of time")
        runtime = definition["offline_verifier_runtime"]
        name = f"agentsmd-routing-v3-{secrets.token_hex(8)}"
        workspace_name = self.definition["tasks"][task_id]["workspace_name"]
        container_workspace = f"/workspaces/{workspace_name}"
        verifier_relative = verifier.resolve().relative_to(frozen.root).as_posix()
        command = [
            str(docker), "run", "--rm", "--name", name,
            "--platform", runtime["platform"], "--network", runtime["network"],
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", str(runtime["pids_limit"]), "--memory", f"{runtime['memory_mebibytes']}m",
            "--memory-swap", f"{runtime['memory_mebibytes']}m", "--cpus", str(runtime["cpus"]),
            "--ulimit", "nofile=128:128", "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=268435456",
            "--user", "65534:65534", "--env", "HOME=/tmp", "--env", "TMPDIR=/tmp",
            "--env", "PATH=/usr/bin:/bin", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={frozen.root},target=/package,readonly",
            "--mount", f"type=bind,source={candidate},target={container_workspace},readonly",
            "--entrypoint", "/usr/bin/python3", runtime["image_id"], "-B", "/package/verifiers/entrypoint.py",
            "--workspace", container_workspace, "--expected-manifest-sha256", manifest_sha256,
            "--verifier", verifier_relative,
        ]
        marker = f"routing-v3-docker-{secrets.token_hex(16)}"
        environment = {**SAFE_ENV, "ROUTING_RUN_MARKER": marker}
        output_root = candidate.parent / f"docker-{task_id}-public-{secrets.token_hex(4)}"
        output_root.mkdir(mode=0o700)
        before = frozen.tree_manifest.build_tree_manifest(candidate)["sha256"]
        try:
            receipt = execution.run_bounded_process(
                command,
                cwd=frozen.root,
                environment=environment,
                stdin_bytes=b"",
                stdout_path=output_root / "stdout",
                stderr_path=output_root / "stderr",
                deadline_monotonic=deadline,
                run_marker=marker,
            )
        finally:
            subprocess.run([str(docker), "rm", "-f", name], cwd=str(frozen.root), env=SAFE_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=20)
        after = frozen.tree_manifest.build_tree_manifest(candidate)["sha256"]
        if before != manifest_sha256 or after != manifest_sha256:
            raise ControllerError("candidate changed during read-only Docker verification")
        status = "PASS" if receipt.returncode == 0 and not receipt.timed_out and not receipt.survivor_pids else "FAIL" if receipt.returncode == 1 else "ERROR"
        return {"status": status, "verifier_sha256": sha256_file(verifier), "workspace_manifest_sha256": manifest_sha256, "process": receipt.as_dict()}

    def _verify_openbot(self, candidate: Path, deadline: float) -> Mapping[str, Any]:
        records: dict[str, Any] = {}
        before_manifest = strict_tree_manifest(candidate)["sha256"]
        verifier_path = (
            candidate
            / ".benchmark"
            / "public"
            / "openbot_acp_public.test.ts"
        )
        stage = candidate.parent / f"verify-public-{secrets.token_hex(4)}"
        stage.mkdir(mode=0o700)
        paths = isolation.CodexPaths(
            candidate_root=candidate,
            home=stage / "home",
            codex_home=stage / "codex-home",
            codex_sqlite_home=stage / "sqlite",
            tmpdir=candidate / ".runner-tmp",
            auth_target=stage / "unused-auth",
            controller_root=stage,
            memory_root=self.config.memory_root,
        )
        marker = f"routing-v3-verify-{secrets.token_hex(16)}"
        child_environment = {
            "ROUTING_RUN_MARKER": marker,
            "ROUTING_CANDIDATE_ACP": str(candidate / "daemon" / "src" / "acp.ts"),
        }
        isolation.write_permission_profile(
            paths,
            reviewer=True,
            child_environment=child_environment,
            runtime_roots=(*self._profile_runtime_roots(), PACKAGE_ROOT),
            command_path=self._command_path(),
        )
        environment = isolation.build_clean_environment(
            paths,
            command_path=self._command_path(),
            extra=child_environment,
        )
        command = [
            str(self.config.codex_executable),
            "sandbox",
            "-P",
            isolation.PROFILE_REVIEWER,
            "-C",
            str(candidate),
            "--",
            str(self._runtime_node()),
            "--import",
            str(candidate / "node_modules" / "tsx" / "dist" / "loader.mjs"),
            "--test",
            str(verifier_path),
        ]
        try:
            receipt = execution.run_bounded_process(
                command,
                cwd=candidate,
                environment=environment,
                stdin_bytes=b"",
                stdout_path=stage / "stdout",
                stderr_path=stage / "stderr",
                deadline_monotonic=deadline,
                run_marker=marker,
            )
        except execution.ExecutionError as exc:
            raise BoundaryFailure(
                f"public OpenBot verifier containment failed: {exc}"
            ) from exc
        finally:
            _remove_runner_tmp(candidate)
        if receipt.timed_out:
            raise StageTimeout("public OpenBot verifier reached the shared deadline")
        if receipt.survivor_pids:
            raise BoundaryFailure(
                "public OpenBot verifier retained a process",
                evidence={"process": receipt.as_dict()},
            )
        records["public"] = (
            "PASS" if receipt.returncode == 0 else "FAIL" if receipt.returncode == 1 else "ERROR"
        )
        records["public_receipt"] = receipt.as_dict()
        hidden = self._split_hidden_verifier("openbot-acp", candidate, deadline)
        records["hidden"] = hidden["status"]
        records["hidden_receipt"] = hidden
        if strict_tree_manifest(candidate)["sha256"] != before_manifest:
            raise ControllerError("candidate changed during read-only OpenBot verification")
        return records

    def validate_canary_audit(self, audit_path: Path) -> dict[str, Any]:
        audit = _load_canonical(audit_path.resolve())
        audit_hash = sha256_file(audit_path.resolve())
        with self._locked():
            state = self._load_state()
            state = lifecycle.record_canary_audit(state, self.definition, audit=audit, audit_sha256=audit_hash)
            self._save_state(state)
        _atomic_json(self.root / "canary-audit.json", audit)
        return audit

    def collect(self) -> dict[str, Any]:
        with self._locked():
            state = self._load_state()
            state_bytes = lifecycle.canonical_state_bytes(state)
            run_order = state["run_order"]
            terminal_cells = state["terminal_cells"]
            audit_state = state.get("canary_audit")
            if state.get("active_cell") is not None:
                raise ControllerError("collection rejects an active lifecycle cell")
            if [cell.get("cell_id") for cell in terminal_cells] != run_order:
                raise ControllerError("collection requires every frozen cell in exact order")
            if any(
                cell.get("terminal", {}).get("status")
                not in lifecycle.SCORABLE_FAILURE_STATUSES | {"ACCEPTED"}
                for cell in terminal_cells
            ):
                raise ControllerError(
                    "collection rejects a safety or integrity terminal status"
                )
            if not isinstance(audit_state, Mapping) or audit_state.get("status") != "ACCEPT":
                raise ControllerError("collection requires the accepted canary audit")
            audit_path = self.root / "canary-audit.json"
            audit = _load_canonical(audit_path)
            expected_audit = dict(audit_state)
            audit_sha256 = expected_audit.pop("audit_sha256", None)
            if (
                audit_sha256 != sha256_file(audit_path)
                or audit != expected_audit
            ):
                raise ControllerError("canary audit file does not bind lifecycle state")

            results: list[dict[str, Any]] = []
            for cell in terminal_cells:
                cell_id = str(cell["cell_id"])
                attempt = self.root / "attempts" / cell_id
                result_path = attempt / "result.json"
                result = _load_canonical(result_path)
                if sha256_file(result_path) != cell["terminal"]["result_sha256"]:
                    raise ControllerError(
                        f"result hash does not bind lifecycle state: {cell_id}"
                    )

                terminal_status = str(cell["terminal"]["status"])
                if terminal_status != "ACCEPTED":
                    implementation_receipt = self._load_optional_receipt(
                        attempt / "implementation-receipt.json"
                    )
                    verification_receipt = self._load_optional_receipt(
                        attempt / "verification-receipt.json"
                    )
                    review_receipt = self._load_optional_receipt(
                        attempt / "review-receipt.json"
                    )
                    implementation_state = cell["implementation"]
                    verification_state = cell["verification"]
                    review_state = cell["review"]
                    artifact, artifact_sha256 = self._load_attempt_artifact(
                        attempt,
                        expected_sha256=(
                            implementation_state.get("artifact_sha256")
                            if isinstance(implementation_state, Mapping)
                            else None
                        ),
                    )
                    for receipt, stage_state, path, label in (
                        (
                            implementation_receipt,
                            implementation_state,
                            attempt / "implementation-receipt.json",
                            "implementation",
                        ),
                        (
                            verification_receipt,
                            verification_state,
                            attempt / "verification-receipt.json",
                            "verification",
                        ),
                        (
                            review_receipt,
                            review_state,
                            attempt / "review-receipt.json",
                            "review",
                        ),
                    ):
                        if isinstance(stage_state, Mapping) and (
                            receipt is None
                            or sha256_file(path) != stage_state["receipt_sha256"]
                        ):
                            raise ControllerError(
                                f"{label} evidence does not bind lifecycle state: {cell_id}"
                    )
                    if artifact is not None:
                        snapshot_path = attempt / "artifact-snapshot"
                        try:
                            snapshot_state = snapshot_path.lstat()
                        except FileNotFoundError as exc:
                            raise ControllerError(
                                f"failed-cell artifact snapshot is not a real directory: {cell_id}"
                            ) from exc
                        if (
                            not stat.S_ISDIR(snapshot_state.st_mode)
                            or stat.S_ISLNK(snapshot_state.st_mode)
                        ):
                            raise ControllerError(
                                f"failed-cell artifact snapshot is not a real directory: {cell_id}"
                            )
                        snapshot = strict_tree_manifest(snapshot_path)
                        if (
                            artifact.get("cell_id") != cell_id
                            or artifact.get("snapshot_manifest_sha256")
                            != snapshot["sha256"]
                        ):
                            raise ControllerError(
                                f"failed-cell artifact is not immutable and bound: {cell_id}"
                            )
                    expected_result = self._terminal_payload(
                        cell_id,
                        terminal_status,
                        implementation_receipt,
                        verification_receipt,
                        review_receipt,
                        artifact=artifact,
                        artifact_sha256=artifact_sha256,
                        error=result.get("error"),
                        failure_evidence=result.get("failure_evidence"),
                    )
                    if result != expected_result:
                        raise ControllerError(
                            f"terminal result differs from failed-cell evidence: {cell_id}"
                        )
                    results.append(result)
                    continue

                implementation_state = cell["implementation"]
                verification_state = cell["verification"]
                review_state = cell["review"]
                if not all(
                    isinstance(item, Mapping)
                    for item in (
                        implementation_state,
                        verification_state,
                        review_state,
                    )
                ):
                    raise ControllerError(
                        f"accepted cell lacks complete stage state: {cell_id}"
                    )

                implementation_path = attempt / "implementation-receipt.json"
                artifact_path = attempt / "artifact.json"
                verification_path = attempt / "verification-receipt.json"
                review_path = attempt / "review-receipt.json"
                implementation_receipt = _load_canonical(implementation_path)
                artifact = _load_canonical(artifact_path)
                verification_receipt = _load_canonical(verification_path)
                review_receipt = _load_canonical(review_path)
                artifact_sha256 = sha256_file(artifact_path)
                if (
                    sha256_file(implementation_path)
                    != implementation_state["receipt_sha256"]
                    or artifact_sha256 != implementation_state["artifact_sha256"]
                    or sha256_file(verification_path)
                    != verification_state["receipt_sha256"]
                    or sha256_file(review_path) != review_state["receipt_sha256"]
                    or artifact.get("cell_id") != cell_id
                ):
                    raise ControllerError(
                        f"stage evidence does not bind lifecycle state: {cell_id}"
                    )

                _rebuilt_range, review_range_sha256, baseline, snapshot = (
                    self._rebuild_attempt_review_range(attempt, artifact)
                )
                review_workspace = attempt / "review-workspace"
                workspace_manifest = strict_tree_manifest(review_workspace)
                artifact_entries = snapshot["entries"]
                workspace_artifact_entries = [
                    entry
                    for entry in workspace_manifest["entries"]
                    if entry["path"] != ".benchmark"
                    and not str(entry["path"]).startswith(".benchmark/")
                ]
                workspace_overlay_paths = {
                    str(entry["path"])
                    for entry in workspace_manifest["entries"]
                    if entry["path"] == ".benchmark"
                    or str(entry["path"]).startswith(".benchmark/")
                }
                if (
                    workspace_artifact_entries != artifact_entries
                    or workspace_overlay_paths
                    != {".benchmark", ".benchmark/review-range.json"}
                ):
                    raise ControllerError(
                        f"review workspace is not the artifact plus exact range: {cell_id}"
                    )

                response = review_receipt.get("response")
                artifact_binding = review_receipt.get("artifact_binding")
                expected_response_fields = {
                    "status",
                    "artifact_sha256",
                    "review_range_sha256",
                    "summary",
                    "findings",
                }
                if (
                    not isinstance(response, Mapping)
                    or set(response) != expected_response_fields
                    or response.get("status") != "PASS"
                    or response.get("artifact_sha256") != artifact_sha256
                    or response.get("review_range_sha256") != review_range_sha256
                    or response.get("findings") != []
                    or review_state.get("artifact_sha256") != artifact_sha256
                    or review_state.get("review_range_sha256")
                    != review_range_sha256
                ):
                    raise ControllerError(
                        f"accepted Luna review does not bind the exact range: {cell_id}"
                    )
                expected_binding = {
                    "artifact_evidence_sha256": artifact_sha256,
                    "baseline_manifest_sha256": baseline["sha256"],
                    "artifact_manifest_sha256": snapshot["sha256"],
                    "review_range_sha256": review_range_sha256,
                    "review_workspace_range_sha256": review_range_sha256,
                    "review_workspace_artifact_manifest_sha256": snapshot["sha256"],
                    "review_workspace_before_sha256": workspace_manifest["sha256"],
                    "review_workspace_after_sha256": workspace_manifest["sha256"],
                    "baseline_before_sha256": baseline["sha256"],
                    "baseline_after_sha256": baseline["sha256"],
                    "artifact_before_sha256": snapshot["sha256"],
                    "artifact_after_sha256": snapshot["sha256"],
                }
                if artifact_binding != expected_binding:
                    raise ControllerError(
                        f"review workspace binding differs from live evidence: {cell_id}"
                    )

                expected_result = self._terminal_payload(
                    cell_id,
                    "ACCEPTED",
                    implementation_receipt,
                    verification_receipt,
                    review_receipt,
                    artifact=artifact,
                    artifact_sha256=artifact_sha256,
                )
                if result != expected_result:
                    raise ControllerError(
                        f"terminal result differs from accepted evidence: {cell_id}"
                    )
                results.append(result)

            if self.state_path.read_bytes() != state_bytes:
                raise ControllerError("lifecycle state changed during collection")
            collection = {
                "schema_version": 1,
                "definition_sha256": self.definition_sha256,
                "package_sha256": self.package_sha256,
                "state_sha256": sha256_bytes(state_bytes),
                "results": results,
            }
            _exclusive_json(self.root / "collection.json", collection)
            return collection

    def _evaluator_payloads(
        self, state: Mapping[str, Any], seed: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        terminal_cells = state["terminal_cells"]
        run_order = state["run_order"]
        if (
            len(terminal_cells) != len(run_order)
            or [cell["cell_id"] for cell in terminal_cells] != run_order
            or any(
                cell["terminal"]["status"]
                not in lifecycle.SCORABLE_FAILURE_STATUSES | {"ACCEPTED"}
                for cell in terminal_cells
            )
        ):
            raise ControllerError(
                "the evaluator requires every frozen cell to have a scorable terminal result"
            )
        collection_path = self.root / "collection.json"
        collection = _load_canonical(collection_path)
        supplied_state_sha256 = sha256_bytes(
            lifecycle.canonical_state_bytes(state)
        )
        if (
            collection.get("definition_sha256") != self.definition_sha256
            or collection.get("package_sha256") != self.package_sha256
            or collection.get("state_sha256") != supplied_state_sha256
            or supplied_state_sha256 != sha256_file(self.state_path)
            or not isinstance(collection.get("results"), list)
            or len(collection["results"]) != len(run_order)
        ):
            raise ControllerError("collection does not bind the completed lifecycle")

        terminal_by_id = {str(cell["cell_id"]): cell for cell in terminal_cells}
        result_by_id = {
            str(result.get("cell_id")): result for result in collection["results"]
            if isinstance(result, Mapping)
        }
        if set(result_by_id) != set(run_order):
            raise ControllerError("collection result identities differ from the run order")
        by_task: dict[str, list[str]] = {
            task: [] for task in self.definition["tasks"]
        }
        for cell_id in run_order:
            if terminal_by_id[cell_id]["terminal"]["status"] == "ACCEPTED":
                by_task[self.definition["cells"][cell_id]["task"]].append(cell_id)
        incomplete_tasks = sorted(
            task_id for task_id, cells in by_task.items() if len(cells) < 2
        )
        if incomplete_tasks:
            raise ControllerError(
                "the evaluator requires at least two accepted artifacts per task: "
                + ", ".join(incomplete_tasks)
            )

        seed_hash = sha256_bytes(seed.encode("utf-8"))
        randomizer = random.Random(seed)
        task_ids = list(by_task)
        randomizer.shuffle(task_ids)
        anonymous_tasks: list[dict[str, Any]] = []
        mapping: dict[str, Any] = {
            "schema_version": 1,
            "shuffle_seed": seed,
            "seed_sha256": seed_hash,
            "tasks": {},
        }
        snapshot_bindings: dict[str, str] = {}
        for task_index, task_id in enumerate(task_ids, 1):
            task_alias = f"task-{task_index}"
            cells = list(by_task[task_id])
            randomizer.shuffle(cells)
            variants: list[dict[str, Any]] = []
            variant_mapping: dict[str, str] = {}
            for variant_index, cell_id in enumerate(cells, 1):
                alias = f"variant-{variant_index}"
                cell_state = terminal_by_id[cell_id]
                result = result_by_id[cell_id]
                attempt = self.root / "attempts" / cell_id
                result_path = attempt / "result.json"
                artifact_path = attempt / "artifact.json"
                snapshot = attempt / "artifact-snapshot"
                implementation_state = cell_state.get("implementation")
                if not isinstance(implementation_state, Mapping):
                    raise ControllerError(f"accepted cell lacks artifact state: {cell_id}")
                artifact = _load_canonical(artifact_path)
                snapshot_manifest = strict_tree_manifest(snapshot)
                artifact_hash = sha256_file(artifact_path)
                if (
                    sha256_file(result_path) != cell_state["terminal"]["result_sha256"]
                    or result != _load_canonical(result_path)
                    or artifact_hash != implementation_state["artifact_sha256"]
                    or result.get("artifact") != artifact
                    or result.get("artifact_sha256") != artifact_hash
                    or artifact.get("snapshot_manifest_sha256")
                    != snapshot_manifest["sha256"]
                    or result.get("artifact_snapshot_manifest_sha256")
                    != snapshot_manifest["sha256"]
                ):
                    raise ControllerError(
                        f"accepted artifact is not immutable and bound: {cell_id}"
                    )
                scope = artifact.get("scope")
                changed_files = (
                    scope.get("changed_file_paths")
                    if isinstance(scope, Mapping)
                    else None
                )
                if not isinstance(changed_files, list) or not all(
                    isinstance(relative, str) and relative for relative in changed_files
                ):
                    raise ControllerError(f"artifact changed-file scope is invalid: {cell_id}")
                files: dict[str, str | None] = {}
                for relative in changed_files:
                    relative_path = Path(relative)
                    if relative_path.is_absolute() or ".." in relative_path.parts:
                        raise ControllerError(f"artifact contains an unsafe path: {cell_id}")
                    path = snapshot / relative_path
                    if path.exists() or path.is_symlink():
                        state_value = path.lstat()
                        if (
                            not stat.S_ISREG(state_value.st_mode)
                            or stat.S_ISLNK(state_value.st_mode)
                            or state_value.st_nlink != 1
                        ):
                            raise ControllerError(
                                f"artifact evaluator input is not an ordinary file: {cell_id}"
                            )
                        files[relative] = base64.b64encode(path.read_bytes()).decode("ascii")
                    else:
                        files[relative] = None
                variants.append(
                    {
                        "variant": alias,
                        "artifact_sha256": artifact_hash,
                        "files_base64": files,
                    }
                )
                variant_mapping[alias] = cell_id
                snapshot_bindings[cell_id] = snapshot_manifest["sha256"]
            packet = PACKAGE_ROOT / self.definition["tasks"][task_id]["packet"] / "TASK.md"
            anonymous_tasks.append(
                {
                    "task_alias": task_alias,
                    "task": packet.read_text(encoding="utf-8"),
                    "variants": variants,
                }
            )
            mapping["tasks"][task_alias] = {
                "task_id": task_id,
                "variants": variant_mapping,
            }
        bundle = {
            "schema_version": 1,
            "anonymous": True,
            "shuffle_seed_sha256": seed_hash,
            "tasks": anonymous_tasks,
        }
        return bundle, mapping, snapshot_bindings

    @staticmethod
    def _grok_usage_unavailable() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "observer": "grok-cli-1.0.13",
            "status": "UNAVAILABLE",
            "reason": "the pinned Grok CLI exposes no account-quota snapshot command",
            "captured_at": utc_now(),
        }

    @staticmethod
    def _first_ordinary_probe_target(path: Path) -> Path:
        candidates = [path] if path.is_file() else sorted(path.rglob("*"))
        for candidate in candidates:
            try:
                state = candidate.lstat()
            except OSError:
                continue
            if stat.S_ISREG(state.st_mode) and state.st_nlink == 1:
                return candidate.resolve(strict=True)
        raise ControllerError("evaluator denial target has no ordinary control file")

    @staticmethod
    def _evaluator_environment(private: Path) -> tuple[dict[str, str], dict[str, Path]]:
        home = private / "home"
        tmp = private / "tmp"
        runtime = private / "runtime"
        grok_home = home / ".grok"
        xdg = {
            "XDG_CONFIG_HOME": home / ".config",
            "XDG_CACHE_HOME": home / ".cache",
            "XDG_DATA_HOME": home / ".local" / "share",
            "XDG_STATE_HOME": home / ".local" / "state",
            "XDG_RUNTIME_DIR": runtime,
        }
        for path in (home, tmp, runtime):
            path.mkdir(mode=0o700)
        for path in sorted({grok_home, *xdg.values()}):
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.chmod(0o700)
        environment = {
            **SAFE_ENV,
            "TERM": "dumb",
            "HOME": str(home),
            "GROK_HOME": str(grok_home),
            "TMPDIR": str(tmp),
            **{name: str(path) for name, path in xdg.items()},
            "GROK_AUTO_UPDATE": "0",
            "GROK_DISABLE_AUTOUPDATER": "1",
            "GROK_SANDBOX": "off",
            "GROK_AUTH_EARLY_INVALIDATION_SECS": "0",
            "GROK_MEMORY": "0",
            "GROK_SUBAGENTS": "0",
            "GROK_WORKFLOWS": "0",
            "GROK_WEB_FETCH": "0",
            "GROK_DISABLE_WEB_FETCH": "1",
            "GROK_TELEMETRY_ENABLED": "0",
            "GROK_TELEMETRY_MIXPANEL_ENABLED": "0",
            "GROK_TELEMETRY_TRACE_UPLOAD": "0",
            "GROK_FEEDBACK_ENABLED": "0",
            "GROK_FEEDBACK_TRACE_CARD": "0",
            "GROK_EXTERNAL_OTEL": "0",
            "GROK_INSTRUMENTATION": "0",
            "GROK_WORKSPACE_DATA_COLLECTION_DISABLED": "1",
            "OTEL_SDK_DISABLED": "true",
            "OTEL_TRACES_EXPORTER": "none",
            "GROK_MANAGED_MCPS_ENABLED": "0",
            "GROK_MANAGED_MCP_GATEWAY_TOOLS_ENABLED": "0",
            "GROK_CURSOR_SKILLS_ENABLED": "0",
            "GROK_CURSOR_RULES_ENABLED": "0",
            "GROK_CURSOR_AGENTS_ENABLED": "0",
            "GROK_CURSOR_MCPS_ENABLED": "0",
            "GROK_CURSOR_HOOKS_ENABLED": "0",
            "GROK_CURSOR_SESSIONS_ENABLED": "0",
            "GROK_CLAUDE_SKILLS_ENABLED": "0",
            "GROK_CLAUDE_RULES_ENABLED": "0",
            "GROK_CLAUDE_AGENTS_ENABLED": "0",
            "GROK_CLAUDE_MCPS_ENABLED": "0",
            "GROK_CLAUDE_HOOKS_ENABLED": "0",
            "GROK_CLAUDE_SESSIONS_ENABLED": "0",
        }
        return environment, {
            "home": home,
            "tmp": tmp,
            "runtime": runtime,
            "grok_home": grok_home,
        }

    def _run_evaluator_profile_command(
        self,
        *,
        command: Sequence[str],
        cwd: Path,
        environment: Mapping[str, str],
        output_root: Path,
        label: str,
        deadline: float,
    ) -> tuple[execution.ProcessReceipt, bytes, bytes]:
        stage = output_root / label
        stage.mkdir(mode=0o700)
        stdout = stage / "stdout"
        stderr = stage / "stderr"
        receipt = execution.run_bounded_process(
            command,
            cwd=cwd,
            environment=environment,
            stdin_bytes=b"",
            stdout_path=stdout,
            stderr_path=stderr,
            deadline_monotonic=deadline,
            run_marker=f"routing-v3-evaluator-probe-{secrets.token_hex(16)}",
        )
        if (
            receipt.timed_out
            or receipt.survivor_pids
            or not receipt.terminal_process_state
            or receipt.broker_usage_observed
            or not receipt.launch_observation_complete
        ):
            raise BoundaryFailure(f"evaluator preflight process proof failed: {label}")
        return receipt, stdout.read_bytes(), stderr.read_bytes()

    def _evaluator_preflight(
        self,
        *,
        prepared: evaluator.PreparedInputs,
        prompt_path: Path,
        schema_path: Path,
        executable: Path,
        expected_version: str,
        environment: Mapping[str, str],
        roots: Mapping[str, Path],
        private: Path,
        deadline: float,
    ) -> tuple[dict[str, Any], str, Path, str, str]:
        probe = private / "evaluator-probe"
        probe_build = _build_evaluator_probe(probe)
        denied_roots = {
            "private_mapping": prepared.mapping_path,
            "attempts": self.root / "attempts",
            "memory": self.config.memory_root,
        }
        unique_sources: dict[Path, str] = {}
        for label, source in (
            ("use_grok_source", self.config.use_grok_repo),
            ("karpathy_source", self.config.karpathy_repo),
            ("openbot_source", self.config.openbot_repo),
        ):
            unique_sources.setdefault(source.resolve(strict=True), label)
        denied_roots.update({label: path for path, label in unique_sources.items()})
        denied_targets = {
            label: self._first_ordinary_probe_target(path)
            for label, path in denied_roots.items()
        }
        allowed_write_targets = {
            "home": roots["home"] / "write-control",
            "tmp": roots["tmp"] / "write-control",
        }
        for path in allowed_write_targets.values():
            _write_private_file(path, b"control\n", mode=0o600)
        readable = [prepared.bundle_path, prompt_path, schema_path]
        metadata_only = [
            prepared.bundle_path.parent,
            *denied_targets.values(),
        ]
        production_profile, production_profile_sha256 = _evaluator_sandbox_profile(
            executable=executable,
            readable_files=readable,
            writable_roots=[roots["home"], roots["tmp"], roots["runtime"]],
            metadata_only_paths=metadata_only,
        )
        probe_profile, probe_profile_sha256 = _evaluator_sandbox_profile(
            executable=probe,
            readable_files=readable,
            writable_roots=[roots["home"], roots["tmp"], roots["runtime"]],
            metadata_only_paths=metadata_only,
        )
        production_policy_core = production_profile.replace(
            json.dumps(str(executable)), json.dumps("<BOUND-EXECUTABLE>")
        )
        probe_policy_core = probe_profile.replace(
            json.dumps(str(probe)), json.dumps("<BOUND-EXECUTABLE>")
        )
        if production_policy_core != probe_policy_core:
            raise ControllerError("evaluator probe and production policy cores differ")
        policy_core_sha256 = sha256_bytes(production_policy_core.encode("utf-8"))
        production_profile_path = private / "evaluator.sb"
        probe_profile_path = private / "evaluator-probe.sb"
        if (
            _write_private_file(
                production_profile_path,
                production_profile.encode("utf-8"),
                mode=0o600,
            )
            != production_profile_sha256
            or _write_private_file(
                probe_profile_path, probe_profile.encode("utf-8"), mode=0o600
            )
            != probe_profile_sha256
        ):
            raise ControllerError("evaluator profile changed while it was persisted")

        output_root = private / "preflight-processes"
        output_root.mkdir(mode=0o700)
        sandbox = Path("/usr/bin/sandbox-exec")
        if not sandbox.is_file():
            raise ControllerError("sandbox-exec is unavailable for evaluator preflight")

        def run_probe(label: str, target: Path, *, denied: bool) -> dict[str, Any]:
            receipt, stdout, _stderr = self._run_evaluator_profile_command(
                command=[
                    str(sandbox),
                    "-f",
                    str(probe_profile_path),
                    str(probe),
                    "read",
                    str(target),
                ],
                cwd=prepared.bundle_path.parent,
                environment=environment,
                output_root=output_root,
                label=label,
                deadline=deadline,
            )
            try:
                result = json.loads(stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BoundaryFailure(f"evaluator probe output is malformed: {label}") from exc
            expected_returncode = 77 if denied else 0
            expected_category = "policy_denied" if denied else "success"
            if (
                receipt.returncode != expected_returncode
                or not isinstance(result, dict)
                or result.get("category") != expected_category
                or (
                    denied
                    and result.get("errno") not in {errno.EPERM, errno.EACCES}
                )
                or (not denied and result.get("errno") != 0)
            ):
                raise BoundaryFailure(f"evaluator file policy probe failed: {label}")
            return {"result": result, "process": receipt.as_dict()}

        def run_write(label: str, target: Path, *, denied: bool) -> dict[str, Any]:
            receipt, stdout, _stderr = self._run_evaluator_profile_command(
                command=[
                    str(sandbox),
                    "-f",
                    str(probe_profile_path),
                    str(probe),
                    "write",
                    str(target),
                ],
                cwd=prepared.bundle_path.parent,
                environment=environment,
                output_root=output_root,
                label=label,
                deadline=deadline,
            )
            try:
                result = json.loads(stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BoundaryFailure(f"evaluator write probe is malformed: {label}") from exc
            expected_returncode = 77 if denied else 0
            expected_category = "policy_denied" if denied else "success"
            if (
                receipt.returncode != expected_returncode
                or not isinstance(result, dict)
                or result.get("category") != expected_category
                or (
                    denied
                    and result.get("errno") not in {errno.EPERM, errno.EACCES}
                )
                or (not denied and result.get("errno") != 0)
            ):
                raise BoundaryFailure(f"evaluator write policy probe failed: {label}")
            return {"result": result, "process": receipt.as_dict()}

        positive = {
            label: run_probe(f"allowed-{label}", path, denied=False)
            for label, path in {
                "bundle": prepared.bundle_path,
                "prompt": prompt_path,
                "schema": schema_path,
            }.items()
        }
        links = roots["home"] / "probe-links"
        links.mkdir(mode=0o700)
        denials: dict[str, Any] = {}
        for label, target in denied_targets.items():
            direct = run_probe(f"denied-{label}-direct", target, denied=True)
            link = links / label
            os.symlink(target, link)
            linked = run_probe(f"denied-{label}-symlink", link, denied=True)
            denials[label] = {"direct": direct, "symlink": linked}
        write_controls = {
            "allowed": {
                label: run_write(f"allowed-write-{label}", target, denied=False)
                for label, target in allowed_write_targets.items()
            },
            "denied": {
                "workspace": run_write(
                    "denied-write-workspace", prepared.bundle_path, denied=True
                ),
                **{
                    label: run_write(
                        f"denied-write-{label}", target, denied=True
                    )
                    for label, target in denied_targets.items()
                },
            },
        }

        network_denials: dict[str, Any] = {}
        for label, arguments in {
            "localhost_tcp_443": ["connect-localhost"],
            "localhost_ipv6_tcp_443": ["connect-localhost6"],
            "documentation_tcp_80": ["connect-other-port"],
            "unix_syslog": ["connect-unix", "/private/var/run/syslog"],
        }.items():
            receipt, stdout, _stderr = self._run_evaluator_profile_command(
                command=[
                    str(sandbox),
                    "-f",
                    str(probe_profile_path),
                    str(probe),
                    *arguments,
                ],
                cwd=prepared.bundle_path.parent,
                environment=environment,
                output_root=output_root,
                label=f"denied-network-{label}",
                deadline=deadline,
            )
            try:
                result = json.loads(stdout)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BoundaryFailure("evaluator network probe output is malformed") from exc
            if (
                receipt.returncode != 77
                or not isinstance(result, dict)
                or result.get("category") != "policy_denied"
                or result.get("errno") not in {errno.EPERM, errno.EACCES}
            ):
                raise BoundaryFailure(f"evaluator network policy probe failed: {label}")
            network_denials[label] = {
                "result": result,
                "process": receipt.as_dict(),
            }

        version_receipt, version_stdout, _version_stderr = (
            self._run_evaluator_profile_command(
                command=[
                    str(sandbox),
                    "-f",
                    str(production_profile_path),
                    str(executable),
                    "--no-leader",
                    "--sandbox",
                    "off",
                    "--no-auto-update",
                    "--version",
                ],
                cwd=prepared.bundle_path.parent,
                environment=environment,
                output_root=output_root,
                label="pinned-grok-version",
                deadline=deadline,
            )
        )
        try:
            observed_version = version_stdout.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise BoundaryFailure("sandboxed Grok version output is not UTF-8") from exc
        if version_receipt.returncode != 0 or observed_version != expected_version:
            raise BoundaryFailure("sandboxed Grok version differs from its exact pin")
        receipt = {
            "schema_version": 1,
            "status": "PASS",
            "no_model_calls": True,
            "production_profile_sha256": production_profile_sha256,
            "probe_profile_sha256": probe_profile_sha256,
            "policy_core_sha256": policy_core_sha256,
            "probe_build": probe_build,
            "required_read_controls": positive,
            "denied_read_controls": denials,
            "write_controls": write_controls,
            "network_denials": network_denials,
            "sandboxed_grok_version": {
                "value": observed_version,
                "process": version_receipt.as_dict(),
            },
            "auth_not_required_or_present_for_preflight": True,
        }
        receipt_hash = _exclusive_json(private / "evaluator-preflight.json", receipt)
        return (
            receipt,
            receipt_hash,
            production_profile_path,
            production_profile_sha256,
            policy_core_sha256,
        )

    def run_evaluator(
        self, grok_executable: Path, grok_auth_source: Path
    ) -> dict[str, Any]:
        self._assert_pins()
        self._require_package_review()
        executable, identity = self._assert_grok_pin(grok_executable)
        evaluator_root = self.root / "evaluator"
        deadline = time.monotonic() + float(
            self.definition["evaluator"]["inclusive_deadline_seconds"]
        )
        with self._locked():
            state = self._load_state()
            if evaluator_root.exists() or evaluator_root.is_symlink():
                raise ControllerError("the one-shot evaluator lifecycle already exists")
            seed = secrets.token_hex(32)
            bundle, mapping, snapshot_bindings = self._evaluator_payloads(state, seed)
            evaluator_root.mkdir(mode=0o700)
            workspace = evaluator_root / "workspace"
            evidence = evaluator_root / "private"
            workspace.mkdir(mode=0o700)
            evidence.mkdir(mode=0o700)
            prepared = evaluator.prepare_anonymous_inputs(
                bundle,
                mapping,
                evaluator_workspace=workspace,
                evidence_directory=evidence,
            )
            schema_source = (
                PACKAGE_ROOT / self.definition["evaluator"]["schema"]
            ).resolve(strict=True)
            try:
                schema_document = json.loads(schema_source.read_bytes())
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ControllerError("evaluator schema is invalid") from exc
            if not isinstance(schema_document, dict):
                raise ControllerError("evaluator schema must be an object")
            schema_path = workspace / "evaluator-schema.json"
            schema_sha256 = _write_private_file(
                schema_path, canonical_bytes(schema_document), mode=0o600
            )
            prompt_path, prompt_sha256 = evaluator.prepare_evaluator_prompt(
                prepared, workspace
            )
            state_sha256 = sha256_file(self.state_path)
            collection_sha256 = sha256_file(self.root / "collection.json")

        expected_roots = {
            "home": evidence / "home",
            "tmp": evidence / "tmp",
            "runtime": evidence / "runtime",
            "grok_home": evidence / "home" / ".grok",
        }
        preflight_entries = (
            expected_roots["home"],
            expected_roots["tmp"],
            expected_roots["runtime"],
            evidence / "evaluator-probe",
            evidence / "evaluator.sb",
            evidence / "evaluator-probe.sb",
            evidence / "evaluator-production.sb",
            evidence / "preflight-processes",
            evidence / "evaluator-preflight.json",
        )
        try:
            environment, roots = self._evaluator_environment(evidence)
            if dict(roots) != expected_roots:
                raise BoundaryFailure(
                    "evaluator environment returned unexpected runtime roots"
                )
            (
                preflight,
                preflight_sha256,
                profile_path,
                profile_sha256,
                policy_core_sha256,
            ) = self._evaluator_preflight(
                prepared=prepared,
                prompt_path=prompt_path,
                schema_path=schema_path,
                executable=executable,
                expected_version=identity["expected_isolated_version"],
                environment=environment,
                roots=roots,
                private=evidence,
                deadline=deadline,
            )
        except BaseException:
            preflight_cleanup_failed = False
            for entry in preflight_entries:
                try:
                    _remove_exact_controller_entry(entry)
                except OSError:
                    preflight_cleanup_failed = True
            if preflight_cleanup_failed or not all(
                _exact_controller_entry_absent(entry) for entry in preflight_entries
            ):
                raise BoundaryFailure("evaluator preflight cleanup failed") from None
            raise
        identity = {
            **identity,
            "observed_isolated_version": preflight["sandboxed_grok_version"][
                "value"
            ],
        }
        auth_target = roots["grok_home"] / "auth.json"
        auth_digest: str | None = None
        auth_identity: tuple[int, ...] | None = None
        auth_admission: str | None = None
        auth_markers: tuple[bytes, ...] = ()
        reservation: dict[str, Any] | None = None
        reservation_hash: str | None = None
        outcome: evaluator.EvaluatorOutcome | None = None
        run_failure: BaseException | None = None
        try:
            (
                auth_digest,
                auth_identity,
                auth_admission,
                auth_markers,
            ) = _copy_evaluator_auth(
                grok_auth_source,
                auth_target,
                minimum_valid_seconds=max(0.0, deadline - time.monotonic()) + 60.0,
            )
            with self._locked():
                if (
                    sha256_file(self.state_path) != state_sha256
                    or sha256_file(self.root / "collection.json")
                    != collection_sha256
                ):
                    raise BoundaryFailure(
                        "benchmark evidence changed during evaluator preflight"
                    )
                reservation = {
                    "schema_version": 1,
                    "definition_sha256": self.definition_sha256,
                    "package_sha256": self.package_sha256,
                    "state_sha256": state_sha256,
                    "collection_sha256": collection_sha256,
                    "prepared": prepared.as_dict(),
                    "prompt_sha256": prompt_sha256,
                    "schema_sha256": schema_sha256,
                    "snapshot_bindings": snapshot_bindings,
                    "grok_identity": identity,
                    "evaluator_profile_sha256": profile_sha256,
                    "evaluator_policy_core_sha256": policy_core_sha256,
                    "evaluator_preflight_sha256": preflight_sha256,
                    "environment_keys": sorted(environment),
                    "auth": {
                        "admission_category": auth_admission,
                        "explicit_source_validated": True,
                        "source_path_content_size_and_digest_persisted": False,
                        "copied_owner_0600_single_link_byte_equal": True,
                        "terminal_cleanup_required": True,
                    },
                    "reserved_at": utc_now(),
                }
                reservation_hash = _exclusive_json(
                    evidence / "evaluator-reservation.json", reservation
                )
            outcome = evaluator.run_grok_evaluator(
                prepared=prepared,
                evaluator_workspace=workspace,
                run_directory=evaluator_root / "run",
                schema_path=schema_path,
                grok_executable=executable,
                sandbox_executable=Path("/usr/bin/sandbox-exec"),
                sandbox_profile_path=profile_path,
                grok_model=self.definition["evaluator"]["model"],
                grok_identity_evidence=identity,
                environment=environment,
                environment_evidence={
                    "keys": sorted(environment),
                    "replacement_only": True,
                    "fresh_home_grok_home_tmp_and_xdg": True,
                    "auth_admission_category": auth_admission,
                    "auth_source_or_value_persisted": False,
                    "account_quota_observer": "unavailable",
                },
                sandbox_preflight_evidence={
                    "receipt_sha256": preflight_sha256,
                    "profile_sha256": profile_sha256,
                    "production_profile_sha256": profile_sha256,
                    "policy_core_sha256": policy_core_sha256,
                    "status": preflight["status"],
                    "no_model_calls": preflight["no_model_calls"],
                },
                before_usage=self._grok_usage_unavailable,
                after_usage=self._grok_usage_unavailable,
                deadline_monotonic=deadline,
                process_runner=execution.run_bounded_process,
            )
        except BaseException as exc:
            run_failure = exc
        cleanup_error: BaseException | None = None
        source_stable = False
        if auth_digest is not None and auth_identity is not None:
            try:
                _assert_evaluator_auth_source_stable(
                    grok_auth_source, digest=auth_digest, identity=auth_identity
                )
                source_stable = True
            except BaseException as exc:
                cleanup_error = exc
        for key in ("home", "tmp", "runtime"):
            try:
                _remove_exact_controller_entry(roots[key])
            except OSError as exc:
                if cleanup_error is None:
                    cleanup_error = exc
        run_retention: dict[str, Any] | None = None
        run_retention_sha256: str | None = None
        evidence_admission_failed = False
        rejected_run_absent: bool | None = None
        run_root = evaluator_root / "run"
        try:
            run_retention = _admit_evaluator_run_evidence(run_root, auth_markers)
            if run_failure is None and outcome is not None:
                _validate_evaluator_success_retention(outcome, run_retention)
            run_retention_sha256 = _exclusive_json(
                evidence / "evaluator-run-retention.json", run_retention
            )
        except BaseException:
            evidence_admission_failed = True
            run_retention = None
            run_retention_sha256 = None
            try:
                _remove_exact_controller_entry(run_root)
            except OSError:
                pass
            rejected_run_absent = _exact_controller_entry_absent(run_root)
        auth_cleanup = {
            "schema_version": 1,
            "source_stable": source_stable,
            "auth_destination_absent": _exact_controller_entry_absent(auth_target),
            "fresh_home_absent": _exact_controller_entry_absent(roots["home"]),
            "fresh_tmp_absent": _exact_controller_entry_absent(roots["tmp"]),
            "fresh_runtime_absent": _exact_controller_entry_absent(roots["runtime"]),
            "run_evidence_exact_allowlist_satisfied": bool(
                run_retention
                and run_retention.get("exact_allowlist_satisfied") is True
            ),
            "run_evidence_auth_material_scan": (
                run_retention.get("auth_material_scan")
                if run_retention is not None
                else "FAIL"
            ),
            "run_evidence_retention_sha256": run_retention_sha256,
            "rejected_run_absent": rejected_run_absent,
            "run_artifacts": (
                run_retention.get("files", [])
                if run_retention is not None
                else []
            ),
            "source_path_content_size_and_digest_persisted": False,
        }
        try:
            auth_cleanup_sha256 = _exclusive_json(
                evidence / "auth-cleanup.json", auth_cleanup
            )
        except BaseException:
            try:
                _remove_exact_controller_entry(run_root)
            except OSError:
                pass
            raise BoundaryFailure(
                "evaluator cleanup evidence could not be published"
            ) from None
        if (
            cleanup_error is not None
            or evidence_admission_failed
            or rejected_run_absent is False
            or not all(
                auth_cleanup[field]
                for field in (
                    "auth_destination_absent",
                    "fresh_home_absent",
                    "fresh_tmp_absent",
                    "fresh_runtime_absent",
                )
            )
        ):
            raise BoundaryFailure(
                "evaluator auth cleanup, evidence admission, or source stability failed"
            ) from None
        if run_failure is not None:
            if isinstance(run_failure, evaluator.EvaluatorRunError):
                raise ControllerError(
                    "the sole Grok evaluator call failed; retry is forbidden: "
                    + str(run_failure)
                ) from run_failure
            raise run_failure
        if outcome is None or reservation is None or reservation_hash is None:
            raise ControllerError("evaluator ended without bound outcome evidence")

        if strict_package_sha256() != self.package_sha256:
            raise BoundaryFailure("benchmark package changed during Grok evaluation")
        if (
            sha256_file(self.state_path) != reservation["state_sha256"]
            or sha256_file(self.root / "collection.json")
            != reservation["collection_sha256"]
        ):
            raise BoundaryFailure("benchmark lifecycle evidence changed during Grok evaluation")
        for cell_id, expected in snapshot_bindings.items():
            observed = strict_tree_manifest(
                self.root / "attempts" / cell_id / "artifact-snapshot"
            )["sha256"]
            if observed != expected:
                raise BoundaryFailure(
                    f"accepted artifact changed during Grok evaluation: {cell_id}"
                )
        evaluator.validate_prepared_inputs(prepared, workspace)
        private_mapping = _load_canonical(prepared.mapping_path)
        resolved_tasks: list[dict[str, Any]] = []
        for task in outcome.result["tasks"]:
            private_task = private_mapping["tasks"][task["task_alias"]]
            resolved_tasks.append(
                {
                    "task_alias": task["task_alias"],
                    "task_id": private_task["task_id"],
                    "preferred_cell_id": private_task["variants"][
                        task["preferred_variant"]
                    ],
                    "ranking": [
                        {
                            **dict(item),
                            "cell_id": private_task["variants"][item["variant"]],
                        }
                        for item in task["ranking"]
                    ],
                }
            )
        attribution = {
            "schema_version": 1,
            "pair_id": prepared.pair_id,
            "mapping_sha256": prepared.mapping_sha256,
            "evaluator_result_sha256": outcome.result_sha256,
            "tasks": resolved_tasks,
        }
        attribution_hash = _exclusive_json(
            evidence / "evaluator-attribution.json", attribution
        )
        controller_result = {
            "schema_version": 1,
            "status": "VALID",
            "definition_sha256": self.definition_sha256,
            "package_sha256": self.package_sha256,
            "reservation_sha256": reservation_hash,
            "preparation_receipt_sha256": prepared.preparation_receipt_sha256,
            "run_receipt_sha256": outcome.run_receipt_sha256,
            "auth_cleanup_sha256": auth_cleanup_sha256,
            "evaluator_run_retention_sha256": run_retention_sha256,
            "result_sha256": outcome.result_sha256,
            "attribution_sha256": attribution_hash,
            "usage_classification": {
                "category": "experiment_overhead",
                "scored": False,
            },
        }
        _exclusive_json(evidence / "controller-result.json", controller_result)
        return controller_result


def _overlap(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def _paths_from_args(args: argparse.Namespace) -> ControllerConfig:
    return ControllerConfig(
        state_root=args.state_root,
        use_grok_repo=args.use_grok_repo,
        karpathy_repo=args.karpathy_repo,
        openbot_repo=args.openbot_repo,
        openbot_runtime_source=args.openbot_runtime_source,
        codex_executable=args.codex_executable,
        codex_launcher=args.codex_launcher,
        node_executable=args.node_executable,
        auth_source=args.auth_source,
        codexbar_executable=args.codexbar_executable,
        memory_root=args.memory_root,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    parser.add_argument("--use-grok-repo", type=Path, required=True)
    parser.add_argument("--karpathy-repo", type=Path, required=True)
    parser.add_argument("--openbot-repo", type=Path, required=True)
    parser.add_argument("--openbot-runtime-source", type=Path, required=True)
    parser.add_argument("--codex-executable", type=Path, required=True)
    parser.add_argument("--codex-launcher", type=Path, required=True)
    parser.add_argument("--node-executable", type=Path, required=True)
    parser.add_argument("--auth-source", type=Path, required=True)
    parser.add_argument("--codexbar-executable", type=Path, default=Path("/opt/homebrew/bin/codexbar"))
    parser.add_argument("--memory-root", type=Path, default=Path.home() / ".codex" / "memories")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight")
    subparsers.add_parser("run-canary")
    audit = subparsers.add_parser("validate-canary-audit")
    audit.add_argument("audit", type=Path)
    subparsers.add_parser("run-next")
    subparsers.add_parser("collect")
    evaluator_command = subparsers.add_parser("run-evaluator")
    evaluator_command.add_argument("--grok-executable", type=Path, required=True)
    evaluator_command.add_argument("--grok-auth-source", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = Controller(_paths_from_args(args))
    actions = {
        "preflight": lambda: controller.preflight(),
        "run-canary": lambda: controller.run_canary(),
        "validate-canary-audit": lambda: controller.validate_canary_audit(args.audit),
        "run-next": lambda: controller.run_next(),
        "collect": lambda: controller.collect(),
        "run-evaluator": lambda: controller.run_evaluator(
            args.grok_executable, args.grok_auth_source
        ),
    }
    try:
        result = actions[args.command]()
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 1
    print(canonical_bytes(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
