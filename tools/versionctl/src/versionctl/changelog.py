from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .errors import ExitCode, VersionCtlError


_ENTRY = re.compile(r"^## \[(?P<version>[^]]+)\] - (?P<date>\d{4}-\d{2}-\d{2})$", re.MULTILINE)
_CATEGORY = {"major": "Changed", "minor": "Added", "patch": "Changed", "adopt": "Added"}


def entry(text: str, version: str) -> tuple[str, str] | None:
    matches = list(_ENTRY.finditer(text))
    for index, match in enumerate(matches):
        if match.group("version") != version:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        return match.group("date"), text[match.start() : end].rstrip() + "\n"
    return None


def read_entry(path: Path, version: str) -> tuple[str, str] | None:
    try:
        return entry(path.read_text(encoding="utf-8"), version)
    except FileNotFoundError:
        return None


def update(
    text: str,
    *,
    version: str,
    reason: str,
    impact: str,
    replace_version: str | None = None,
) -> str:
    reason = " ".join(reason.split()).strip()
    if not reason:
        raise VersionCtlError(ExitCode.INVALID_ARGUMENT, "reason must not be empty")
    today = date.today().isoformat()
    category = _CATEGORY[impact]
    bullet = f"- {reason}"

    if replace_version and replace_version != version:
        old = entry(text, replace_version)
        if old is None:
            raise VersionCtlError(
                ExitCode.CHANGELOG_INVALID,
                f"pending changelog entry for {replace_version} is missing",
            )
        text = re.sub(
            rf"^## \[{re.escape(replace_version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$",
            f"## [{version}] - {today}",
            text,
            count=1,
            flags=re.MULTILINE,
        )

    existing = entry(text, version)
    if existing is not None:
        if bullet in existing[1]:
            return text
        heading = f"## [{version}] - {existing[0]}"
        section_start = text.index(heading)
        next_match = _ENTRY.search(text, section_start + len(heading))
        section_end = next_match.start() if next_match else len(text)
        section = text[section_start:section_end].rstrip()
        category_heading = f"### {category}"
        if category_heading in section:
            insert_at = section.index(category_heading) + len(category_heading)
            section = section[:insert_at] + f"\n\n{bullet}" + section[insert_at:]
        else:
            section += f"\n\n{category_heading}\n\n{bullet}"
        suffix = "\n\n" if next_match else "\n"
        return text[:section_start] + section + suffix + text[section_end:].lstrip("\n")

    block = f"## [{version}] - {today}\n\n### {category}\n\n{bullet}\n"
    first = _ENTRY.search(text)
    if first:
        return text[: first.start()].rstrip() + "\n\n" + block + "\n" + text[first.start() :].lstrip()
    return text.rstrip() + "\n\n" + block


def require_entry(path: Path, version: str) -> tuple[str, str]:
    found = read_entry(path, version)
    if found is None:
        raise VersionCtlError(
            ExitCode.CHANGELOG_INVALID,
            f"CHANGELOG.md has no entry for {version}",
            details={"version": version, "path": str(path)},
        )
    return found
