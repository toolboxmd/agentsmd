from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import ExitCode, VersionCtlError
from .policy import Policy
from .semver import SemVer


@dataclass(frozen=True)
class VersionTag:
    name: str
    version: SemVer
    commit: str


class GitRepository:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def discover(cls, start: Path | None = None) -> "GitRepository":
        cwd = (start or Path.cwd()).resolve()
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise VersionCtlError(
                ExitCode.NOT_GIT_REPOSITORY,
                "current directory is not inside a Git repository",
                details={"cwd": str(cwd), "stderr": result.stderr.strip()},
            )
        return cls(Path(result.stdout.strip()).resolve())

    def run(
        self,
        args: Iterable[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = ["git", *args]
        result = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            raise VersionCtlError(
                ExitCode.GIT_ERROR,
                f"Git command failed: {' '.join(command)}",
                details={
                    "returnCode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                },
            )
        return result

    @property
    def head(self) -> str:
        return self.run(["rev-parse", "HEAD"]).stdout.strip()

    def head_or_none(self) -> str | None:
        result = self.run(["rev-parse", "--verify", "HEAD"], check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    @property
    def branch(self) -> str | None:
        value = self.run(["branch", "--show-current"]).stdout.strip()
        return value or None

    def status(self) -> dict[str, list[str] | bool]:
        staged = self._zpaths(["diff", "--cached", "--name-only", "-z", "--diff-filter=ACDMRTUXB"])
        unstaged = self._zpaths(["diff", "--name-only", "-z", "--diff-filter=ACDMRTUXB"])
        untracked = self._zpaths(["ls-files", "--others", "--exclude-standard", "-z"])
        changed = sorted(set(staged) | set(unstaged) | set(untracked))
        return {
            "dirty": bool(changed),
            "changed": changed,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        }

    def _zpaths(self, args: list[str]) -> list[str]:
        output = self.run(args).stdout
        return sorted(path for path in output.split("\0") if path)

    def cached_divergence(self) -> tuple[int | None, int | None, str | None]:
        upstream = self.run(["rev-parse", "--abbrev-ref", "@{upstream}"], check=False)
        if upstream.returncode != 0:
            return None, None, None
        name = upstream.stdout.strip()
        counts = self.run(["rev-list", "--left-right", "--count", f"HEAD...{name}"]).stdout.split()
        if len(counts) != 2:
            return None, None, name
        ahead, behind = (int(value) for value in counts)
        return ahead, behind, name

    def ref_exists(self, ref: str) -> bool:
        return self.run(["cat-file", "-e", f"{ref}^{{commit}}"], check=False).returncode == 0

    def file_at(self, ref: str, path: str) -> str | None:
        result = self.run(["show", f"{ref}:{path}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout

    def index_file(self, path: str) -> str | None:
        result = self.run(["show", f":{path}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout

    def diff_paths(self, base: str, target: str = "HEAD") -> list[str]:
        if not self.ref_exists(base):
            raise VersionCtlError(
                ExitCode.INVALID_ARGUMENT,
                f"base ref does not resolve to a commit: {base}",
                details={"base": base},
            )
        return self._zpaths(["diff", "--name-only", "-z", f"{base}...{target}"])

    def list_version_tags(self, policy: Policy) -> list[VersionTag]:
        prefix, suffix = policy.tag_parts()
        tags: list[VersionTag] = []
        for name in self.run(["tag", "--list"]).stdout.splitlines():
            if not name.startswith(prefix) or (suffix and not name.endswith(suffix)):
                continue
            end = len(name) - len(suffix) if suffix else len(name)
            raw_version = name[len(prefix) : end]
            try:
                version = SemVer.parse(raw_version, label=f"tag {name}")
            except VersionCtlError:
                continue
            target = self.tag_target(name)
            if target is not None:
                tags.append(VersionTag(name=name, version=version, commit=target))
        return sorted(tags, key=lambda item: item.version)

    def tag_target(self, tag: str) -> str | None:
        result = self.run(["rev-parse", f"{tag}^{{commit}}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def tag_object_type(self, tag: str) -> str | None:
        result = self.run(["cat-file", "-t", f"refs/tags/{tag}"], check=False)
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def changed_since(self, ref: str) -> list[str]:
        return self.diff_paths(ref)

    def git_dir(self) -> Path:
        raw = self.run(["rev-parse", "--git-dir"]).stdout.strip()
        path = Path(raw)
        return path.resolve() if path.is_absolute() else (self.root / path).resolve()

    def hooks_dir(self) -> Path:
        configured = self.run(["config", "--path", "--get", "core.hooksPath"], check=False)
        if configured.returncode == 0 and configured.stdout.strip():
            path = Path(configured.stdout.strip()).expanduser()
            return path.resolve() if path.is_absolute() else (self.root / path).resolve()
        return self.git_dir() / "hooks"

    def environment_identity(self) -> dict[str, str | None]:
        return {
            "githubSha": os.environ.get("GITHUB_SHA"),
            "githubRef": os.environ.get("GITHUB_REF"),
        }
