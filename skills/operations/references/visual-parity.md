# Visual parity

Use when the task requires preserving or matching an existing visual contract.
Identify the baseline revision and relevant states: viewport, fonts, locale,
theme, data, loading, errors, selection, hover/focus, and responsive boundaries.
Capture the independent baseline before replacing the implementation.

Freeze capture conditions, comparison method, and acceptance before inspecting
candidate differences. Exact zero-pixel parity fits deterministic captures when
the contract requires it. Declared tolerances, perceptual measures, or masks for
irrelevant nondeterminism can be valid. Do not widen them after seeing failure
merely to make a comparison pass.

Drive the actual route and state. A blank image or a screenshot before the
interaction proves little. Inspect both the baseline and candidate artifacts.
Separate environmental differences from implementation differences with a
controlled recapture. Record changed conditions instead of silently moving the
baseline. Compare the states the change can affect, not only a flattering one.

Investigate meaningful deltas through the owning layout, typography, component,
or data path. Structural refactoring is allowed when it belongs to the request;
the output contract remains independently fixed. Recheck interaction behavior
alongside images. Pixel similarity alone cannot prove keyboard navigation,
semantics, or correct effects.

Finish with exact artifacts, states exercised, comparison results, and remaining
gaps. A reviewed intentional visual change needs its appropriate user decision;
an unexplained difference is not silently an updated design.
