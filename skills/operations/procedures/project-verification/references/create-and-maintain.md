# Create and maintain verification support

## Create

1. Inspect the product's surfaces, documented commands, existing drivers, and
   proof requirements. Identify the smallest missing capability that prevents a
   reliable observation. Ask only for prerequisites that inspection cannot resolve.
2. Select a representative feature that exposes launch, state, interaction, and
   evidence requirements. Use a disposable target within authority. Verify that
   even a claimed dry-run does not make unwanted requests or open an external flow.
3. Author the project procedure using the shared [contract](verification-contract.md).
   Include only real commands and supported driver APIs. Keep reusable runtime
   setup in one place and link feature-specific recipes conditionally.
4. Execute the instructions as written. Correct missing dependencies, misleading
   readiness, ambiguous target identity, and lost evidence before claiming success.
   Fresh-context discovery matters when a warm session had undeclared tools.
5. Clean up owned state after successful and failed attempts. Verify the retained
   evidence survives. Report the actual demonstration and explicit coverage limits.

The first recipe is a vertical slice through the verification contract. Do not
generate an exhaustive-looking map before proving one route can run.

## Maintain

Keep a strict edit boundary around the verification procedure, its owned harness,
and feature map. Compare recipes with current routes, commands, permissions,
and behavior. Remove obsolete entries only after checking their consumers and
unique coverage. Add or update recipes for real changed behavior.

Distinguish documentation drift, a broken driver, and a product regression.
Repairing the first two may be the requested work. A product regression needs
its own authorized implementation path; do not rewrite expectations to bless it.

Run changed harness paths through the actual supported surface. Recheck target
identity, evidence retention, and teardown when their mechanics change. Mark
unexecuted recipes honestly. Preserve working unrelated instructions and private
configuration. Do not add a recurring maintenance job to a one-shot request.
