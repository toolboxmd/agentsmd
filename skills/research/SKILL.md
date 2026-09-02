---
name: research
description: Resolve a precise question from high-trust primary sources and capture cited findings for its owning GitHub Issue, including a Wayfinder Research Decision Issue.
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/research
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

# Research

When a session claims a Wayfinder **Research Decision Issue**, invoke this
Skill without asking the human to select it. For a direct research request,
use the user's question as the owning question.

1. Read the owning GitHub Issue and state the precise question and completion
   condition before searching.
2. Investigate against **primary sources** such as official documentation,
   source code, specifications, and first-party APIs. Follow consequential
   claims back to the source that owns them.
3. Separate verified facts from inference, conflicting evidence, and unknowns.
   Name missing proof when it could change the answer.
4. Write the findings to a single Markdown file with citations near the claims
   they support. Follow the repository's existing research-note convention;
   when none exists, use a clear location and report it.
5. Post the answer and the file's repository-relative link on the owning
   GitHub Issue. Close the Issue only when its question is answered to its
   stated completion condition.

Use a **background agent** when the host supports delegation and the parent can
continue independent useful work. Otherwise research in the current context.
Parallel Research Issues must have independent questions and file ownership.
