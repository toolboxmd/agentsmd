# Model Routing Benchmark V3

This package implements the fail-closed execution controller for AgentsMD
Issue #33. Its purpose is to measure whether the lowest-load reliable,
predeclared model route preserves accepted quality on representative ToolboxMD
development work. It does not change the global routing contract.

This README describes the frozen experiment and how to operate it. It does not
claim that preflight, a model cell, the independent canary audit, or the Grok
evaluation has run. Results belong in controller evidence and the final
benchmark report, not in this package description.

## Local trust boundary

V3 is a local, non-adversarial decision experiment. It trusts the local user,
this controller, the pinned Codex client, CodexBar observer, and Grok CLI,
macOS, Seatbelt, and the private Darwin coalition interfaces used by the
controller. It makes one additional explicit assumption: a candidate route
will not intentionally use a same-user macOS broker, such as `launchctl`,
`open`, or `osascript`, to escape the controller's process attribution. Known
broker paths are observed on a best-effort basis and retained in the receipt,
but that observation is not a general hostile-code containment claim.

It does not claim isolation from a malicious local operator, administrator or
kernel compromise, a compromised Codex client, falsified controller evidence,
or intentional escape through an arbitrary same-user macOS broker. If that
assumption is unacceptable, this benchmark must stop before a model call and
move to a separately administered Linux container or dedicated UID boundary.

A separate `HOME`, `CODEX_HOME`, SQLite home, and temporary directory alone is
not isolation. The named Codex permission profile, enforced through the local
macOS Seatbelt boundary, is the candidate command boundary. The profile denies
candidate command network access and access to the hidden verifier,
authentication target, controller state, and real Codex memory. Candidate
workspaces are plain trees without Git metadata. Candidate model stages, split
hidden-verifier peers, the OpenBot public verifier, the Luna reviewer, and the
Grok evaluator are launched in transient same-user launchd services. The
controller binds each such service to a distinct resource and jetsam
coalition, tears it down, and records service removal, coalition reaping, and
terminal member state. Environment markers and process groups are not process
identity or cleanup evidence. Reviewer commands use a separate read-only
profile.

The `use-grok` and `karpathy-pointer` public verifiers do not use the launchd
coalition path. They run through the pinned frozen-v2 Docker image under the
same-user local Docker Desktop daemon, which is part of this local trust
boundary and is not an independently administered verifier. Their containers
have no network, a read-only root and bind mounts, no added capabilities,
`no-new-privileges`, a non-root UID, bounded resources, and a private temporary
filesystem. This Docker exception applies only to those two public verifiers;
their hidden verifiers continue to use the split launchd path. Only the host
Docker CLI is launchd-supervised; verifier processes inside the container are
owned by the trusted Docker daemon and are outside the launchd coalition
receipt.

Hidden verification has two separate Seatbelt-constrained peers. The trusted
driver owns the hidden assertions; the worker is the only peer allowed to load
candidate code. A narrow canonical JSONL mediator binds both peers to the task,
candidate manifest, component hashes, and shared deadline. The worker cannot
read the driver's hidden inputs, and the driver cannot import candidate code.
Each peer receives separate inherited read and write pipes. No socketpair is
shared between the peers. Both peer runtimes and the mediator are inside the
outer launchd coalition.

The OpenBot peers have different signal authority. The trusted hidden driver
receives unrestricted Seatbelt signal permission, but its exact frozen source
uses only signal 0 to observe whether candidate-owned PIDs and process groups
are absent. It never sends a nonzero cleanup signal and cannot import candidate
code. The candidate-importing worker receives only
`(allow signal (target same-sandbox))`. It uses that authority to manage its
own same-invocation descendants, including ACP process groups whose direct
leader has exited and whose remaining members have been reparented. The worker
does not receive unrestricted same-user signal authority. Before any model
call, preflight launches an unrelated control through a separate
`sandbox-exec` invocation with the identical worker profile. The trusted driver
must observe the control PID and PGID with signal 0, while a separate worker
profile invocation must receive `EPERM` or `EACCES` for both targets and leave
the control alive. These permissions and probes support deterministic cleanup
inside the stated local, non-adversarial boundary; they are not a hostile-code
containment claim.

The frozen `use-grok` and `karpathy-pointer` verifiers invoke legacy Bash tests
that create heredoc temporary files. Their worker profile therefore permits
only `/private/var/tmp/sh-thd-[0-9]+` for that runtime behavior. The controller
records the exact `sh-thd-*` names before and after verification and fails the
boundary unless the two name sets are equal. The exception does not apply to
the OpenBot worker and does not permit general temporary-file access.

The no-model native preflight must prove the actual profile before any model
cell can run. These controls are local containment under the stated trust
model, not an independently administered security boundary.

## Frozen workload

The fixtures reconstruct three exact accepted ToolboxMD histories without
placing the accepted answer in the candidate workspace:

| Task | Complexity | Required change | Allowed production scope |
|---|---|---|---|
| `use-grok` | Low | Prepare a portable three-host release with consistent Codex, Claude Code, and Grok Build contracts | Seven release, manifest, documentation, and test paths |
| `karpathy-pointer` | Medium | Exclude proven pointer pages from wiki navigation and discovery while handling malformed or unreadable input conservatively | Three index, discovery, and test paths |
| `openbot-acp` | Hard | Bound aggregate ACP output across asynchronous startup, attachment, active Turn, cancellation drain, and idle phases | `daemon/src/acp.ts` only |

Each baseline must fail both its public and hidden verifier, while the
controller-built known-good tree must pass both. Fixture construction imports
pinned commits into controller-owned bare clones and exports ordinary files
into the state root. It never edits the source repositories. Candidate changes
occur only in per-attempt copies below the controller state root.

## Frozen cells and order

The seven unique comparisons run at most once in this exact order:

| Order | Cell | Route | Role |
|---:|---|---|---|
| 1 | `use-grok--terra-high` | Terra, high | Canary |
| 2 | `use-grok--spark-high` | Spark, high | Low-complexity comparison |
| 3 | `openbot-acp--sol-high` | Sol, high | Hard-task comparison |
| 4 | `openbot-acp--sol-max` | Sol, max | Hard-task control |
| 5 | `karpathy-pointer--sol-high` | Sol, high | Medium-task comparison |
| 6 | `karpathy-pointer--terra-high` | Terra, high | Medium-task route |
| 7 | `karpathy-pointer--sol-max` | Sol, max | Medium-task control |

The canary is Terra high. Spark is not used for the canary. After a successful
canary, the controller still blocks order 2 until one independent audit accepts
the exact canary result and artifact hashes.

There is no batch runner or arbitrary cell selector. `run-next` authorizes only
the next frozen cell. An attempt is reserved atomically before model execution,
and an existing attempt directory makes a repeated attempt invalid.

## Gates and cell lifecycle

Before model execution, the fixed package needs an exact-hash review artifact
at `<STATE_ROOT>/package-review.json`. It must bind the current definition and
strict package hashes and contain exactly three clean, independent review axes:
standards, specification, and security. All three must report `PASS`, with
distinct reviewers and no findings. The required shape is in
`schemas/package-review.schema.json`. Any package byte change invalidates the
gate.

The single-use no-model preflight then proves:

- pinned Codex, launcher, Node, Node OpenSSL configuration, controller Python,
  Command Line Tools Python 3.9.6 used by the split verifier, and the sandboxed
  CodexBar observer identities;
- both Codex model-facing response schemas use only the package's reviewed
  OpenAI Structured Outputs keyword allowlist, require every object field, and
  deny additional properties before any fixture work or provider request;
- frozen v2 dependency integrity and exact source commit and tree identities;
- fixture construction, allowed-path scope, and baseline versus known-good
  discrimination for all three tasks;
- candidate write access only where declared and denial of hidden verifier,
  accepted-answer files, authentication, controller, memory, and external
  targets;
- denial of TCP and Unix-socket egress, process timeout behavior, launchd
  coalition binding and terminal reap proof, detached-descendant cleanup, and
  exact positive controls;
- split-driver and candidate-worker separation, including denial of hidden
  driver material to the worker and denial of candidate execution to the
  driver; and
- candidate working directory, workspace root, exact effective managed-policy
  semantics, and absence of injected Skills in the isolated prompt input.

Codex 0.149.1 does not expose the named profile ID in `debug prompt-input`.
The exact `routing_candidate` ID is instead bound by the generated config hash
and exercised directly by every `codex sandbox -P routing_candidate` probe.
The live Unix-socket control uses a short, temporary controller-created path
under `/private/tmp` to stay within macOS `AF_UNIX` limits; the path is removed
when the no-model probe ends and is recorded in the receipt.
The controller also recomputes the strict package hash and all base,
historical, candidate, and known-good fixture tree hashes immediately before
and after the native probes.

Every cell has one inclusive 600-second deadline shared by implementation,
immutable artifact snapshotting, deterministic public and hidden verification,
and one read-only Luna max review.
A fixed `TSX_DISABLE_CACHE=1` removes optional compiler-cache writes. Verifier
and reviewer profiles keep the artifact read-only and may write only the
controller-cleaned `.runner-tmp` needed by the OpenBot implementation itself.
A safely completed implementation receives review even when deterministic
verification fails. Unsafe scope or telemetry stops before review. Reaching
the inclusive deadline is `TIMEOUT`.

The controller copies a baseline snapshot before implementation and publishes
the implementation receipt once, then copies the candidate artifact into a
second immutable controller-owned snapshot. It derives Luna's canonical review
range only from those two snapshots, with sorted changed paths, exact entry
metadata, and base64 bytes for ordinary single-link files. The identical range
is persisted in the attempt and overlaid at
`review-workspace/.benchmark/review-range.json`; that overlay is controller
evidence, not candidate output or allowed production scope. Luna receives and
echoes the exact artifact and range hashes and may read surrounding after-state
code from the review workspace. The snapshot manifests and `artifact.json`
bind the implementation receipt, declared scope, before and after trees, and
every later verification or review input. Implementation, artifact,
verification, review, result, and collection evidence are each one-shot
canonical receipts. A later stage never reads the mutable candidate tree.

Every outcome terminalizes its cell and forbids a retry. After the accepted
canary audit, scored outcomes such as an implementation failure, route
unavailability, quota exhaustion, timeout, verifier failure, or review finding
remain results and allow the next frozen cell to run. A boundary failure,
controller error, telemetry failure, unsafe scope, or unsafe telemetry stops
later execution. Terminal statuses are exactly `ACCEPTED`, `BOUNDARY_FAILURE`,
`CONTROLLER_ERROR`, `IMPLEMENTATION_FAILED`, `PROVIDER_UNAVAILABLE`,
`QUOTA_EXHAUSTED`, `TELEMETRY_FAILURE`, `TIMEOUT`, `UNSAFE_SCOPE`,
`UNSAFE_TELEMETRY`, `VERIFICATION_FAILED`, and `REVIEW_BLOCKED`. There is no
automatic retry, repair, replacement run, or rereview.

## Controller usage

Run from the AgentsMD repository root with a fresh persistent state root outside
the repository. Do not use `/tmp` or `/private/tmp` for benchmark state. Replace
the two placeholders below with absolute paths. `AUTH_SOURCE` must identify the
existing authenticated Codex JSON file, and the state root must be new for this
run.

```bash
ROUTING_V3_PYTHON=/opt/homebrew/opt/python@3.14/bin/python3.14
ROUTING_V3_CONTROLLER="$PWD/evals/model-routing-v3/controller.py"
ROUTING_V3_STATE_ROOT=/ABSOLUTE/CONTROLLER-OWNED/PERSISTENT/STATE-ROOT
ROUTING_V3_AUTH_SOURCE=/ABSOLUTE/PATH/TO/AUTHENTICATED-CODEX-AUTH.JSON

ROUTING_V3_COMMON=(
  --state-root "$ROUTING_V3_STATE_ROOT"
  --use-grok-repo /Users/lukaszmaj/dev/toolboxmd/use-grok
  --karpathy-repo /Users/lukaszmaj/dev/toolboxmd/karpathy-wiki
  --openbot-repo /Users/lukaszmaj/.codex/worktrees/dee9/openbot
  --openbot-runtime-source /Users/lukaszmaj/dev/toolboxmd/openbot/node_modules
  --codex-executable /Users/lukaszmaj/.nvm/versions/node/v22.23.1/lib/node_modules/@openai/codex/node_modules/@openai/codex-darwin-arm64/vendor/aarch64-apple-darwin/bin/codex
  --codex-launcher /Users/lukaszmaj/.nvm/versions/node/v22.23.1/lib/node_modules/@openai/codex/bin/codex.js
  --node-executable /Users/lukaszmaj/.nvm/versions/node/v22.23.1/bin/node
  --auth-source "$ROUTING_V3_AUTH_SOURCE"
  --codexbar-executable /Applications/CodexBar.app/Contents/Helpers/CodexBarCLI
  --memory-root /Users/lukaszmaj/.codex/memories
)
```

Run the package tests without writing Python bytecode:

```bash
PATH=/Users/lukaszmaj/.nvm/versions/node/v22.23.1/bin:/usr/bin:/bin:/usr/sbin:/sbin \
PYTHONDONTWRITEBYTECODE=1 "$ROUTING_V3_PYTHON" -B -m unittest discover \
  -s evals/model-routing-v3/tests -p 'test_*.py' -v
```

After the package bytes are final, obtain the two hashes that the three-axis
review must bind:

```bash
"$ROUTING_V3_PYTHON" -B -c '
import sys
from pathlib import Path
root = Path("evals/model-routing-v3").resolve()
sys.path.insert(0, str(root))
import controller
print("definition_sha256=" + controller.sha256_file(root / "definition.json"))
print("package_sha256=" + controller.strict_package_sha256(root))
'
```

Only the independent review producer should write the resulting canonical JSON
object to `$ROUTING_V3_STATE_ROOT/package-review.json`. With the reviewed
package unchanged, run the single-use no-model preflight:

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" preflight
```

Inspect `preflight-receipt.json` and `state.json`. If and only if preflight is
`PASS`, start the sole canary:

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" run-canary
```

An independent auditor must inspect the canary evidence and produce a canonical
artifact matching `schemas/canary-audit.schema.json`. Bind it once:

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" validate-canary-audit \
  /ABSOLUTE/PATH/TO/CANARY-AUDIT.JSON
```

If the canary and its audit are both accepted, invoke the next command once,
inspect the terminal evidence, and repeat manually for each remaining frozen
cell. The command cannot skip or select a route.

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" run-next
```

Collect all terminal results into one hash-bound artifact:

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" collect
```

All commands fail closed. Do not delete or reuse a failed state root to turn a
terminal result into a retry. Correcting package code requires a new exact-hash
review and a fresh state root.

## Telemetry and quota evidence

Each implementation and review stage starts with fresh isolated Codex state.
Route identity comes from exactly one promoted rollout `turn_context`, bound
to the planned model, effort, permission profile, OpenAI provider, pinned Codex
CLI version, execution thread, and terminal task event. The final rollout token
record must exactly match `codex exec --json` usage.

The normalized receipt records input, cached input, derived uncached input,
cache-write input, output, and reasoning-output tokens without double counting.
Reasoning output remains a subset of output. Router observations are diagnostic
only and cannot establish route identity. Only raw execution JSONL, the
promoted rollout JSONL, stderr, and the structured last message remain private
in the mode-0700 attempt tree for independent audit. Before retaining them, the
controller scans the complete `CODEX_HOME/sessions` tree without following
aliases, propagates read errors, enforces a fixed entry bound, and requires one
ordinary single-link rollout. It scans every retained artifact's exact bytes
for the copied auth document, OAuth fields, and token values, then binds the
admitted files by relative path, byte count, and SHA-256 in both successful and
terminal-failure evidence. It then deletes the fresh `HOME`, `CODEX_HOME`,
`CODEX_SQLITE_HOME`, candidate `.runner-tmp`, copied auth link, and auth target.
Before the inclusive deadline, an unreadable artifact, credential match,
unexpected stage entry, special runtime root, or incomplete cleanup is a
boundary failure; reaching the inclusive deadline remains `TIMEOUT` by the
lifecycle contract. There is no broader retained Codex state.

There is no numerical quota ceiling in this experiment. A valid before and
after CodexBar observation is still required for every model stage. Evidence
stores a hash of the raw provider response and whitelisted percentage windows,
not account identity. A delta is reported only when the same quota window is
comparable across both observations. Missing windows, changed windows, unknown
boundaries, or reset boundaries remain explicit and receive no invented delta.
A missing observation blocks a decision-ready claim.

## Evidence layout

Durable evidence is under the chosen state root:

- `package-review.json` binds the three independent package reviews;
- `preflight-receipt.json`, `fixtures.json`, `fixtures/`, and
  `native-preflight/` bind no-model readiness and exact fixture trees;
- `state.json` is the canonical lifecycle state and frozen-order authority;
- `attempts/<CELL>/reservation.json` proves the single attempt reservation;
- `attempts/<CELL>/candidate/` is the implementation workspace and is not a
  later-stage input;
- `attempts/<CELL>/baseline-snapshot/`, `artifact-snapshot/`, `artifact.json`,
  and `review-range.json` bind the immutable baseline, accepted artifact, and
  exact baseline-to-artifact Luna range;
- `attempts/<CELL>/review-workspace/.benchmark/review-range.json` is the
  identical controller-owned range overlay presented to Luna;
- `attempts/<CELL>/<STAGE>/` retains only the produced subset of four private
  direct audit files: raw execution, the promoted rollout, stderr, and the
  structured response;
- `attempts/<CELL>/verification-receipt.json`, `review-receipt.json`, and
  `result.json` bind verification, review, timing, telemetry, quota, and typed
  terminal evidence;
- `canary-audit.json` binds the independent canary decision;
- `collection.json` binds every terminal result to lifecycle state; and
- `evaluator/` contains the one-shot public bundle, exact bounded prompt,
  private mapping and preparation commitment, copied canonical schema,
  Seatbelt profile and no-model preflight receipt, transient-auth cleanup
  receipt, exact evaluator-run retention receipt, pinned Grok invocation
  receipt, raw response, and validated anonymous result.

The controller removes the copied authentication link and target plus every
fresh Codex runtime root after each model stage. Raw stage evidence remains
private under the attempt directory and is hash-bound by the durable receipt.

## Grok xhigh comparison

The sole evaluator call is permitted only after all seven cells have a scored
terminal result and every task retains at least two accepted artifacts. Failed
results remain in `collection.json` but are excluded from the anonymous
comparison. The controller creates a public bundle from immutable accepted
artifact snapshots and a separate private mapping in a one-shot committed
pair. A recorded non-empty seed shuffles task and variant order. The public
bundle contains task text and artifact files but hides route and model
identities behind task and variant aliases. The mapping, preparation receipt,
and all route identity stay outside the evaluator workspace.

```bash
"$ROUTING_V3_PYTHON" -B "$ROUTING_V3_CONTROLLER" \
  "${ROUTING_V3_COMMON[@]}" run-evaluator \
  --grok-executable /Users/lukaszmaj/.grok/downloads/grok-1.0.13-macos-aarch64 \
  --grok-auth-source /Users/lukaszmaj/.grok/auth.json
```

Use the exact pinned evaluator executable:

```text
/Users/lukaszmaj/.grok/downloads/grok-1.0.13-macos-aarch64
grok 1.0.13 (5e9a58528b76) [stable]
isolated-home output: grok 1.0.13 (5e9a58528b76)
sha256 8669e0fdadceec25b8c159c355f427ffbd82583525d774b6ab1522197ea83b80
```

The controller builds one size-bounded prompt from fixed instructions plus the
exact canonical anonymous bundle bytes and SHA-256. It retains the standalone
bundle, copies the canonical schema into the evaluator workspace, and binds all
three hashes before the call. It then invokes the pinned local Grok Build CLI
once through `/usr/bin/sandbox-exec -f` with explicit `--model grok-4.6` and
`--reasoning-effort xhigh`, plus `--prompt-file`, `--verbatim`, the fixed
evaluator `--cwd`, `--always-approve`, `--output-format json`, the locked
`--json-schema`, and the frozen tool-free flags. It records the executable and
profile identities, argument hash, raw stdout and stderr, process-containment
receipt, anonymous input commitment, and validated result. It never resumes,
follows up, retries, repairs, or makes a second evaluator call.

The evaluator gets fresh `HOME`, `GROK_HOME`, `TMPDIR`, and XDG directories and
a replacement-only environment that disables updater, memory, subagent,
workflow, web-fetch, telemetry, trace, feedback, and external OTEL surfaces.
The explicit auth source must be an absolute owner-owned `0600` ordinary
single-link file no larger than 4 MiB. The controller opens it nonblocking with
no-follow, validates the descriptor as regular before reading, and copies it
with exclusive-create checks into the fresh Grok home. It admits either
deadline-fresh access or a non-empty refresh credential, derives in-memory
auth markers, verifies the source stayed byte-identical, and removes the
transient home and auth after every terminal outcome. Auth path, content,
size, digest, token values, expiry timestamps, and markers are not persisted.
The pinned trusted CLI can read that transient copied auth file during its sole
invocation.

After success, process failure, invalid output, timeout, or controller failure,
the controller admits only the six fixed evaluator-run files. It reads each
ordinary single-link artifact under a fixed byte bound and scans its exact
bytes for the in-memory auth markers. An unexpected, aliased, special,
unreadable, oversized, or credential-bearing artifact deletes the complete
`run/` directory and raises a boundary failure without secret-bearing error
detail. Clean artifacts are bound by relative path, byte count, and SHA-256 in
`evaluator-run-retention.json`, `auth-cleanup.json`, and the final controller
result. A valid success additionally requires all six files and reconciles
their hashes and sizes with the evaluator outcome, raw response bindings,
usage bindings, result, and run receipt. A preflight failure removes its exact
fresh runtime roots, probe,
profiles, process output, and partial receipt while preserving the anonymous
input commitment for audit.

The default-deny Seatbelt profile grants exact executable read/map, exact
bundle/prompt/schema reads, and writes only under fresh home, temporary, and
XDG-runtime roots. It grants no process-fork or broad process authority. Before the sole
call, a no-model probe under the same file/network policy projection proves the
required reads, fresh-home/TMP write controls, direct and symlink denials for
private mapping, attempts, fixture sources, and memory, IPv4/IPv6 localhost
denial, a non-443 TEST-NET TCP denial, and a representative Unix syslog-socket
denial. The production profile also runs the exact pinned Grok `--version` in
the isolated environment. The Unix probe is a sampled control; this package
does not claim that every possible Unix socket allowed by imported macOS system
policy was enumerated or denied.

Outbound network authority is limited by Seatbelt to mDNSResponder and remote
TCP port 443, with localhost explicitly denied and inbound connections denied.
That IP/port policy is not proof of provider hostname attribution. The one
trusted CLI invocation may internally refresh authentication or retry HTTP
requests without authorizing a second evaluator invocation.

Grok CLI 1.0.13 exposes no account-quota snapshot command. The controller
therefore records both before and after account-quota observations as typed
`UNAVAILABLE` receipts, retains their hashes and the raw Grok response envelope,
and invents no account-level delta. All Grok evaluator usage is classified as
experiment overhead, not as a routing-cell metric.

## Explicit non-claims

This package does not claim a universal model ranking, hostile-user isolation,
protection from an administrator or compromised client, a numerical quota
stop-loss, or completed Live Verification. It does not authorize a routing
contract change, retry, repair, rereview, merge, release, publication,
installation, or deployment.

The benchmark becomes decision-ready only after the frozen lifecycle produces
complete accepted evidence, the anonymous Grok xhigh comparison validates, and
the final report recommends adopt, narrow, replicate, or reject from the
observed results.
