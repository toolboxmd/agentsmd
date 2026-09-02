# Model Routing Benchmark V2 Readiness

This directory is a zero-spend replacement definition for Issue #33. It is an
authorized research detour from the current Project Objective. It does not
change the global agent contract or establish a routing policy.

The package intentionally has no model runner. It cannot invoke a candidate,
Luna reviewer, Grok evaluator, repair, retry, or multi-cell command. Its only
jobs are to freeze the experiment definition, prove deterministic fixture
discrimination, validate filesystem contracts, and emit replayable evidence
for why paid execution remains blocked.

This package can never emit `READY` or authorize model spend. Supplying quota,
adapter, receipt, or review strings cannot clear its permanent
`paid_execution_surface_absent` and
`trusted_external_boundary_verifier_absent` blockers. A future paid run needs a
separate successor package with its own exact-hash review.

## Current stop

Paid execution remains blocked. A separately reviewed successor package would
need all of the following before its first candidate call:

1. the user's exact numerical quota stop-loss ceiling;
2. a concrete external candidate boundary with an independently measured,
   signed receipt;
3. an exact runner, prompt, output schema, profile, telemetry collector, and
   stop-first state machine;
4. signed stage and canary evidence derived from controller-collected raw data,
   not caller-provided assertions; and
5. another independent standards, specification, and security review of the
   complete execution surface.

None of these values may be supplied as an unbound command-line override. A
receipt schema by itself is not boundary evidence. The lifecycle in
`definition.json` freezes requirements only; this package deliberately exposes
no stage validator, canary transition, or next-cell authorization function.

The current host cannot supply or independently attest the required boundary.
Codex 0.149.1 has only its Darwin ARM64 native package installed. Docker
Desktop is the only local Linux facility, has no Linux Codex package or
prepared controller, and is owned by the same macOS principal as the Codex
authentication and Docker daemon. Nested macOS Seatbelt profiles fail with
`sandbox_apply: Operation not permitted`. The existing no-network Docker
verifier is useful containment, but it is not a candidate-stage adapter or an
independent issuer.

The smallest external procedure needs explicit authority to provision a fresh,
pinned Linux controller under a separate trust principal, install the exact
Linux Codex client, provision only its provider authentication, and create
separate no-network candidate and verifier namespaces without host sockets. An
issuer key unavailable to this controller must sign a probe receipt bound to
the definition, package, adapter, and runtime identities. A successor package
can pin those identities and undergo another exact-hash review. Until that
external procedure exists, the adapter, issuer, and receipt remain null.

## Frozen comparison

The route named `adaptive` keeps the historical cell identifier, but it is a
fixed predeclared assignment, not dynamic routing:

- use-grok: GPT-5.3 Codex Spark at high effort;
- Karpathy pointer: GPT-5.6 Terra at high effort;
- controls: GPT-5.6 Sol at high and max effort; and
- review: GPT-5.6 Luna at max effort, only after a strictly accepted
  implementation and deterministic proof.

The stricter replacement contract overrides the old repair loop. Any anomaly,
timeout, schema failure, scope breach, telemetry gap, verifier failure,
unexpected quota movement, or review finding stops the experiment. There is no
automatic repair or retry.

`use-grok--adaptive` is the only future canary. The remaining five cells need a
separate accepted canary-audit artifact bound to the exact canary evidence. Its
auditor must be independent of the candidate, implementation controller, and
boundary issuer.

## Model-stage deadline

Every possible model stage kind shares one maximum of 600 seconds:
implementation, initial review, repair, and rereview. Listing repair and
rereview here does not enable them. Their frozen call counts remain zero and
automatic repair remains disabled.

The eventual trusted controller must record
`actual_terminal_duration_seconds` for every terminal outcome from its
monotonic clock, measured from process start through terminal process-tree
observation. The deadline is inclusive. Reaching 600 seconds is `TIMEOUT`, the
cell stops, and cleanup cannot enqueue an automatic retry or replacement run.
Cleanup overhead may make the recorded duration greater than 600 seconds. This
readiness-only package has no model runner, so it freezes the evidence contract
without claiming to have collected paid-stage duration evidence.

## Source and known-good language

The two historical commits are source material, not exact known-good commits.
The use-grok commit has the historical changelog date `2026-08-27`, while the
packet fixes the benchmark date at `2026-08-31`. The Karpathy commit implements
pointer filtering but does not satisfy the conservative unreadable, non-UTF-8,
and non-mapping cases. The reviewed files in `known-good/` make those limited
adjustments. Preflight hashes both patches and the resulting strict tree
manifests.

Candidate workspaces must be plain exported trees with no `.git`. Trusted Git
commands must never run against candidate-controlled data. Preflight imports
the two pinned source repositories into controller-owned bare clones without
running `git status` or repository fsmonitor configuration. It then exports
exact commit objects into plain trees. Before any trusted read, the controller
rejects symlinks, hard links, special files, path escapes, backslash path
aliases, oversized files, excessive depth, excessive directory entries, and
filesystem identity changes. Tree manifests bind regular files, directories,
normalized modes, and content.

The Karpathy source tree contains `CLAUDE.md` as a symlink. Its exclusion is an
explicit part of `definition.json`; preflight still binds the original commit
and tree, the filtered archive, and the resulting regular-file manifest. No
link is followed or silently materialized.

The controller-owned public use-grok verifier never executes candidate-owned
tests. Behavioral verifiers for Karpathy and the hidden use-grok test-mutation
checks do execute workspace code. Current preflight runs every verifier inside
the already-installed Docker image pinned by exact image ID in
`definition.json`, with no network, a read-only root, read-only package and
workspace mounts, a non-root user, no capabilities, no new privileges, bounded
PIDs, CPU, memory, file descriptors, output, and wall time, and a private
temporary filesystem. It never pulls an image. This verifier containment does
not substitute for the still-missing external candidate boundary.

The package itself is copied into a private repository-shaped snapshot before
any test or verifier runs. The initial snapshot manifest and final package
manifest must match. Known-good patch scope is recomputed from strict before
and after manifests and must remain within each task's frozen paths.

## No-model commands

```bash
python3 -m unittest discover -s evals/model-routing-v2/tests -p 'test_*.py'

python3 evals/model-routing-v2/readiness.py check \
  --definition evals/model-routing-v2/definition.json \
  --use-grok-repo /Users/lukaszmaj/dev/toolboxmd/use-grok \
  --karpathy-repo /Users/lukaszmaj/dev/toolboxmd/karpathy-wiki \
  --output /private/tmp/agentsmd-routing-v2-readiness.json

python3 evals/model-routing-v2/readiness.py validate-report \
  --definition evals/model-routing-v2/definition.json \
  --use-grok-repo /Users/lukaszmaj/dev/toolboxmd/use-grok \
  --karpathy-repo /Users/lukaszmaj/dev/toolboxmd/karpathy-wiki \
  --report /private/tmp/agentsmd-routing-v2-readiness.json
```

`validate-report` reruns all no-model checks from a fresh private snapshot and
compares stable proof with the existing report. Raw verifier and test-output
hashes are retained as per-run evidence, but they are not required to repeat
byte-for-byte because trusted test output can contain run timing and temporary
paths. Their terminal status, return code, verifier hash, workspace hash,
source identity, patch identity, and all other stable evidence must replay
exactly.

The expected current outcome is `BLOCKED` with
`paid_execution_authorized=false`. This is a successful fail-closed readiness
check, not a benchmark run. The static no-paid-command unit test is a regression
heuristic. The stronger control is the exact CLI allowlist plus the permanent
zero-spend report gate.
