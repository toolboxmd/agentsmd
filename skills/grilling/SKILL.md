---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
license: MIT
metadata:
  owner: toolboxmd
  origin: mattpocock/skills
  origin-skill: skills/productivity/grilling
  source-revision: 6654f6b60cd9d5be8b54c6fafe44346dabeb3b76
---

Interview the user relentlessly until shared understanding. Map a **design tree**
of decisions and their dependencies. Ask in rounds: the **frontier** contains all
questions whose prerequisites are settled. Ask the whole frontier in one round,
number questions, recommend answers, then wait.

```text
❓ **Q1** - **<title>**: <question, with needed context or choices>

➡️ <recommended answer>

---

❓ **Q2** - **<title>**: <question>

➡️ <recommended answer>
```

Recompute the frontier after answers. Questions depending on open questions wait
for later rounds. Find environmental facts yourself: dispatch a sub-agent instead
of asking for facts you can inspect. Running exploration is an unsettled prerequisite;
ask independent frontier questions while it runs. Decisions belong to the user;
never answer for them.

Finish when the frontier is empty: every design branch visited, nothing silently
assumed. Do not act until the user confirms shared understanding.
