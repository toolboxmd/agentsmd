"""Parse the Project Direction hook block back into one payload."""

from __future__ import annotations

import json

BLOCK_START = "<<<AGENTSMD_PROJECT_DIRECTION_V1>>>"
BLOCK_END = "<<<END_AGENTSMD_PROJECT_DIRECTION_V1>>>"


def parse_block(context: str) -> dict:
    """Return the JSON header with each section restored as a content field."""
    if not context.startswith(BLOCK_START + "\n") or not context.endswith(
        "\n" + BLOCK_END
    ):
        raise ValueError("missing block delimiters")
    body = context[len(BLOCK_START) + 1 : -(len(BLOCK_END) + 1)]
    header_line, _, rest = body.partition("\n")
    payload = json.loads(header_line)
    nonce = payload.pop("sections", None)
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
