# AgentsMD Glossary

**AgentsMD**:
The ToolboxMD project that owns the portable agent operating contract and its
installable workflow plugin.
_Avoid_: Matt Skill pack, global prompt repository

**Project Direction**:
The coherent repository-root triad of `VISION.md`, `MISSION.md`, and
`OBJECTIVE.md` that owns the project's confirmed long-range destination,
present purpose, and single current milestone-level outcome.
_Avoid_: North Star, strategy bundle, project brief

**Potentially stale Project Direction**:
A complete checkout-local Project Direction whose known upstream is ahead or
diverged and changes at least one direction file relative to `HEAD`. The loader
reports `potentially_stale`; the triad remains checkout-scoped evidence until
the intended base is reconciled and all three files are reread.
_Avoid_: missing Project Direction, invalid Project Direction

**Vision**:
The grand and visionary aspirational long-range destination the project wants
to make real, not the current work. It expands ambition and may be directional
rather than measurable. It is recorded in root `VISION.md`.
_Avoid_: long-term Objective, roadmap

**Mission**:
The strategic present-tense reason the project exists, the problem it solves,
and its approach to moving toward the Vision, grounded in what the project does
now. It is recorded in root `MISSION.md`.
_Avoid_: Vision, Objective, company slogan

**Objective**:
The single current milestone-level outcome the project must accomplish now,
with a recognizable completion condition. It is narrower than the Mission but
broader than an individual request, task, Issue, commit, or PR. It normally
organizes and survives several contributing Issues and is recorded in root
`OBJECTIVE.md`.
_Avoid_: Current Goal, task outcome, task list, backlog

**Parent Spec only**:
An explicit request that runs `to-spec` through verified parent Issue
publication and opts out before ticket decomposition or implementation.
_Avoid_: parent-Spec-only, planning-only

**Skill**:
An Agent Skills-compatible package that gives an agent a reusable procedure or
reference behind a named invocation boundary.
_Avoid_: command, prompt file

**Skill Catalogue**:
The authoritative AgentsMD inventory of active, deferred, retired, and
upstream-reference Skills, including ownership and provenance.
_Avoid_: Product Registry, Plugin Registry

**Active Skill**:
A Skill that AgentsMD owns and exposes through active plugin discovery.
_Avoid_: installed Skill, referenced Skill

**Adapted Skill**:
An Active Skill whose current AgentsMD behavior derives from an external Skill
and records that origin and local change.
_Avoid_: copied Skill, Matt Skill

**Native Skill**:
An Active Skill created and maintained inside AgentsMD.
_Avoid_: adapted Skill

**ToolboxMD-native Skill**:
An Active Skill created in another ToolboxMD project and intentionally bundled
by AgentsMD with its original lineage intact.
_Avoid_: third-party Skill, AgentsMD-native Skill

**Upstream Reference**:
An external Skill recorded for later evaluation but absent from active
AgentsMD discovery.
_Avoid_: supported Skill, bundled Skill

**Deferred Skill**:
A Skill kept inactive until its recorded reconsideration trigger occurs.
_Avoid_: retired Skill

**Retired Skill**:
A previously considered Skill whose behavior is intentionally absent from
active AgentsMD discovery.
_Avoid_: deleted Skill, deferred Skill

**Product Registry**:
The `toolbox.md` discovery surface for ToolboxMD products and their roles.
_Avoid_: Skill Catalogue, Plugin Registry

**Plugin Registry**:
The `toolboxmd/marketplace` distribution surface for installable ToolboxMD
plugins.
_Avoid_: Product Registry, Skill Catalogue

**ContextMD**:
The future ToolboxMD Agent Knowledge and Learning System.
_Avoid_: glossary, context file

**World Model**:
ContextMD's structured representation of entities, relationships,
observations, provenance, and learned experience.
_Avoid_: glossary, project documentation

**Persistent Host Automation**:
Agent-created or agent-maintained host services, scheduled jobs, checks, and
recovery automation that operate beyond the current task. It excludes
project-local build tooling and one-off diagnostics.
_Avoid_: machine runbook, persistent script
