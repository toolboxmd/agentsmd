#!/usr/bin/env python3
"""Build or replay a hash-bound, zero-spend benchmark readiness report."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence


sys.dont_write_bytecode = True
PACKAGE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = PACKAGE_ROOT.parents[1]
VERIFIER_ENTRYPOINT = PACKAGE_ROOT / "verifiers/entrypoint.py"
GIT_BIN = Path("/usr/bin/git")
DOCKER_BIN = Path("/usr/local/bin/docker")
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40}$")
FROZEN_DEFINITION_CANONICAL_SHA256 = (
    "903cdf41665be748902a7fd515b29e289d294e6a0a899726ed969bd789bdbedd"
)
SNAPSHOT_ENV = "AGENTSMD_ROUTING_V2_PRIVATE_SNAPSHOT"
MAX_COMMAND_STDOUT = 4 * 1024 * 1024
MAX_COMMAND_STDERR = 4 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024

sys.path.insert(0, str(PACKAGE_ROOT))
from gates import (  # noqa: E402
    GateError,
    canonical_sha256,
    definition_blockers,
    report_payload_sha256,
    validate_adversarial_review,
    validate_readiness_report,
)
from tree_manifest import (  # noqa: E402
    TreeManifestError,
    build_tree_manifest,
    safe_extract_tar,
)


class ReadinessError(RuntimeError):
    """A no-model readiness operation could not produce trustworthy evidence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_file_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    chunks: list[bytes] = []
    observed = 0
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ReadinessError(f"not a single-link regular file: {path}")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity = (
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_nlink,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        final_identity = (
            after.st_dev,
            after.st_ino,
            after.st_mode,
            after.st_nlink,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity != final_identity or observed != before.st_size:
            raise ReadinessError(f"file changed while reading: {path}")
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def sha256_file(path: Path) -> str:
    return sha256_bytes(read_file_bytes(path))


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_file_bytes(path).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReadinessError(f"JSON root must be an object: {path}")
    return value


def safe_environment(*, temporary_home: str | None = None) -> dict[str, str]:
    runtime_home = temporary_home or "/var/empty"
    return {
        "PATH": SAFE_PATH,
        "HOME": runtime_home,
        "TMPDIR": temporary_home or "/tmp",
        "LANG": "C",
        "LC_ALL": "C",
        "NO_COLOR": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false",
        "GIT_SSH_COMMAND": "/usr/bin/false",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM": "0",
    }


def _controller_limits(maximum_file_bytes: int) -> None:
    _, file_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    file_soft = (
        maximum_file_bytes
        if file_hard == resource.RLIM_INFINITY
        else min(maximum_file_bytes, file_hard)
    )
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_soft, file_hard))
    _, nofile_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    nofile_soft = 256 if nofile_hard == resource.RLIM_INFINITY else min(256, nofile_hard)
    resource.setrlimit(resource.RLIMIT_NOFILE, (nofile_soft, nofile_hard))


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int = 120,
    environment: Mapping[str, str] | None = None,
    maximum_stdout_bytes: int = MAX_COMMAND_STDOUT,
    maximum_stderr_bytes: int = MAX_COMMAND_STDERR,
) -> subprocess.CompletedProcess[bytes]:
    if not command or not Path(command[0]).is_absolute():
        raise ReadinessError("trusted command must use an absolute executable path")
    maximum_file_bytes = max(maximum_stdout_bytes, maximum_stderr_bytes)
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            process = subprocess.Popen(
                list(command),
                cwd=cwd,
                env=dict(environment) if environment is not None else safe_environment(),
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
                preexec_fn=lambda: _controller_limits(maximum_file_bytes),
            )
        except OSError as exc:
            raise ReadinessError(f"cannot start command {command[0]}: {exc}") from exc
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise ReadinessError(f"command timed out: {' '.join(command)}") from exc

        stdout_size = os.fstat(stdout_file.fileno()).st_size
        stderr_size = os.fstat(stderr_file.fileno()).st_size
        if stdout_size > maximum_stdout_bytes or stderr_size > maximum_stderr_bytes:
            raise ReadinessError(f"command output exceeded its bound: {command[0]}")
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            list(command), returncode, stdout_file.read(), stderr_file.read()
        )


def git_prefix() -> list[str]:
    return [
        str(GIT_BIN),
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "protocol.file.allow=always",
    ]


def clone_source(source: Path, destination: Path) -> None:
    try:
        source_state = os.lstat(source)
        metadata_state = os.lstat(source / ".git")
    except OSError as exc:
        raise ReadinessError(f"cannot inspect source Git metadata: {source}") from exc
    if not stat.S_ISDIR(source_state.st_mode) or stat.S_ISLNK(source_state.st_mode):
        raise ReadinessError(f"source root is not a real directory: {source}")
    if not (
        stat.S_ISDIR(metadata_state.st_mode) or stat.S_ISREG(metadata_state.st_mode)
    ) or stat.S_ISLNK(metadata_state.st_mode):
        raise ReadinessError(f"source is not a Git worktree: {source}")
    command = [
        *git_prefix(),
        "clone",
        "--bare",
        "--no-local",
        "--no-hardlinks",
        "--",
        str(source),
        str(destination),
    ]
    result = run_command(command, cwd=destination.parent, timeout_seconds=180)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-1000:].decode("utf-8", "replace")
        raise ReadinessError(f"controller-owned bare clone failed: {detail}")


def bare_git(
    repository: Path,
    arguments: Sequence[str],
    *,
    timeout_seconds: int = 120,
    archive_output: bool = False,
) -> bytes:
    command = [*git_prefix(), f"--git-dir={repository}", *arguments]
    result = run_command(
        command,
        cwd=repository.parent,
        timeout_seconds=timeout_seconds,
        maximum_stdout_bytes=MAX_ARCHIVE_BYTES if archive_output else MAX_COMMAND_STDOUT,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout)[-1000:].decode("utf-8", "replace")
        raise ReadinessError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def verify_source_objects(
    source_path: Path,
    bare_repository: Path,
    *,
    base_commit: str,
    base_tree: str,
    historical_commit: str,
    historical_tree: str,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {"repo": str(source_path.resolve())}
    for label, commit, expected_tree in (
        ("base", base_commit, base_tree),
        ("historical_source", historical_commit, historical_tree),
    ):
        resolved_commit = bare_git(
            bare_repository, ["rev-parse", f"{commit}^{{commit}}"]
        ).decode().strip()
        resolved_tree = bare_git(
            bare_repository, ["rev-parse", f"{commit}^{{tree}}"]
        ).decode().strip()
        if resolved_commit != commit or resolved_tree != expected_tree:
            raise ReadinessError(
                f"{label} identity mismatch in {source_path}: "
                f"commit={resolved_commit}, tree={resolved_tree}"
            )
        listing = bare_git(
            bare_repository, ["ls-tree", "-r", "-z", "--full-tree", commit]
        )
        evidence[f"{label}_commit"] = commit
        evidence[f"{label}_tree"] = resolved_tree
        evidence[f"{label}_ls_tree_sha256"] = sha256_bytes(listing)
    evidence["object_evidence_rechecked"] = False
    return evidence


def finish_source_check(bare_repository: Path, evidence: dict[str, Any]) -> None:
    for label in ("base", "historical_source"):
        commit = evidence[f"{label}_commit"]
        tree = bare_git(
            bare_repository, ["rev-parse", f"{commit}^{{tree}}"]
        ).decode().strip()
        if tree != evidence[f"{label}_tree"]:
            raise ReadinessError(f"source object tree changed during preflight: {label}")
        listing = bare_git(
            bare_repository, ["ls-tree", "-r", "-z", "--full-tree", commit]
        )
        if sha256_bytes(listing) != evidence[f"{label}_ls_tree_sha256"]:
            raise ReadinessError(f"source tree listing changed during preflight: {label}")
    evidence["object_evidence_rechecked"] = True


def export_commit(
    bare_repository: Path,
    commit: str,
    destination: Path,
    *,
    excludes: Sequence[str],
) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=False)
    arguments = ["archive", "--format=tar", commit, "--", "."]
    arguments.extend(f":(exclude){path}" for path in excludes)
    archive = bare_git(bare_repository, arguments, archive_output=True)
    manifest = safe_extract_tar(archive, destination).as_dict()
    manifest["archive_sha256"] = sha256_bytes(archive)
    return manifest


def _manifest_files(manifest: Mapping[str, Any]) -> dict[str, tuple[Any, ...]]:
    return {
        entry["path"]: (entry["mode"], entry["size"], entry["sha256"])
        for entry in manifest["entries"]
        if entry.get("kind") == "file"
    }


def apply_known_good_patch(
    destination: Path,
    patch: Path,
    *,
    before_manifest: Mapping[str, Any],
    allowed_paths: Sequence[str],
) -> dict[str, Any]:
    if not patch.is_file():
        raise ReadinessError(f"known-good patch is missing: {patch}")
    environment = safe_environment()
    environment["GIT_CEILING_DIRECTORIES"] = str(destination.parent.resolve())
    for check_only in (True, False):
        command = [*git_prefix(), "apply", "--no-index", "--whitespace=error-all"]
        if check_only:
            command.append("--check")
        command.append(str(patch))
        result = run_command(command, cwd=destination, environment=environment)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout)[-1000:].decode("utf-8", "replace")
            stage = "check" if check_only else "apply"
            raise ReadinessError(f"known-good patch {stage} failed: {detail}")
    after_manifest = build_tree_manifest(destination)
    before = _manifest_files(before_manifest)
    after = _manifest_files(after_manifest)
    changed = sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )
    if not changed or not set(changed).issubset(set(allowed_paths)):
        raise ReadinessError(
            f"known-good patch changed paths outside frozen scope: {changed}"
        )
    after_manifest["changed_paths"] = changed
    return after_manifest


def verify_offline_runtime(definition: Mapping[str, Any]) -> None:
    runtime = definition["offline_verifier_runtime"]
    if not DOCKER_BIN.is_file():
        raise ReadinessError(f"offline verifier runtime is missing: {DOCKER_BIN}")
    result = run_command(
        [str(DOCKER_BIN), "image", "inspect", runtime["image_id"], "--format", "{{.Id}}"],
        cwd=PACKAGE_ROOT,
        timeout_seconds=30,
    )
    observed = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0 or observed != runtime["image_id"]:
        raise ReadinessError("exact offline verifier image is unavailable; pulling is forbidden")


def _remove_container(name: str) -> None:
    try:
        run_command(
            [str(DOCKER_BIN), "rm", "--force", name],
            cwd=PACKAGE_ROOT,
            timeout_seconds=20,
        )
    except ReadinessError:
        pass


def _workspace_binding(workspace: Path, expected_manifest_sha256: str) -> tuple[int, int]:
    """Bind a verifier pathname to one unchanged directory and tree manifest."""

    try:
        before = os.lstat(workspace)
    except OSError as error:
        raise ReadinessError(f"verifier workspace is unavailable: {workspace}") from error
    if not stat.S_ISDIR(before.st_mode):
        raise ReadinessError(f"verifier workspace is not a real directory: {workspace}")
    manifest = build_tree_manifest(workspace)
    try:
        after = os.lstat(workspace)
    except OSError as error:
        raise ReadinessError(f"verifier workspace disappeared: {workspace}") from error
    before_identity = (before.st_dev, before.st_ino)
    after_identity = (after.st_dev, after.st_ino)
    if before_identity != after_identity or not stat.S_ISDIR(after.st_mode):
        raise ReadinessError("verifier workspace identity changed while binding evidence")
    if manifest["sha256"] != expected_manifest_sha256:
        raise ReadinessError("verifier workspace differs from its expected manifest")
    return after_identity


def verifier_status(
    verifier: Path,
    workspace: Path,
    *,
    task_id: str,
    hidden: bool,
    workspace_manifest_sha256: str,
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    if not verifier.is_file():
        raise ReadinessError(f"verifier is missing: {verifier}")
    if not VERIFIER_ENTRYPOINT.is_file():
        raise ReadinessError("trusted verifier entrypoint is missing")
    runtime = definition["offline_verifier_runtime"]
    try:
        verifier_relative = verifier.resolve().relative_to(PACKAGE_ROOT).as_posix()
    except ValueError as exc:
        raise ReadinessError("verifier escapes the package") from exc
    workspace_identity = _workspace_binding(workspace, workspace_manifest_sha256)
    name = f"agentsmd-routing-v2-{secrets.token_hex(8)}"
    container_workspace = f"/workspaces/{workspace.name}"
    command = [
        str(DOCKER_BIN),
        "run",
        "--rm",
        "--name",
        name,
        "--platform",
        runtime["platform"],
        "--network",
        runtime["network"],
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(runtime["pids_limit"]),
        "--memory",
        f"{runtime['memory_mebibytes']}m",
        "--memory-swap",
        f"{runtime['memory_mebibytes']}m",
        "--cpus",
        str(runtime["cpus"]),
        "--ulimit",
        "nofile=128:128",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=268435456",
        "--user",
        "65534:65534",
        "--env",
        "HOME=/tmp",
        "--env",
        "TMPDIR=/tmp",
        "--env",
        "PATH=/usr/bin:/bin",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--mount",
        f"type=bind,source={PACKAGE_ROOT},target=/package,readonly",
        "--mount",
        f"type=bind,source={workspace},target={container_workspace},readonly",
        "--entrypoint",
        "/usr/bin/python3",
        runtime["image_id"],
        "-B",
        "/package/verifiers/entrypoint.py",
        "--workspace",
        container_workspace,
        "--expected-manifest-sha256",
        workspace_manifest_sha256,
        "--verifier",
        verifier_relative,
    ]
    if hidden:
        command.extend(["--task", task_id])
    try:
        result = run_command(
            command,
            cwd=PACKAGE_ROOT,
            timeout_seconds=240,
            maximum_stdout_bytes=2 * 1024 * 1024,
            maximum_stderr_bytes=2 * 1024 * 1024,
        )
    finally:
        _remove_container(name)
    if _workspace_binding(workspace, workspace_manifest_sha256) != workspace_identity:
        raise ReadinessError("verifier workspace identity changed during execution")
    status = "PASS" if result.returncode == 0 else "FAIL" if result.returncode == 1 else "ERROR"
    return {
        "status": status,
        "returncode": result.returncode,
        "stdout_sha256": sha256_bytes(result.stdout),
        "stderr_sha256": sha256_bytes(result.stderr),
        "verifier_sha256": sha256_file(verifier),
        "workspace_manifest_sha256": workspace_manifest_sha256,
    }


def _safe_relative_path(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise ReadinessError(f"{name} must be a nonempty relative path")
    parts = value.split("/")
    if any(part in {"", ".", "..", ".git", "__pycache__"} or "\\" in part for part in parts):
        raise ReadinessError(f"{name} is unsafe")
    return value


def validate_definition_files(definition: Mapping[str, Any]) -> None:
    if canonical_sha256(definition) != FROZEN_DEFINITION_CANONICAL_SHA256:
        raise ReadinessError("definition semantics differ from the frozen v2 definition")
    if definition.get("schema_version") != 2:
        raise ReadinessError("definition schema version is not v2")
    if set(definition.get("tasks", {})) != {"use-grok", "karpathy-pointer"}:
        raise ReadinessError("definition must contain exactly two frozen tasks")
    for task_id, task in definition["tasks"].items():
        for field in ("base_commit", "base_tree", "historical_source_commit", "historical_source_tree"):
            if not isinstance(task.get(field), str) or not GIT_OBJECT_RE.fullmatch(task[field]):
                raise ReadinessError(f"{task_id}.{field} is not an exact Git object ID")
        for field in ("known_good_patch", "task_packet", "public_verifier", "hidden_verifier"):
            relative = _safe_relative_path(task.get(field), f"{task_id}.{field}")
            path = (PACKAGE_ROOT / relative).resolve()
            try:
                path.relative_to(PACKAGE_ROOT)
            except ValueError as exc:
                raise ReadinessError(f"{task_id}.{field} escapes the package") from exc
            if not path.is_file():
                raise ReadinessError(f"{task_id}.{field} is missing")
        paths = task.get("allowed_paths")
        if not isinstance(paths, list) or not paths or len(paths) != len(set(paths)):
            raise ReadinessError(f"{task_id}.allowed_paths must be unique and nonempty")
        for index, path in enumerate(paths):
            _safe_relative_path(path, f"{task_id}.allowed_paths[{index}]")
        excludes = task.get("export_excludes")
        if not isinstance(excludes, list) or len(excludes) != len(set(excludes)):
            raise ReadinessError(f"{task_id}.export_excludes must be a unique array")
        for index, path in enumerate(excludes):
            _safe_relative_path(path, f"{task_id}.export_excludes[{index}]")
    if definition["execution_surface"] != {
        "model_runner_in_this_package": False,
        "run_all_command": False,
        "paid_execution_authorized": False,
    }:
        raise ReadinessError("the readiness package must remain zero-spend")
    review_path = (PACKAGE_ROOT / definition["adversarial_review"]["artifact"]).resolve()
    try:
        review_path.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise ReadinessError("adversarial review artifact escapes the repository snapshot") from exc


def run_security_tests() -> dict[str, Any]:
    command = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        str(PACKAGE_ROOT / "tests"),
        "-p",
        "test_*.py",
    ]
    result = run_command(
        command,
        cwd=REPOSITORY_ROOT,
        timeout_seconds=300,
        environment=safe_environment(),
    )
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "stdout_sha256": sha256_bytes(result.stdout),
        "stderr_sha256": sha256_bytes(result.stderr),
    }


def validate_review_artifact(
    definition: Mapping[str, Any], definition_sha256: str, package_sha256: str
) -> tuple[dict[str, Any], list[str]]:
    path = (PACKAGE_ROOT / definition["adversarial_review"]["artifact"]).resolve()
    if not path.is_file():
        return (
            {
                "status": "MISSING",
                "artifact_sha256": None,
                "definition_sha256": None,
                "package_sha256": None,
                "unresolved_findings": [],
            },
            ["independent_adversarial_review_required"],
        )
    value = load_object(path)
    try:
        validate_adversarial_review(
            value,
            definition_sha256=definition_sha256,
            package_sha256=package_sha256,
        )
    except GateError as exc:
        return (
            {
                "status": "FAIL",
                "artifact_sha256": None,
                "definition_sha256": None,
                "package_sha256": None,
                "unresolved_findings": [],
            },
            [f"independent_adversarial_review_invalid:{type(exc).__name__}"],
        )
    return (
        {
            "status": "PASS",
            "artifact_sha256": sha256_file(path),
            "definition_sha256": definition_sha256,
            "package_sha256": package_sha256,
            "unresolved_findings": [],
        },
        [],
    )


def build_report(
    definition_path: Path,
    repositories: Mapping[str, Path],
) -> dict[str, Any]:
    definition_path = definition_path.resolve()
    if definition_path != (PACKAGE_ROOT / "definition.json").resolve():
        raise ReadinessError("only the package's frozen definition.json is accepted")
    definition = load_object(definition_path)
    validate_definition_files(definition)
    initial_package = build_tree_manifest(PACKAGE_ROOT)
    definition_sha256 = sha256_file(definition_path)
    package_sha256 = str(initial_package["sha256"])
    blockers = definition_blockers(definition)

    verify_offline_runtime(definition)
    security_tests = run_security_tests()
    if security_tests["status"] != "PASS":
        blockers.append("deterministic_security_tests_failed")

    review_evidence, review_blockers = validate_review_artifact(
        definition, definition_sha256, package_sha256
    )
    blockers.extend(review_blockers)

    sources: dict[str, Any] = {}
    task_evidence: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="agentsmd-routing-v2-readiness-") as raw:
        root = Path(raw)
        for task_id in ("use-grok", "karpathy-pointer"):
            task = definition["tasks"][task_id]
            source_path = repositories[task_id].resolve()
            bare_repository = root / task_id / "source.git"
            bare_repository.parent.mkdir(parents=True)
            clone_source(source_path, bare_repository)
            source = verify_source_objects(
                source_path,
                bare_repository,
                base_commit=task["base_commit"],
                base_tree=task["base_tree"],
                historical_commit=task["historical_source_commit"],
                historical_tree=task["historical_source_tree"],
            )
            sources[task_id] = source
            base = root / task_id / "base" / task["workspace_name"]
            known = root / task_id / "known-good" / task["workspace_name"]
            base.parent.mkdir(parents=True)
            known.parent.mkdir(parents=True)
            base_manifest = export_commit(
                bare_repository,
                task["base_commit"],
                base,
                excludes=task["export_excludes"],
            )
            historical_manifest = export_commit(
                bare_repository,
                task["historical_source_commit"],
                known,
                excludes=task["export_excludes"],
            )
            source["export_excludes"] = task["export_excludes"]
            source["base_archive_sha256"] = base_manifest["archive_sha256"]
            source["historical_source_archive_sha256"] = historical_manifest[
                "archive_sha256"
            ]
            patch = PACKAGE_ROOT / task["known_good_patch"]
            known_manifest = apply_known_good_patch(
                known,
                patch,
                before_manifest=historical_manifest,
                allowed_paths=task["allowed_paths"],
            )

            public_verifier = PACKAGE_ROOT / task["public_verifier"]
            hidden_verifier = PACKAGE_ROOT / task["hidden_verifier"]
            runs = {
                "public_baseline": verifier_status(
                    public_verifier,
                    base,
                    task_id=task_id,
                    hidden=False,
                    workspace_manifest_sha256=base_manifest["sha256"],
                    definition=definition,
                ),
                "public_known_good": verifier_status(
                    public_verifier,
                    known,
                    task_id=task_id,
                    hidden=False,
                    workspace_manifest_sha256=known_manifest["sha256"],
                    definition=definition,
                ),
                "hidden_baseline": verifier_status(
                    hidden_verifier,
                    base,
                    task_id=task_id,
                    hidden=True,
                    workspace_manifest_sha256=base_manifest["sha256"],
                    definition=definition,
                ),
                "hidden_known_good": verifier_status(
                    hidden_verifier,
                    known,
                    task_id=task_id,
                    hidden=True,
                    workspace_manifest_sha256=known_manifest["sha256"],
                    definition=definition,
                ),
            }
            task_evidence[task_id] = {
                "base_manifest_sha256": base_manifest["sha256"],
                "known_good_manifest_sha256": known_manifest["sha256"],
                "public_verifier_sha256": sha256_file(public_verifier),
                "hidden_verifier_sha256": sha256_file(hidden_verifier),
                "known_good_patch_sha256": sha256_file(patch),
                "runs": runs,
            }
            required = {
                "public_baseline": ("FAIL", 1),
                "public_known_good": ("PASS", 0),
                "hidden_baseline": ("FAIL", 1),
                "hidden_known_good": ("PASS", 0),
            }
            if any(
                (runs[name]["status"], runs[name]["returncode"]) != expected
                for name, expected in required.items()
            ):
                blockers.append(f"{task_id}_fixture_discrimination_failed")
            finish_source_check(bare_repository, source)

    final_package = build_tree_manifest(PACKAGE_ROOT)
    if final_package["sha256"] != package_sha256:
        raise ReadinessError("package changed after its initial manifest was captured")

    blockers = sorted(set(blockers))
    report: dict[str, Any] = {
        "schema_version": 3,
        "definition_id": definition["definition_id"],
        "definition_sha256": definition_sha256,
        "package_sha256": package_sha256,
        "generated_at": utc_now(),
        "status": "BLOCKED",
        "paid_execution_authorized": False,
        "blockers": blockers,
        "sources": sources,
        "tasks": task_evidence,
        "security_tests": security_tests,
        "adversarial_review": review_evidence,
        "external_boundary": definition["external_boundary"],
        "quota_guard": definition["quota_guard"],
        "offline_verifier_runtime": definition["offline_verifier_runtime"],
        "payload_sha256": "0" * 64,
    }
    report["payload_sha256"] = report_payload_sha256(report)
    validate_readiness_report(
        report,
        definition=definition,
        definition_sha256=definition_sha256,
        package_sha256=package_sha256,
        blockers=blockers,
    )
    return report


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path = path.resolve()
    try:
        path.relative_to(PACKAGE_ROOT)
    except ValueError:
        pass
    else:
        raise ReadinessError("report output must be outside the hashed package")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)
    sidecar = path.with_name(path.name + ".sha256")
    sidecar_payload = f"{sha256_bytes(payload.encode('utf-8'))}  {path.name}\n"
    sidecar_temporary = sidecar.with_name(f".{sidecar.name}.{secrets.token_hex(8)}.tmp")
    sidecar_temporary.write_text(sidecar_payload, encoding="utf-8")
    os.replace(sidecar_temporary, sidecar)


def _replay_view(report: Mapping[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(report))
    value.pop("generated_at", None)
    value.pop("payload_sha256", None)
    security = value.get("security_tests")
    if isinstance(security, dict):
        security.pop("stdout_sha256", None)
        security.pop("stderr_sha256", None)
    tasks = value.get("tasks")
    if isinstance(tasks, dict):
        for task in tasks.values():
            runs = task.get("runs") if isinstance(task, dict) else None
            if not isinstance(runs, dict):
                continue
            for run in runs.values():
                if isinstance(run, dict):
                    run.pop("stdout_sha256", None)
                    run.pop("stderr_sha256", None)
    return value


def check_command(arguments: argparse.Namespace) -> int:
    report = build_report(
        arguments.definition,
        {
            "use-grok": arguments.use_grok_repo,
            "karpathy-pointer": arguments.karpathy_repo,
        },
    )
    write_report(arguments.output, report)
    print(f"status={report['status']}")
    print("paid_execution_authorized=false")
    print(f"payload_sha256={report['payload_sha256']}")
    print(f"blockers={','.join(report['blockers'])}")
    return 0


def validate_report_command(arguments: argparse.Namespace) -> int:
    definition_path = arguments.definition.resolve()
    if definition_path != (PACKAGE_ROOT / "definition.json").resolve():
        raise ReadinessError("only the package's frozen definition.json is accepted")
    definition = load_object(definition_path)
    validate_definition_files(definition)
    observed = build_report(
        definition_path,
        {
            "use-grok": arguments.use_grok_repo,
            "karpathy-pointer": arguments.karpathy_repo,
        },
    )
    report_path = arguments.report.resolve()
    report = load_object(report_path)
    validate_readiness_report(
        report,
        definition=definition,
        definition_sha256=observed["definition_sha256"],
        package_sha256=observed["package_sha256"],
        blockers=observed["blockers"],
    )
    sidecar = report_path.with_name(report_path.name + ".sha256")
    if not sidecar.is_file():
        raise ReadinessError("readiness report SHA-256 sidecar is missing")
    fields = read_file_bytes(sidecar).decode("utf-8").split()
    if len(fields) != 2 or fields[1] != report_path.name:
        raise ReadinessError("readiness report SHA-256 sidecar is malformed")
    if not SHA256_RE.fullmatch(fields[0]) or fields[0] != sha256_file(report_path):
        raise ReadinessError("readiness report SHA-256 sidecar does not match")
    if _replay_view(report) != _replay_view(observed):
        raise ReadinessError("readiness report differs from replayed no-model evidence")
    print("status=BLOCKED")
    print("paid_execution_authorized=false")
    print(f"payload_sha256={report['payload_sha256']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check", help="run no-model readiness checks")
    check.add_argument("--definition", type=Path, required=True)
    check.add_argument("--use-grok-repo", type=Path, required=True)
    check.add_argument("--karpathy-repo", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.set_defaults(handler=check_command)
    validate = subparsers.add_parser(
        "validate-report", help="replay no-model checks and compare an existing report"
    )
    validate.add_argument("--definition", type=Path, required=True)
    validate.add_argument("--use-grok-repo", type=Path, required=True)
    validate.add_argument("--karpathy-repo", type=Path, required=True)
    validate.add_argument("--report", type=Path, required=True)
    validate.set_defaults(handler=validate_report_command)
    return parser


def _copy_review_artifact(snapshot_package: Path) -> None:
    definition = load_object(snapshot_package / "definition.json")
    relative = definition["adversarial_review"]["artifact"]
    source = (PACKAGE_ROOT / relative).resolve()
    if not source.is_file():
        return
    destination = (snapshot_package / relative).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(read_file_bytes(source))


def _snapshot_arguments(arguments: argparse.Namespace, snapshot_package: Path) -> list[str]:
    common = [
        arguments.command,
        "--definition",
        str(snapshot_package / "definition.json"),
        "--use-grok-repo",
        str(arguments.use_grok_repo.resolve()),
        "--karpathy-repo",
        str(arguments.karpathy_repo.resolve()),
    ]
    if arguments.command == "check":
        common.extend(["--output", str(arguments.output.resolve())])
    else:
        common.extend(["--report", str(arguments.report.resolve())])
    return common


def run_in_private_snapshot(arguments: argparse.Namespace) -> int:
    if arguments.definition.resolve() != (PACKAGE_ROOT / "definition.json").resolve():
        raise ReadinessError("only the package's frozen definition.json is accepted")
    original_manifest = build_tree_manifest(PACKAGE_ROOT)
    with tempfile.TemporaryDirectory(prefix="agentsmd-routing-v2-package-") as raw:
        snapshot_repository = Path(raw) / "repository"
        snapshot_package = snapshot_repository / "evals" / "model-routing-v2"
        snapshot_package.parent.mkdir(parents=True)
        shutil.copytree(PACKAGE_ROOT, snapshot_package, copy_function=shutil.copy2)
        if build_tree_manifest(snapshot_package)["sha256"] != original_manifest["sha256"]:
            raise ReadinessError("private package snapshot differs from the reviewed source")
        _copy_review_artifact(snapshot_package)
        environment = safe_environment(temporary_home=str(Path(raw) / "home"))
        Path(environment["HOME"]).mkdir()
        environment[SNAPSHOT_ENV] = "1"
        command = [
            sys.executable,
            "-B",
            str(snapshot_package / "readiness.py"),
            *_snapshot_arguments(arguments, snapshot_package),
        ]
        result = run_command(
            command,
            cwd=snapshot_repository,
            timeout_seconds=1800,
            environment=environment,
        )
        final_original = build_tree_manifest(PACKAGE_ROOT)
        if final_original["sha256"] != original_manifest["sha256"]:
            raise ReadinessError("source package changed while the private snapshot ran")
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        return result.returncode


def main() -> int:
    arguments = build_parser().parse_args()
    try:
        if os.environ.get(SNAPSHOT_ENV) != "1":
            return run_in_private_snapshot(arguments)
        return int(arguments.handler(arguments))
    except (GateError, ReadinessError, TreeManifestError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
