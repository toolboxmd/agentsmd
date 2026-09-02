# Task: Portable Three-Host Release

Prepare the next backward-compatible installable release of use-grok. The
current release is `0.1.0`. Adding Claude Code and Grok Build as supported
plugin hosts is a minor capability.

Required behavior:

- add valid Claude Code and Grok Build plugin manifests beside the existing
  Codex manifest;
- keep the canonical identity `use-grok`, repository
  `https://github.com/toolboxmd/use-grok`, Apache-2.0 license, description, and
  author name consistent across all three manifests;
- keep Codex-only `skills`, `interface`, `homepage`, and `keywords` metadata in
  the Codex manifest only;
- make all manifest versions and a root `VERSION` file agree on `0.2.0`;
- update README layout and installation instructions for Codex, Grok Build,
  and Claude Code while preserving the existing workflow description;
- add a changelog entry dated `2026-08-31` for this release; and
- strengthen contract tests so they fail when any host manifest name or
  version drifts, while all existing skill and Codex-specific contracts remain
  covered.

Allowed paths:

- `.claude-plugin/plugin.json`
- `.codex-plugin/plugin.json`
- `.grok-plugin/plugin.json`
- `CHANGELOG.md`
- `README.md`
- `VERSION`
- `tests/use-grok.test.py`

The controller-owned public and hidden verifiers are outside the candidate
workspace. Candidate-owned tests are supplemental evidence only.

Do not change the skill, CLI reference, license, wiki, or public test runner.
Do not install anything, stage, commit, use the network, or inspect paths
outside the exported workspace.

