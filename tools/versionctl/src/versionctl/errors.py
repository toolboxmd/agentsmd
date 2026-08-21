from __future__ import annotations

from enum import IntEnum
from typing import Any


class ExitCode(IntEnum):
    OK = 0
    NOT_GIT_REPOSITORY = 10
    INVALID_POLICY = 11
    MISSING_VERSION = 12
    INVALID_VERSION = 13
    NO_CHANGES = 14
    STALE_MIRROR = 15
    BUMP_REQUIRED = 16
    CHANGELOG_INVALID = 17
    VERSION_CONFLICT = 18
    TAG_CONFLICT = 19
    DIRTY_TREE = 20
    AUTHORIZATION_REQUIRED = 21
    INVALID_ARGUMENT = 22
    IO_ERROR = 23
    GIT_ERROR = 24


class VersionCtlError(Exception):
    def __init__(
        self,
        code: ExitCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.name,
            "exitCode": int(self.code),
            "message": self.message,
            "details": self.details,
        }
