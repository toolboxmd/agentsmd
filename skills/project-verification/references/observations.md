# Design discriminating observations

Name the expected state, broken state, and observation distinguishing them before
choosing a screenshot, assertion, or log. Reach that state through the interface
appropriate to the defect. Setup, loading, compilation, and a plausible source
diff do not substitute for the claimed final behavior.

| Surface | Useful observation |
| --- | --- |
| UI change | Action plus resulting state at the relevant viewport and route |
| Persisted operation | Confirmation plus independent read through the supported interface |
| CLI | Exact arguments, exit status, stdout, stderr, and relevant external effect |
| API | Request identity, response contract, and observable persisted/effect state |
| Background job | Input, lifecycle completion, destination, result, and failure behavior |
| Performance | User-visible interval under a controlled comparable workload |

Read-only internal state can corroborate the result. Do not inject the symptom
and present it as reproduction. Repeat from reset state when a single attempt
could be accidental. Baseline and candidate need comparable environment, data,
and actions. Record translated conditions and what they cannot prove.

For media evidence, frame the exact question the image or recording must answer.
Inspect the artifact itself. A file that exists may be blank, show the wrong
build, or stop before divergence. Narrow independent evidence review can help
when a consequential claim rests on ambiguous media; it is not a compulsory
extra worker for every screenshot.

For visual preservation, use the dedicated
[visual parity method](../../operations/references/visual-parity.md). For
performance, use `diagnosis`' measurement method. Their acceptance contracts
must be established before selecting the most flattering result.
