from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ExitCode, VersionCtlError


POLICY_FILE = ".version-policy.json"


@dataclass(frozen=True)
class Mirror:
    path: str
    pointer: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "pointer": self.pointer}


@dataclass(frozen=True)
class Policy:
    schema: int
    bump_policy: str
    version_source: str
    tag_pattern: str
    tag_policy: str
    github_release_policy: str
    distribution_policy: str
    publish_policy: str
    release_branch: str
    wip_prefixes: tuple[str, ...]
    mirrors: tuple[Mirror, ...]

    @classmethod
    def load(cls, root: Path) -> "Policy":
        path = root / POLICY_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"missing {POLICY_FILE} at repository root",
                details={"path": str(path)},
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"cannot read {POLICY_FILE}: {exc}",
                details={"path": str(path)},
            ) from exc

        if not isinstance(raw, dict):
            raise VersionCtlError(ExitCode.INVALID_POLICY, "version policy must be a JSON object")

        required = {
            "schema",
            "bumpPolicy",
            "versionSource",
            "tagPattern",
            "tagPolicy",
            "githubReleasePolicy",
            "distributionPolicy",
            "publishPolicy",
            "mirrors",
        }
        allowed = required | {"releaseBranch", "wipPrefixes"}
        missing = sorted(required - raw.keys())
        if missing:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "version policy is missing required fields",
                details={"missing": missing},
            )
        unknown = sorted(raw.keys() - allowed)
        if unknown:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "version policy contains unknown schema 1 fields",
                details={"unknown": unknown},
            )

        if raw["schema"] != 1:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "only version policy schema 1 is supported",
                details={"schema": raw["schema"]},
            )

        cls._expect(raw, "bumpPolicy", {"every-deliverable"})
        cls._expect(raw, "tagPolicy", {"every-version"})
        cls._expect(raw, "githubReleasePolicy", {"manual", "on-version-commit"})
        cls._expect(raw, "distributionPolicy", {"released-tags-only"})
        cls._expect(raw, "publishPolicy", {"manual"})

        version_source = cls._relative_path(raw["versionSource"], "versionSource")
        if version_source != "VERSION":
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "schema 1 requires the root VERSION file as versionSource",
                details={"versionSource": version_source},
            )
        tag_pattern = raw["tagPattern"]
        if not isinstance(tag_pattern, str) or tag_pattern.count("{version}") != 1:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "tagPattern must contain {version} exactly once",
            )

        release_branch = raw.get("releaseBranch", "main")
        if not isinstance(release_branch, str) or not release_branch.strip():
            raise VersionCtlError(ExitCode.INVALID_POLICY, "releaseBranch must be a non-empty string")

        prefixes = raw.get("wipPrefixes", ["wip:"])
        if (
            not isinstance(prefixes, list)
            or not prefixes
            or any(not isinstance(item, str) or not item for item in prefixes)
        ):
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                "wipPrefixes must be a non-empty array of non-empty strings",
            )

        raw_mirrors = raw["mirrors"]
        if not isinstance(raw_mirrors, list):
            raise VersionCtlError(ExitCode.INVALID_POLICY, "mirrors must be an array")
        mirrors: list[Mirror] = []
        seen_paths: set[str] = set()
        for index, item in enumerate(raw_mirrors):
            if not isinstance(item, dict) or set(item) != {"path", "pointer"}:
                raise VersionCtlError(
                    ExitCode.INVALID_POLICY,
                    "each mirror must contain only path and pointer",
                    details={"index": index},
                )
            mirror_path = cls._relative_path(item["path"], f"mirrors[{index}].path")
            pointer = item["pointer"]
            if not isinstance(pointer, str) or not pointer.startswith("/"):
                raise VersionCtlError(
                    ExitCode.INVALID_POLICY,
                    "mirror pointer must be an absolute JSON Pointer",
                    details={"index": index, "pointer": pointer},
                )
            if mirror_path == version_source or mirror_path in seen_paths:
                raise VersionCtlError(
                    ExitCode.INVALID_POLICY,
                    "mirror paths must be unique and cannot equal versionSource",
                    details={"path": mirror_path},
                )
            seen_paths.add(mirror_path)
            mirrors.append(Mirror(mirror_path, pointer))

        return cls(
            schema=1,
            bump_policy=raw["bumpPolicy"],
            version_source=version_source,
            tag_pattern=tag_pattern,
            tag_policy=raw["tagPolicy"],
            github_release_policy=raw["githubReleasePolicy"],
            distribution_policy=raw["distributionPolicy"],
            publish_policy=raw["publishPolicy"],
            release_branch=release_branch,
            wip_prefixes=tuple(prefixes),
            mirrors=tuple(mirrors),
        )

    @staticmethod
    def _expect(raw: dict[str, Any], field: str, allowed: set[str]) -> None:
        if raw[field] not in allowed:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"unsupported {field}: {raw[field]!r}",
                details={"allowed": sorted(allowed)},
            )

    @staticmethod
    def _relative_path(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise VersionCtlError(ExitCode.INVALID_POLICY, f"{label} must be a non-empty string")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
            raise VersionCtlError(
                ExitCode.INVALID_POLICY,
                f"{label} must stay inside the repository",
                details={"path": value},
            )
        return path.as_posix()

    def tag_for(self, version: str) -> str:
        return self.tag_pattern.replace("{version}", version)

    def tag_parts(self) -> tuple[str, str]:
        prefix, suffix = self.tag_pattern.split("{version}", 1)
        return prefix, suffix

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "bumpPolicy": self.bump_policy,
            "versionSource": self.version_source,
            "tagPattern": self.tag_pattern,
            "tagPolicy": self.tag_policy,
            "githubReleasePolicy": self.github_release_policy,
            "distributionPolicy": self.distribution_policy,
            "publishPolicy": self.publish_policy,
            "releaseBranch": self.release_branch,
            "wipPrefixes": list(self.wip_prefixes),
            "mirrors": [mirror.as_dict() for mirror in self.mirrors],
        }
