from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import changelog
from .errors import ExitCode, VersionCtlError
from .files import (
    MirrorState,
    mirror_states,
    parse_version_text,
    read_version_file,
    transactional_write,
    updated_mirror_text,
    version_from_mirror_text,
)
from .policy import Mirror, Policy
from .repository import GitRepository, VersionTag
from .semver import SemVer


CHANGELOG_PATH = "CHANGELOG.md"
_IMPACT_RANK = {"patch": 1, "minor": 2, "major": 3}


@dataclass(frozen=True)
class CommandOutcome:
    report: dict[str, Any]
    exit_code: ExitCode = ExitCode.OK


class VersionService:
    def __init__(self, repo: GitRepository, policy: Policy) -> None:
        self.repo = repo
        self.policy = policy

    @classmethod
    def discover(cls, start: Path | None = None) -> "VersionService":
        repo = GitRepository.discover(start)
        return cls(repo, Policy.load(repo.root))

    @property
    def managed_paths(self) -> set[str]:
        return {
            self.policy.version_source,
            CHANGELOG_PATH,
            *(mirror.path for mirror in self.policy.mirrors),
        }

    def doctor(
        self,
        *,
        staged: bool = False,
        ci: bool = False,
        base: str | None = None,
    ) -> CommandOutcome:
        if staged and ci:
            raise VersionCtlError(ExitCode.INVALID_ARGUMENT, "--staged and --ci are mutually exclusive")
        if ci and not base:
            raise VersionCtlError(ExitCode.INVALID_ARGUMENT, "doctor --ci requires --base <ref>")
        if base and not ci:
            raise VersionCtlError(ExitCode.INVALID_ARGUMENT, "--base is valid only with --ci")

        scope = "staged" if staged else "ci" if ci else "working"
        current = self._snapshot_version("index" if staged else "worktree")
        head_version = self._snapshot_version("head", required=False)
        states = self._snapshot_mirrors("index" if staged else "worktree", current)
        changelog_text = self._snapshot_text(CHANGELOG_PATH, "index" if staged else "worktree")
        changelog_entry = changelog.entry(changelog_text or "", str(current))
        status = self.repo.status()
        head = self.repo.head_or_none()
        tags = self.repo.list_version_tags(self.policy)
        current_tag_name = self.policy.tag_for(str(current))
        current_tag_target = self.repo.tag_target(current_tag_name)
        latest_tag = tags[-1] if tags else None
        ahead, behind, upstream = self.repo.cached_divergence()

        if ci:
            assert base is not None
            changed = self.repo.diff_paths(base)
            base_version = self._snapshot_version_at(base)
        elif staged:
            changed = list(status["staged"])
            base_version = head_version
        else:
            changed = list(status["changed"])
            base_version = head_version

        content_changes = sorted(set(changed) - self.managed_paths)
        managed_changes = sorted(set(changed) & self.managed_paths)
        transition_valid: bool | None = None
        bump_required = False
        bump_reason: str | None = None

        if ci:
            if content_changes:
                if base_version is None:
                    transition_valid = True
                else:
                    transition_valid = base_version.transition_impact(current) is not None
                bump_required = not transition_valid
                if bump_required:
                    bump_reason = "content changed without one valid SemVer transition from the base"
            elif base_version is not None and current != base_version:
                transition_valid = False
                bump_required = True
                bump_reason = "repository version changed without deliverable content"
        elif staged:
            if content_changes:
                transition_valid = (
                    (
                        base_version is None
                        or base_version.transition_impact(current) is not None
                    )
                    and self.policy.version_source in status["staged"]
                )
                bump_required = not transition_valid
                if bump_required:
                    bump_reason = "staged content requires a staged one-step SemVer transition"
            elif base_version is not None and current != base_version:
                transition_valid = False
                bump_required = True
                bump_reason = "staged version changed without deliverable content"
        else:
            if content_changes:
                transition_valid = (
                    head_version is None
                    or head_version.transition_impact(current) is not None
                )
                bump_required = not transition_valid
                if bump_required:
                    bump_reason = "working content requires one SemVer transition before commit"
            elif head_version is not None and current != head_version:
                transition_valid = False
                bump_required = True
                bump_reason = "working version changed without deliverable content"
            elif current_tag_target and current_tag_target != head:
                committed_content = sorted(
                    set(self.repo.changed_since(current_tag_name)) - self.managed_paths
                )
                if committed_content:
                    content_changes = committed_content
                    bump_required = True
                    transition_valid = False
                    bump_reason = "HEAD contains deliverable commits after the current version tag"

        issues: list[dict[str, Any]] = []
        inconsistent = [state.as_dict() for state in states if not state.consistent]
        if inconsistent:
            issues.append(
                self._issue(
                    ExitCode.STALE_MIRROR,
                    "one or more declared mirrors do not equal the canonical version",
                    mirrors=inconsistent,
                )
            )
        if bump_required:
            issues.append(
                self._issue(
                    ExitCode.BUMP_REQUIRED,
                    bump_reason or "a repository version bump is required",
                    contentChanges=content_changes,
                    baseVersion=str(base_version) if base_version else None,
                    currentVersion=str(current),
                )
            )
        if changelog_entry is None:
            issues.append(
                self._issue(
                    ExitCode.CHANGELOG_INVALID,
                    f"CHANGELOG.md has no entry for {current}",
                    version=str(current),
                )
            )
        if current_tag_target and current_tag_target != head:
            issues.append(
                self._issue(
                    ExitCode.TAG_CONFLICT,
                    f"{current_tag_name} already identifies different content",
                    tag=current_tag_name,
                    tagSha=current_tag_target,
                    head=head,
                )
            )

        report = {
            "schema": 1,
            "command": "doctor",
            "ok": not issues,
            "scope": scope,
            "repository": {
                "root": str(self.repo.root),
                "branch": self.repo.branch,
                "head": head,
                "dirty": status["dirty"],
                "upstream": upstream,
                "ahead": ahead,
                "behind": behind,
                **self.repo.environment_identity(),
            },
            "version": {
                "current": str(current),
                "source": self.policy.version_source,
                "head": str(head_version) if head_version else None,
                "tag": current_tag_name,
                "tagSha": current_tag_target,
                "alreadyUsed": current_tag_target is not None,
                "latestTag": self._tag_dict(latest_tag),
            },
            "changes": {
                "base": base,
                "changed": changed,
                "staged": status["staged"],
                "unstaged": status["unstaged"],
                "untracked": status["untracked"],
                "content": content_changes,
                "managed": managed_changes,
            },
            "bump": {
                "required": bump_required,
                "transitionValid": transition_valid,
                "baseVersion": str(base_version) if base_version else None,
            },
            "mirrors": [state.as_dict() for state in states],
            "changelog": {
                "path": CHANGELOG_PATH,
                "consistent": changelog_entry is not None,
                "entryDate": changelog_entry[0] if changelog_entry else None,
            },
            "policy": self.policy.as_dict(),
            "issues": issues,
        }
        return CommandOutcome(report, self._issue_exit_code(issues))

    def adopt(self, version_value: str, *, reason: str, dry_run: bool = False) -> CommandOutcome:
        version = SemVer.parse(version_value, label="initial version")
        version_path = self.repo.root / self.policy.version_source
        if version_path.exists() or self.repo.file_at("HEAD", self.policy.version_source) is not None:
            raise VersionCtlError(
                ExitCode.VERSION_CONFLICT,
                "repository is already adopted; use prepare for later transitions",
                details={"path": self.policy.version_source},
            )

        status = self.repo.status()
        content_changes = sorted(set(status["changed"]) - self.managed_paths)
        if not content_changes:
            raise VersionCtlError(
                ExitCode.NO_CHANGES,
                "initial adoption requires repository content to identify",
            )

        changes: dict[Path, str] = {version_path: f"{version}\n"}
        fields: list[dict[str, Any]] = [
            {"path": self.policy.version_source, "pointer": None, "before": None, "after": str(version)}
        ]
        for mirror in self.policy.mirrors:
            path = self.repo.root / mirror.path
            updated, normalization = updated_mirror_text(path, mirror.pointer, str(version))
            before = version_from_mirror_text(path, mirror.pointer, path.read_text(encoding="utf-8"))
            changes[path] = updated
            fields.append(
                {
                    "path": mirror.path,
                    "pointer": mirror.pointer,
                    "before": before,
                    "after": str(version),
                    "normalization": normalization,
                }
            )

        changelog_path = self.repo.root / CHANGELOG_PATH
        changelog_text = (
            changelog_path.read_text(encoding="utf-8")
            if changelog_path.exists()
            else "# Changelog\n"
        )
        changes[changelog_path] = changelog.update(
            changelog_text,
            version=str(version),
            reason=reason,
            impact="adopt",
        )
        fields.append(
            {"path": CHANGELOG_PATH, "pointer": f"entry:{version}", "before": None, "after": reason}
        )

        if not dry_run:
            transactional_write(changes)
        report = {
            "schema": 1,
            "command": "adopt",
            "ok": True,
            "dryRun": dry_run,
            "version": str(version),
            "reason": " ".join(reason.split()),
            "changes": fields,
            "next": ["inspect the diff", "stage the deliverable and version files", "commit atomically"],
        }
        return CommandOutcome(report)

    def prepare(self, impact: str, *, reason: str, dry_run: bool = False) -> CommandOutcome:
        current = read_version_file(self.repo.root / self.policy.version_source)
        states = mirror_states(self.repo.root, self.policy.mirrors, current)
        inconsistent = [state.as_dict() for state in states if not state.consistent]
        if inconsistent:
            raise VersionCtlError(
                ExitCode.STALE_MIRROR,
                "refusing to prepare from stale mirrors",
                details={"mirrors": inconsistent},
            )

        head_version = self._snapshot_version("head", required=False)
        if head_version is None:
            raise VersionCtlError(
                ExitCode.MISSING_VERSION,
                "canonical version is not committed; use adopt for initial migration",
            )

        status = self.repo.status()
        content_changes = sorted(set(status["changed"]) - self.managed_paths)
        current_tag = self.policy.tag_for(str(current))
        current_tag_target = self.repo.tag_target(current_tag)
        if not content_changes and current_tag_target and current_tag_target != self.repo.head:
            content_changes = sorted(set(self.repo.changed_since(current_tag)) - self.managed_paths)
        if not content_changes:
            raise VersionCtlError(
                ExitCode.NO_CHANGES,
                "no deliverable content change exists to version",
            )

        pending_impact: str | None = None
        replace_version: str | None = None
        if current == head_version:
            target = current.bump(impact)
        else:
            pending_impact = head_version.transition_impact(current)
            if pending_impact is None:
                raise VersionCtlError(
                    ExitCode.VERSION_CONFLICT,
                    "working VERSION is not one valid transition from HEAD",
                    details={"headVersion": str(head_version), "currentVersion": str(current)},
                )
            chosen = impact if _IMPACT_RANK[impact] > _IMPACT_RANK[pending_impact] else pending_impact
            target = head_version.bump(chosen)
            if target != current:
                replace_version = str(current)

        target_tag = self.policy.tag_for(str(target))
        existing_target = self.repo.tag_target(target_tag)
        if existing_target is not None:
            raise VersionCtlError(
                ExitCode.VERSION_CONFLICT,
                f"target version is already used by {target_tag}",
                details={"tag": target_tag, "sha": existing_target},
            )

        changes: dict[Path, str] = {
            self.repo.root / self.policy.version_source: f"{target}\n"
        }
        fields: list[dict[str, Any]] = [
            {
                "path": self.policy.version_source,
                "pointer": None,
                "before": str(current),
                "after": str(target),
            }
        ]
        for mirror in self.policy.mirrors:
            path = self.repo.root / mirror.path
            updated, normalization = updated_mirror_text(path, mirror.pointer, str(target))
            before = read_version_file_from_mirror(path, mirror)
            changes[path] = updated
            fields.append(
                {
                    "path": mirror.path,
                    "pointer": mirror.pointer,
                    "before": before,
                    "after": str(target),
                    "normalization": normalization,
                }
            )

        changelog_path = self.repo.root / CHANGELOG_PATH
        try:
            changelog_text = changelog_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            changelog_text = "# Changelog\n"
        changes[changelog_path] = changelog.update(
            changelog_text,
            version=str(target),
            reason=reason,
            impact=impact,
            replace_version=replace_version,
        )
        fields.append(
            {
                "path": CHANGELOG_PATH,
                "pointer": f"entry:{target}",
                "before": replace_version,
                "after": " ".join(reason.split()),
            }
        )

        if not dry_run:
            transactional_write(changes)
        report = {
            "schema": 1,
            "command": "prepare",
            "ok": True,
            "dryRun": dry_run,
            "impact": impact,
            "pendingImpact": pending_impact,
            "version": {"before": str(current), "after": str(target)},
            "reason": " ".join(reason.split()),
            "contentChanges": content_changes,
            "changes": fields,
            "next": [
                "inspect the version and changelog diff",
                "commit deliverable, version, mirrors, and changelog atomically",
                "run versionctl release-check on the clean commit",
            ],
        }
        return CommandOutcome(report)

    def release_check(
        self,
        *,
        version_value: str | None = None,
        sha: str | None = None,
        tag: str | None = None,
    ) -> CommandOutcome:
        status = self.repo.status()
        if status["dirty"]:
            raise VersionCtlError(
                ExitCode.DIRTY_TREE,
                "release-check requires a clean working tree",
                details={"changed": status["changed"]},
            )

        head = self.repo.head
        if sha:
            if not self.repo.ref_exists(sha):
                raise VersionCtlError(
                    ExitCode.INVALID_ARGUMENT,
                    f"release SHA does not resolve to a commit: {sha}",
                )
            resolved = self.repo.run(["rev-parse", f"{sha}^{{commit}}"]).stdout.strip()
            if resolved != head:
                raise VersionCtlError(
                    ExitCode.VERSION_CONFLICT,
                    "proposed distribution SHA is not exact HEAD",
                    details={"proposedSha": resolved, "head": head},
                )

        current = read_version_file(self.repo.root / self.policy.version_source)
        head_version = self._snapshot_version("head")
        if current != head_version:
            raise VersionCtlError(
                ExitCode.VERSION_CONFLICT,
                "HEAD does not contain the declared working-tree version",
                details={"workingVersion": str(current), "headVersion": str(head_version)},
            )
        if version_value and SemVer.parse(version_value, label="requested version") != current:
            raise VersionCtlError(
                ExitCode.VERSION_CONFLICT,
                "requested version does not equal the declared version",
                details={"requestedVersion": version_value, "currentVersion": str(current)},
            )

        states = mirror_states(self.repo.root, self.policy.mirrors, current)
        inconsistent = [state.as_dict() for state in states if not state.consistent]
        if inconsistent:
            raise VersionCtlError(
                ExitCode.STALE_MIRROR,
                "release mirrors do not equal the canonical version",
                details={"mirrors": inconsistent},
            )

        entry_date, notes = changelog.require_entry(self.repo.root / CHANGELOG_PATH, str(current))
        expected_tag = self.policy.tag_for(str(current))
        if tag and tag != expected_tag:
            raise VersionCtlError(
                ExitCode.TAG_CONFLICT,
                "requested tag does not match project policy",
                details={"requestedTag": tag, "expectedTag": expected_tag},
            )

        target = self.repo.tag_target(expected_tag)
        if target and target != head:
            raise VersionCtlError(
                ExitCode.TAG_CONFLICT,
                f"{expected_tag} already references different content",
                details={"tagSha": target, "head": head},
            )
        if target and self.repo.tag_object_type(expected_tag) != "tag":
            raise VersionCtlError(
                ExitCode.TAG_CONFLICT,
                f"{expected_tag} exists but is not an annotated tag",
            )

        for version_tag in self.repo.list_version_tags(self.policy):
            if version_tag.version > current:
                raise VersionCtlError(
                    ExitCode.VERSION_CONFLICT,
                    "a newer repository version tag already exists",
                    details={"newerTag": version_tag.name, "newerVersion": str(version_tag.version)},
                )
            if version_tag.version == current and version_tag.commit != head:
                raise VersionCtlError(
                    ExitCode.VERSION_CONFLICT,
                    "the declared version was already used for different content",
                    details={"tag": version_tag.name, "sha": version_tag.commit},
                )

        prior_tags = [
            version_tag
            for version_tag in self.repo.list_version_tags(self.policy)
            if version_tag.version < current
        ]
        if prior_tags and prior_tags[-1].version.transition_impact(current) is None:
            raise VersionCtlError(
                ExitCode.VERSION_CONFLICT,
                "declared version skips the next valid transition from the latest prior tag",
                details={
                    "priorTag": prior_tags[-1].name,
                    "priorVersion": str(prior_tags[-1].version),
                    "currentVersion": str(current),
                },
            )

        report = {
            "schema": 1,
            "command": "release-check",
            "ok": True,
            "version": str(current),
            "sha": head,
            "tag": expected_tag,
            "tagExists": target is not None,
            "tagSha": target,
            "changelogDate": entry_date,
            "changelogEntry": notes,
            "mirrors": [state.as_dict() for state in states],
            "distribution": {
                "policy": self.policy.distribution_policy,
                "releaseSha": head,
                "proposedSha": sha or head,
                "consistent": True,
            },
            "publication": {
                "githubReleasePolicy": self.policy.github_release_policy,
                "publishPolicy": self.policy.publish_policy,
            },
        }
        return CommandOutcome(report)

    def install_hooks(self) -> CommandOutcome:
        hooks_dir = self.repo.hooks_dir()
        hooks_dir.mkdir(parents=True, exist_ok=True)
        scripts = {
            "pre-commit": self._hook_script("pre-commit"),
            "commit-msg": self._hook_script("commit-msg"),
        }
        changed: list[str] = []
        for name, content in scripts.items():
            path = hooks_dir / name
            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if existing != content and "managed-by: versionctl schema 1" not in existing:
                    raise VersionCtlError(
                        ExitCode.AUTHORIZATION_REQUIRED,
                        f"refusing to replace existing unmanaged hook: {path}",
                        details={"path": str(path)},
                    )
        for name, content in scripts.items():
            path = hooks_dir / name
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8")
                path.chmod(0o755)
                changed.append(name)
        return CommandOutcome(
            {
                "schema": 1,
                "command": "install-hooks",
                "ok": True,
                "hooksDirectory": str(hooks_dir),
                "installed": changed,
                "unchanged": sorted(set(scripts) - set(changed)),
            }
        )

    def hook_check(self, phase: str, *, message_file: Path | None = None) -> CommandOutcome:
        wip_intent = os.environ.get("VERSIONCTL_WIP") == "1"
        if phase == "pre-commit":
            if wip_intent:
                return CommandOutcome(
                    {
                        "schema": 1,
                        "command": "hook-check",
                        "ok": True,
                        "phase": phase,
                        "wipIntent": True,
                        "deferred": "commit-msg",
                    }
                )
            return self.doctor(staged=True)

        if phase != "commit-msg" or message_file is None:
            raise VersionCtlError(
                ExitCode.INVALID_ARGUMENT,
                "commit-msg hook check requires --message-file",
            )
        try:
            first_line = message_file.read_text(encoding="utf-8").splitlines()[0].strip()
        except (FileNotFoundError, IndexError, OSError) as exc:
            raise VersionCtlError(
                ExitCode.INVALID_ARGUMENT,
                f"cannot read commit message: {message_file}",
            ) from exc
        is_wip = any(first_line.lower().startswith(prefix.lower()) for prefix in self.policy.wip_prefixes)
        if wip_intent and not is_wip:
            raise VersionCtlError(
                ExitCode.INVALID_ARGUMENT,
                "VERSIONCTL_WIP=1 requires an allowed WIP commit prefix",
                details={"allowedPrefixes": list(self.policy.wip_prefixes), "subject": first_line},
            )
        if is_wip and not wip_intent:
            raise VersionCtlError(
                ExitCode.AUTHORIZATION_REQUIRED,
                "WIP checkpoints require explicit VERSIONCTL_WIP=1 intent",
                details={"subject": first_line},
            )
        if is_wip:
            return CommandOutcome(
                {
                    "schema": 1,
                    "command": "hook-check",
                    "ok": True,
                    "phase": phase,
                    "wipIntent": True,
                    "subject": first_line,
                }
            )
        return self.doctor(staged=True)

    def _snapshot_version(self, snapshot: str, *, required: bool = True) -> SemVer | None:
        if snapshot == "worktree":
            if required:
                return read_version_file(self.repo.root / self.policy.version_source)
            path = self.repo.root / self.policy.version_source
            return read_version_file(path) if path.exists() else None
        if snapshot == "index":
            raw = self.repo.index_file(self.policy.version_source)
        elif snapshot == "head":
            raw = self.repo.file_at("HEAD", self.policy.version_source)
        else:
            raise AssertionError(snapshot)
        parsed = parse_version_text(raw, label=f"{snapshot} {self.policy.version_source}")
        if parsed is None and required:
            raise VersionCtlError(
                ExitCode.MISSING_VERSION,
                f"{snapshot} has no canonical version file",
            )
        return parsed

    def _snapshot_version_at(self, ref: str) -> SemVer | None:
        return parse_version_text(
            self.repo.file_at(ref, self.policy.version_source),
            label=f"{ref} {self.policy.version_source}",
        )

    def _snapshot_text(self, path: str, snapshot: str) -> str | None:
        if snapshot == "worktree":
            target = self.repo.root / path
            try:
                return target.read_text(encoding="utf-8")
            except FileNotFoundError:
                return None
        if snapshot == "index":
            return self.repo.index_file(path)
        raise AssertionError(snapshot)

    def _snapshot_mirrors(
        self,
        snapshot: str,
        current: SemVer,
    ) -> list[MirrorState]:
        if snapshot == "worktree":
            return mirror_states(self.repo.root, self.policy.mirrors, current)
        states: list[MirrorState] = []
        for mirror in self.policy.mirrors:
            raw = self.repo.index_file(mirror.path)
            if raw is None:
                states.append(MirrorState(mirror.path, mirror.pointer, None, False, "missing from index"))
                continue
            try:
                value = version_from_mirror_text(self.repo.root / mirror.path, mirror.pointer, raw)
                states.append(MirrorState(mirror.path, mirror.pointer, value, value == str(current)))
            except VersionCtlError as exc:
                states.append(MirrorState(mirror.path, mirror.pointer, None, False, exc.message))
        return states

    @staticmethod
    def _tag_dict(tag: VersionTag | None) -> dict[str, str] | None:
        if tag is None:
            return None
        return {"name": tag.name, "version": str(tag.version), "sha": tag.commit}

    @staticmethod
    def _issue(code: ExitCode, message: str, **details: Any) -> dict[str, Any]:
        return {"code": code.name, "exitCode": int(code), "message": message, "details": details}

    @staticmethod
    def _issue_exit_code(issues: list[dict[str, Any]]) -> ExitCode:
        if not issues:
            return ExitCode.OK
        priority = [
            ExitCode.STALE_MIRROR,
            ExitCode.BUMP_REQUIRED,
            ExitCode.CHANGELOG_INVALID,
            ExitCode.TAG_CONFLICT,
        ]
        codes = {ExitCode(issue["exitCode"]) for issue in issues}
        return next((code for code in priority if code in codes), ExitCode.INVALID_ARGUMENT)

    @staticmethod
    def _hook_script(phase: str) -> str:
        message_arg = ' --message-file "$1"' if phase == "commit-msg" else ""
        return f"""#!/bin/sh
# managed-by: versionctl schema 1
set -eu

repo_root=$(git rev-parse --show-toplevel)
bundled="$repo_root/tools/versionctl/bin/versionctl"

if [ -x "$bundled" ]; then
  exec "$bundled" hook-check {phase}{message_arg}
fi
if command -v versionctl >/dev/null 2>&1; then
  exec versionctl hook-check {phase}{message_arg}
fi

echo "versionctl is required by the repository commit hook" >&2
exit {int(ExitCode.AUTHORIZATION_REQUIRED)}
"""


def read_version_file_from_mirror(path: Path, mirror: Mirror) -> str:
    return version_from_mirror_text(path, mirror.pointer, path.read_text(encoding="utf-8"))
