# agentsmd Repository Override

Before work in this repository, read `AGENTS.md` and apply it as the global
baseline.

- This repository's root `AGENTS.md` is the version-controlled source of the
  global agent contract.
- The project `Recent Changes` rule does not apply to this canonical global
  instruction file. Keep release history out of `AGENTS.md`.
- Record released outcomes in `CHANGELOG.md`. Use `STATUS.md` only for the
  current snapshot defined by `AGENTS.md`.
- For AgentsMD releases, agent-owned proof is deterministic repository,
  package, distribution, and installation verification. User-owned behavioral
  Live Verification occurs after release through normal work in real projects.
  Synthetic model-run scenarios and disposable behavioral fixtures are not
  release gates unless the user explicitly requests them. Report behavioral
  verification as pending until user evidence exists, then turn observed
  failures into GitHub Issues and deterministic regressions where practical.
