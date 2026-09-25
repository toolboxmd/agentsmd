# AgentsMD Glossary

**AgentsMD**:
The ToolboxMD project that owns the portable agent operating contract and its
installable workflow plugin.
_Avoid_: Matt Skill pack, global prompt repository

**Model Router**:
The separate ToolboxMD router, labelled Prism in the interface, that accepts
delegated work and selects its models, effort, and roles. AgentsMD owns
workflow, authority, proof, and review.
_Avoid_: AgentsMD model policy, routing matrix

**Planner**:
The top-level agent the user works with. It owns judgment, specs, and
acceptance, and delegates the rest.
_Avoid_: main agent

**Routing tool**:
The host-provided means of delegating work with routed model and role
selection, such as Model Router.
_Avoid_: model-routing Skill

**Agent Observer**:
The separate ToolboxMD plugin that connects native agent usage to explicitly
owned tasks and outcome evidence. AgentsMD retains workflow, authority and proof.
_Avoid_: AgentsMD accounting engine, Model Router billing

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

**Delivery Authority**:
Authorization to deliver an identified outcome or scope in named Issues and
repositories through granted operations and targets. It carries through routine
repairs; explicit candidate limits still apply.
_Avoid_: standing authority, repository-wide permission

**Delivery System**:
The portable AgentsMD contract that carries qualified work through separate
implementation, Proof, review, merge, release, distribution or deployment,
installation or activation, loading, Live Verification, and website-current
states.
_Avoid_: release pipeline, orchestration engine

**Delivery Profile**:
The optional root `.toolboxmd/delivery.json` containing only a Project's real
delivery-command, artifact-build, and website-mapping differences from the
shared Delivery System.
_Avoid_: Project Record, release policy, delivery state

**Merge Unit**:
One independently reviewable and mergeable change, or one dependent stack
that must ship as a single release identity and SemVer transition.
_Avoid_: commit, implementation slice

**Final approval PR**:
The cumulative outcome PR merged under human approval for the task and intended base.
_Avoid_: component PR, task integration branch

**Component PR**:
An internally reviewed change feeding the integration branch and final approval PR.
_Avoid_: final approval PR, independent release

**Implementation Slice**:
One authored part of a Merge Unit with an exclusive writer and an independent
exact-SHA review obligation.
_Avoid_: generated promotion pull request, Merge Unit

**Delivery Finalization**:
The post-review lifecycle step for a verified terminal outcome that closes
tracker state truthfully, checks every temporary checkout for removal, and
retires eligible task-owned transient resources. It preserves required durable
information and justified current needs, records exact retained exceptions,
and distinguishes unresolved obstacles from completed finalization.
_Avoid_: cleanup sweep, Repository Reconciliation

**Temporary checkout**:
A worktree or equivalent task workspace whose lifecycle ends with verified
removal or an exact retained exception during Delivery Finalization. Required
persistent local state has a stable home outside it.
_Avoid_: archive, permanent task workspace

**Fresh context**:
A child start seeded with the minimal durable packet and no prior transcript.
Do not fork the parent transcript. The default is a nested child in the
coordinator session. A separate host task is the exception when the slice must
outlive the parent, a human must open it independently, or the writer must
continue after the parent stops.
_Avoid_: new sidebar session, new chat as the default, forked parent context

**Repository Reconciliation**:
A bounded repair path triggered when repository orientation detects drift. It
refreshes exact evidence, resolves only approved legacy changes, and preserves
durable, unsafe, or ambiguous state with an explicit next action.
_Avoid_: cleanup sweep, recurring repository audit

**Review-ready pull request stack**:
A dependency-ordered set of pull request layers whose exact heads, bases,
proof, review, revalidation, retarget, and merge states are recorded
independently. It begins only from a complete exact-SHA predecessor candidate.
_Avoid_: dependent branch chain, pull request queue

**Parent Spec only**:
An explicit request that runs `to-spec` through verified parent Issue
publication and opts out before ticket decomposition or implementation.
_Avoid_: parent-Spec-only, planning-only

**Skill**:
An Agent Skills-compatible package discovered through `SKILL.md`, with a named
invocation boundary and metadata describing when to load its body.
_Avoid_: command, prompt file

**Skill Catalogue**:
The authoritative AgentsMD inventory of active Skills, retained procedures,
and deferred, retired or upstream-reference material, including provenance.
_Avoid_: Product Registry, Plugin Registry

**Active Skill**:
A Skill that AgentsMD owns and exposes through active plugin discovery.
_Avoid_: installed Skill, referenced Skill

**Adapted Skill**:
A Skill or retained procedure whose current AgentsMD behavior derives from an external Skill
and records that origin and local change.
_Avoid_: copied Skill, Matt Skill

**Native Skill**:
A Skill or retained procedure created and maintained inside AgentsMD.
_Avoid_: adapted Skill

**ToolboxMD-native Skill**:
A Skill or retained procedure created in another ToolboxMD project and intentionally bundled
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

**Scoped proof**:
Complete required coverage composed from authenticated unaffected baseline
results and current affected and artifact checks under a trusted Project policy.
_Avoid_: skipped proof, fast check, complete test rerun

**Complete-proof baseline**:
An exact commit with direct successful proof for every declared check, used as
the cumulative comparison anchor for scoped proof.
_Avoid_: previous scoped candidate, latest commit

**Operations module**:
The existing name for an Operations-owned Reference containing procedure detail.
It is not a separate package or discovery type.
_Avoid_: custom loader, orchestration service

**Elon method**:
The AgentsMD method combining first principles, idiot index, current constraint,
and the ordered Algorithm to choose means within confirmed direction and authority.

**Algorithm**:
The fixed sequence of questioning requirements, deleting unnecessary work,
simplifying survivors, accelerating, and automating last.

**Current constraint**:
The evidence-supported limiter whose relief enables the next useful progress
toward the authorized outcome under confirmed Project Direction.
_Avoid_: busiest component, permanent bottleneck

**Idiot index**:
The ratio of quoted finished cost to constituent cost for comparable units and
scope, used as a diagnostic hypothesis about possible overhead.
_Avoid_: guaranteed savings, delivery estimate

**Canonical instruction source**:
The stable `AGENTS.md` shared through each configured host's native global link.
_Avoid_: plugin-cache instructions, project instructions

**Private preferences**:
Personal defaults in `PREFERENCES.md` beside the canonical instruction source,
subject to explicit task instructions, required project constraints and authority.
_Avoid_: shared policy, project preferences

**Procedure**:
Instructions for a bounded action, selected through Operations and stored in
ordinary linked files without a separate host Skill discovery entry.
_Avoid_: hidden Skill, mode command

**Reference**:
A linked supporting document containing detail, examples, or constraints loaded
when its caller's stated condition applies. It has no separate discovery entry.
_Avoid_: hidden Skill, package type

**Workflow**:
An ordered sequence of actions toward an outcome, which may use several
Procedures and References; it is not another registration type.
_Avoid_: Skill, package type

**Playbook**:
pstack's upstream term for an operating guide. AgentsMD retains its useful
content in Procedures and References, without a separate playbook package type.
_Avoid_: fourth package kind

**Task evidence folder**:
The single lazily created home for retained task-specific findings and experiments,
linked from the owning Issue; it is not an active tracker or a second knowledge owner.
_Avoid_: reflection diary, local backlog
