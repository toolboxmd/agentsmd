# Artifact placement

Create a file only when it preserves useful evidence or supports a required
handoff. A short answer or a reflection with no durable correction needs no
file. Reading, reviewing, or reflecting does not itself authorize repository
mutation or publication.

## One owner and one task folder

Inspect the project's artifact convention first. Reuse its declared task-evidence
root and the existing folder for this Issue. Otherwise use
`docs/work/<issue-number>-<short-slug>/`; for authorized local work without an
Issue, use one stable task slug. Create the folder lazily. Multiple procedures
working the same task use this same folder, not research/, reviews/, prototype/
and reflection/ folders scattered through the repository.

Keep the smallest useful retained material there: normally one `notes.md` for
cited findings, comparisons, experimental observations and unresolved limits.
Add separate files only for genuinely distinct reusable evidence or formats.
Link evidence from the owning Issue; the Issue remains the sole active plan,
status and durable handoff. Do not create another local task ledger or copy the
Issue into the folder. An existing report can serve as the notes; do not create
a duplicate merely to match the filename.

| Content | Durable owner |
| --- | --- |
| Active intent, acceptance, blockers, proof and continuation | Owning GitHub Issue, linking exact CI or artifact evidence |
| Retained task-specific research or experiments | The task's single evidence folder |
| Validated project knowledge | Existing README, glossary, ADR, code or tests, according to the core's ownership rules |
| Reusable verification driver and recipes | Existing project verification owner; otherwise `.toolboxmd/verification/` with `index.md` and conditional references |
| A learned operating rule | Its existing canonical procedure, only within authorized scope |
| Personal defaults | Canonical adjacent private `PREFERENCES.md`, never task reports |
| Model Router jobs, reports and raw runner output | Model Router's existing state directory, linked by identity when needed |

Do not move unrelated existing material as part of recording a new result.
Promote a lesson into its canonical owner instead of keeping competing versions
in the report. ADR eligibility and Project Direction confirmation still apply.

## Scratch, prototypes and proof

Put disposable scripts, raw traces, profiles and unselected variants in task-owned
temporary storage outside tracked source, or on an explicitly disposable branch.
Prototype shells stay off the production branch. Keep only the question, exact
artifact identity/location, reproducible command, relevant conditions, decisive
observations, conclusion and limits when retaining experimental evidence.
A required regression belongs in the real test suite, not in an evidence folder.

Keep evidence outside the temporary runtime it describes. Before deleting task
storage, retain required sanitized proof at the task owner or durable artifact
store. For large or binary evidence, prefer the project's established artifact
store and link the immutable identity/digest; do not commit bulk logs by default.
A temporary local path is not durable delivery evidence. Preserve secrets and
user data boundaries before any authorized commit or external upload.

No directory or empty index is required until there is material to retain.
