"""Shared native instruction paths, source identity and private setup."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from typing import Any

def absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


HOSTS = ("codex", "grok", "opencode", "claude")


def default_target(host: str = "codex") -> Path:
    if host == "codex":
        return absolute(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "AGENTS.md"
    if host == "grok":
        return absolute(os.environ.get("GROK_HOME") or Path.home() / ".grok") / "AGENTS.md"
    if host == "claude":
        return absolute(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "CLAUDE.md"
    if host == "opencode":
        custom = os.environ.get("OPENCODE_CONFIG_DIR")
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg and not Path(xdg).is_absolute():
            raise ValueError("XDG_CONFIG_HOME must be absolute")
        return (absolute(custom) if custom else
                (Path(xdg) if xdg else Path.home() / ".config") / "opencode") / "AGENTS.md"
    raise ValueError("unsupported host")


def is_cache_path(path: Path) -> bool:
    parts = path.parts
    return any(
        parts[index : index + 2] == ("plugins", "cache")
        for index in range(len(parts) - 1)
    )


def target_location(target: Path) -> Path:
    return target.parent.resolve(strict=False) / target.name


def target_is_in_cache(target: Path) -> bool:
    return is_cache_path(target) or is_cache_path(target_location(target))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_target(target: Path, source: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "target": str(target),
        "healthy": False,
        "status": "missing",
    }
    if target_is_in_cache(target):
        report["status"] = "cache-bound-target"
        return report
    if not os.path.lexists(target):
        return report
    if not target.is_symlink():
        report["status"] = "non-symlink"
        report["target_kind"] = "directory" if target.is_dir() else "file"
        return report

    link_target = os.readlink(target)
    linked = Path(link_target)
    linked_path = absolute(linked if linked.is_absolute() else target.parent / linked)
    resolved = linked_path.resolve(strict=False)
    report.update(
        {
            "link_target": link_target,
            "resolved_target": str(resolved),
            "target_kind": "symlink",
        }
    )
    if is_cache_path(linked_path) or is_cache_path(resolved):
        report["status"] = "cache-bound-link"
        return report
    if not resolved.is_file():
        report["status"] = "broken-link"
        return report
    if resolved.name != "AGENTS.md":
        report["status"] = "invalid-link-target"
        return report

    if resolved.parent.name != "global":
        report["status"] = "stale-source-layout"
        return report

    target_digest = digest(resolved)
    report.update(
        {
            "healthy": True,
            "sha256": target_digest,
            "status": "valid-stable-link",
            "target_sha256": target_digest,
        }
    )
    if source is not None:
        report["source"] = str(source)
        report["source_sha256"] = digest(source)
        if resolved != source.resolve():
            report.update(status="divergent-link", healthy=False)
    return report


def validate_source(source: Path) -> tuple[Path | None, dict[str, Any] | None]:
    if is_cache_path(source):
        return None, {
            "error": "cache-bound-source",
            "source": str(source),
        }
    try:
        resolved = source.resolve(strict=True)
    except FileNotFoundError:
        return None, {"error": "missing-source", "source": str(source)}
    if is_cache_path(resolved):
        return None, {
            "error": "cache-bound-source",
            "source": str(source),
            "resolved_source": str(resolved),
        }
    if not resolved.is_file():
        return None, {"error": "invalid-source", "source": str(source)}
    if resolved.name != "AGENTS.md":
        return None, {
            "error": "invalid-source-name",
            "source": str(source),
            "resolved_source": str(resolved),
        }
    if resolved.parent.name != "global":
        return None, {
            "error": "invalid-source-layout",
            "source": str(source),
            "resolved_source": str(resolved),
        }
    return resolved, None


def initialize_preferences(source: Path) -> dict[str, Any]:
    source = source.resolve()
    destination = source.parent.parent / "PREFERENCES.md"
    if os.path.lexists(destination):
        return {"path": str(destination), "action": "preserved"}
    example = source.parent.parent / "PREFERENCES.example.md"
    if not example.is_file():
        return {"path": str(destination), "action": "absent", "reason": "example-missing"}
    raw = example.read_bytes()
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {"path": str(destination), "action": "preserved"}
    with os.fdopen(descriptor, "wb") as output:
        output.write(raw)
    return {"path": str(destination), "action": "created"}


UNCHANGED_ACTION = (
    "The canonical global/AGENTS.md is unchanged since this session started "
    "(same SHA-256). Nothing is needed."
)
CHANGED_ACTION = (
    "The global rules changed since this session started. Read the current "
    "canonical global/AGENTS.md in full before acting."
)
REREAD_ACTION = (
    "The global rules in context are unverified. Read the current canonical "
    "global/AGENTS.md in full before acting and report this status."
)


def session_action(start_sha256: str | None, current_sha256: str) -> str:
    """Compare the file with its SHA-256 recorded when the session started."""
    if start_sha256 is None:
        return REREAD_ACTION
    return UNCHANGED_ACTION if start_sha256 == current_sha256 else CHANGED_ACTION


def context_payload(host: str = "codex", require_unambiguous: bool = False) -> dict[str, Any]:
    """Resolve only the selected native global link, never cwd or plugin cache."""
    boundary = (
        "Preferences supply personal defaults. Explicit task instructions, required "
        "project constraints, proof and authority boundaries take precedence. "
        "Machine roles do not authorize deployment. Do not publish private contents."
    )
    try:
        target = default_target(host)
        inspection = inspect_target(target)
        if not inspection["healthy"]:
            inspection["action"] = REREAD_ACTION
            return {"instructions": inspection, "preferences": {
                "status": "source-unavailable", "boundary": boundary,
                "action": "Inspect the native global link; suspend previously loaded preferences until resolved. Do not substitute project-local preferences or the example."}}
        if require_unambiguous:
            # Legacy hooks select Codex only when other configured hosts cannot
            # imply a different source. Never infer host identity from inherited env.
            for other in HOSTS:
                if other == host:
                    continue
                other_target = default_target(other)
                if not os.path.lexists(other_target):
                    continue
                other_inspection = inspect_target(other_target)
                if (not other_inspection["healthy"] or
                        other_inspection["resolved_target"] != inspection["resolved_target"]):
                    return {"instructions": {
                        "status": "source-ambiguous", "healthy": False,
                        "action": "Set AGENTSMD_HOST or pass --host for this process; configured native sources differ or cannot be verified. " + REREAD_ACTION},
                        "preferences": {"status": "source-unavailable", "boundary": boundary,
                                        "action": "Suspend previously loaded preferences until the host source is selected."}}
        source = Path(inspection["resolved_target"])
        # Without a session record nothing proves which revision is in context;
        # the hook replaces this with session_action.
        inspection["action"] = REREAD_ACTION
        path = source.parent.parent / "PREFERENCES.md"
        preferences: dict[str, Any] = {"path": str(path), "boundary": boundary}
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            if os.path.lexists(path):
                preferences.update(status="unreadable", detail="broken preference link")
            else:
                preferences.update(status="absent", action="Shared defaults apply; discard previously loaded preferences.")
        except OSError:
            preferences.update(status="unreadable", detail="read failed")
        else:
            preferences["sha256"] = hashlib.sha256(raw).hexdigest()
            # A diagnostic with a full-read fallback is safer than host truncation.
            if len(raw) > 8192:
                preferences.update(status="oversized", bytes=len(raw), limit_bytes=8192,
                                   action="Read the complete private file explicitly; no contents were injected.")
            else:
                try:
                    preferences.update(status="ready", content=raw.decode("utf-8"))
                except UnicodeDecodeError:
                    preferences.update(status="unreadable", detail="not valid UTF-8")
        return {"instructions": inspection, "preferences": preferences}
    except (OSError, ValueError, RuntimeError) as error:
        return {"instructions": {"status": "unreadable", "detail": str(error), "action": REREAD_ACTION},
                "preferences": {"status": "source-unavailable", "boundary": boundary}}
