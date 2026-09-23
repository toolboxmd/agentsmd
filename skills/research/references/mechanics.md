# Explain current mechanics

Determine what the reader needs: runtime behavior, ownership, placement, change
impact, or an initial mental model. Use context to infer prior knowledge. State
a reversible interpretation when scope is ambiguous, then inspect the system.

Find a real trigger: command, request, event, user action, or scheduled callback.
Follow the code actually executed. Track inputs, transformations, controlling
conditions, state transitions, effects, outputs, and failure paths needed for
the question. Read central type definitions and concrete implementations. A name,
interface, directory tree, or comment alone does not establish behavior.

Build a compact evidence map:

- Entry point and how it is selected.
- State owner, lifetime, and transformations.
- Calls and boundaries, including asynchronous work or external dependencies.
- Observable result, failure, cancellation, and cleanup where relevant.
- Exact source references, surprising behavior, and untraced connections.

Trace enough representative paths to explain the claimed scope. Do not claim a
repository-wide rule from one convenient example. If exploration is divided,
workers return evidence maps and gaps. The lead resolves missing connections and
contradictions rather than concatenating summaries.

Separate current placement from recommended placement. Code can show where a
responsibility lives; deciding where it should live also needs domain ownership
and the design tradeoff. Use `software-design` when the request includes that
decision. Historical purpose belongs to [history](history.md); present behavior
cannot prove what its author intended.

Lead with the smallest complete explanation, then walk through one concrete
operation. Show only the source map the reader needs to continue. Use diagrams
for relationships that are easier to see, not as mandatory decoration. Preserve
the distinction between an observed path and a proposed improvement.
