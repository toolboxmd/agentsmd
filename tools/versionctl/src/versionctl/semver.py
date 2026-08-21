from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ExitCode, VersionCtlError


_STABLE_SEMVER = re.compile(
    r"^(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)$"
)


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str, *, label: str = "version") -> "SemVer":
        match = _STABLE_SEMVER.fullmatch(value)
        if match is None:
            raise VersionCtlError(
                ExitCode.INVALID_VERSION,
                f"{label} must be stable SemVer in MAJOR.MINOR.PATCH form: {value!r}",
                details={"label": label, "value": value},
            )
        return cls(*(int(match.group(name)) for name in ("major", "minor", "patch")))

    def bump(self, impact: str) -> "SemVer":
        if impact == "major":
            return SemVer(self.major + 1, 0, 0)
        if impact == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if impact == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise VersionCtlError(
            ExitCode.INVALID_ARGUMENT,
            f"unknown impact: {impact}",
            details={"impact": impact},
        )

    def transition_impact(self, target: "SemVer") -> str | None:
        if target == self.bump("major"):
            return "major"
        if target == self.bump("minor"):
            return "minor"
        if target == self.bump("patch"):
            return "patch"
        return None

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
