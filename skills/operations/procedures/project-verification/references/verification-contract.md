# Project verification contract

## Runtime ownership

The authored procedure names the real launch command, dependencies, readiness signal,
target address, expected build, driver, disposable data, side effects, evidence
location, and teardown command. Prefer existing browser, PTY, CLI, or HTTP tools.
Do not invent a universal wrapper that the repository does not contain.

A read-only doctor check confirms identity as well as liveness: expected build,
process/session, address, and data location. A healthy wrong server is not ready.
Wait for observable readiness with a bounded timeout, not a fixed sleep. Record
the instance owned by the run and stop only that instance. Never kill broadly by
process name or free a port by terminating an unknown owner.

One driver owns each shared app instance. Parallel source readers may inspect
different areas without interfering. Reuse valid state deliberately. After
surprising behavior, repeat identity checks and reset or relaunch owned disposable
state when a process is healthy but its interaction state is corrupt.

## Feature map

Seed entries from real routes, commands, menus, and documented behaviors. Each
entry states:

- User behavior and relevant entrypoints.
- Prerequisites, permission, disposable fixtures, and side effects.
- Exact driver actions using current project tools.
- Reset or cleanup needed to restore the next attempt's preconditions.
- Expected observations, including the discriminating final state.
- Evidence to retain and known gotchas.

Keep implementation architecture elsewhere. A map is a recipe index, not a record
that those features passed or an affected-test policy. State initial partial
coverage. Several entrypoints can reach one operation, but testing a toolbar
does not prove its keyboard shortcut. Record the actual route exercised.

For example, a save recipe can enter a unique disposable value, invoke Save,
observe confirmation, reopen through a separate user-facing view, and compare
the persisted value. Its prerequisites name the local account and disposable
record. Its evidence identifies build, route, value, and observation without
capturing secrets. Product-specific commands must come from the inspected repo.

## Evidence and completion

Bind each observation to revision/build, runtime target, data, route, driver
actions, and result. Keep evidence outside the temporary instance so teardown
does not erase it. Sanitize before authorized publication. Do not put raw customer
data or local credentials into a committed feature map.

Classify blocked entitlement, missing OS capability, inaccessible integration, or
unavailable safe data as unverified with its prerequisite. "Unreachable" is not a
successful feature check. Keep mocks, local real-code checks, and authorized Live
Verification distinct under `operations`. Project-specific proof exceptions,
including AgentsMD's user-owned behavioral verification, continue to apply.
