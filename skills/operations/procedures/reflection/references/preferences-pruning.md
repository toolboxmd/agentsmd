# Keep preferences within budget

Private `PREFERENCES.md` loads into every session, so it has a budget of 4,000
characters. The Project Direction hook reports its size in
`budgets.preferences`.

Leave the file within budget after every edit, including an edit that only adds
a line. In the same edit:

1. Merge entries that say the same thing or overlap.
2. Cut filler, examples that change no decision, and dated narration.
3. Move content that has a better owner out: machine facts and tooling to the
   runbook, project commands and rules to the project, shared behavior to the
   core or the owning Skill. Remove it from preferences once the owner holds it.

Measure the result with `wc -m PREFERENCES.md`. If the file still exceeds the
budget, show the user the cuts you propose; the user decides what to keep.
