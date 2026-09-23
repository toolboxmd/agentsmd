# Skill mechanics

Use the writing guidance in [common procedure](index.md); this reference covers packaging
and invocation choices.

## General Skill authoring

A discoverable Skill uses `SKILL.md` with valid YAML frontmatter. Give it a stable
name and an economical description stating what it does and when it applies,
including exclusions that prevent plausible wrong selections. Keep procedural
detail in the body and conditionally linked references.

Validate required frontmatter fields, value types, host-supported invocation
settings, loading triggers, and relative references against the target host
and package contract. Check the installed or copied layout as well as source;
a description or fixture alone does not prove correct model selection.

## AgentsMD packaging and progressive disclosure

The following single-entry policy applies to the AgentsMD package. Other
projects may expose their own discoverable Skills under their host contracts.

AgentsMD exposes only `operations`. Its concise description supports automatic
selection. Keep Codex `allow_implicit_invocation: true`; do not hide procedures
with explicit-only flags and then bypass their invocation policy.

Add a method as an ordinary conditional reference within Operations, normally
`workflows/<name>/index.md`. Do not name it `SKILL.md`: recursive hosts would
advertise it. Give its caller a concrete loading trigger. Preserve human gates
inside the owning procedure. Selection grants no new authority.

Keep shared rules at one owner. Link from the actual file and test reference
closure after copying the operations directory alone. Executables and global
instructions remain supported installation components; copied role kits must
resolve those through the canonical source instead of inventing relative roots.

A separate discoverable skill requires a concrete capability that cannot work
through the existing entry point. Check current host behavior before relying on
an invocation flag. A larger catalogue is not evidence of better selection.
