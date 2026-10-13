# Change existing systems

## Establish the change boundary

Map direct callers, public exports, generated consumers, storage formats,
background jobs, configuration, and external users. Text search finds many
callers; it does not establish absence of dynamic or independently deployed
consumers. Classify breakage, required migration, and unaffected behavior.

Define what equivalence means before a refactor: returned values, errors,
ordering, side effects, persisted shape, timing bounds, or visual behavior.
Choose proof for the promises being preserved. A textual diff or a passing
compiler does not establish semantic equivalence.

## Migrate toward one target

Write the target usage, migrate the owned callers, and remove the old API in the
same completed change when compatibility permits. Remove temporary adapters,
dead exports, obsolete flags, and replaced tests only after all relevant callers
are accounted for. Search again and exercise the consuming seam.

Keep compatibility when external consumers, independently deployed versions, or
rollback require it. Name its owner, scope, and removal condition. A deliberate
expand-and-contract migration is different from retaining an accidental second
architecture forever. Honor explicit intermediate build or release constraints.

Break large work into units with an observable result and a check after each.
Choose units around behavior or consumer groups, not arbitrary file counts.
For mechanical changes, a codemod or script can make coverage reproducible.
Build it only when repeatability, scale, or proof repays its cost. Include dry
run, bounded scope, and a postcondition when omission or repeat execution matters.

Use controlled old/new comparisons for critical equivalence: identical inputs,
normalization limited to declared irrelevant differences, and assertions on
observable results. Independent expected outcomes or invariants are still needed
when both implementations could share a bug. Differential success alone proves
agreement, not correctness.

## Separate before serializing

When concurrent actors conflict, first identify exactly what they share. Give
each actor its own state, workspace, output, or transaction when the domain
allows it. Separate files do not isolate a shared process, port, database,
branch, or deployment target.

If sharing is a real invariant, choose one owner or an appropriate transactional
primitive. Define lock scope, ownership, release, stale-holder behavior, and
crash recovery. A lock file without fencing cannot prevent an old writer from
continuing after another actor declares it stale. Check the storage system's
actual atomicity rather than assuming several file writes form one transaction.

## Make retries converge

Describe the desired final state and every partial state a failed run can leave.
Prefer reconcile-to-state operations over blind append or toggle actions. Use
stable identity or an idempotency key where the external API supports it.
Re-read ambiguous outcomes before retrying; a timeout may follow a successful
write. Deduplication must account for concurrent attempts, not only sequential
replays. Compensate only the exact task-owned change through an authorized inverse.

Prove first execution, repeated execution, partial completion, and changed input
where each can invalidate the contract. Keep authority checks at the actual
effect. Idempotence does not grant permission to repeat an unauthorized action.
