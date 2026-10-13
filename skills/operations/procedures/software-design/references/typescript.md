# TypeScript patterns

Use these patterns when TypeScript owns the implementation. Read the project's
actual compiler settings, runtime schema tools, and supported TypeScript version.
Do not assume strict options or library availability.

## Parse once, preserve meaning

Treat external values as `unknown` until validated. Derive static types from the
authoritative runtime schema when the project supports it. A type assertion
does not parse JSON, authorize access, or validate persisted data.

Use discriminated unions for mutually exclusive states. Handle variants with an
exhaustive switch and an unreachable-case helper so a new state exposes missing
consumers during compilation. Keep fields on the variants that own them instead
of making every field optional.

Brand primitives only when mixing them up is a realistic error. Establish the
brand in a constructor that checks the domain constraint:

```ts
declare const durationBrand: unique symbol;
type DurationMs = number & { readonly [durationBrand]: true };

function durationMs(value: number): DurationMs {
  if (!Number.isFinite(value) || value < 0) {
    throw new RangeError("Duration must be finite and nonnegative");
  }
  return value as DurationMs; // The checked construction boundary owns this cast.
}

type TimeRange = Readonly<{ startMs: number; durationMs: DurationMs }>;
```

This example enforces only the duration constraint. Validate the start and any
sum or platform limits when the domain requires them. Do not spread unchecked
casts through callers or pretend the brand survives serialization automatically.

## Keep the compiler truthful

Prefer narrowing to `any`, non-null assertions, or chained casts. When an escape
hatch is unavoidable, contain it at one reviewed boundary, state the external
guarantee, and test the assumption. Preserve a useful explanation until the
structure can express it.

Use `satisfies` when checking a configuration shape while retaining its specific
inferred keys matters. Prefer derived unions from an authoritative data source
to a second handwritten list. Remember that `readonly` is generally shallow and
compile-time only; it is not runtime freezing or a concurrency primitive.

A nonempty tuple type can lose its runtime guarantee through mutable aliases or
unchecked updates. Use `readonly [T, ...T[]]` or controlled mutation when continued
nonemptiness matters, and check the actual indexed-access compiler behavior.
Use `as const` deliberately for literal/readonly inference; it still does not
validate external values or freeze an object at runtime.

Avoid boolean parameter puzzles and positional sequences of indistinguishable
primitives. A domain object can expose intent without an excessive builder or
class hierarchy. Return meaningful errors or variants at the API boundary;
do not require every caller to reverse-engineer thrown text.

## Prove the boundary

Use compiler checks for assignability and exhaustiveness, runtime tests for
parsing and behavior, and the real integration seam for external contracts.
Compile the example in its owning project rather than assuming a isolated
snippet proves the installed configuration. Never silence a compiler error as
the default way to finish a migration.
