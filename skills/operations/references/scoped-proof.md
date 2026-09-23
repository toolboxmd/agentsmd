# Scoped delivery proof

Use this contract when a Project declares proof reuse. Without a declaration,
retain its complete-proof commands and existing delivery behavior. A fast
changed-scope check alone never qualifies a candidate.

## Eligibility and ownership

The Project owns a small reviewed scope policy. Begin with a baseline commit
that has direct, complete successful coverage under that policy. Classify the
cumulative diff from that baseline to the frozen versioned candidate, including
callers, metadata, assets, tests, fixtures, configuration and dependencies.
Every changed path has exactly one rule naming affected checks and the behavior
they cover, or an explicit exclusion explaining why it has no affected behavior.
Input changes also select their consuming checks. Shared fixtures name every
consumer. Unknown paths, ambiguous rules and protected changes stop scoped
selection with a reason. No command silently runs the full suite instead.

Use the complete path explicitly for broad or unsupported work. Policy changes
require independent authorization and a new complete baseline. First adoption
also commits the policy and establishes complete proof once; an older release
cannot be claimed to have passed a policy that did not exist there. Authentication,
funding, schemas, dependencies, infrastructure and release controls require
broader proof unless a separately approved scope actually covers their impact.
A narrow sharing scope cannot approve those changes. A scoped candidate never
becomes another scoped candidate's complete baseline.

The policy is a reviewed coverage claim, not automatic dependency analysis.
Review must establish that its inputs and rules include indirect behavior and
unique privacy, financial and accessibility assertions. The tool verifies that
claim consistently; it cannot discover an omitted semantic dependency.

## Trust boundary

Load both the validator and policy from separately trusted, pinned control.
Candidate code cannot choose or modify the effective policy, validator,
authentication callback, or expected environment. The policy must already exist
unchanged in the complete baseline and candidate. Its canonical JSON digest
identifies its content; the digest does not establish authority.

An authorized operator or trusted workflow runs the commands through `run` in
an isolated execution environment. Protect the resulting record bytes and
provenance using the Project's existing authenticated transport. For example,
a workflow adapter verifies the run's repository, authorized workflow revision,
actor, source commit and successful execution, then retrieves its exact artifact
bytes through the authenticated API. A local operator may transfer exact bytes
through an authenticated session and keep their identity in protected control.
An arbitrary artifact with a matching filename or digest is insufficient.

The adapter's `authenticate(raw_bytes)` verifies that provenance for those exact
bytes and returns the authenticated issuer, or rejects. The record's `issuer`
is only a label that must match. Never implement authentication as a constant
return, a bare `passed` flag, or an allowlist supplied by candidate data. A digest
selected through already authenticated provenance can bind bytes, but cannot
replace provenance. The shared library intentionally supplies no permissive
authentication implementation and adds no keys, service or credential store.

`observe(check_name)` measures relevant current environment and external input
identities through trusted control. Include runtime/platform versions, dependency
installation identity, fixture/data digests and configuration identities where
they affect results. Record identifiers, never secrets or customer data. For
artifact checks, include the immutable artifact digest. Source inputs are
computed separately from Git file modes and object identities. Ignored files,
external symlink targets, services and installed dependencies need explicit
observations or an isolated environment that removes their influence. Merely
copying environment fields from an old record does not observe current state.

## Adapter interface

Python 3.11+ and Git are required. Import `scoped_proof` from `bin/` in the
trusted AgentsMD installation. The sibling `bin/scoped-proof select` command
prints eligibility JSON and exits 2 on unsupported input; it does not grant
promotion authority. `--help` describes its exact arguments.

The API accepts a `Path` repository root and full commit SHAs. Commit generated
content and the version transition before recording proof. The source checkout
must be clean before and after each executed check. Later changes need a new
candidate; they do not enter the frozen release.

- `select(root, baseline, candidate, policy)` returns `execute`, `reuse`, input
  identities and the explanation for every changed path.
- `run(root, baseline, candidate, policy, mode=..., observe=..., output=...,
  issuer=..., checks=None)` executes argv arrays without a shell and returns
  exact JSON bytes. `complete` mode requires baseline equal to candidate;
  `scoped` mode selects cumulative affected checks plus all artifact checks.
  Optional `checks` partitions that selection between appropriate hosts.
- `validate_complete(root, candidate, policy, raw, authenticate=..., observe=...,
  now=None)` validates direct complete execution on the exact candidate. One
  record or a disjoint list must cover every check, with current observations
  and the configured current-record lifetime. This lets generated promotion
  commit/version once, execute once, and validate the same authenticated bytes
  in later trusted jobs without a second baseline run or relabelled records.
- `validate(root, baseline, candidate, policy, baseline_raw, current_raw,
  authenticate=..., observe=..., now=None)` authenticates and validates all
  records. Each raw argument accepts one byte string or a list from multiple
  hosts. Coverage must be complete and disjoint: all declared baseline checks,
  and all selected candidate checks. Reuse directly references that complete
  baseline. Missing, failed, altered, expired, mismatched or duplicate evidence
  raises `ProofError`. There is no fallback execution.

A record contains schema, repository, policy digest, baseline, candidate, mode,
issuer, start/finish times and executed results. Each result binds the exact
argv, source input digest, observed environment, exit code and stdout/stderr
SHA-256. Complete records may partition execution across hosts, but only their
complete union qualifies a baseline. `validate` reports `executed`, `reused`
and `unverified` separately. `validate_complete` reports `coverage: complete`;
its `executed` checks describe the authenticated candidate execution, not work
performed by the validation call. Both validation APIs run no tests. Reusing
complete candidate records still compares every current input, environment and
artifact digest. Fresh external-state admission remains outside test proof.
Catch refusals as blocked scoped delivery, retain
the reason, and explicitly select broader proof when appropriate.

Each run creates its own previously nonexistent output directory outside the
checkout. Each check receives a distinct `SCOPED_PROOF_OUTPUT` directory for
its database, fixtures and build output. Commands must honor that directory,
allocate unique ports when needed and give state-changing tests independent
data. Logs and `proof.json` remain there for authenticated transport. Nonzero
execution produces a failed, possibly incomplete record for diagnosis; it
cannot validate. Environment movement or a changed checkout aborts recording.

A Project can run behavioral checks locally and artifact checks on GitHub,
or run everything on GitHub. Baseline assumptions are compared only for reused
checks; current checks must match their current observed environment. Host
identity is a relevant input only when results depend on it. Builds and artifact
checks can remain separate: build once, record the artifact digest in the check
environment, and promote those unchanged bytes.

## Policy v1 example

This illustrative map covers a deliberately small repository. Real Projects
must declare their actual coverage and environment; copying these patterns does
not establish eligibility.

```json
{
  "schema": 1,
  "repository": "owner/project",
  "policyPath": ".toolboxmd/scoped-proof.json",
  "maxAgeSeconds": 86400,
  "blocked": [".github/*", "package*.json", "schema/*", "auth/*"],
  "checks": {
    "sharing": {
      "argv": ["npm", "run", "test:sharing"],
      "inputs": ["src/sharing/*", "tests/sharing/*", "assets/sharing/*"],
      "environment": ["runtime", "dependencies", "fixtures"],
      "kind": "behavior"
    },
    "artifact": {
      "argv": ["npm", "run", "check:artifact"],
      "inputs": ["*"],
      "environment": ["runtime", "artifactDigest"],
      "kind": "artifact"
    }
  },
  "rules": [
    {
      "paths": ["src/sharing/*", "tests/sharing/*", "assets/sharing/*"],
      "checks": ["sharing"],
      "reason": "public rendering and its callers, fixtures and assets"
    },
    {"paths": ["docs/*"], "exclude": "documentation with no runtime consumers"}
  ]
}
```

Paths are case-sensitive repository-relative Python `fnmatch` patterns; `*`
includes `/`. Renames are classified as deletion plus addition. Check inputs
are nonempty tracked blob sets. Gitlinks are unsupported inputs. Every policy
has behavioral and artifact checks, explicit blocked patterns, a finite positive
`maxAgeSeconds` for current execution and an explanation for each rule. Immutable
complete-baseline records do not expire by age; reused inputs and environmental
assumptions must still match current trusted observations. Select the current
record lifetime for real Project freshness needs, not as a proxy for source
coverage. Policy v1 rejects unknown
fields. Keep argv values literal; no substitution or shell evaluation occurs.

## Development and delivery

Update obsolete tests with approved behavior during development. Preserve
independent assertions. After a failure, run corrected tests and all affected
fixture consumers before retrying hosted proof. Fix shared mutable fixtures;
concurrent runs use separate outputs, databases and ports. Keep this feedback
loop separate from the final exact-candidate evidence.

Independent review and preparation may overlap. Promotion still requires the
applicable exact-SHA authored or generated-scope review, valid composed coverage,
current artifact checks, and fresh external-state admission. Recheck actor,
authority, PR/base/head, newest eligible release, immutable source identity and
other mutable prerequisites immediately before each external mutation. These
observations are not reusable test proof. Retain backup, rollback and health
boundaries. Reuse the one built artifact across delivery stages.

Record request-to-live time, verification time, review overlap, runner usage,
build, promotion and coordination gaps where observable. Report unavailable
measurements explicitly. Performance targets never waive required coverage.
Installation, loading and user-owned behavioral Live Verification remain
separate claims.

Delivery Profile v1 is unchanged. Its existing `commands.changedScope`,
`commands.complete` and `commands.release` may invoke the Project adapter.
The scope map is a separate Project-owned policy selected by trusted control;
a command string or profile field alone cannot authorize reuse. Projects with
no adapter keep their existing complete path. Adoption and live evidence for
from. and Marketplace belong to their own Issues.
