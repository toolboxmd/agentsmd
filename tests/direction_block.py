"""Parse the Project Direction hook block back into one payload."""

from __future__ import annotations

import json

BLOCK_START = "<<<AGENTSMD_PROJECT_DIRECTION_V1>>>"
BLOCK_END = "<<<END_AGENTSMD_PROJECT_DIRECTION_V1>>>"


def block_end(nonce: str) -> str:
    return f"<<<END_AGENTSMD_PROJECT_DIRECTION_V1 {nonce}>>>"


def parse_block(context: str) -> dict:
    """Return the JSON header with each section restored as a content field."""
    if not context.startswith(BLOCK_START + "\n"):
        raise ValueError("missing block start")
    header_line, _, rest = context[len(BLOCK_START) + 1 :].partition("\n")
    payload = json.loads(header_line)
    nonce = payload.pop("sections", None)
    # With sections, only the end marker carrying the nonce closes the block.
    end = BLOCK_END if nonce is None else block_end(nonce)
    if rest == end:
        rest = ""
    elif rest.endswith("\n" + end):
        rest = rest[: -(len(end) + 1)]
    else:
        raise ValueError("missing block end")
    if nonce is None:
        if rest:
            raise ValueError("sections without a nonce")
        return payload
    prefix = f"<<<AGENTSMD_SECTION {nonce} "
    sections: dict[str, str] = {}
    name = None
    lines: list[str] = []
    for line in rest.split("\n"):
        if line.startswith(prefix) and line.endswith(">>>"):
            if name is not None:
                sections[name] = "\n".join(lines)
            name, lines = line[len(prefix) : -3], []
        elif name is None:
            raise ValueError("text before the first section")
        else:
            lines.append(line)
    if name is not None:
        sections[name] = "\n".join(lines)
    for item in payload.get("files", []):
        if item["name"] in sections:
            item["content"] = sections.pop(item["name"])
    if "PREFERENCES.md" in sections:
        payload["preferences"]["content"] = sections.pop("PREFERENCES.md")
    if sections:
        raise ValueError(f"unexpected sections {sorted(sections)}")
    return payload
