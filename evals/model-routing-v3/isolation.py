"""Local trusted-boundary helpers for the Issue 33 model-routing benchmark.

The candidate is not hostile code.  This module nevertheless makes the
benchmark's local boundary explicit and testable: the candidate receives only
its exported fixture, a dedicated temporary directory, and a fresh Codex
state directory whose authentication file is a link to a controller-owned
target.  A missing or failed probe is a preflight failure, never a reason to
start a scored model run.
"""

from __future__ import annotations

import hashlib
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


CODEX_VERSION = "0.149.1"
PROFILE_CANDIDATE = "routing_candidate"
PROFILE_REVIEWER = "routing_reviewer"
ALLOWED_CHILD_ENVIRONMENT = frozenset(
    {"ROUTING_CANDIDATE_ACP", "ROUTING_RUN_MARKER"}
)


class IsolationError(RuntimeError):
    """A controller supplied a boundary that cannot be made unambiguous."""


@dataclass(frozen=True)
class CodexPaths:
    """Absolute controller and candidate locations for one isolated rollout."""

    candidate_root: Path
    home: Path
    codex_home: Path
    codex_sqlite_home: Path
    tmpdir: Path
    auth_target: Path
    controller_root: Path
    memory_root: Path

    def normalized(self) -> "CodexPaths":
        """Return absolute, lexically normal paths after enforcing separation."""

        candidate = _absolute(self.candidate_root)
        home = _absolute(self.home)
        codex_home = _absolute(self.codex_home)
        sqlite_home = _absolute(self.codex_sqlite_home)
        tmpdir = _absolute(self.tmpdir)
        auth_target = _absolute(self.auth_target)
        controller = _absolute(self.controller_root)
        memory = _absolute(self.memory_root)

        if not _is_within(tmpdir, candidate):
            raise IsolationError("TMPDIR must be an allowed candidate subdirectory")
        for label, protected in (
            ("HOME", home),
            ("CODEX_HOME", codex_home),
            ("CODEX_SQLITE_HOME", sqlite_home),
            ("auth target", auth_target),
            ("controller root", controller),
            ("memory root", memory),
        ):
            if _is_within(protected, candidate):
                raise IsolationError(f"{label} must be outside the candidate workspace")
        if _is_within(candidate, controller):
            raise IsolationError("candidate workspace must not be inside controller state")
        return CodexPaths(
            candidate_root=candidate,
            home=home,
            codex_home=codex_home,
            codex_sqlite_home=sqlite_home,
            tmpdir=tmpdir,
            auth_target=auth_target,
            controller_root=controller,
            memory_root=memory,
        )


@dataclass(frozen=True)
class ProbeSpec:
    """One executable no-model preflight assertion."""

    name: str
    argv: tuple[str, ...]
    expect_success: bool
    timeout_seconds: float = 5.0


@dataclass(frozen=True)
class ProbeResult:
    name: str
    passed: bool
    returncode: int | None
    timed_out: bool
    stdout: str
    stderr: str
    elapsed_seconds: float


@dataclass(frozen=True)
class ProbeReport:
    results: tuple[ProbeResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)

    def require_passed(self) -> None:
        failures = [result.name for result in self.results if not result.passed]
        if failures:
            raise IsolationError("sandbox preflight failed: " + ", ".join(failures))


def permission_profile_toml(
    paths: CodexPaths,
    *,
    reviewer: bool = False,
    reasoning_effort: str = "high",
    child_environment: Mapping[str, str] | None = None,
    writable_paths: Sequence[str] | None = None,
    runtime_roots: Sequence[Path | str] = (),
    command_path: Sequence[Path | str] | None = None,
) -> bytes:
    """Render canonical, SHA-ready Codex config bytes for one role.

    The generated profile deliberately has no ``sandbox_mode``.  Permission
    profiles and legacy sandbox modes do not compose safely.  Callers persist
    these bytes as ``CODEX_HOME/config.toml`` before invoking ``codex exec``.
    """

    normalized = paths.normalized()
    if reasoning_effort not in {"low", "medium", "high", "xhigh", "max", "ultra"}:
        raise IsolationError("unsupported reasoning effort")
    profile = PROFILE_REVIEWER if reviewer else PROFILE_CANDIDATE
    if reviewer and writable_paths:
        raise IsolationError("reviewer writes are fixed to the ephemeral runner temp")
    writes = [".runner-tmp"] if reviewer else list(writable_paths or (".runner-tmp",))
    if any(not item or Path(item).is_absolute() or ".." in Path(item).parts for item in writes):
        raise IsolationError("writable paths must be nonempty relative candidate paths")
    if "." in writes:
        # A write grant implies read, so emitting a separate read grant below
        # would create invalid duplicate TOML keys.
        workspace_read = False
    else:
        workspace_read = True
    readonly_runtime = _runtime_roots(normalized, runtime_roots)
    child_env = dict(minimal_child_environment(normalized, command_path=command_path))
    if child_environment:
        _validate_extra_environment(normalized, child_environment)
        child_env.update({str(key): str(value) for key, value in child_environment.items()})

    lines = [
        "# Generated by evals/model-routing-v3/isolation.py. Do not edit.",
        f"# Codex CLI pin: {CODEX_VERSION}",
        'approval_policy = "never"',
        'web_search = "disabled"',
        f'model_reasoning_effort = {_toml_string(reasoning_effort)}',
        f'default_permissions = "{profile}"',
        "",
        "[features]",
        "apps = false",
        "auth_elicitation = false",
        "browser_use = false",
        "browser_use_external = false",
        "browser_use_full_cdp_access = false",
        "code_mode_host = false",
        "computer_use = false",
        "goals = false",
        "hooks = false",
        "image_generation = false",
        "in_app_browser = false",
        "memories = false",
        "multi_agent = false",
        "multi_agent_v2 = false",
        "plugins = false",
        "remote_plugin = false",
        "skill_search = false",
        "tool_call_mcp_elicitation = false",
        "tool_suggest = false",
        "view_image = false",
        "workspace_dependencies = false",
        "",
        f"[permissions.{profile}]",
        'description = "Issue 33 isolated benchmark role"',
        "",
        f"[permissions.{profile}.filesystem]",
        '":root" = "deny"',
        '":minimal" = "read"',
        '":slash_tmp" = "deny"',
    ]
    lines.extend(f'{_toml_string(str(item))} = "read"' for item in readonly_runtime)
    lines.extend(["", f'[permissions.{profile}.filesystem.":workspace_roots"]'])
    if workspace_read:
        lines.append('"." = "read"')
    lines.extend(f'{_toml_string(item)} = "write"' for item in writes)
    lines.extend(
        [
            "",
            f"[permissions.{profile}.network]",
            "enabled = false",
            "",
            "[shell_environment_policy]",
            'inherit = "none"',
            "",
            "[shell_environment_policy.set]",
        ]
    )
    lines.extend(
        f"{_toml_string(key)} = {_toml_string(value)}"
        for key, value in sorted(child_env.items())
    )
    for skill_name in ("imagegen", "openai-docs", "plugin-creator", "skill-creator", "skill-installer"):
        lines.extend(
            [
                "",
                "[[skills.config]]",
                f"path = {_toml_string(str(normalized.codex_home / 'skills' / '.system' / skill_name / 'SKILL.md'))}",
                "enabled = false",
            ]
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def config_sha256(config: bytes) -> str:
    """Return the evidence-friendly SHA-256 of generated config bytes."""

    return hashlib.sha256(config).hexdigest()


def write_permission_profile(
    paths: CodexPaths,
    *,
    reviewer: bool = False,
    reasoning_effort: str = "high",
    child_environment: Mapping[str, str] | None = None,
    writable_paths: Sequence[str] | None = None,
    runtime_roots: Sequence[Path | str] = (),
    command_path: Sequence[Path | str] | None = None,
) -> tuple[Path, str]:
    """Write the isolated config and return its path and content hash."""

    normalized = paths.normalized()
    normalized.home.mkdir(parents=True, exist_ok=True)
    normalized.codex_home.mkdir(parents=True, exist_ok=True)
    normalized.codex_sqlite_home.mkdir(parents=True, exist_ok=True)
    normalized.tmpdir.mkdir(parents=True, exist_ok=True)
    config = permission_profile_toml(
        normalized,
        reviewer=reviewer,
        reasoning_effort=reasoning_effort,
        child_environment=child_environment,
        writable_paths=writable_paths,
        runtime_roots=runtime_roots,
        command_path=command_path,
    )
    config_path = normalized.codex_home / "config.toml"
    config_path.write_bytes(config)
    return config_path, config_sha256(config)


def minimal_child_environment(
    paths: CodexPaths, *, command_path: Sequence[Path | str] | None = None
) -> dict[str, str]:
    """Build the complete environment inherited by a candidate shell.

    It is intentionally a replacement environment, not a filtered copy of
    the controller environment.  ``PATH`` contains only system directories and
    only controller-supplied non-Codex, non-npm command directories, so user
    package managers and shell profiles cannot leak into a run.  Codex itself
    is executed by absolute path and must never appear in this shell PATH.
    """

    normalized = paths.normalized()
    safe_path = _command_path(command_path)
    return {
        "CODEX_HOME": str(normalized.codex_home),
        "CODEX_SQLITE_HOME": str(normalized.codex_sqlite_home),
        "HOME": str(normalized.home),
        "LANG": "C",
        "LC_ALL": "C",
        "NO_COLOR": "1",
        "PATH": ":".join(safe_path),
        "TERM": "dumb",
        "TMPDIR": str(normalized.tmpdir),
        "TSX_DISABLE_CACHE": "1",
    }


def build_clean_environment(
    paths: CodexPaths,
    *,
    command_path: Sequence[Path | str] | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a fresh exact environment for ``subprocess``.

    ``extra`` is restricted to explicit benchmark variables.  It cannot
    replace the controller-owned HOME, Codex state, PATH, or TMPDIR values.
    """

    environment = minimal_child_environment(paths, command_path=command_path)
    if extra:
        _validate_extra_environment(paths.normalized(), extra)
        environment.update({key: str(value) for key, value in extra.items()})
    return environment


def build_codex_command(
    *,
    codex_executable: Path | str,
    paths: CodexPaths,
    model: str,
    output_schema: Path | str,
    last_message_path: Path | str,
) -> list[str]:
    """Build the sole allowed Codex invocation form for a scored stage."""

    normalized = paths.normalized()
    message_path = _absolute(Path(last_message_path))
    if not _is_within(message_path, normalized.controller_root):
        raise IsolationError("last-message evidence must stay under controller state")
    command = [
        str(_absolute(Path(codex_executable))),
        "exec",
        "--strict-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--json",
        "--output-schema",
        str(_absolute(Path(output_schema))),
        "--output-last-message",
        str(message_path),
        "-C",
        str(normalized.candidate_root),
        "-m",
        model,
        "-",
    ]
    forbidden = {"--sandbox", "--ignore-user-config", "--ephemeral", "--dangerously-bypass-approvals-and-sandbox"}
    if forbidden.intersection(command):
        raise AssertionError("isolation command contains a forbidden legacy flag")
    return command


def build_sandbox_probe_contracts(
    *,
    probe_executable: Path | str,
    paths: CodexPaths,
    allowed_read: Path | str,
    allowed_write: Path | str,
    symlink_escape: Path | str,
    timeout_seconds: float = 5.0,
) -> tuple[ProbeSpec, ...]:
    """Declare all mandatory no-model checks for an isolation preflight.

    The controller supplies a tiny probe executable that performs the named
    operation under the generated profile.  Each denied operation must exit
    nonzero.  Tests use a fake executable, while production wires this to the
    native no-model permission probe.
    """

    normalized = paths.normalized()
    executable = str(_absolute(Path(probe_executable)))
    def spec(name: str, expect_success: bool, *arguments: str) -> ProbeSpec:
        return ProbeSpec(name, (executable, name, *arguments), expect_success, timeout_seconds)

    return (
        spec("allowed-read", True, str(_absolute(Path(allowed_read)))),
        spec("allowed-write", True, str(_absolute(Path(allowed_write)))),
        spec("denied-controller", False, str(normalized.controller_root)),
        spec("denied-auth", False, str(normalized.auth_target)),
        spec("denied-memory", False, str(normalized.memory_root)),
        spec("environment-leakage", False, "USER", "SSH_AUTH_SOCK", "AWS_SECRET_ACCESS_KEY"),
        spec("denied-external-network", False, "https://example.com"),
        spec("denied-loopback-network", False, "http://127.0.0.1:1"),
        spec("denied-unix-socket", False, "/var/run/docker.sock"),
        spec("denied-symlink-escape", False, str(_absolute(Path(symlink_escape)))),
        spec("timeout-breakaway", False, str(normalized.tmpdir)),
    )


def run_sandbox_probes(
    probes: Iterable[ProbeSpec], *, environment: Mapping[str, str], cwd: Path | str
) -> ProbeReport:
    """Run a no-model probe suite and return every outcome, including failures."""

    results = tuple(_run_probe(probe, environment=environment, cwd=Path(cwd)) for probe in probes)
    return ProbeReport(results)


def terminate_process_group(process: subprocess.Popen[bytes], *, grace_seconds: float = 0.25) -> None:
    """Terminate a timed-out probe and all descendants, then reap the leader."""

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        if process.poll() is None:
            process.wait(timeout=grace_seconds)
        return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    if process.poll() is None:
        process.wait(timeout=grace_seconds)


def _run_probe(probe: ProbeSpec, *, environment: Mapping[str, str], cwd: Path) -> ProbeResult:
    started = time.monotonic()
    process = subprocess.Popen(
        probe.argv,
        cwd=str(cwd),
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=probe.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_group(process)
        stdout, stderr = process.communicate()
    elapsed = time.monotonic() - started
    succeeded = process.returncode == 0 and not timed_out
    return ProbeResult(
        name=probe.name,
        passed=succeeded == probe.expect_success,
        returncode=process.returncode,
        timed_out=timed_out,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
        elapsed_seconds=elapsed,
    )


def _absolute(path: Path) -> Path:
    # Resolve existing ancestors so a controller cannot accidentally grant a
    # candidate path through an already-present symlink. ``strict=False`` also
    # supports the intentionally not-yet-created rollout directories.
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _runtime_roots(paths: CodexPaths, raw_roots: Sequence[Path | str]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for raw_root in raw_roots:
        root = _absolute(Path(raw_root))
        protected_paths = (
            paths.candidate_root,
            paths.home,
            paths.codex_home,
            paths.codex_sqlite_home,
            paths.tmpdir,
            paths.auth_target,
            paths.controller_root,
            paths.memory_root,
        )
        if any(_paths_overlap(root, protected) for protected in protected_paths):
            raise IsolationError("runtime root overlaps candidate or protected state")
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _command_path(raw_paths: Sequence[Path | str] | None) -> list[str]:
    values = raw_paths or ("/usr/bin", "/bin", "/usr/sbin", "/sbin")
    result: list[str] = []
    for raw_value in values:
        directory = _absolute(Path(raw_value))
        if not directory.is_dir():
            raise IsolationError("candidate shell PATH entry is not a directory")
        forbidden = ("codex", "npm", "npx")
        if any((directory / name).exists() or (directory / name).is_symlink() for name in forbidden):
            raise IsolationError("candidate shell PATH may not include Codex or npm")
        value = str(directory)
        if value not in result:
            result.append(value)
    if not result:
        raise IsolationError("candidate shell PATH may not be empty")
    return result


def _validate_extra_environment(
    paths: CodexPaths, values: Mapping[str, str]
) -> None:
    unexpected = sorted(set(values) - ALLOWED_CHILD_ENVIRONMENT)
    if unexpected:
        raise IsolationError(
            "unexpected isolated environment keys: " + ", ".join(unexpected)
        )
    candidate_acp = values.get("ROUTING_CANDIDATE_ACP")
    if candidate_acp is not None and not _is_within(
        _absolute(Path(str(candidate_acp))), paths.candidate_root
    ):
        raise IsolationError("ROUTING_CANDIDATE_ACP must be inside the candidate workspace")
    marker = values.get("ROUTING_RUN_MARKER")
    if marker is not None and (
        len(str(marker)) < 24
        or not all(character.isalnum() or character in "-_" for character in str(marker))
    ):
        raise IsolationError("ROUTING_RUN_MARKER must be a long safe identifier")


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_within(first, second) or _is_within(second, first)


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
