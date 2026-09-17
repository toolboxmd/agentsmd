# Skill mechanics

Use the writing guidance in [SKILL.md](SKILL.md); this reference covers packaging
and invocation choices.

## Invocation

Choose model invocation when the agent needs to discover the skill autonomously.
Write its description for selection: what it does and when it applies. Keep the
description economical because discovery exposes it before the body is loaded.
Omit `disable-model-invocation` for this mode.

Use `disable-model-invocation: true` for human-controlled workflows. Write a short
human-facing description and match the target host's invocation metadata to that
choice. User control is valuable where judgment belongs to the user; avoid making
them remember routine routing the agent can perform.

## Shared references and separate skills

Put shared guidance in one referenced file when consumers need the same rules.
A reference need not become another discoverable skill. Create a separate skill
when it has a distinct useful invocation trigger or must be selected independently.

A router earns its place when selecting among existing workflows is itself a
recurring problem. It should identify the right workflow without duplicating it.
Preserve explicit human-selection boundaries; naming another workflow does not
authorize invoking it. Check the target host's supported invocation behavior
rather than assuming every host loads or composes skills identically.
