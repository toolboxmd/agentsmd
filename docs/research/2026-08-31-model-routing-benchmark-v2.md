# Model Routing Benchmark V2 Readiness

## Outcome

Issue [#33](https://github.com/toolboxmd/agentsmd/issues/33) does not yet have a
valid model-routing result. The previous six-cell experiment is rejected as
quantitative evidence. The replacement work produced a reviewed, deterministic,
zero-spend readiness package and then stopped before the canary because the
required quota and candidate-isolation gates are not available.

This is the intended result of the fail-closed contract. No candidate, Luna
reviewer, Grok evaluator, repair, retry, or other benchmark model call occurred
during the V2 replacement work.

## Rejected predecessor

Historical experiment `d9f83255-1560-4851-a6a3-74a7c1a84abd` completed its
orchestration but did not produce one strictly accepted cell:

- accepted completion: 0 of 6;
- protocol-complete implementation and review evidence: 0 of 6;
- exact usage-complete evidence: 0 of 6; and
- price-equivalent completeness: false for every route.

Its artifacts under
`/private/tmp/agentsmd-model-routing-20260831-v3/` may support qualitative
debugging only. They cannot compare route quality, time, tokens, or cost. The
hardened predecessor preflight at
`/private/tmp/agentsmd-routing-preflight-33-hardened-v4.json` also remained
blocked by its missing external isolation receipt. Neither artifact authorizes a
rerun.

## Frozen replacement

The reviewed package lives in `evals/model-routing-v2/`.

- Package SHA-256:
  `c5e75781469cb4ef0ddb4e2a5b9706aa409e69327e0b4ff21c3cc83aa5dfda94`
- Definition byte SHA-256:
  `ed5b9589eced9ba8420efcaec9f6f5d21b445a242d4944aab63213a3deb07cac`
- Definition canonical semantic SHA-256:
  `903cdf41665be748902a7fd515b29e289d294e6a0a899726ed969bd789bdbedd`
- Independent review artifact SHA-256:
  `98dc1d9dc1e681db254c8a834d2112a3ed82c5da5724be3b6796d0392bd4e05a`

The historical `adaptive` cell name now means a fixed, predeclared assignment:

| Route | use-grok | Karpathy pointer |
| --- | --- | --- |
| adaptive | GPT-5.3 Codex Spark high | GPT-5.6 Terra high |
| sol-high | GPT-5.6 Sol high | GPT-5.6 Sol high |
| sol-max | GPT-5.6 Sol max | GPT-5.6 Sol max |

`use-grok--adaptive` is the sole future canary. The package freezes six unique
cells, no automatic retry or repair, Luna max only after trusted deterministic
proof, and Grok xhigh only after all cells. It deliberately contains no runner,
stage validator, canary transition, or next-cell authorization surface.

## Follow-up contract

The user confirmed that only `use-grok--adaptive` may run first and that an
independent audit of its exact evidence must be accepted before any remaining
cell. Paid execution remains unauthorized because the user has not supplied an
exact numerical quota stop-loss ceiling.

The old 300-second implementation and 240-second initial-review limits are
replaced by one inclusive 600-second maximum for implementation, initial
review, repair, and rereview. A future trusted controller must record
`actual_terminal_duration_seconds` from its monotonic clock for every terminal
outcome. Reaching 600 seconds is `TIMEOUT`, stops the cell, and cannot enqueue
an automatic retry or replacement run. Naming repair and rereview does not
enable them. Their frozen call counts remain zero and automatic repair remains
disabled.

Applying the Algorithm removed the unused quota-transition validator, its
tests, and two dead telemetry helpers. They were unreachable successor-runner
machinery. It also removed an invented second numerical quota-delta gate. The
user owns one stop-loss ceiling; before/after telemetry still records actual
quota movement without asking the user to authorize another number.

The final standards pass also found and removed a redundant quadratic archive
path scan. Direct tests preserve both conflict orders. Source export now reuses
the descriptor-bound extraction manifest, rejects a rebound destination, and
binds the verifier workspace before and after Docker. Inside the no-network
container, a trusted entrypoint copies the actual mount into private tmpfs with
no-follow stable reads, verifies the exact snapshot manifest, and runs the
target verifier only against that immutable copy. This closes mount-time ABA
and post-manifest host-mutation gaps without adding any model surface.

## Boundary feasibility

The required trusted external boundary cannot be built or proven under the
current local authority. The host is macOS 15.7.3 ARM64 and Codex 0.149.1 has
only its Darwin ARM64 native package installed. Docker Desktop is the only
local Linux facility, but it has no Linux Codex controller, no provider-only
egress policy, no independent authorization or attestation service, and is
controlled by the same macOS principal as Codex authentication. Nested
Seatbelt profiles fail with `sandbox_apply: Operation not permitted`.

Docker continues to prove the offline verifier lane only. A locally generated
key or receipt would be self-assertion, not an independent issuer. The smallest
legitimate next procedure requires separate authority to provision a fresh,
pinned Linux controller under another administrative trust principal, install
and hash-pin its exact Codex client and adapter, provision scoped provider
authentication and provider-only egress, isolate candidate and hidden verifier
in separate no-network namespaces, and have an external key sign a
definition-bound probe receipt. Those are installation, credential, network,
and system-configuration Human Gates, so this task stopped before them.

## Deterministic proof

All 38 no-model unit and security tests pass. Preflight proves the expected
red/green discrimination for both task fixtures inside the exact pinned,
no-network Docker verifier runtime:

| Task | Baseline | Reviewed known-good | Baseline manifest | Known-good manifest |
| --- | --- | --- | --- | --- |
| use-grok | public FAIL, hidden FAIL | public PASS, hidden PASS | `5d712d5e22a1e27755ea786c802ec4e1c6bd3799842ef3ec418a49e99250e5c5` | `68c86b7ea7c52179533c55899def39a967c429b9d801051337ef4a2c3d8d8728` |
| Karpathy pointer | public FAIL, hidden FAIL | public PASS, hidden PASS | `568d24d0294cf38f08697e194385eafc8d5f35d9ad8e95cf3ff0c6dcb188aab0` | `c2ce5a075efbaefc6c39968f217d6ca679848cec6437f84e522cdd6619d27977` |

The report at `/private/tmp/agentsmd-routing-v2-readiness.json` has file
SHA-256
`7d7855da709d8685b1e1fe951809736e3e26bd08767681b2d959694e2a13fd6c`
and payload SHA-256
`a651a93ce62a0254d45cb5c1a527dcbcce4b175430146c1a7c25a77afb028331`.
Fresh `validate-report` replay returned exit code 0 and reproduced only:

```text
status=BLOCKED
paid_execution_authorized=false
payload_sha256=a651a93ce62a0254d45cb5c1a527dcbcce4b175430146c1a7c25a77afb028331
```

Standards, specification, and security reviewers independently checked the
exact package hash. The first specification pass found that canary-auditor
independence was not explicit. Later passes found a redundant quadratic archive
scan and verifier workspace-binding races. Those P2 findings were resolved by
the exact contract, single-pass archive validation, extraction identity check,
host binding, container-private snapshot, and focused regressions. All three
final passes have no unresolved P1, P2, or P3 findings. The bound evidence is in
`docs/research/evidence/2026-08-31-model-routing-v2-review.json`.

## Remaining blockers

The final report retains seven blockers:

1. `boundary_receipt_required`
2. `exact_quota_ceiling_required`
3. `external_boundary_adapter_required`
4. `external_boundary_unproven`
5. `paid_execution_surface_absent`
6. `trusted_boundary_issuer_required`
7. `trusted_external_boundary_verifier_absent`

`paid_execution_surface_absent` and
`trusted_external_boundary_verifier_absent` are permanent in this package.
Filling JSON fields cannot clear them. Any paid attempt needs a separate
successor package that implements and proves the missing runner and boundary,
binds the user's exact quota ceiling, receives another exact-hash three-axis
review, and then runs only the canary. No global model-routing policy follows
from this readiness work.
