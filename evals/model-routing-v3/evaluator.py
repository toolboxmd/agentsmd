#!/usr/bin/env python3
"""One-shot anonymous Grok evaluator for model-routing benchmark v3.

The module prepares a public bundle and private mapping as a mutually bound
pair, then owns one exact blocking Grok Build invocation. It never resumes,
retries, follows up, repairs, or makes a second evaluator call.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import stat
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence


HASH_LENGTH = 64
TASK_ALIAS_PREFIX = "task-"
VARIANT_ALIAS_PREFIX = "variant-"
MAX_EVALUATOR_PROMPT_BYTES = 4 * 1024 * 1024
PROMPT_BUNDLE_BEGIN = b"<exact-evaluator-bundle-json>\n"
PROMPT_BUNDLE_END = b"</exact-evaluator-bundle-json>\n"


class EvaluatorError(RuntimeError):
    """Evaluator evidence cannot be accepted without weakening the contract."""


class EvaluatorRunError(EvaluatorError):
    """The sole evaluator call ended without a valid accepted result."""

    def __init__(self, message: str, *, receipt: Mapping[str, Any], receipt_sha256: str):
        super().__init__(message)
        self.receipt = dict(receipt)
        self.receipt_sha256 = receipt_sha256


@dataclass(frozen=True, slots=True)
class PreparedInputs:
    bundle_path: Path
    mapping_path: Path
    preparation_receipt_path: Path
    pair_id: str
    bundle_sha256: str
    mapping_sha256: str
    preparation_receipt_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


@dataclass(frozen=True, slots=True)
class EvaluatorOutcome:
    result: Mapping[str, Any]
    result_path: Path
    result_sha256: str
    run_receipt: Mapping[str, Any]
    run_receipt_path: Path
    run_receipt_sha256: str


ProcessRunner = Callable[..., Any]
EvidenceHook = Callable[[], Mapping[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def canonical_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvaluatorError(f"value is not canonical JSON: {exc}") from exc


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_copy(value: Any) -> Any:
    return json.loads(canonical_bytes(value))


def _load_json(path: Path) -> Any:
    state = path.lstat()
    if not stat.S_ISREG(state.st_mode) or stat.S_ISLNK(state.st_mode):
        raise EvaluatorError(f"evidence is not an ordinary file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvaluatorError(f"invalid JSON evidence at {path}: {exc}") from exc


def _require_directory(path: Path, *, empty: bool = False) -> Path:
    if not path.is_absolute():
        raise EvaluatorError(f"directory must be absolute: {path}")
    state = path.lstat()
    if not stat.S_ISDIR(state.st_mode) or stat.S_ISLNK(state.st_mode):
        raise EvaluatorError(f"path is not a real directory: {path}")
    if empty and next(path.iterdir(), None) is not None:
        raise EvaluatorError(f"evaluator workspace must be empty: {path}")
    return path.resolve(strict=True)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=True))
        return True
    except ValueError:
        return False


def _stage_file(path: Path, data: bytes, *, mode: int = 0o600) -> Path:
    temporary = path.parent / f".{path.name}.{secrets.token_hex(16)}.prepared"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _publish_staged(staged: Mapping[Path, Path]) -> None:
    published: list[tuple[Path, tuple[int, int]]] = []
    try:
        for destination, temporary in staged.items():
            if destination.exists() or destination.is_symlink():
                raise EvaluatorError(f"one-shot evidence already exists: {destination}")
            temporary_state = temporary.stat()
            os.link(temporary, destination, follow_symlinks=False)
            published.append(
                (destination, (temporary_state.st_dev, temporary_state.st_ino))
            )
        for directory in {path.parent for path in staged}:
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except BaseException:
        for destination, identity in reversed(published):
            try:
                state = destination.lstat()
            except FileNotFoundError:
                continue
            if (state.st_dev, state.st_ino) == identity:
                destination.unlink()
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def _publish_json(path: Path, value: Any) -> str:
    data = canonical_bytes(value)
    temporary = _stage_file(path, data)
    _publish_staged({path: temporary})
    return sha256_bytes(data)


def _stage_documents(documents: Mapping[Path, bytes]) -> dict[Path, Path]:
    staged: dict[Path, Path] = {}
    try:
        for destination, data in documents.items():
            staged[destination] = _stage_file(destination, data)
    except BaseException:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        raise
    return staged


def _validate_alias(value: Any, *, prefix: str, field: str) -> str:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise EvaluatorError(f"{field} is not an anonymous alias")
    suffix = value.removeprefix(prefix)
    if not suffix.isdigit() or int(suffix) < 1:
        raise EvaluatorError(f"{field} is not a numbered anonymous alias")
    return value


def _validate_hash(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != HASH_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise EvaluatorError(f"{field} is not a lowercase SHA-256 digest")
    return value


def _validate_public_bundle(bundle: Mapping[str, Any]) -> dict[str, set[str]]:
    expected = {"schema_version", "anonymous", "shuffle_seed_sha256", "tasks"}
    if set(bundle) != expected or bundle.get("schema_version") != 1:
        raise EvaluatorError("anonymous bundle has unexpected top-level fields")
    if bundle.get("anonymous") is not True:
        raise EvaluatorError("evaluator bundle is not marked anonymous")
    _validate_hash(bundle.get("shuffle_seed_sha256"), "shuffle_seed_sha256")
    tasks = bundle.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 3:
        raise EvaluatorError("anonymous bundle must contain exactly three tasks")
    aliases: dict[str, set[str]] = {}
    for task in tasks:
        if not isinstance(task, dict) or set(task) != {"task_alias", "task", "variants"}:
            raise EvaluatorError("anonymous task has unexpected fields")
        task_alias = _validate_alias(
            task.get("task_alias"), prefix=TASK_ALIAS_PREFIX, field="task_alias"
        )
        if task_alias in aliases:
            raise EvaluatorError("anonymous task aliases are not unique")
        if not isinstance(task.get("task"), str) or not task["task"]:
            raise EvaluatorError("anonymous task text must be non-empty")
        variants = task.get("variants")
        if not isinstance(variants, list) or not 2 <= len(variants) <= 3:
            raise EvaluatorError("anonymous task must contain two or three variants")
        variant_aliases: set[str] = set()
        for variant in variants:
            if not isinstance(variant, dict) or set(variant) != {
                "variant",
                "artifact_sha256",
                "files_base64",
            }:
                raise EvaluatorError("anonymous variant has unexpected fields")
            alias = _validate_alias(
                variant.get("variant"),
                prefix=VARIANT_ALIAS_PREFIX,
                field="variant",
            )
            if alias in variant_aliases:
                raise EvaluatorError("anonymous variant aliases are not unique")
            variant_aliases.add(alias)
            _validate_hash(variant.get("artifact_sha256"), "artifact_sha256")
            files = variant.get("files_base64")
            if not isinstance(files, dict):
                raise EvaluatorError("files_base64 must be an object")
            for relative, encoded in files.items():
                if not isinstance(relative, str) or not relative or not isinstance(
                    encoded, (str, type(None))
                ):
                    raise EvaluatorError("files_base64 contains a malformed entry")
        aliases[task_alias] = variant_aliases
    return aliases


def _validate_private_mapping(
    mapping: Mapping[str, Any], public_aliases: Mapping[str, set[str]], seed_hash: str
) -> None:
    if set(mapping) != {"schema_version", "shuffle_seed", "seed_sha256", "tasks"}:
        raise EvaluatorError("private mapping has unexpected top-level fields")
    shuffle_seed = mapping.get("shuffle_seed")
    if not isinstance(shuffle_seed, str) or not shuffle_seed:
        raise EvaluatorError("private mapping has no recorded shuffle seed")
    if (
        mapping.get("schema_version") != 1
        or mapping.get("seed_sha256") != seed_hash
        or sha256_bytes(shuffle_seed.encode("utf-8")) != seed_hash
    ):
        raise EvaluatorError("private mapping seed does not bind the public bundle")
    tasks = mapping.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != set(public_aliases):
        raise EvaluatorError("private mapping task aliases differ from the bundle")
    task_ids: set[str] = set()
    cell_ids: set[str] = set()
    for task_alias, expected_variants in public_aliases.items():
        task = tasks[task_alias]
        if not isinstance(task, dict) or set(task) != {"task_id", "variants"}:
            raise EvaluatorError("private task mapping has unexpected fields")
        if not isinstance(task.get("task_id"), str) or not task["task_id"]:
            raise EvaluatorError("private task mapping has an invalid task id")
        if task["task_id"] in task_ids:
            raise EvaluatorError("private task ids are not unique")
        task_ids.add(task["task_id"])
        variants = task.get("variants")
        if not isinstance(variants, dict) or set(variants) != expected_variants:
            raise EvaluatorError("private variant aliases differ from the bundle")
        if any(not isinstance(value, str) or not value for value in variants.values()):
            raise EvaluatorError("private variant mapping has an invalid cell id")
        for cell_id in variants.values():
            if cell_id in cell_ids:
                raise EvaluatorError("private cell ids are not unique")
            cell_ids.add(cell_id)


def prepare_anonymous_inputs(
    bundle_payload: Mapping[str, Any],
    mapping_payload: Mapping[str, Any],
    *,
    evaluator_workspace: Path,
    evidence_directory: Path,
) -> PreparedInputs:
    """Publish a one-shot anonymous bundle and controller-only mapping.

    Each document carries the same pair commitment over both unbound payloads.
    The preparation receipt binds the exact final bytes. The private mapping
    is rejected if its destination is inside the evaluator workspace.
    """

    workspace = _require_directory(evaluator_workspace, empty=True)
    evidence = _require_directory(evidence_directory)
    bundle_path = workspace / "evaluator-bundle.json"
    mapping_path = evidence / "evaluator-mapping.json"
    receipt_path = evidence / "evaluator-preparation.json"
    if _is_within(mapping_path, workspace) or _is_within(receipt_path, workspace):
        raise EvaluatorError("private evaluator evidence cannot be inside the workspace")
    if any(path.exists() or path.is_symlink() for path in (bundle_path, mapping_path, receipt_path)):
        raise EvaluatorError("one-shot evaluator input evidence already exists")

    public = _json_copy(bundle_payload)
    private = _json_copy(mapping_payload)
    if not isinstance(public, dict) or not isinstance(private, dict):
        raise EvaluatorError("bundle and mapping payloads must be objects")
    if "binding" in public or "binding" in private:
        raise EvaluatorError("caller cannot pre-populate evaluator bindings")
    aliases = _validate_public_bundle(public)
    _validate_private_mapping(private, aliases, public["shuffle_seed_sha256"])

    bundle_payload_hash = sha256_bytes(canonical_bytes(public))
    mapping_payload_hash = sha256_bytes(canonical_bytes(private))
    pair_id = sha256_bytes(
        canonical_bytes(
            {
                "bundle_payload_sha256": bundle_payload_hash,
                "mapping_payload_sha256": mapping_payload_hash,
            }
        )
    )
    binding = {
        "schema_version": 1,
        "pair_id": pair_id,
        "bundle_payload_sha256": bundle_payload_hash,
        "mapping_payload_sha256": mapping_payload_hash,
    }
    bundle = {**public, "binding": binding}
    mapping = {**private, "binding": binding}
    bundle_bytes = canonical_bytes(bundle)
    mapping_bytes = canonical_bytes(mapping)
    bundle_hash = sha256_bytes(bundle_bytes)
    mapping_hash = sha256_bytes(mapping_bytes)
    receipt = {
        "schema_version": 1,
        "status": "PREPARED",
        "pair_id": pair_id,
        "bundle_payload_sha256": bundle_payload_hash,
        "mapping_payload_sha256": mapping_payload_hash,
        "bundle_sha256": bundle_hash,
        "mapping_sha256": mapping_hash,
    }
    receipt_bytes = canonical_bytes(receipt)
    receipt_hash = sha256_bytes(receipt_bytes)
    staged = _stage_documents(
        {
            mapping_path: mapping_bytes,
            bundle_path: bundle_bytes,
            receipt_path: receipt_bytes,
        }
    )
    _publish_staged(staged)
    return PreparedInputs(
        bundle_path=bundle_path,
        mapping_path=mapping_path,
        preparation_receipt_path=receipt_path,
        pair_id=pair_id,
        bundle_sha256=bundle_hash,
        mapping_sha256=mapping_hash,
        preparation_receipt_sha256=receipt_hash,
    )


def validate_prepared_inputs(prepared: PreparedInputs, evaluator_workspace: Path) -> dict[str, Any]:
    """Revalidate exact bytes, pair commitment, anonymity, and separation."""

    workspace = _require_directory(evaluator_workspace)
    if prepared.bundle_path.resolve(strict=True) != workspace / "evaluator-bundle.json":
        raise EvaluatorError("prepared bundle is not at the fixed workspace path")
    if _is_within(prepared.mapping_path, workspace):
        raise EvaluatorError("private evaluator mapping is inside the workspace")
    if _is_within(prepared.preparation_receipt_path, workspace):
        raise EvaluatorError("evaluator preparation receipt is inside the workspace")
    if sha256_file(prepared.bundle_path) != prepared.bundle_sha256:
        raise EvaluatorError("prepared evaluator bundle bytes changed")
    if sha256_file(prepared.mapping_path) != prepared.mapping_sha256:
        raise EvaluatorError("prepared evaluator mapping bytes changed")
    if sha256_file(prepared.preparation_receipt_path) != prepared.preparation_receipt_sha256:
        raise EvaluatorError("evaluator preparation receipt bytes changed")
    bundle = _load_json(prepared.bundle_path)
    mapping = _load_json(prepared.mapping_path)
    if not isinstance(bundle, dict) or not isinstance(mapping, dict):
        raise EvaluatorError("prepared evaluator documents must be objects")
    bundle_binding = bundle.pop("binding", None)
    mapping_binding = mapping.pop("binding", None)
    if bundle_binding != mapping_binding or not isinstance(bundle_binding, dict):
        raise EvaluatorError("prepared evaluator pair bindings differ")
    aliases = _validate_public_bundle(bundle)
    _validate_private_mapping(mapping, aliases, bundle["shuffle_seed_sha256"])
    bundle_payload_hash = sha256_bytes(canonical_bytes(bundle))
    mapping_payload_hash = sha256_bytes(canonical_bytes(mapping))
    expected_pair = sha256_bytes(
        canonical_bytes(
            {
                "bundle_payload_sha256": bundle_payload_hash,
                "mapping_payload_sha256": mapping_payload_hash,
            }
        )
    )
    expected_binding = {
        "schema_version": 1,
        "pair_id": expected_pair,
        "bundle_payload_sha256": bundle_payload_hash,
        "mapping_payload_sha256": mapping_payload_hash,
    }
    if bundle_binding != expected_binding or expected_pair != prepared.pair_id:
        raise EvaluatorError("prepared evaluator pair commitment is invalid")
    receipt = _load_json(prepared.preparation_receipt_path)
    expected_receipt = {
        "schema_version": 1,
        "status": "PREPARED",
        "pair_id": expected_pair,
        "bundle_payload_sha256": bundle_payload_hash,
        "mapping_payload_sha256": mapping_payload_hash,
        "bundle_sha256": prepared.bundle_sha256,
        "mapping_sha256": prepared.mapping_sha256,
    }
    if receipt != expected_receipt:
        raise EvaluatorError("evaluator preparation receipt does not bind the pair")
    return {
        "pair_id": expected_pair,
        "bundle_sha256": prepared.bundle_sha256,
        "mapping_sha256": prepared.mapping_sha256,
        "preparation_receipt_sha256": prepared.preparation_receipt_sha256,
        "aliases": {key: sorted(value) for key, value in aliases.items()},
    }


def _validate_schema(instance: Any, schema: Mapping[str, Any], path: str = "result") -> None:
    expected_type = schema.get("type")
    allowed = expected_type if isinstance(expected_type, list) else [expected_type]
    matches = False
    for kind in allowed:
        if kind == "object" and isinstance(instance, dict):
            matches = True
        elif kind == "array" and isinstance(instance, list):
            matches = True
        elif kind == "string" and isinstance(instance, str):
            matches = True
        elif kind == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            matches = True
        elif kind == "null" and instance is None:
            matches = True
    if expected_type is not None and not matches:
        raise EvaluatorError(f"{path} does not match schema type {expected_type!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise EvaluatorError(f"{path} is outside the schema enum")
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = [field for field in required if field not in instance]
        if missing:
            raise EvaluatorError(f"{path} is missing required fields: {missing}")
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(properties)
            if extra:
                raise EvaluatorError(f"{path} has additional fields: {sorted(extra)}")
        for field, value in instance.items():
            if field in properties:
                _validate_schema(value, properties[field], f"{path}.{field}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            raise EvaluatorError(f"{path} has too few items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise EvaluatorError(f"{path} has too many items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                _validate_schema(item, item_schema, f"{path}[{index}]")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise EvaluatorError(f"{path} is below the schema minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise EvaluatorError(f"{path} is above the schema maximum")


def validate_evaluator_result(
    result: Any,
    *,
    schema: Mapping[str, Any],
    public_aliases: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Validate the locked schema plus task, variant, and ranking semantics."""

    _validate_schema(result, schema)
    if not isinstance(result, dict):
        raise EvaluatorError("evaluator result must be an object")
    expected_tasks = {key: set(values) for key, values in public_aliases.items()}
    tasks = result.get("tasks")
    if not isinstance(tasks, list):
        raise EvaluatorError("evaluator tasks must be a list")
    seen_tasks: set[str] = set()
    for task in tasks:
        alias = task["task_alias"]
        if alias not in expected_tasks or alias in seen_tasks:
            raise EvaluatorError("evaluator task aliases are not exact and unique")
        seen_tasks.add(alias)
        expected_variants = expected_tasks[alias]
        ranking = task["ranking"]
        if len(ranking) != len(expected_variants):
            raise EvaluatorError("evaluator ranking cardinality differs from the bundle")
        variants = [item["variant"] for item in ranking]
        ranks = [item["rank"] for item in ranking]
        if set(variants) != expected_variants or len(set(variants)) != len(variants):
            raise EvaluatorError("evaluator variants are not exact and unique")
        if sorted(ranks) != list(range(1, len(ranking) + 1)):
            raise EvaluatorError("evaluator ranks are not exact and unique")
        preferred = task["preferred_variant"]
        if preferred not in expected_variants:
            raise EvaluatorError("preferred evaluator variant is unknown")
        if next(item["rank"] for item in ranking if item["variant"] == preferred) != 1:
            raise EvaluatorError("preferred evaluator variant must have rank 1")
    if seen_tasks != set(expected_tasks):
        raise EvaluatorError("evaluator omitted an anonymous task")
    return _json_copy(result)


def _process_receipt(value: Any, argv: Sequence[str]) -> dict[str, Any]:
    if hasattr(value, "as_dict"):
        value = value.as_dict()
    elif hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    receipt = _json_copy(value)
    if not isinstance(receipt, dict):
        raise EvaluatorError("process runner returned a non-object receipt")
    observed_argv = receipt.get("argv")
    if observed_argv is not None and list(observed_argv) != list(argv):
        raise EvaluatorError("process receipt argv differs from the sole evaluator call")
    receipt["argv"] = list(argv)
    return receipt


def _run_blocking_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    stdin_bytes: bytes,
    stdout_path: Path,
    stderr_path: Path,
    deadline_monotonic: float,
    run_marker: str,
) -> dict[str, Any]:
    """Small default runner. Production may inject the hardened controller runner."""

    started_at = utc_now()
    started = time.monotonic()
    timed_out = False
    process: subprocess.Popen[bytes] | None = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            process = subprocess.Popen(
                list(argv),
                cwd=str(cwd),
                env=dict(environment),
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                process.communicate(
                    input=stdin_bytes,
                    timeout=max(0.0, deadline_monotonic - time.monotonic()),
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())
        except OSError as exc:
            raise EvaluatorError(f"cannot execute Grok evaluator: {exc}") from exc
    finished = time.monotonic()
    return {
        "argv": list(argv),
        "returncode": process.returncode if process else None,
        "timed_out": timed_out,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_seconds": finished - started,
        "survivor_pids": [],
        "survivor_check": "default_runner_process_group_only",
    }


def _capture_hook(hook: EvidenceHook, label: str, run_directory: Path) -> tuple[dict[str, Any], str]:
    value = _json_copy(hook())
    if not isinstance(value, dict):
        raise EvaluatorError(f"{label} evidence hook returned a non-object")
    path = run_directory / f"{label}-usage.json"
    return value, _publish_json(path, value)


def _prompt(bundle_bytes: bytes, bundle_hash: str, pair_id: str) -> bytes:
    prefix = (
        "Goal: evaluate anonymous locked implementation variants.\n"
        "Question: compare every variant for every task in the exact JSON below.\n"
        "Workspace: the fixed current working directory.\n"
        "Evidence: the embedded bytes are an exact copy of the standalone "
        "evaluator-bundle.json file.\n"
        f"Locked bundle SHA-256: {bundle_hash}.\n"
        f"Locked bundle byte length: {len(bundle_bytes)}.\n"
        f"Anonymous pair id: {pair_id}.\n"
        "Constraints: do not modify files; do not identify authors, routes, models, "
        "or source cells; evaluate only the supplied task text and artifacts; return "
        "one result matching the supplied JSON schema.\n"
        "Done when: every task and variant is ranked once, or status is blocked with "
        "a concrete blocker.\n"
    ).encode("utf-8")
    return prefix + PROMPT_BUNDLE_BEGIN + bundle_bytes + PROMPT_BUNDLE_END


def prepare_evaluator_prompt(
    prepared: PreparedInputs,
    evaluator_workspace: Path,
) -> tuple[Path, str]:
    """Publish the bounded prompt before any evaluator process is launched."""

    workspace = _require_directory(evaluator_workspace)
    validate_prepared_inputs(prepared, workspace)
    present = sorted(path.name for path in workspace.iterdir())
    if present != ["evaluator-bundle.json", "evaluator-schema.json"]:
        raise EvaluatorError("fixed evaluator workspace contains unexpected entries")
    bundle_bytes = prepared.bundle_path.read_bytes()
    if sha256_bytes(bundle_bytes) != prepared.bundle_sha256:
        raise EvaluatorError("prepared evaluator bundle bytes changed")
    if bundle_bytes != canonical_bytes(_load_json(prepared.bundle_path)):
        raise EvaluatorError("prepared evaluator bundle is not canonical JSON")
    prompt_data = _prompt(bundle_bytes, prepared.bundle_sha256, prepared.pair_id)
    if len(prompt_data) > MAX_EVALUATOR_PROMPT_BYTES:
        raise EvaluatorError(
            "evaluator prompt exceeds the fixed "
            f"{MAX_EVALUATOR_PROMPT_BYTES}-byte maximum"
        )
    prompt_path = workspace / "evaluator-prompt.txt"
    prompt_temporary = _stage_file(prompt_path, prompt_data)
    _publish_staged({prompt_path: prompt_temporary})
    return prompt_path, sha256_bytes(prompt_data)


def _ordinary_executable(path: Path, *, label: str = "Grok executable") -> Path:
    if not path.is_absolute():
        raise EvaluatorError(f"{label} path must be absolute")
    resolved = path.resolve(strict=True)
    state = resolved.stat()
    if not stat.S_ISREG(state.st_mode) or not os.access(resolved, os.X_OK):
        raise EvaluatorError(f"{label} is not an executable ordinary file")
    return resolved


def _ordinary_file(path: Path, *, label: str) -> Path:
    if not path.is_absolute():
        raise EvaluatorError(f"{label} path must be absolute")
    if path.is_symlink():
        raise EvaluatorError(f"{label} is not an ordinary file")
    resolved = path.resolve(strict=True)
    state = resolved.stat()
    if not stat.S_ISREG(state.st_mode):
        raise EvaluatorError(f"{label} is not an ordinary file")
    return resolved


def run_grok_evaluator(
    *,
    prepared: PreparedInputs,
    evaluator_workspace: Path,
    run_directory: Path,
    schema_path: Path,
    grok_executable: Path,
    sandbox_executable: Path,
    sandbox_profile_path: Path,
    grok_model: str,
    grok_identity_evidence: Mapping[str, Any],
    environment: Mapping[str, str],
    environment_evidence: Mapping[str, Any],
    sandbox_preflight_evidence: Mapping[str, Any],
    before_usage: EvidenceHook,
    after_usage: EvidenceHook,
    deadline_monotonic: float,
    process_runner: ProcessRunner | None = None,
) -> EvaluatorOutcome:
    """Make exactly one blocking Grok xhigh call and bind all local evidence."""

    workspace = _require_directory(evaluator_workspace)
    if not run_directory.is_absolute():
        raise EvaluatorError("evaluator run directory must be absolute")
    _require_directory(run_directory.parent)
    if run_directory.exists() or run_directory.is_symlink():
        raise EvaluatorError("one-shot evaluator run directory already exists")
    if _is_within(run_directory, workspace):
        raise EvaluatorError("controller run evidence cannot be inside the evaluator workspace")
    if _is_within(prepared.mapping_path, workspace):
        raise EvaluatorError("private evaluator mapping is inside the workspace")
    input_binding = validate_prepared_inputs(prepared, workspace)
    present = sorted(path.name for path in workspace.iterdir())
    if present != [
        "evaluator-bundle.json",
        "evaluator-prompt.txt",
        "evaluator-schema.json",
    ]:
        raise EvaluatorError("fixed evaluator workspace contains unexpected entries")
    fixed_schema_path = _ordinary_file(schema_path, label="evaluator schema")
    if fixed_schema_path != workspace / "evaluator-schema.json":
        raise EvaluatorError("evaluator schema is not at its fixed workspace path")
    schema_bytes = fixed_schema_path.read_bytes()
    schema = _load_json(fixed_schema_path)
    if not isinstance(schema, dict):
        raise EvaluatorError("evaluator schema must be an object")
    if schema_bytes != canonical_bytes(schema):
        raise EvaluatorError("evaluator schema is not canonical JSON")
    schema_hash = sha256_bytes(schema_bytes)
    executable = _ordinary_executable(grok_executable)
    executable_hash = sha256_file(executable)
    sandbox = _ordinary_executable(
        sandbox_executable, label="sandbox-exec executable"
    )
    sandbox_hash = sha256_file(sandbox)
    sandbox_profile = _ordinary_file(
        sandbox_profile_path, label="sandbox profile"
    )
    if _is_within(sandbox_profile, workspace):
        raise EvaluatorError("sandbox profile cannot be inside the evaluator workspace")
    sandbox_profile_hash = sha256_file(sandbox_profile)
    if grok_model != "grok-4.6":
        raise EvaluatorError("Grok evaluator model must be exactly grok-4.6")
    grok_identity = _json_copy(grok_identity_evidence)
    if not isinstance(grok_identity, dict):
        raise EvaluatorError("Grok identity evidence must be an object")
    environment_receipt = _json_copy(environment_evidence)
    if not isinstance(environment_receipt, dict):
        raise EvaluatorError("environment evidence must be an object")
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in environment.items()
    ):
        raise EvaluatorError("evaluator environment must contain only string pairs")
    if environment_receipt.get("keys") != sorted(environment):
        raise EvaluatorError("environment evidence does not bind the exact key set")
    environment_hash = sha256_bytes(canonical_bytes(dict(environment)))
    sandbox_preflight = _json_copy(sandbox_preflight_evidence)
    if not isinstance(sandbox_preflight, dict) or not sandbox_preflight:
        raise EvaluatorError("sandbox preflight evidence must be a non-empty object")
    if (
        sandbox_preflight.get("status") != "PASS"
        or sandbox_preflight.get("no_model_calls") is not True
        or sandbox_preflight.get("production_profile_sha256")
        != sandbox_profile_hash
    ):
        raise EvaluatorError("sandbox preflight does not bind the production profile")
    if "ROUTING_RUN_MARKER" in environment:
        raise EvaluatorError("caller cannot choose the evaluator run marker")
    if time.monotonic() >= deadline_monotonic:
        raise EvaluatorError("evaluator deadline elapsed before its sole call")

    prompt_path = workspace / "evaluator-prompt.txt"
    prompt_file = _ordinary_file(prompt_path, label="evaluator prompt")
    if prompt_file != prompt_path:
        raise EvaluatorError("evaluator prompt is not at its fixed workspace path")
    prompt_data = prompt_path.read_bytes()
    if len(prompt_data) > MAX_EVALUATOR_PROMPT_BYTES:
        raise EvaluatorError("evaluator prompt exceeds its fixed maximum")
    bundle_bytes = prepared.bundle_path.read_bytes()
    expected_prompt = _prompt(
        bundle_bytes, prepared.bundle_sha256, prepared.pair_id
    )
    if prompt_data != expected_prompt:
        raise EvaluatorError("evaluator prompt does not embed the exact locked bundle")
    prompt_hash = sha256_bytes(prompt_data)
    run_directory.mkdir(mode=0o700)
    schema_argument = canonical_bytes(schema).decode("utf-8").rstrip("\n")
    argv = [
        str(sandbox),
        "-f",
        str(sandbox_profile),
        str(executable),
        "--prompt-file",
        str(prompt_path),
        "--verbatim",
        "--cwd",
        str(workspace),
        "--always-approve",
        "--model",
        grok_model,
        "--output-format",
        "json",
        "--reasoning-effort",
        "xhigh",
        "--no-leader",
        "--sandbox",
        "off",
        "--no-auto-update",
        "--tools",
        "todo_write",
        "--deny",
        "*",
        "--max-turns",
        "1",
        "--disable-web-search",
        "--no-subagents",
        "--no-plan",
        "--json-schema",
        schema_argument,
    ]
    argv_hash = sha256_bytes(canonical_bytes(argv))
    marker = f"routing-v3-grok-evaluator-{secrets.token_hex(16)}"
    child_environment = dict(environment)
    child_environment["ROUTING_RUN_MARKER"] = marker
    stdout_path = run_directory / "stdout.raw"
    stderr_path = run_directory / "stderr.raw"
    before_value, before_hash = _capture_hook(before_usage, "before", run_directory)
    runner = process_runner or _run_blocking_process
    invocation_count = 0
    process_value: dict[str, Any] | None = None
    process_error: BaseException | None = None
    invocation_count += 1
    try:
        process_value = _process_receipt(
            runner(
                argv,
                cwd=workspace,
                environment=child_environment,
                stdin_bytes=b"",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                deadline_monotonic=deadline_monotonic,
                run_marker=marker,
            ),
            argv,
        )
    except BaseException as exc:
        process_error = exc
    try:
        after_value, after_hash = _capture_hook(after_usage, "after", run_directory)
    except BaseException as exc:
        after_value, after_hash = {}, None
        if process_error is None:
            process_error = exc

    stdout_hash = sha256_file(stdout_path) if stdout_path.is_file() else None
    stderr_hash = sha256_file(stderr_path) if stderr_path.is_file() else None
    stdout_bytes = stdout_path.stat().st_size if stdout_path.is_file() else None
    stderr_bytes = stderr_path.stat().st_size if stderr_path.is_file() else None
    workspace_bundle_hash = sha256_file(prepared.bundle_path)
    prompt_after_hash = sha256_file(prompt_path)
    schema_after_hash = sha256_file(fixed_schema_path)
    sandbox_profile_after_hash = sha256_file(sandbox_profile)
    workspace_entries = sorted(path.name for path in workspace.iterdir())
    workspace_unchanged = (
        workspace_bundle_hash == prepared.bundle_sha256
        and prompt_after_hash == prompt_hash
        and schema_after_hash == schema_hash
        and workspace_entries
        == [
            "evaluator-bundle.json",
            "evaluator-prompt.txt",
            "evaluator-schema.json",
        ]
    )
    sandbox_profile_unchanged = sandbox_profile_after_hash == sandbox_profile_hash

    status = "VALID"
    error: str | None = None
    result: dict[str, Any] | None = None
    envelope_hash: str | None = None
    result_hash: str | None = None
    result_path = run_directory / "result.json"
    if process_error is not None:
        status, error = "CONTROLLER_ERROR", f"{type(process_error).__name__}: {process_error}"
    elif process_value is None:
        status, error = "CONTROLLER_ERROR", "process runner returned no receipt"
    elif process_value.get("timed_out") is True:
        status, error = "TIMEOUT", "the sole Grok evaluator call timed out"
    elif process_value.get("returncode") != 0:
        status, error = "PROCESS_FAILED", "the sole Grok evaluator call exited nonzero"
    elif process_value.get("survivor_pids"):
        status, error = "BOUNDARY_FAILURE", "the evaluator process left survivors"
    elif process_value.get("terminal_process_state") is not True:
        status, error = "BOUNDARY_FAILURE", "the evaluator process tree is not terminal"
    elif process_value.get("broker_usage_observed") is not False:
        status, error = "BOUNDARY_FAILURE", "the evaluator used a same-user broker"
    elif process_value.get("launch_observation_complete") is not True:
        status, error = "BOUNDARY_FAILURE", "the evaluator launch observation is incomplete"
    elif not sandbox_profile_unchanged:
        status, error = "BOUNDARY_FAILURE", "the evaluator sandbox profile changed during review"
    elif not workspace_unchanged:
        status, error = "WORKSPACE_MUTATED", "the evaluator workspace changed during review"
    else:
        try:
            stdout_text = stdout_path.read_text(encoding="utf-8")
            envelope = json.loads(stdout_text)
            if not isinstance(envelope, dict):
                raise EvaluatorError("Grok JSON stdout is not an object")
            envelope_hash = sha256_bytes(canonical_bytes(envelope))
            if envelope.get("stopReason") != "end_turn":
                raise EvaluatorError(
                    f"Grok evaluator stopReason is {envelope.get('stopReason')!r}"
                )
            if not isinstance(envelope.get("sessionId"), str) or not envelope["sessionId"]:
                raise EvaluatorError("Grok evaluator sessionId is missing")
            turns = envelope.get("num_turns")
            if isinstance(turns, bool) or not isinstance(turns, int) or turns != 1:
                raise EvaluatorError("Grok evaluator num_turns is invalid")
            text = envelope.get("text")
            if isinstance(text, str):
                decoded = json.loads(text)
            elif isinstance(text, dict):
                decoded = text
            else:
                raise EvaluatorError("Grok evaluator text is not structured JSON")
            result = validate_evaluator_result(
                decoded,
                schema=schema,
                public_aliases=input_binding["aliases"],
            )
            result_hash = _publish_json(result_path, result)
        except (UnicodeDecodeError, json.JSONDecodeError, EvaluatorError) as exc:
            status, error = "INVALID_RESULT", f"{type(exc).__name__}: {exc}"

    process_hash = sha256_bytes(canonical_bytes(process_value)) if process_value is not None else None
    receipt_payload = {
        "schema_version": 1,
        "status": status,
        "error": error,
        "invocation_count": invocation_count,
        "invocation_policy": {
            "blocking": True,
            "resume": False,
            "retry": False,
            "follow_up": False,
            "repair": False,
            "second_call": False,
        },
        "usage_classification": {
            "category": "experiment_overhead",
            "scored": False,
        },
        "inputs": {
            **input_binding,
            "schema_sha256": schema_hash,
            "grok_executable_sha256": executable_hash,
            "sandbox_executable_sha256": sandbox_hash,
            "sandbox_profile_sha256": sandbox_profile_hash,
            "sandbox_profile_after_sha256": sandbox_profile_after_hash,
            "grok_model": grok_model,
            "grok_identity_evidence": grok_identity,
            "grok_identity_evidence_sha256": sha256_bytes(canonical_bytes(grok_identity)),
            "prompt_sha256": prompt_hash,
            "prompt_bytes": len(prompt_data),
            "prompt_max_bytes": MAX_EVALUATOR_PROMPT_BYTES,
            "argv_sha256": argv_hash,
            "environment_evidence": environment_receipt,
            "environment_evidence_sha256": sha256_bytes(canonical_bytes(environment_receipt)),
            "environment_sha256": environment_hash,
            "sandbox_preflight_evidence": sandbox_preflight,
            "sandbox_preflight_evidence_sha256": sha256_bytes(
                canonical_bytes(sandbox_preflight)
            ),
        },
        "usage_evidence": {
            "before": before_value,
            "before_sha256": before_hash,
            "after": after_value,
            "after_sha256": after_hash,
        },
        "raw_evidence": {
            "stdout_file": stdout_path.name,
            "stdout_bytes": stdout_bytes,
            "stdout_sha256": stdout_hash,
            "stderr_file": stderr_path.name,
            "stderr_bytes": stderr_bytes,
            "stderr_sha256": stderr_hash,
        },
        "process": process_value,
        "process_sha256": process_hash,
        "envelope_sha256": envelope_hash,
        "result_file": result_path.name if result_hash is not None else None,
        "result_sha256": result_hash,
        "workspace_unchanged": workspace_unchanged,
        "sandbox_profile_unchanged": sandbox_profile_unchanged,
    }
    payload_hash = sha256_bytes(canonical_bytes(receipt_payload))
    receipt = {**receipt_payload, "receipt_payload_sha256": payload_hash}
    receipt_path = run_directory / "run-receipt.json"
    receipt_hash = _publish_json(receipt_path, receipt)
    if status != "VALID" or result is None or result_hash is None:
        raise EvaluatorRunError(
            error or "evaluator run was not valid",
            receipt=receipt,
            receipt_sha256=receipt_hash,
        )
    return EvaluatorOutcome(
        result=result,
        result_path=result_path,
        result_sha256=result_hash,
        run_receipt=receipt,
        run_receipt_path=receipt_path,
        run_receipt_sha256=receipt_hash,
    )
