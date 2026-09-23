# Model state and boundaries

Choose data structures before control flow. A useful structure makes valid work
easy to express and invalid work difficult to construct. Name the domain with
the project's glossary; software representation and terminology are related but
have different owners.

## Remove representable contradictions

- Replace unrelated flags with named variants when only some combinations are
  valid. Give each variant only the fields it can use.
- Keep one authoritative fact and derive views. A stored count plus a collection
  creates a consistency obligation that a computed count may avoid.
- Use a keyed record when access is by identity. Use an ordered collection when
  order is a domain fact. Do not select a structure merely because it is familiar.
- Make ownership, time, units, and identity explicit. Two strings may represent
  different things even when they share a machine representation.

A range represented by a start and duration still needs a nonnegative, finite
duration. Moving a constraint into a type name does not enforce it. Validate
construction and preserve the invariant through every update. Specify whether
time uses wall clocks or monotonic clocks when elapsed time matters.

## Separate values from effects

Parse untrusted input where it enters: command line, files, network, database,
plugin, or interprocess boundary. Convert it into a validated domain value or a
specific error. Keep the calculation over that value independent from storage,
network, and user interaction where doing so makes the behavior easier to prove.

Trust an internal invariant only while its premises hold. Shared mutation,
concurrency, persisted old versions, and authorization can invalidate earlier
checks. Recheck identity and authority at the effect when required; a typed
identifier does not prove present access. Remove redundant guards only after
locating the boundary that actually establishes the invariant.

Represent expected domain outcomes explicitly. Preserve unexpected errors with
enough cause and context to diagnose them. A broad fallback that converts every
failure into success hides broken assumptions and makes proof meaningless.

## Put each decision at its owner

The caller should provide intent, not reconstruct hidden implementation state.
The callee should own sequencing that is invariant across callers. Keep policy
separate from mechanism when policy varies. An interface needs demonstrated value
through ownership, hidden complexity, adaptation, policy, or a stable contract;
multiple implementations are neither required nor sufficient justification.

Inspect abstraction depth by following a real question through the code. Each
layer should hide a useful invariant, effect, or independent policy. Inline a
one-caller wrapper when it only relocates the same complexity. Keep a small
wrapper when it establishes units, access, ownership, or a testable boundary.

Prefer local immutable state to distant mutable state. Smaller lexical scope
reduces the facts a reader must keep in mind and the actors that can invalidate
them. These choices often remove tests and guards by eliminating the invalid
path, not by suppressing its symptom.
