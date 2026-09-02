# Objective

Bound ACP child output across every lifecycle phase without changing the
accepted active-Turn behavior or adding a normal thinking timeout.

Completion requires startup, attachment, active Turn and cancellation drain,
and idle output to use truthful per-phase aggregate accounting. Boundary data
is charged exactly once, overflow follows the sanitized containment path and
reaps the process group, an overflowed client cannot be reused, and a fresh
client remains healthy.

Non-goals are Messenger, Home, Screen, PinchTab, HTTP, or WebSocket redesign;
batch-element accounting changes; and a wall-clock timeout for a healthy
post-flush active Turn.
