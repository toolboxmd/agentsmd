# Model Routing Benchmark V3 Terminal Report

## Outcome

Recommendation: **REPLICATE** under a new experiment identity after explicit
authorization. Do not adopt, narrow, or reject any model route from this run.

The no-model preflight passed, but the Terra high canary did not reach model
inference. The OpenAI API rejected the implementation response schema with HTTP
400 because `uniqueItems` is not permitted in the strict Structured Outputs
subset used by Codex. The controller recorded `CONTROLLER_ERROR` and stopped
the frozen lifecycle after 9.390 seconds, as required.

This is a benchmark-package failure, not a Terra quality result. No candidate
change, deterministic verification, Luna review, Spark cell, other comparison
cell, or Grok evaluator ran. The evidence therefore supports no routing-policy
change and does not complete the repository Objective.

## Executed identity

The terminal experiment is preserved at
`/Users/lukaszmaj/.codex/routing-benchmark-v3/run-20260901-v3-02`.

| Evidence | SHA-256 |
| --- | --- |
| Frozen definition | `e0e211a8ca46fca4c60b877cfc45cbcb5372ca1c746d256010f7ffd40541739b` |
| Frozen executed package | `b78bd8cfb1fb7ed59a4a1bcb0d78b38000ec27585a86ed073dbadd2df1a295c8` |
| Package review | `e307a1cb8f1b71a3a4e5b1e9e30839869eb5393db60c35dc442e844baa84335e` |
| Preflight receipt | `70281d72100c045f723b355e13318e8f48ca9b980242328c27dedcb052cadb80` |
| Lifecycle state | `aad3ab51b223dfc148aea195b8cd9b4d3f810f85af4d9951696705f224a45bb2` |
| Canary result | `1dacb7c015dd1555fe6f889cffe8b42b556bc669a436e00019675440d30ee2f7` |

The exact-hash package review reported `ACCEPT` across standards,
specification, and security before preflight. That review missed response
schema admission compatibility.

An earlier preparation root,
`/Users/lukaszmaj/.codex/routing-benchmark-v3/run-20260901-v3`, stopped during
provider-free split preflight before publishing state or a receipt. Its probe
selected a newly added answer path that did not exist in the baseline. The
selection logic was corrected to use an existing changed path, regression
tested, independently reviewed, and rerun under the `-02` identity. No model
call occurred in that preparation root.

## Preflight result

The final no-model preflight reported `PASS` with `no_model_calls: true`.

- Native permission and process boundary: PASS.
- Split driver and candidate-worker separation: PASS.
- Controller package and fixture binding recheck: matched.
- Telemetry compatibility: PASS.
- Quota observer compatibility: PASS.
- Numerical quota ceiling: none, matching the authorized experiment.
- Reset redemption: not authorized and not used.

All three fixtures discriminated before model execution:

| Task | Baseline public / hidden | Known-good public / hidden | Fixture SHA-256 |
| --- | --- | --- | --- |
| `use-grok` | FAIL / FAIL | PASS / PASS | `a72146a0e9b12492f844b2453fb4c397b26a997fd3b1c94159fab356922d5f6d` |
| `karpathy-pointer` | FAIL / FAIL | PASS / PASS | `bd4a1a1156c3d584350851b5ea1c88079cbbb98b7825304f7db7800ae8561d04` |
| `openbot-acp` | FAIL / FAIL | PASS / PASS | `d2f0b5addd5a31a493588a1e829852793d93e55272cd0385449a68873bf1196c` |

This proves that the frozen baselines and accepted historical answers are
distinguishable by the public and hidden verifier lanes. It does not prove that
the tasks differentiate model capability.

## Canary terminal evidence

The only reserved attempt was `use-grok--terra-high`, using
`gpt-5.6-terra` at high reasoning effort. The persisted rollout binds the
OpenAI provider, Codex CLI 0.149.1, and the `routing_candidate` permission
profile.

The provider returned `invalid_json_schema` for parameter
`text.format.schema`:

```text
Invalid schema for response_format 'codex_output_schema': In
context=('properties', 'changed_paths'), 'uniqueItems' is not permitted.
```

The final lifecycle facts are:

- terminal status: `CONTROLLER_ERROR`;
- controller elapsed time: 9.390127792 seconds;
- implementation receipt: absent;
- artifact: absent;
- public and hidden verification: not run;
- Luna review: not run;
- token-count record: null;
- last agent message: null; and
- candidate manifest before and after the request:
  `68f28e6c73aff432652ef707c8932f7ebeb692176963c4937bde7377cf521932`.

The request reached provider-side schema validation but was rejected before
inference or candidate action. No model token usage was reported. The evidence
does not assert an account-level zero-cost result because no completed stage
receipt exists.

The raw execution stream also emitted a notice that Code Mode was unavailable
because `code_mode_host` is intentionally disabled in the isolated profile.
That notice was not the terminal error and the turn continued to the provider
request. This run does not establish whether the notice would affect candidate
execution after schema admission, so the next canary must retain and inspect
it rather than silently dismiss it.

`state.json` contains one terminal cell at ordinal 0, has no active cell, and
sets `stopped: true` with `stop_reason: CONTROLLER_ERROR`. The only directory
under `attempts/` is the Terra canary. No review directory or top-level
`evaluator/` directory exists. These facts prove that Spark, the other five
comparison cells, Luna max, and Grok 4.6 xhigh were not invoked. Spark quota
windows in the preflight receipt are CodexBar observations only, not Spark
model use.

## Workload complexity assessment

The selected projects are structurally adequate for a three-tier pilot. There
is no evidence from this run that they are empirically difficult enough to
separate the routes because no implementation completed.

- `use-grok` is intentionally low complexity. It is more than a one-line edit:
  the accepted change coordinates three plugin manifests, release metadata,
  documentation, and tests across seven allowed paths. It is still a sensible
  floor for testing whether a scarce route is unnecessary on routine contract
  work.
- `karpathy-pointer` is medium complexity, not a simple wiki prose edit. It
  changes Python index and discovery behavior across files, preserves malformed
  and unreadable inputs conservatively, excludes only proven pointer pages, and
  is checked through public and answer-hidden cases.
- `openbot-acp` is a hard asynchronous state-machine task despite its one-file
  production scope. The implementation must bound aggregate ACP output across
  startup, attachment, active Turn, cancellation drain, and idle phases without
  regressing cleanup or event behavior.

Replacing these fixtures with Trusthacker work before the next canary would add
scope without addressing the observed failure. The smallest falsifying next
step is to replicate the same frozen complexity ladder with the repaired
schema. If accepted routes later saturate all three fixtures, add a second hard
task from OpenBot or Trusthacker as a separate benchmark revision rather than
silently changing this matrix.

## Postmortem hardening

The executed package remains immutable and terminal. A later package revision
contains a future-run fix:

- remove only `uniqueItems` from the implementation schema;
- preserve `pattern` and `minimum` in the Luna review schema because the
  current [OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)
  lists them as supported constraints for non-fine-tuned models;
- enforce unique, nonempty changed paths and all implementation and review
  value semantics in the controller;
- recursively allowlist the model-facing strict-schema keywords before fixture
  work and again before every Codex stage;
- regression test the exact nested `uniqueItems` failure before any model hook
  can run;
- promote the one safely read rollout into the direct audit directory instead
  of retaining the CLI-created Codex home;
- scan the complete session tree without following aliases, propagate every
  read error, stop at a fixed entry bound, and classify ambiguous, aliased,
  hardlinked, special, or unreadable rollout state as a boundary failure even
  when the provider process exits nonzero;
- retain only execution JSONL, promoted rollout JSONL, stderr, and the
  structured last message, while removing fresh `HOME`, `CODEX_HOME`,
  `CODEX_SQLITE_HOME`, and `.runner-tmp` on setup failures, quota failures,
  provider failures, timeouts, containment failures, and success;
- derive non-persisted markers from the exact copied OAuth document and reject
  all retained evidence if its auth fields or token values appear;
- bind every admitted artifact by relative path, byte count, and SHA-256 in
  both success and terminal-failure evidence, including generic controller
  failures and timeouts;
- preserve generic Luna controller failures and Luna timeouts as typed terminal
  results with their direct stage evidence, without fabricating a review
  receipt;
- bound the Grok auth source to 4 MiB, derive non-persisted markers from its
  exact bytes, scan the exact evaluator raw, result, usage, and receipt
  allowlist after every terminal outcome, delete the complete evaluator run on
  any credential match, and bind every admitted evaluator artifact by relative
  path, byte count, and SHA-256;
- open private evidence and Grok auth sources nonblocking with no-follow, then
  reject FIFO and other special descriptors before any read; and
- require every successful evaluator run to retain all six expected artifacts
  and reconcile their sizes and hashes with the evaluator outcome, usage, raw
  output, result, and run-receipt bindings; and
- remove exact fresh evaluator runtime roots, probes, profiles, process output,
  and any partial preflight receipt when evaluator preflight fails.

The unchanged definition SHA-256 is
`e0e211a8ca46fca4c60b877cfc45cbcb5372ca1c746d256010f7ffd40541739b`.
The postmortem package SHA-256 is
`c9aee354a95cc152b558b5044e79e2eac1a6ef10eb310e5a9dde207476f215b7`.
Its implementation schema SHA-256 is
`4f26f18bf27a342d0c376424175ad7f77558f1fa94759b811b360391968dc2f9`.
All 174 V3 and 38 frozen V2 provider-free tests pass. The focused controller
subset accounts for 49 of the V3 tests.

This deterministic guard prevents the observed defect. It is not live provider
acceptance proof, and the terminal state root was not modified or reused. That
executed root predates the retention hardening and still contains disposable
Codex home and SQLite state. Treat it as sensitive local evidence until its
separate cleanup is explicitly authorized.

## Source preservation

The benchmark used controller-owned exports and attempt copies. Read-only
checks before and after the canary showed the three source worktrees unchanged:

- use-grok: `625abafeabd32ecbb2108c37ed716ce7ff493f10`, with the pre-existing
  `wiki/.ingest-runs.jsonl` modification;
- Karpathy Wiki: `993356b4f2002972d21d626c33639432a4ad2212`, with the pre-existing
  `.wiki-config`, `CONTEXT.md`, `docs/adr/`, and `wiki/` untracked state; and
- OpenBot PR #116 worktree: `94af08e7a4dc571593dba5dc694ca12aebb3c65e`, clean.

These cleanliness observations are an external pre/post audit, not fields
bound inside the frozen state root. The fixture source object identities and
export manifests are receipt-bound.

## Decision and next authority gate

V3 provides strong readiness evidence and one terminal controller failure, but
zero comparative model-quality observations. The supported decision is
`REPLICATE`, with no global routing change.

A new scored run requires explicit authorization because the frozen lifecycle
for `run-20260901-v3-02` prohibits retry or replacement. After authorization,
the procedure is:

1. freeze and independently review the repaired package hash;
2. use a fresh persistent state root and new experiment identity;
3. rerun the provider-free preflight;
4. run only the Terra high canary;
5. accept an independent audit of the exact canary result and artifact; and
6. only then permit the remaining frozen cells, including Spark.

No merge, release, install, deployment, or benchmark rerun is authorized by
this report.
