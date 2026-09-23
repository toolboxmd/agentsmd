---
name: diagnosis
description: >
  Diagnose bugs, regressions, runtime failures, traces, and performance problems;
  verify an existing fix or run a bounded optimization effort. Use when cause or
  measurement is uncertain. A diagnostic request remains read-only unless repair
  is authorized.
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/poteto-mode/playbooks/bug-fix.md
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Diagnosis

Establish intended behavior, observed failure, exact build, environment, inputs,
and the surface exposing the problem. Treat the user's causal explanation as a
hypothesis while preserving the reported symptom and constraints. Determine
whether the requested outcome is an explanation, a verified existing fix, or
an implemented repair. Investigation alone grants no repair authority.

| Work | Read |
| --- | --- |
| Defect, regression, duplicate report, or existing fix | [Reproduction and cause](references/reproduction-and-cause.md) |
| Running process, CPU profile, heap, trace, or runtime lifecycle | [Runtime and trace forensics](references/runtime-and-traces.md) |
| Latency, throughput, resource cost, benchmark, or sustained optimization | [Performance experiments](references/performance.md) |

Separate observations from explanations. Keep a short hypothesis table while it
helps: mechanism, predicted observation, cheapest distinguishing check, result.
Choose a check because it separates plausible causes, not because it produces
more data. Stop repeating a failed repair when its premise needs investigation.

For an authorized fix, capture the baseline before changing it. Repair the
earliest owning cause that explains the observations. Use `operations` for
implementation and [test design](../operations/references/test-design.md) for
regression proof. A guard, retry, or compatibility path can be the correct
design; require its domain reason instead of banning the syntax.

Finish with the supported mechanism, exact evidence, alternatives rejected or
still open, and the scope of proof. A missing reproduction or inaccessible
environment is an explicit limit. Report a result as verified, not verified, or
inconclusive for the particular claim; do not convert uncertainty into success.
