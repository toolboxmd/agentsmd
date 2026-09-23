---
license: MIT
metadata:
  owner: toolboxmd
  origin: cursor/plugins
  origin-skill: pstack/skills/technical-writing
  source-revision: b42effe0aa50f59c693d7e2924714e015e00bf7c
---

# Technical writing

Identify the reader, prior knowledge, immediate task, and what the document must
enable. Choose a shape that serves that purpose. A large document may contain
several clearly separated modes; do not split files solely to enforce a taxonomy.

| Mode | Reader needs | Write |
| --- | --- | --- |
| Tutorial | Learn through successful practice | A complete activity with prerequisites, actions, and visible expected results |
| How-to | Achieve a known goal | Direct steps with relevant conditions, forks, and failure recovery |
| Reference | Look up an exact fact | Structure mirroring the system, consistent fields, and verified examples |
| Explanation | Understand a mechanism or tradeoff | One bounded question developed through concepts, examples, evidence, and reasons |

Keep unrelated background out of an action sequence; link it where helpful.
Put conditions and warnings before the action they govern. Name the expected
result of each meaningful step and what failure looks like. Mirror actual
interfaces in reference material and generate repetitive facts when practical.
For an explanation requiring investigation, use [research](../research/index.md) instead of inventing
historical intent from the present code.

Read [prose editing](references/prose.md) when revising unclear or padded text.
Verify commands, paths, examples, counts, and important claims against the current
artifact. Preserve repository formatting and product-copy conventions. For PRs,
lead with the concrete problem and resulting behavior, then give the proof and
material limits a reviewer needs; link large evidence rather than pasting logs.

Finish when the intended reader can perform the action or understand the claim
without guessing a missing prerequisite. A prose cleanup must preserve facts,
negation, uncertainty, conditions, authority, and technical notation.
