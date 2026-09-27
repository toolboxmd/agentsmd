---
license: MIT
compatibility: Requires a GitHub repository and authenticated GitHub access.
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/engineering/to-tickets
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
  workflow: specify
  workflow-stage: ticket-graph
  default-completion: verified-ticket-publication
  ticket-publication-approval: unresolved-user-decision-only
  implementation-target: first-unblocked-issue
  implementation-context: fresh
  implementation-authority-source: full-current-request
  missing-authority-prompt-limit: 1
  selection: operations
---

# To Tickets

Turn a plan, parent Issue, or conversation into the smallest useful
graph of implementation GitHub Issues when decomposition is needed or requested.
Each Issue owns one narrow, complete, independently provable outcome and fits one
fresh context. Preserve the user-decision gate in the shared procedure below.

Tracer-bullet and expand-contract language guides the decomposition. The
published artifacts are called GitHub Issues.

When this procedure is selected, read and perform [ticket decomposition](references/ticket-decomposition.md), including source gathering, the user-decision gate, publication verification, and the implementation boundary. This shared procedure owns those steps.
