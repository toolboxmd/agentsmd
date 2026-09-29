# Trigger table (Issue #164, step 1)

Source: `skills/operations/SKILL.md` at `origin/main` `36d60b2`. Every routing
row and every conditional reference its procedure points to. Paths are relative
to `skills/operations/`. The exact regexes live in `measure.py` (`ROWS` and the
patterns above it); the `Row` column gives its row id.

**Counts as firing** for every row: a read of the required file at or before the
step of the first triggering call. A read is a Read/`read_file`/`read` tool call
on the path, or a shell command that names the path together with a reader
(`cat`, `sed`, `head`, `tail`, `nl`, `less`, `awk`, `git show`). Generic tails
such as `references/delivery.md` also need `operations` in the same call. A
`workflows/<name>/index.md` also fires through a Skill tool call, a Claude slash
command, or a Codex `[$agentsmd:<name>](...)` mention naming `<name>`, and
through its pre-2026-09-23 standalone path `skills/<name>/SKILL.md` (#120 moved
workflows under `operations/`). The entry point fires through a Skill call
naming `operations` or a read of `operations/SKILL.md`.

**Edit** means an Edit/Write/MultiEdit/`edit`/`write`/`search_replace`/
`apply_patch` path, or a shell `cat >`/`tee` target. Writes under `/tmp`,
`~/.claude/projects|plans|packets` and scratchpads are not work edits.

## Routing rows

| Routing row | Procedure file | Observable trigger event | Row |
| --- | --- | --- | --- |
| Entry (task start, action changes) | `SKILL.md` | First work edit, `gh issue create`, `gh pr create/ready`, or `git commit` in the session | `entry` |
| Elon method preamble ("material work") | `workflows/elon-method/index.md` (or `references/algorithm.md`) | `gh issue create` (the #138 method) | `elon` |
| Initialize or reload Project Direction | `workflows/project-direction/references/context.md` | **Not measured.** Delivered by the SessionStart/PreToolUse hook on Claude, Codex and Grok, not by a read; the only row enforced by mechanism | - |
| Repair or change Project Direction | `workflows/project-direction/index.md` | Edit of `VISION.md`, `MISSION.md` or `OBJECTIVE.md` outside `templates/` | `pd` |
| Research | `workflows/research/index.md` | **Not observable.** Any read, search or web fetch can be research; nothing in a call separates it from orientation | - |
| Software design | `workflows/software-design/index.md` | **Not observable.** "Choose interfaces, state, architecture" is a judgment made before any edit; the edit looks the same as a microfix | - |
| Prototype | `workflows/prototype/index.md` | **Not observable.** A disposable experiment has no distinguishing path or command | - |
| Diagnosis | `workflows/diagnosis/index.md` | **Not observable** directly. A failing test run followed by edits is a candidate proxy but also matches ordinary TDD; not measured | - |
| Grilling / grill with docs | `workflows/grilling/index.md`, `workflows/grill-with-docs/index.md` | Human prompt (1200 chars or less) matching `grill`. "Unresolved human-owned choices" is not observable | `grilling` |
| Domain modeling | `workflows/domain-modeling/index.md` | Edit of `GLOSSARY.md`, `GLOSSARY-MAP.md`, `CONTEXT.md`, `CONTEXT-MAP.md` or `docs/adr/*.md` | `domain` |
| Wayfinder | `workflows/wayfinder/index.md` | Human prompt matching `wayfind`. "Dependent unresolved decisions" is not observable | `wayfinder` |
| Specify / tickets | `workflows/to-spec/index.md`, `workflows/to-tickets/index.md` | Human prompt matching `to-spec`, `to-tickets`, `specification`, `PRD`, `write a/the spec` | `spec` |
| Implementation | `references/implementation.md` | First work edit | `impl` |
| Orchestration | `references/orchestration.md` | Agent/Task tool, `spawn_thread`, `prism_submit`, Codex `spawn_agent`, OpenCode `task`, or a shell `opencode run`, `codex exec`, `claude -p` | `orch` |
| Verification (claim readiness) | `references/verification.md` | `gh pr create` or `gh pr ready` | `verif` |
| Verification -> code review | `workflows/code-review/index.md` | Prompt asking for a code review (`code review`, `review this/the PR/diff/branch/code`), including long dispatched reviewer packets | `review` |
| Project verification | `workflows/project-verification/index.md` | Edit of `verif*/SKILL.md`, `VERIFY.md`/`VERIFYING.md` or `docs/verification/`. Approximate: the procedure names no fixed output path | `proj-verif` |
| Artifact placement | `references/artifacts.md` | New-file Write under `docs/work/`, `research/`, `reviews/`, `prototype(s)/`, `reflection(s)/` | `artifacts` |
| Writing for agents | `workflows/writing-for-agents/index.md` | Edit of `SKILL.md`, `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `GEMINI.md`, `skills/**/*.md`, `.claude/agents|commands|packets/*.md` (memory files excluded) | `wfa` |
| Technical writing | `workflows/technical-writing/index.md` | Edit of `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, or `docs/**/*.md` outside `docs/work/` and `docs/adr/`, not an agent-instruction path | `tw` |
| Reflection | `workflows/reflection/index.md` | Human prompt matching `reflect`, `retro(spective)`, `lessons learned`, `post-mortem`; **proxy:** a write to Claude memory (`~/.claude/projects/*/memory/`), which usually follows a correction | `reflection` |
| Version control | `workflows/version-control/index.md` | `git commit` (any `git ... commit`) | `vc` |
| Delivery profile | `workflows/delivery-profile/index.md` | Any read, command or edit naming `.toolboxmd/delivery.json` | `delivery-profile` |
| Delivery | `references/delivery.md` | `gh pr create`, `gh pr merge`, `gh release create`, `git tag -a`, `git push --tags`, `npm publish` | `delivery` |
| Finalization | `references/finalization.md` | `gh issue close`, `git worktree remove`, `git branch -d/-D` | `final` |
| Repository setup | `references/repository-setup.md` | `gh repo edit`, `gh label create`, `gh ruleset`, or a mutating `gh api` on rulesets, branch protection, action permissions or labels | `repo-setup` |
| Reconciliation | `references/reconciliation.md` | **Not observable.** "Orientation detects drift" is a judgment; cleanup commands it would approve also appear in ordinary finalization | - |
| Use Grok | `workflows/use-grok/index.md` | Shell `grok -p/--prompt/--print/exec/run` | `grok` |

## Conditional references inside those procedures

| From | Reference | Observable trigger event | Row |
| --- | --- | --- | --- |
| Elon method | `references/algorithm.md` | `gh issue create` (material requirement) | `elon>algorithm` |
| Elon method | `first-principles.md`, `idiot-index.md`, `current-constraint.md` | **Not observable.** Analogy, cost claims, acceleration are judgments inside reasoning | - |
| Project Direction | `references/file-contracts.md` | Same as `pd` | `pd>contracts` |
| Project Direction | `templates/*.md` | **Not observable** separately from `pd` ("only when drafting") | - |
| Context | `project-direction/index.md` on missing/stale direction | **Not measured.** The hook's `status` field would show it; not parsed here | - |
| Research | `mechanics.md`, `history.md`, `recall.md`, `explanation.md` | **Not observable** (question type) | - |
| Software design | `compare-designs.md`, `state-and-boundaries.md`, `typescript.md`, `change-existing-systems.md` | **Not observable** (design question type) | - |
| Prototype | `LOGIC.md`, `UI.md`, `EMPIRICAL.md` | **Not observable** (question type) | - |
| Diagnosis | `reproduction-and-cause.md`, `runtime-and-traces.md`, `performance.md` | **Not observable** (symptom type) | - |
| Domain modeling | `GLOSSARY-FORMAT.md` | Edit of a glossary/context file | `domain>glossary` |
| Domain modeling | `ADR-FORMAT.md` | Edit of `docs/adr/*.md` | `domain>adr` |
| To-tickets / to-spec | `to-tickets/references/ticket-decomposition.md` | Second `gh issue create` in one session (proxy for decomposition) | `tickets>decomp` |
| Implementation | `references/verification.md` ("before proof/review") | First test command (`pytest`, `unittest`, `npm/pnpm/bun/yarn test`, `vitest`, `jest`, `go test`, `cargo test`, `make test/check`, `swift test`) after a work edit | `impl>verif` |
| Implementation / Verification | `references/test-design.md` | Edit of a test file (`tests/`, `__tests__/`, `test_*.py`, `*_test.*`, `*.test.*`, `*.spec.*`) | `test-design` |
| Orchestration | `references/bounded-delegation.md` ("before parallel work") | Two or more spawns in one assistant step | `orch>bounded` |
| Orchestration | `references/external-handoffs.md` | **Not observable** ("authorized external intake or automation adapter") | - |
| Code review | `references/review-method.md` | Same as `review` | `review>method` |
| Code review | `impact-analysis.md`, `structure-and-constraints.md` | **Not observable** ("risky boundary, API change, safety claim") | - |
| Verification | `visual-parity.md`, `evaluation.md`, `scoped-proof.md` | **Not observable** (contract type); scoped proof is also named by delivery profile and version control | - |
| Project verification | `verification-contract.md`, `create-and-maintain.md`, `observations.md` | Same trigger as `proj-verif`; not measured separately (one session) | - |
| Writing for agents | `SKILL-MECHANICS.md` ("before choosing frontmatter or invocation") | Edit of any `SKILL.md` | `wfa>mechanics` |
| Writing for agents | `technical-writing/references/prose.md` ("substantive prose editing") | Same as `wfa` | `wfa>prose` |
| Technical writing | `references/prose.md` ("revising unclear or padded text") | Same as `tw` | `tw>prose` |
| Reflection | `references/learning-and-placement.md` | Same as `reflection`; not measured separately | - |
| Version control | `references/bump-rules.md` | Edit of a `VERSION` file or `versionctl bump` | `vc>bump` |
| Version control | `references/project-policy.md` | **Not observable** separately (schema, adoption, hooks) | - |
| Delivery | `delivery-profile/index.md` | Same as `delivery-profile` | - |
| Delivery | `references/finalization.md` ("at terminal disposition") | `gh pr merge` | `delivery>final` |
| Finalization | `references/reconciliation.md` | **Not observable** ("unknown residue") | - |
| Use Grok | `references/grok-cli.md` | **Not observable** ("non-default flags"); flag parsing possible later | - |
| Research / Wayfinder / Grill with docs | links to other routing rows | Covered by those rows | - |
