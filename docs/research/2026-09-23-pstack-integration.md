# Distilling pstack into AgentsMD

## Recommendation and scope

Integrate pstack's engineering methods into AgentsMD's existing operating contract. Add six capabilities: `software-design`, `diagnosis`, `code-review`, `project-verification`, `reflection`, and `technical-writing`. Expand `research` to cover current mechanics, historical rationale, scoped recall, and teaching. Strengthen operations with practical engineering, proof, refactoring, coordination, and recovery procedures. Preserve all sixteen existing public skills and their intentional invocation and approval contracts.

The opportunity is substantive. AgentsMD already defines strong authority, ownership, Project Direction, versioning, and delivery boundaries. Its technical procedures are comparatively thin. pstack supplies ways to choose representations, compare interfaces, investigate causes, measure performance, test consequential assumptions, maintain executable product knowledge, and learn from failed workflows. These methods can improve existing capabilities even where their governing principles already overlap.

This report records the source analysis and adopted integration design. Execution proof and delivery state belong to [Issue #119](https://github.com/toolboxmd/agentsmd/issues/119); this document does not claim behavioral verification. The source is Lauren Tan's pstack `0.15.3`, pinned to `cursor/plugins` commit `b42effe0aa50f59c693d7e2924714e015e00bf7c`. The comparison baseline is AgentsMD commit `c71b43a5d6b28668ebe1301cce99bc5433c8c704`. The review covered the upstream Markdown and scripts, including all 50 `SKILL.md` files and 23 operating playbooks. Binary assets were inventoried rather than behaviorally inspected. No live integration, comparative model evaluation, or product verification is claimed.

pstack is [MIT-licensed with Lauren Tan's copyright notice][license]. Adaptations retain that notice in `LICENSES/pstack-MIT.txt` and record pinned source lineage in `provenance/pstack.lock.json`. Existing skills adapted from another source retain their original lineage alongside the pstack contribution. Destinations below identify capability owners. The pinned inventory and source-to-file map are in [the provenance lock](../../provenance/pstack.lock.json).

## The engineering method beneath the wrappers

### Start from the actual consumer and the actual system

pstack connects system understanding to design. Its `how` procedure traces a real trigger through calls, transformations, state transitions, boundaries, and observable results. It does not stop at a file map. Its architecture procedure then writes how a consumer will use the proposed design before drawing internal modules. This asks a better simplicity question: how much responsibility must the caller understand and coordinate? [How][how] and [Architect][architect] supply the complementary halves.

A short helper is not necessarily simple if twelve callers must perform `load`, `validate`, `lock`, `write`, and `unlock` in the correct order. A deeper module can expose one meaningful operation and own that invariant. Conversely, a wrapper that hides no policy or ownership may only create another layer to learn. File length and layer counts can signal a problem, but the useful measure is the work imposed on consumers and maintainers.

AgentsMD should retain this procedure in `software-design`, with research mechanics supplying the current-system trace. Use it for material changes in ownership, state, API shape, or migration. Crossing any function boundary must not automatically trigger a panel of architects. Small established changes remain direct.

### Make invariants structural, but respect what the structure guarantees

The source repeatedly replaces scattered coordination with representations: explicit lifecycle states, discriminated unions, correct collections, clear boundaries, one owner for mutable state, and operation identities for retry. Its strongest idea is that a valid design makes whole classes of mistakes difficult to express. The same principle applies to instructions: a schema or structural check can outperform another repeated warning. [Domain modeling][principle-model-the-domain], [type discipline][principle-type-system-discipline], [idempotency][principle-make-operations-idempotent], and [structural learning][principle-encode-lessons-in-structure] form one connected method.

The adaptation must preserve runtime honesty. A type annotation does not validate external input. A value can become invalid after mutation or across a lifetime boundary. Authorization and resource existence can change between checks and use. A PID is not a durable ownership token. Independent actor reports can be separated and combined on read; a shared account balance needs an actual consistency model.

Put code-level states, types, ownership, concurrency, and migrations in `software-design`. Existing `domain-modeling` continues to own project terms, glossaries, and qualifying ADRs. Link the two where names and representations interact. Do not make them competing architecture procedures.

### Compare structures through evidence, not taste or model votes

pstack's architecture and arena workflows ask for genuinely different solutions and deliberate synthesis. A comparison between three names for the same shared mutable object teaches little. A comparison between one canonical writer and independently owned facts can expose meaningful differences in recovery, consistency, consumer burden, and proof. [Arena][arena] makes candidate selection explicit; [Interrogate][interrogate] adds focused adversarial scrutiny.

Preserve independent candidates when uncertainty justifies their cost. Two written sketches may be enough; a cheap executable prototype may resolve the uncertain behavior. Multiple models agreeing is not proof, and disagreement does not necessarily mean the brief was poor. Read the evidence behind the disagreement. Select one coherent base and incorporate compatible improvements. The synthesized result is a new candidate and needs its own proof.

This fits `software-design`, `code-review`, and bounded orchestration references. Model selection remains with Model Router and explicit user constraints. Fixed model families, worker counts, and reasoning levels do not belong in AgentsMD's engineering contract.

### Diagnose by discriminating observations

The defect workflows connect the symptom, intended behavior, environment, competing mechanisms, and a check that would separate those mechanisms. A queue can fail because work was never scheduled, never started, failed during execution, or completed without publishing its result. Each explanation predicts different evidence. Repeated patches built on the same failed premise should trigger a test of that premise. [Bug fix][pb-bug-fix], [runtime forensics][pb-runtime-forensics], and [attack the premise][principle-attack-the-premise] provide the useful pattern.

Benny makes the observation unusually concrete. Name the correct final state and the broken final state. Reach the point where they differ. A loading screen, setup dialog, familiar app title, or successful compile does not establish the reported defect. Reset and repeat when state carryover could explain the result. Read-only internal state can corroborate an observation but must not manufacture it. [Benny reproduction][benny-reproduce] and its [control adapter][control-adapter] turn “prove it” into an executable epistemic boundary.

The best seam is the cheapest one that retains the causal conditions. A captured byte sequence may fully reproduce a parser bug. A focus-loss bug may need the real browser interaction. Do not require a video, two UI attempts, or a specialist reviewer for every change. Preserve the source's discriminating test without universalizing its particular automation budget.

### Proof must challenge the load-bearing assumption

pstack's impact analysis asks what the safety claim depends on and whether that assumption can be exercised directly. Symbol search alone misses serialized fields, cross-language readers, delayed callbacks, teardown, persisted formats, and dependency semantics. Read the actual pinned dependency and local patches. A documentation quotation can support an expectation; invoking the real function can expose an unexpected notification, mutation, or lifecycle effect. [Blast radius][blast-radius] is more useful than a generic instruction to run tests.

Test design should use an oracle independent of the implementation. Calculating the expected URL with the same URL builder can duplicate the defect on both sides. A literal, fixture, independently stated relation, or reference implementation can give stronger evidence. But negative assertions, boundary mocks, exact text, and compile-time error tests can all protect real contracts. The source's blanket assertion blacklist needs correction, not adoption. [Test behavior][principle-test-behavior-not-implementation] and [TDD][tdd] supply motivation, while AgentsMD's exact proof rules supply the delivery boundary.

Do not confuse an experiment with complete proof. Affected checks provide fast feedback. Reused evidence still needs authenticated candidate, input, environment, and coverage identity under the existing scoped-proof policy. Matching patch IDs after a rebase cannot prove that a changed base preserves behavior.

### Performance is an experimental discipline

The performance playbooks contribute more than “measure first.” Select a representative workload and user-facing metric, validate the measurement's sensitivity, capture the baseline, freeze the comparison method, and control cache warmth, ordering, runtime, data, and concurrency. Interleave or randomize baseline and candidate runs where drift could bias the result. Keep raw observations and report variance relevant to the claim. [Performance issue][pb-perf-issue] and [hillclimb][pb-hillclimb] distinguish one repair from sustained optimization.

Retain all eight strategy families as hypotheses: eliminate work, partition, cache, index, batch, defer, reschedule, and use safe redundant execution for tail latency. Each has conditions. Caching needs invalidation; deferred work may move rather than remove cost; redundant requests need resource headroom and safe duplicate semantics. Run an interpretable experiment, verify correctness, and retain improvements beyond noise. A simpler result with equivalent speed is a simplification, not a measured speedup.

When the baseline lacks a feature, do not invent a ratio between unlike workloads. Measure the added work and the end-to-end state the user awaits against justified absolute budgets. A plateau prompts reassessment of workload, metric, and mechanism, not an arbitrary minimum number of iterations.

### Preserve knowledge about both the system and the work

pstack distinguishes understanding current mechanics from explaining historical intent. Blame records last touch, not necessarily origin. Search substantive diffs, rename history, exact-text pickaxe, linked PRs, review threads, tickets, design notes, incidents, and runtime evidence. Code cannot prove its own author's motivation. A direct quote establishes stated rationale, not that the rationale was correct or the outcome succeeded. [Why][why] and [its epistemics reference][epistemics] are a major expansion over generic citation advice.

Recall serves a different purpose again. It reconstructs intent, corrections, failed attempts, and reverts across a bounded topic and time range, then reconciles that history with current Git, Issues, artifacts, and live state. A canonical handoff is preferable when sufficient. A transcript is evidence of an earlier action or claim, never current delivery truth. [Recall][recall] and [session pickup][pb-session-pickup] should become research modes linked to operations recovery.

Reflection closes the loop. Diagnose whether guidance was missing, failed to trigger, was buried, was clear but not followed, or required structural enforcement. Read the proposed owner before adding a rule. A useful lesson names the observed failure and the future decision it changes. Zero lessons is valid. [Reflect][reflect] provides judgment, tooling, and alternative-explanation lenses without requiring three workers every time.

### Coordination has a throughput limit and a failure model

The orchestration source treats the coordinator's attention as a scarce resource. Completion notifications become pending evidence instead of interrupts to every brief or topology operation. Capacity comes from the ability to validate and integrate results, not the platform's maximum fan-out. A rolling window avoids waiting for the slowest member of each batch. Another coordination layer is justified only when it relieves a measured constraint. [Orchestrate][pb-orchestrate] supplies these concrete mechanisms.

A dependency also transfers knowledge. Clearing a native blocker must relay the exact artifact, decisions, proof, and limitations its consumer needs. Pilot a novel workflow through the last authorized delivery state before multiplying it. Integrate reviewed components continuously into the owned integration branch rather than accumulating fragile VM-local output. Preserve the final approval PR and one version transition.

Recovery must distinguish exhausted scope, infrastructure failure, bad upstream contracts, stalled work, and obsolete late results. Confirm a writer stopped before replacing it in shared resources. Reconcile a late result with current base, head, ownership, and proof. Account for failed, superseded, abandoned, and absorbed units; their acceptance criteria do not disappear with the workers. Keep a compact frontier derived from Git/GitHub and a canonical Issue handoff, not a second orchestration database.

## Integration ownership and concrete improvements

The following layout retains established entrypoints while assigning each procedure one owner.

| Destination | Concrete responsibility | Boundary |
| --- | --- | --- |
| `skills/software-design/` | Grounding, consumer examples, alternatives, module depth, state/types, ownership, concurrency, idempotency, migration | Routine reversible design is agent-owned; consequential choices retain existing gates |
| `skills/diagnosis/` | Reproduction, hypotheses, existing-fix verification, runtime/trace forensics, performance experiments | Read-only diagnosis does not authorize hot patches, restarts, or fixes |
| `skills/code-review/` | Reviewer brief, evidence rubric, finding adjudication, impact analysis, comments and hidden constraints | Supplements required independent exact-candidate review; does not replace it |
| `skills/project-verification/` | Create and maintain project-local launch/doctor/driver/evidence/cleanup instructions and feature maps | Executable acceptance knowledge, not a tracker or automatic scheduler |
| `skills/reflection/` | Judgment/tooling/divergent lenses, failure classification, scoped preference capture | No automatic policy mutation or public private-history export |
| `skills/technical-writing/` | Tutorials, how-to guides, reference, explanation, and shared prose editing | Human-reader purpose; `writing-for-agents` retains instruction design |
| `skills/research/references/` | Mechanics, history, epistemics, recall, teaching, and eight source categories | Classify first, load only useful modes and sources |
| `skills/operations/references/` | Engineering routing, behavior-preserving refactoring, practical proof, bounded coordination, recovery, safe cleanup | Existing lifecycle, authority, exact proof, and canonical Issue state remain authoritative |
| `skills/prototype/` | Add empirical script/native-harness experiments beside existing logic/UI branches | Throwaway decision evidence; preserve the owning workflow's human verdict where required |
| `skills/elon-method/` | Failed-premise examples and proportional instruments before acceleration | Algorithm order remains; no mandatory tool or worker for every task |

Research needs source-sensitive procedures, not an eight-connector sweep. The eight categories below preserve distinct evidence tactics while treating vendor names as examples.

| Source category and upstream reference | Retained method | Required qualification |
| --- | --- | --- |
| [Code history][src-code] | Trace origin, renames, co-changes, full diffs, PR discussions, tests, ADRs, releases, copied patterns | Last touch differs from origin; fetch relevant inline review threads; shallow history limits claims |
| [Tracker][src-tracker] | Linked IDs, full comments/history, parent and duplicate chains, business terms, deadlines | Current body can postdate the decision; labels are hints |
| [Documents][src-documents] | Full pages, child pages, alternatives, meeting records, authors, dates, approved/draft status | Latest is not necessarily contemporaneous or authoritative |
| [Chat][src-chat] | Exact symbols/errors/URLs, author and time filters, full threads, attribution | Retention and inaccessible channels are missing coverage, not negative evidence |
| [Observability][src-observability] | Service map, query definitions, units, thresholds, time-bounded traces/logs, incident links | Instrumentation changes and nearby releases are confounders |
| [Errors][src-errors] | Signature, first/last seen, release tags, grouping, sampling, representative breadcrumbs | Resolved status and disappearance do not alone prove a fix |
| [Analytics][src-analytics] | Actual schema, typed/deduplicated models, distributions, variants, lineage, bounded aggregate queries | Sampling, lag, schema history, cost, and customer-data access matter |
| [Incidents][src-incidents] | Join postmortem, mitigation, prevention, action item, commit, and release identities | Cross-source angle, not necessarily another database or worker |

A historical investigation should anchor the code, choose sources that can distinguish plausible answers, record queries and gaps, follow cross-source leads, reconcile contradictions, and produce Preserve / Change / Avoid / Risk constraints. Direct, supported, inferred, speculative, and unknown claims remain distinguishable. Copied references do not become independent corroboration.

Project verification deserves one create/maintain owner because its core contracts are shared. Inspect existing surfaces and harnesses before asking for facts. Identify the exact build, process, address, data location, and readiness condition. A “doctor” check must verify identity as well as liveness. Drive one real feature, retain action and outcome evidence, clean up only owned resources, and verify evidence survives. An unexecuted generated procedure remains a draft. [Create verification][create-verification-skill] and [maintain verification][maintain-verification-skill] supply the foundation.

A feature map records user paths, preconditions, adapter actions, reset, expected observations, and gotchas. It should rediscover changing internals rather than freeze them into user instructions. Exercising a toolbar does not prove a keyboard shortcut. Maintenance distinguishes documentation drift, harness failure, and product regression; it must not rewrite the expected result to bless a regression. Source readers may work independently, but each app instance has one driver. Missing entitlement or OS capability remains unverified coverage.

Practical proof and refactoring references should replace vague advice with a preserved contract and a structural target. Pin relevant outputs, errors, ordering, and effects. Name the improvement, such as replacing synchronized flags with explicit connection states. Migrate all controlled consumers and remove old APIs when release boundaries permit. External clients, persisted formats, and rolling deployments can justify a compatibility window with a removal criterion. Temporary breakage stays inside an unfinished isolated unit; consumers do not start from a falsely review-ready predecessor. [Refactoring][pb-refactoring] and [caller migration][principle-migrate-callers-then-delete-legacy-apis] need this adaptation.

Technical writing adds document purpose rather than another blanket style pass. Tutorials need visible expected results; how-to guides put conditions before guarded actions; reference mirrors actual structure; explanation develops mechanisms and tradeoffs. Large documents may separate modes into clear sections. Preserve uncertainty, exceptions, articles, verbs, and necessary technical terms. Teaching reuses established evidence and adapts depth to the reader. Simpler restatement supplies the missing concept instead of defending the previous answer. [Technical writing][technical-writing], [Unslop][unslop], [Teach][teach], and [Bro][bro] contribute different parts.

## Preserve existing contracts; remove duplication

Keep the sixteen current public skills: `algorithm`, `delivery-profile`, `domain-modeling`, `elon-method`, `grill-with-docs`, `grilling`, `operations`, `project-direction`, `prototype`, `research`, `to-spec`, `to-tickets`, `use-grok`, `version-control`, `wayfinder`, and `writing-for-agents`. No current active skill deletion is justified by this source review.

Compatibility is valuable when an entrypoint has established meaning. `algorithm` remains a compatibility router to the owned method. `grill-with-docs` composes explicit decision sharpening with terminology and ADR capture. `grilling` retains its strict explicitly invoked behavior. Wayfinder retains its deliberate decision frontier and explicit transition gates. To Spec and To Tickets retain approved publication and implementation boundaries. This integration does not reopen Project Direction or broadly relax planning gates.

By contrast, importing separate wrappers for every pstack principle would duplicate routing. Merge `how`, `why`, `recall`, and `teach` as distinct research modes with discoverable triggers. Merge create/maintain verification into one capability. Merge arena/swarm coordination into operations references. Put prose cleanup in one shared reference. Retire destructive comment stripping as a workflow while retaining comments as evidence during review.

The removals are precise: duplicate imported wrappers, the stale operations sentence that gives an unbundled `implement` skill stronger authority, and unconditional fresh-approval wording that ignores authority already granted for the exact operation and target. Preserve actual human gates and skill-specific approval contracts. Updating the catalogue means recording where source capabilities went, not deleting existing names to reach a smaller count.

Overlap should improve the owner. “Bound workers” becomes a capacity test and recovery procedure. “Search duplicates” becomes a causal evidence ladder. “Prove it” gains a discriminating observation. “Use clear language” gains document-purpose selection. “Learn from errors” gains a diagnosis of missing guidance versus missed triggers versus mechanism failure. These are operational improvements, not extra slogans.

## Complete source-skill disposition

“Merge” preserves the method inside its destination without adding a public wrapper. “Adapt” keeps a substantial procedure with corrected assumptions. “Defer” records a reconsideration condition. The table includes 47 ordinary skills and three dormant Benny automation skills.

| Source skill | Disposition | Destination | Method retained and adaptation |
| --- | --- | --- | --- |
| [architect][architect] | Adapt | software-design | Trace the consumer path, compare structures, write usage first, hide invariants. Remove automatic panels at every function boundary. |
| [arena][arena] | Merge | operations coordination | Compare independent alternatives, choose a coherent base, synthesize deliberately, then verify the new candidate. Agreement alone proves nothing. |
| [automate-me][automate-me] | Merge | reflection | Capture explicit preferences and supported habits in their private owner. Do not generate public personal-mode policy or infer scheduling authority. |
| [blast-radius][blast-radius] | Adapt | code-review impact analysis | Trace direct and hidden consumers, test load-bearing dependency assumptions, separate confirmed, cleared, and unproven risks. |
| [bro][bro] | Merge | research explanation and existing core re-pitch guidance | Restate the claim plainly, supply the missing concept, preserve consequential caveats, and stop. No separate wrapper needed. |
| [create-verification-skill][create-verification-skill] | Adapt | project-verification create mode | Discover the real surface and harness; define launch, doctor, driver, evidence, cleanup, and a runnable initial feature map. |
| [figure-it-out][figure-it-out] | Merge | operations engineering | Define falsifiable done, capture baseline, resolve the riskiest unknown, inspect artifacts, and distinguish verified from inconclusive. |
| [how][how] | Adapt | research mechanics mode | Trace real triggers, calls, types, state, boundaries, and failures. Separate exploration evidence from the reader-facing mental model. |
| [interrogate][interrogate] | Adapt | code-review | Use focused independent lenses and a shared evidence rubric; adjudicate each finding. Remove vote-based truth, quotas, and compelled restructuring. |
| [maintain-verification-skill][maintain-verification-skill] | Adapt | project-verification maintain mode | Reconcile feature coverage, repair owned harness drift, distinguish product regressions, and preserve unverified routes. One driver owns each app instance. |
| [make-bot-ui][make-bot-ui] | Defer | authorized automation reference | Retain server-side secrets, authenticated narrow actions, and untrusted payloads. Exclude host-specific installation, network exposure, and vendor backend assumptions. |
| [no-comments][no-comments] | Merge corrected subset | code-review comments reference | Treat comments as evidence of missing structure or hidden constraints. Preserve useful rationale until its replacement is verified; reject ambiguous deletion. |
| [poteto-mode][poteto-mode] | Merge selected routes | existing operations and core | Retain candid judgment and concrete workflow distinctions. Exclude persona, compulsory wrapper chains, fixed models, and blanket external-write authority. |
| [principle-attack-the-premise][principle-attack-the-premise] | Merge | elon-method and diagnosis | After repeated premise-sharing failures, name the assumption and run a distinguishing check. Actor imbalance census is one example, not the universal method. |
| [principle-boundary-discipline][principle-boundary-discipline] | Merge | software-design | Separate representation, validation, and policy at owning boundaries. Internal types do not erase changing trust, lifetime, or concurrency conditions. |
| [principle-build-the-lever][principle-build-the-lever] | Merge | elon-method and operations | Use rerunnable instruments when scale, reproducibility, or recurrence earns them. Do not require tooling as an extra deliverable for every task. |
| [principle-encode-lessons-in-structure][principle-encode-lessons-in-structure] | Merge | reflection | Prefer a schema, check, metadata, or runtime guard when it can enforce the lesson. Keep judgment, rationale, and authority that mechanisms cannot replace. |
| [principle-exhaust-the-design-space][principle-exhaust-the-design-space] | Merge | software-design and prototype | Compare meaningfully different designs for real uncertainty. Bounded alternatives suffice; forced or established designs need no exploration quota. |
| [principle-experience-first][principle-experience-first] | Merge | software-design | Begin with consumer interaction, failure, and recovery. Respect confirmed priorities instead of making visual delight override reliability or scope. |
| [principle-fix-root-causes][principle-fix-root-causes] | Merge | diagnosis | Explain the mechanism and reproduce the original trigger. Guards and retries are legitimate when their input and failure contracts justify them. |
| [principle-foundational-thinking][principle-foundational-thinking] | Merge | software-design | Choose representations and dependency order before scattered logic. Foundational work needs a current constraint, not speculative future usefulness. |
| [principle-guard-the-context-window][principle-guard-the-context-window] | Merge | operations coordination | Bound context, use precise packets and evidence pointers, and avoid transcript dumps. Never omit mandatory full instructions or direction to compress. |
| [principle-laziness-protocol][principle-laziness-protocol] | Merge | elon-method and code-review | Remove unnecessary layers, branches, and coordination. Judge total consumer burden rather than fixed file/layer counts or minimum changed lines. |
| [principle-make-operations-idempotent][principle-make-operations-idempotent] | Merge | software-design and recovery | Name operation identity, commit point, durable result, and reconciliation path. Retries must not duplicate effects; PIDs alone do not prove ownership. |
| [principle-migrate-callers-then-delete-legacy-apis][principle-migrate-callers-then-delete-legacy-apis] | Merge | software-design and operations refactoring | Migrate controlled consumers and remove obsolete paths. Retain explicit compatibility when external clients, persisted data, or independent deployment require it. |
| [principle-minimize-reader-load][principle-minimize-reader-load] | Merge | software-design and technical-writing | Reduce hidden state and unnecessary caller knowledge. Keep a boundary when it owns meaningful policy, even with one current caller. |
| [principle-model-the-domain][principle-model-the-domain] | Merge | software-design linked to domain-modeling | Choose states, reducers, registries, and collections from invariants and access patterns. Avoid structures that make local clear code harder to understand. |
| [principle-never-block-on-the-human][principle-never-block-on-the-human] | Merge existing owner | core authority and continuation | Proceed through authorized reversible work. Reversibility does not itself authorize messages, spending, deployment, or scope changes. |
| [principle-outcome-oriented-execution][principle-outcome-oriented-execution] | Merge | software-design migrations and operations | Use explicit transformation boundaries and converge on the target. Temporary breakage stays isolated and cannot masquerade as review-ready output. |
| [principle-prove-it-works][principle-prove-it-works] | Merge | operations proof and project-verification | Inspect the real artifact and discriminating result. Validate the observer too; a suspiciously easy pass may mean the intended behavior never ran. |
| [principle-redesign-from-first-principles][principle-redesign-from-first-principles] | Merge | elon-method and software-design | Use the new requirement to challenge inherited shape. A greenfield sketch informs the smallest authorized change, not an automatic system rewrite. |
| [principle-separate-before-serializing-shared-state][principle-separate-before-serializing-shared-state] | Merge | software-design and operations | Separate actor-owned facts when semantics permit; otherwise enforce real serialization. Include services, ports, databases, and topology in ownership. |
| [principle-sequence-verifiable-units][principle-sequence-verifiable-units] | Merge | operations engineering and delivery | Give meaningful transformations checkable boundaries. Preserve final combined proof and dependency readiness; do not publish broken intermediate merge units. |
| [principle-subtract-before-you-add][principle-subtract-before-you-add] | Merge existing method | elon-method with engineering examples | Delete unnecessary machinery before optimization. Preserve unique regressions, required compatibility, user work, and evidence-backed defensive behavior. |
| [principle-test-behavior-not-implementation][principle-test-behavior-not-implementation] | Merge corrected subset | operations test-design | Use public behavior and independent oracles. Correct false undefined examples; retain meaningful negative assertions, boundary mocks, and exact product contracts. |
| [principle-type-system-discipline][principle-type-system-discipline] | Merge | software-design types reference | Encode valid states and parse boundaries. Explain mutation, brands, predicates, casts, and the actual limits of static guarantees. |
| [recall][recall] | Adapt | research recall mode | Recover scoped intent, corrections, recurring problems, failed attempts, and reverts. Reconcile history with canonical and live state before resuming. |
| [reflect][reflect] | Adapt | reflection | Apply judgment, tooling, and alternative-explanation lenses. Diagnose missing guidance, trigger failure, placement, execution, or mechanism before adding prose. |
| [setup-pstack][setup-pstack] | Defer to existing owner | Model Router | Discover actual model availability and honor explicit budgets. Do not import another per-role routing file, model-slug policy, or installation surface. |
| [show-me-your-work][show-me-your-work] | Merge | operations evidence and recovery | Keep optional material-decision history with receipts and explicit corrections. Canonical current state remains on the Issue; do not create a second ledger. |
| [swarm][swarm] | Merge | operations coordination | Distinguish required coverage, optional alternatives, and races. Missing required slices remain gaps; define aggregation and stopping before dispatch. |
| [tdd][tdd] | Merge | operations test-design and diagnosis | Observe a practical regression fail for the intended reason, then pass after repair. State evidence limits when a useful deterministic seam is unavailable. |
| [teach][teach] | Merge | research teaching mode | Explain the problem and mechanism through a concrete example, layer detail, and preserve historical confidence. No forced diagrams, quizzes, or premature stopping. |
| [technical-writing][technical-writing] | Adapt | technical-writing | Select tutorial, how-to, reference, or explanation by reader need. Keep visible results, conditions before actions, exact terms, and meaningful tradeoffs. |
| [typescript-best-practices][typescript-best-practices] | Adapt corrected reference | software-design language examples | Retain purposeful unions, parsing, and consumer types. Correct invalid-range, nonempty mutation, satisfies, cast, and transport-coupling overclaims. |
| [unslop][unslop] | Merge | shared prose reference | Replace vague claims with mechanisms, remove stock framing and repetition, preserve natural grammar and uncertainty. Do not install a global taboo vocabulary. |
| [why][why] | Adapt | research history and epistemics | Anchor code origin, investigate selected evidence categories, follow linked leads, preserve contradiction and uncertainty, and return actionable change constraints. |
| [Benny / setup-benny][benny-setup] | Defer pack; retain mechanisms | project-verification and automation boundary | Validate fresh target capabilities, separate user configuration, preserve updates, and prove deployment identity before activation. |
| [Benny / triage-issue-reports][benny-triage] | Defer pack; retain mechanisms | diagnosis intake and automation boundary | Freeze source identity, trace cause before routing, classify duplicate confidence, authenticate handoffs, and record partial external outcomes. |
| [Benny / reproduce-and-fix-issues][benny-reproduce] | Defer pack; retain mechanisms | diagnosis and project-verification | Confirm the discriminating state, respect fix ownership, verify existing artifacts, bound optional repair, retain before/after evidence, and clean owned resources. |

## Complete playbook disposition

All 23 playbooks are under `skills/poteto-mode/playbooks/` in the pinned pstack source. Their methods are retained through the named owners; their host-specific lifecycle is not copied wholesale.

| Source playbook | Destination | Retained method and boundary |
| --- | --- | --- |
| [authoring-a-skill][pb-authoring-a-skill] | writing-for-agents and normal delivery | Validate triggers, frontmatter, references, and decision-changing prose. Use supported skill authoring, without a mandatory PR for read-only or local work. |
| [autonomous-run][pb-autonomous-run] | operations bounded execution | Falsifiable predicate, evidence-based iterations, honest discarded hypotheses, durable checkpoints. No unsolicited scheduler, out-of-scope side fixes, or weakening done. |
| [autopilot-full][pb-autopilot-full] | operations coordination | End-to-end ownership, code-ready exact SHA, parallel independent review, accumulated findings, stop propagation. Preserve final approval and confirm writer shutdown before replacement. |
| [autopilot-stack][pb-autopilot-stack] | operations stack management | One topology writer, exact parents, current remote state, dependent revalidation, truthful bottom-up reviewability. Preserve AgentsMD final approval PR and proof policy. |
| [babysit][pb-babysit] | operations delivery | Distinguish check, comments, merge-readiness, and landing; classify CI and review claims. No status request silently authorizes fixes or merge. |
| [bug-fix][pb-bug-fix] | diagnosis and implementation | Reproduce at the causal seam, discriminate hypotheses, repair the mechanism, retain failing-before/passing-after proof, and inspect nearby behavior. |
| [eval][pb-eval] | operations evaluation reference | Consistent tasks, blinded evaluation metadata where useful, fair criteria, privacy, and calibrated outcomes. No synthetic model-run release gate by default. |
| [feature][pb-feature] | software-design and operations engineering | Consumer outcome, data shape, justified boundary, implementation, and proof. No mandatory architecture panel or worker for a clear microfix. |
| [hillclimb][pb-hillclimb] | diagnosis optimization mode | Freeze measurement, log bounded experiments, preserve correctness, retain improvements beyond noise. No arbitrary minimum iteration count or endless unattended loop. |
| [investigation][pb-investigation] | expanded research | Read-only mechanics, rationale, or recommendation with citations and actual judgment. Remove ceremonial throughput messages and unnecessary handbacks between evidence modes. |
| [multi-phase-plan][pb-multi-phase-plan] | existing specification/tickets plus proof links | Make visible outcomes and evidence explicit, record alternatives and risks, preserve plan-only scope. Do not copy fixed swarms or replace approved native Issue graphs. |
| [opening-a-pr][pb-opening-a-pr] | existing delivery and technical-writing | Brief reviewers on intent, scope, tradeoffs, impact, and evidence. Reject reset-hard shortcuts, draft bans, unowned patch movement, and arbitrary PR counts. |
| [orchestrate][pb-orchestrate] | operations coordination and recovery | Capacity-limited rolling windows, safe drains, dependency relay, pilot, continuous integration, exact evidence, mode-specific retries, and stale-result reconciliation. |
| [pause-safely][pb-pause-safely] | operations recovery and version-control | Stop at safe boundaries, preserve owned work, record exact recovery state. Do not commit user-owned changes or treat task completion as a pause. |
| [perf-issue][pb-perf-issue] | diagnosis performance mode | Representative workload, user metric, validated baseline, eight hypothesis families, controlled comparison, behavioral constraints, and honest noise limits. |
| [prototype][pb-prototype] | existing prototype empirical branch | Use the cheapest executable artifact for the decision, including scripts or native harnesses. Keep human-facing logic/UI variants and existing verdict gates. |
| [refactoring][pb-refactoring] | software-design change method, routed by operations | State preserved behavior and structural target, inventory consumers, compare old/new outcomes, migrate safely, and retain necessary compatibility. |
| [runtime-forensics][pb-runtime-forensics] | diagnosis runtime mode | Use live state and instrumentation to separate mechanisms. Distinguish read-only observation from authorized injection, restart, or repair. |
| [session-pickup][pb-session-pickup] | research recall and operations recovery | Recover intent and failed attempts, verify current state, reuse exact valid proof, and resume the right task without replaying completed work. |
| [shipping][pb-shipping] | existing delivery | Check current candidate, contiguous dependencies, actual merge state, and post-merge retargeting. Do not import patch-id-only reuse or merge authority. |
| [trace-forensics][pb-trace-forensics] | diagnosis artifact mode | Inspect capture conditions, symbols, time intervals, self/inclusive cost, retained objects, and confounders. Paired traces alone do not establish causality. |
| [visual-parity][pb-visual-parity] | operations proof reference | Freeze representative states, viewport, environment, baseline, and tolerances before comparison. Investigate deltas; no universal zero-pixel rule. |
| [worktree-cleanup][pb-worktree-cleanup] | existing finalization/reconciliation | Inventory real worktrees, verify ownership and current use, preserve ambiguous and untracked work. Reject automatic force deletion and blanket simulator pruning. |

## Defects and assumptions that must not survive adaptation

The following are static source findings and counterexamples. They are not reports of executed failure demonstrations.

| Source | Precise problem | Correction |
| --- | --- | --- |
| [TypeScript patterns][ts-patterns] | `{ start: Date; durationMs: number }` still admits negative, non-finite durations and invalid dates | State the narrower benefit or use a validating constructor and appropriate representation |
| [TypeScript patterns][ts-patterns] | Mutable nonempty arrays can lose the runtime invariant; `satisfies` does not validate JSON or universally freeze literals | Explain mutation/aliasing and compile-time versus runtime guarantees |
| [Test principle][principle-test-behavior-not-implementation] | Claims about assertions surviving an `undefined` implementation are false for several listed assertions | Ask what plausible defect the oracle rejects instead of blacklisting assertion names |
| [Boundary principle][principle-boundary-discipline] | Unconditional internal trust ignores mutation, concurrency, persistence, and changing authorization | Validate at the owning trust or lifetime boundary |
| [No Comments][no-comments] | Ambiguous constraints can be deleted while their invariant remains unenforced | Preserve useful rationale and suppression explanations until a verified replacement exists |
| [Runtime forensics][pb-runtime-forensics] | Evaluation, hot patches, instrumentation, and restart can mutate the running system | Keep read-only diagnosis distinct from authorized intervention |
| [Shipping][pb-shipping] | Equal patch ID does not establish equal behavior on a changed base; build-noise heuristics can overstate reusable proof | Preserve AgentsMD's exact-input, environment, complete-coverage, and scoped-proof contract |
| [Autopilot full][pb-autopilot-full] | Replacement may proceed even when stopping the previous worker fails | Confirm stop or isolate every shared resource before replacement |
| [Orchestration store][orch-store] | Inbox drain deletes received pointers before the coordinator durably handles them | A future queue needs acknowledgement or recoverable event identity; notifications cannot own durable truth |
| [Orchestration store][orch-store] | Same PR/SHA verdict is overwritten without verifier precedence or history; evidence is only a nonempty string | Preserve reviewer authority and exact evidence; do not treat the store as an enforcement gate |
| [Orchestration store][orch-store] | Summaries count old-SHA verdicts; aggregate counts can miss changed unit identities | Derive readiness from current candidate joins and material state changes |
| [Orchestration CLI][orch-cli] | Existing failed/blocked verdict lookup exits successfully; default standing-order output truncates after four rows | Distinguish successful lookup from passing proof; never truncate authority-bearing constraints |
| [Orchestration store][orch-store] | PID locks and forced takeover lack distributed identity and fencing; per-file atomic writes are not multi-file transactions | Do not inherit a general coordination runtime from local bookkeeping |
| [Bootstrap][bootstrap] | Dependency installation runs before argument parsing, including apparently read-only commands | Keep installation explicit and separate from read-only queries |
| [Plan checker][check-plan] | Literal strings, a model slug, lane count, and headings are enforced, but semantic proof, authorization, and viable dependency coverage are not | Validate actual invariants without enforcing arbitrary workflow cost |
| [Decision trail][show-me-your-work] | Append-only history conflicts with later instructions to cut or rewrite entries | Append corrections and render a clean view; do not rewrite history into success |
| [Decision log helper][decision-log] | No ownership, symlink, concurrent-header, or evidence-resolution enforcement | Use single-writer owned artifacts; add mechanisms only when real requirements justify them |
| [Benny prompt templates][benny-triage-template] | Templates provide `message_ts`, while operational instructions use `trigger.ts` when no thread timestamp exists | Define and validate adapter normalization |
| [Benny triage][benny-triage] | Preflight, dedupe, ticket creation, and Slack reply are separate writes with race and ambiguous-response windows | Use idempotency, re-fetch uncertain outcomes, explicit partial success, and only authorized compensation |
| [Benny setup][benny-setup] | A committed path and configured capability list do not prove the scheduled runtime resolves or enforces them | Validate fresh target capability and preserve controlled deployed identity |

Additional numerical rules are heuristics, not portable quality gates: fixed reviewer counts, maximum findings, ten live lanes, thirty-second comprehension targets, a 70% spawning cutoff, mandatory iterations, and blanket file-size limits. Keep the failure signal behind each rule and demand evidence for its applicability.

Autonomy also needs careful translation. A reversible action can still send a message, spend credits, expose data, or alter a live target. pstack's broad permission to use external tools is not AgentsMD authority. Silence during a Benny correction window is not general approval. A trusted marker can establish a workflow handoff only within prior authorization; it cannot grant new authority.

## Runtime and automation ideas to defer

Do not import the `orch` service-shaped local database, Graphite-only frontier reader, or a mandatory standing-order mirror. Git, GitHub Issues, existing host task tools, and the canonical handoff already own the necessary state. Retain readable derived status, exact candidate identity, recoverable events, and honest incomplete outcomes as design requirements if a real future bottleneck justifies tooling.

Do not import the watcher as a merge-authorization oracle. Its policy allows `UNKNOWN` and can allow `BLOCKED` when the head rollup is not failing; readiness rejects `CHANGES_REQUESTED` but can permit `REVIEW_REQUIRED`. Tests explicitly expect these outcomes. Review-thread retrieval stops at the first 100 threads and first 10 comments per thread. Metadata and checks are read separately without reconciling a stable head. Stack ordering follows branch-name relationships without a visited-node guard or repository identity. These are concrete limits on using a progress helper as a complete merge gate. [Policy][watch-policy], [GitHub adapter][watch-github], and [policy tests][watch-policy-tests] support this assessment.

Retain its useful separation between a one-shot check, comment handling, merge-readiness work, and authorized landing. Forge state, proof state, and authority are distinct. A polling wakeup is a reason to refresh live state, not permission to merge. A future portable adapter needs explicit unknown states, reliable pagination, current head/base identity, and deterministic coverage of policy decisions. [Babysit][pb-babysit] and [Shipping][pb-shipping] contain those useful separations despite their runtime assumptions.

The worktree audit is useful inventory, not deletion authority. Its script assumes `origin/main`, parses worktree paths through whitespace-sensitive fields, consults a bounded author-filtered PR list, and treats untracked-only state as disposable scratch. It also performs a fetch despite describing itself as read-only. Closed PR state, old transcript timestamps, and a clean checkout do not establish ownership or safe removal. Preserve AgentsMD's ownership and retained-exception checks; do not copy force-removal or blanket simulator cleanup. [Audit script][worktree-audit] and [cleanup playbook][pb-worktree-cleanup] are explicit examples of why classification must remain separate from permission.

Benny is a well-bounded optional product workflow, not a default feature for every repository. Preserve immutable source identity, causal routing, duplicate confidence, authenticated handoffs, capability-isolated external writes, existing-fix verification, bounded effort, and cleanup ownership. Defer its Slack/tracker pack until an authorized recurring intake problem needs it. Configuration is not capability enforcement, and compensating deletion is not automatically safer than recording partial success.

`make-bot-ui` remains a host-specific reference. Server-side secrets, untrusted webhook payloads, narrow JSON actions, and a harmless live probe are useful. Automatic installation, binding all interfaces, HTTP assumptions, webhook-provider internals, and local log draining require an independently designed authorized target. The persistent automation ADR already owns canonical sources, controlled deployed copies, identity, health, rollback, and drift. A scheduled job must not execute mutable checkout contents merely because its path was committed. [Make Bot UI][make-bot-ui] supplies ideas, not a deployable portable contract.

## Implementation sequence and evidence limits

First establish the six capability owners and research modes with substantial procedures and examples. Preserve all eight source categories through four grouped source references, alongside their technical distinctions and discoverable triggers. Add links from operations at the actual point of use. Expand prototype with an empirical branch. Keep everyday direct work from loading the entire library.

Then revise overlapping current text so each rule has one owner. Keep language and ADR contracts in domain-modeling, planning gates in their selected workflows, proof and lifecycle authority in operations, model routing outside AgentsMD, and Project Direction unchanged. Record source-to-destination dispositions and licensing. Remove only the identified duplicate wrappers and stale instructions.

Deterministic validation should check frontmatter, catalogue completeness, packaged references, installed link resolution, source attribution, preserved gates, and any actual helper through its public seam. Instruction text can itself be a product contract, so precise text assertions are sometimes appropriate. They prove packaging and required clauses, not model behavior. Correct technical examples should have executable checks when presented as compiling or running examples.

No testing is claimed by this report. Behavioral improvement remains a hypothesis until ordinary user work supplies evidence. Preserve AgentsMD's deterministic repository, package, distribution, and installation release proof, with user-owned behavioral Live Verification after release. Do not introduce synthetic model-run scenarios as an automatic release gate.

The integration succeeds if an agent gains better technical judgment without a second workflow authority: fewer invented explanations, more decisive experiments, designs with less caller coordination, truthful evidence, useful recovery, and durable lessons that change future decisions.

[architect]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/architect/SKILL.md
[arena]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/arena/SKILL.md
[automate-me]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/automate-me/SKILL.md
[blast-radius]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/blast-radius/SKILL.md
[bro]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/bro/SKILL.md
[create-verification-skill]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/create-verification-skill/SKILL.md
[figure-it-out]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/figure-it-out/SKILL.md
[how]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/how/SKILL.md
[interrogate]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/interrogate/SKILL.md
[maintain-verification-skill]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/maintain-verification-skill/SKILL.md
[make-bot-ui]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/make-bot-ui/SKILL.md
[no-comments]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/no-comments/SKILL.md
[poteto-mode]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/SKILL.md
[principle-attack-the-premise]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-attack-the-premise/SKILL.md
[principle-boundary-discipline]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-boundary-discipline/SKILL.md
[principle-build-the-lever]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-build-the-lever/SKILL.md
[principle-encode-lessons-in-structure]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-encode-lessons-in-structure/SKILL.md
[principle-exhaust-the-design-space]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-exhaust-the-design-space/SKILL.md
[principle-experience-first]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-experience-first/SKILL.md
[principle-fix-root-causes]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-fix-root-causes/SKILL.md
[principle-foundational-thinking]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-foundational-thinking/SKILL.md
[principle-guard-the-context-window]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-guard-the-context-window/SKILL.md
[principle-laziness-protocol]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-laziness-protocol/SKILL.md
[principle-make-operations-idempotent]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-make-operations-idempotent/SKILL.md
[principle-migrate-callers-then-delete-legacy-apis]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md
[principle-minimize-reader-load]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-minimize-reader-load/SKILL.md
[principle-model-the-domain]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-model-the-domain/SKILL.md
[principle-never-block-on-the-human]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-never-block-on-the-human/SKILL.md
[principle-outcome-oriented-execution]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-outcome-oriented-execution/SKILL.md
[principle-prove-it-works]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-prove-it-works/SKILL.md
[principle-redesign-from-first-principles]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-redesign-from-first-principles/SKILL.md
[principle-separate-before-serializing-shared-state]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md
[principle-sequence-verifiable-units]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-sequence-verifiable-units/SKILL.md
[principle-subtract-before-you-add]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-subtract-before-you-add/SKILL.md
[principle-test-behavior-not-implementation]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-test-behavior-not-implementation/SKILL.md
[principle-type-system-discipline]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/principle-type-system-discipline/SKILL.md
[recall]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/recall/SKILL.md
[reflect]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/reflect/SKILL.md
[setup-pstack]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/setup-pstack/SKILL.md
[show-me-your-work]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/show-me-your-work/SKILL.md
[swarm]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/swarm/SKILL.md
[tdd]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/tdd/SKILL.md
[teach]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/teach/SKILL.md
[technical-writing]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/technical-writing/SKILL.md
[typescript-best-practices]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/typescript-best-practices/SKILL.md
[unslop]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/unslop/SKILL.md
[why]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/SKILL.md
[benny-setup]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/automations/benny/skills/setup-benny/SKILL.md
[benny-triage]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/automations/benny/skills/triage-issue-reports/SKILL.md
[benny-reproduce]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/automations/benny/skills/reproduce-and-fix-issues/SKILL.md
[pb-authoring-a-skill]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/authoring-a-skill.md
[pb-autonomous-run]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/autonomous-run.md
[pb-autopilot-full]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/autopilot-full.md
[pb-autopilot-stack]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/autopilot-stack.md
[pb-babysit]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/babysit.md
[pb-bug-fix]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/bug-fix.md
[pb-eval]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/eval.md
[pb-feature]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/feature.md
[pb-hillclimb]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/hillclimb.md
[pb-investigation]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/investigation.md
[pb-multi-phase-plan]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md
[pb-opening-a-pr]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/opening-a-pr.md
[pb-orchestrate]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/orchestrate.md
[pb-pause-safely]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/pause-safely.md
[pb-perf-issue]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/perf-issue.md
[pb-prototype]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/prototype.md
[pb-refactoring]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/refactoring.md
[pb-runtime-forensics]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/runtime-forensics.md
[pb-session-pickup]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/session-pickup.md
[pb-shipping]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/shipping.md
[pb-trace-forensics]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/trace-forensics.md
[pb-visual-parity]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/visual-parity.md
[pb-worktree-cleanup]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/playbooks/worktree-cleanup.md
[license]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/LICENSE
[epistemics]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/epistemics.md
[src-code]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/code-archaeology.md
[src-tracker]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/linear.md
[src-documents]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/notion.md
[src-chat]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/slack.md
[src-observability]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/datadog.md
[src-errors]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/sentry.md
[src-analytics]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/databricks.md
[src-incidents]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/why/references/sources/incident-postmortem.md
[control-adapter]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/automations/benny/skills/reproduce-and-fix-issues/references/control-adapter.md
[ts-patterns]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/typescript-best-practices/references/patterns.md
[orch-store]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/orch/store.ts
[orch-cli]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/orch/orch.ts
[bootstrap]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/bootstrap.ts
[check-plan]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/check-plan.mjs
[decision-log]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/show-me-your-work/scripts/log.sh
[benny-triage-template]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/automations/benny/templates/triage-automation-prompt.md
[worktree-audit]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/worktree-audit.sh
[watch-policy]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/watch-pr/policy.ts
[watch-github]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/watch-pr/github.ts
[watch-policy-tests]: https://github.com/cursor/plugins/blob/b42effe0aa50f59c693d7e2924714e015e00bf7c/pstack/skills/poteto-mode/scripts/watch-pr/policy.test.ts
