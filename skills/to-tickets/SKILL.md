---
name: to-tickets
description: Break an approved plan or parent Issue into linked implementation Issues with explicit proof and native relationships.
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
  ticket-publication-approval: required
  implementation-target: first-unblocked-issue
  implementation-context: fresh
  implementation-authority-source: full-current-request
  missing-authority-prompt-limit: 1
  invocation: model
---

# To Tickets

Turn an approved plan, parent Issue, or conversation into the smallest useful
graph of implementation GitHub Issues when the user explicitly selects this
Skill. Each Issue owns one narrow, complete, independently provable outcome and
fits one fresh context.

Tracer-bullet and expand-contract language guides the decomposition. The
published artifacts are called GitHub Issues.

When this Skill is selected, read and perform [ticket decomposition](references/ticket-decomposition.md), including source gathering, graph approval, publication verification, and the implementation boundary. This shared procedure owns those steps.
