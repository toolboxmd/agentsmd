# Semantic impact rules

The public contract is whatever consumers rely on. It can be executable code,
documentation, agent instructions, prompts, configuration, schemas, tests used
as examples, or a published dataset. Classify the completed outcome, not the
number of changed files or commits.

## Major

Use `major` when an existing consumer must change to keep working or receives
meaningfully incompatible behavior.

- Remove or rename a public command, option, API, schema field, or skill input.
- Change a default in a way that invalidates existing workflows.
- Replace an agent rule or prompt contract with incompatible semantics.
- Change data meaning while retaining field names or identifiers.
- Remove support that the repository previously promised.

For a `0.y.z` repository, schema 1 still uses a literal major transition for an
incompatible contract. It does not reinterpret breaking changes as minor.

## Minor

Use `minor` for a backward-compatible capability.

- Add a command, option, API, workflow, skill, prompt behavior, or schema field
  that leaves existing consumers working.
- Add a new supported repository or artifact type.
- Add an opt-in behavior with the old behavior preserved by default.
- Substantially extend documented, user-consumable functionality.

## Patch

Use `patch` for every other completed tracked deliverable.

- Fix incorrect behavior without breaking the contract.
- Correct documentation, examples, agent wording, or metadata.
- Improve tests, internal implementation, performance, or maintainability
  without adding a consumer-facing capability.
- Update configuration, data, or research while preserving its contract.

Patch is the floor for a completed tracked change. A docs-only repository still
has consumers, so completed documentation changes are versioned.

## Exemptions and aggregation

- Strictly read-only work has no bump.
- An explicitly incomplete `wip:` checkpoint has no bump.
- Intermediate technical commits may be WIP, but the completed deliverable
  commit includes one version transition.
- When several changes are delivered together, select the highest impact.
- Do not bump separately for the generated `VERSION`, mirror, or changelog
  edits. They belong to the same atomic deliverable.
