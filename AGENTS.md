# agentsmd Repository Instructions

Before work in this repository, read `global/AGENTS.md` and apply it as the global
baseline.

- The global contract lives in `global/AGENTS.md` and is edited there.
- Record released outcomes in `CHANGELOG.md`. Use `STATUS.md` only for the
  current snapshot defined by `global/AGENTS.md`.
- Final PR merges stay with the user. After the user merges, Delivery
  Authority for this repository includes, without another prompt: the
  resulting GitHub release through the release workflow, and installing that
  released version on the maintainer's local hosts (every agent harness that
  carries AgentsMD) with post-install verification. Third-party marketplace
  submission and publication still need explicit authority.
- For AgentsMD releases, agent-owned proof is deterministic repository,
  package, distribution, and installation verification. User-owned behavioral
  Live Verification occurs after release through normal work in real projects.
  Synthetic model-run scenarios and disposable behavioral fixtures are not
  release gates unless the user explicitly requests them. Report behavioral
  verification as pending until user evidence exists, then turn observed
  failures into GitHub Issues and deterministic regressions where practical.
