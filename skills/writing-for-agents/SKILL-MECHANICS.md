# Skill mechanics

Use the writing guidance in [SKILL.md](SKILL.md); this reference covers packaging
and invocation choices.

## Invocation

AgentsMD Skills are model-invocable. Write the description for autonomous
selection. State what the Skill does and when it applies. Keep the description
economical because discovery exposes it before the body loads. Do not set
`disable-model-invocation`. Put human control in approval gates inside the body.
Show the draft. Get explicit approval before publication or mutation. Match host
metadata to that policy. Set Codex `allow_implicit_invocation: true`.

## Shared references and separate skills

Put shared guidance in one referenced file when consumers need the same rules.
A reference need not become another discoverable skill. Create a separate skill
when it has a distinct useful invocation trigger or must be selected independently.

A router earns its place when selecting among existing workflows is itself a
recurring problem. It should identify the right workflow without duplicating it.
Preserve approval gates; naming another workflow does not run it. Check
the target host's supported invocation behavior rather than assuming
every host loads or composes skills identically.
