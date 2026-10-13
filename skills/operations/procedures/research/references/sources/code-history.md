# Code archaeology

Start from exact paths and symbols on the relevant revision. Inspect full
substantive diffs, neighboring changes, tests, and consumer changes. Follow file
renames and moves. Use blame as an entry point, not a final explanation.

Useful Git probes include `git log --follow -- path` for one file, `git log -S
'exact text' -- path` for count changes of exact text, and `git log -G 'pattern'
-- path` for matching changed lines. Their semantics differ. Inspect the resulting
commit rather than treating a search hit as the origin. A copied pattern may have
an older origin in another module. Squashes and shallow history limit resolution.

Read the PR body, complete relevant review threads, linked Issues, ADRs, release
notes, and later corrective or reverting changes. A review API's top-level
comments can omit inline conversations; discover the endpoint and pagination
needed for the actual evidence. Bot-authored dependency updates may encode a real
compatibility constraint and should not be discarded merely by author identity.

Distinguish the reason proposed, the decision accepted, the implementation merged,
and later behavior. A rejected review suggestion is not the shipped design. An
open PR does not prove current production state. Cite immutable code revisions
and exact discussion links where possible. Note unavailable forge access or
incomplete history instead of silently substituting remembered intent.
