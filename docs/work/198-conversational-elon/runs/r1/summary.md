| Scenario | Host | Arm | Valid | Invalid | SMALL | LARGER | NONE | 4 labels | C pass (crit. 2) | Control pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| control-trivial | claude | A | 3 | 0 | | | | 0 | | 3 |
| control-trivial | claude | B | 3 | 0 | | | | 0 | | 3 |
| control-trivial | claude | C | 3 | 0 | | | | 0 | | 3 |
| control-trivial | codex | A | 3 | 0 | | | | 0 | | 3 |
| control-trivial | codex | B | 3 | 0 | | | | 0 | | 3 |
| control-trivial | codex | C | 3 | 0 | | | | 0 | | 3 |
| control-trivial | grok | A | 3 | 0 | | | | 0 | | 3 |
| control-trivial | grok | B | 3 | 0 | | | | 0 | | 3 |
| control-trivial | grok | C | 3 | 0 | | | | 0 | | 3 |
| control-trivial | opencode | A | 3 | 0 | | | | 0 | | 3 |
| control-trivial | opencode | B | 3 | 0 | | | | 0 | | 3 |
| control-trivial | opencode | C | 3 | 0 | | | | 0 | | 3 |
| target-monitoring | claude | A | 3 | 0 | 0 | 3 | 0 | 0 | 0 | |
| target-monitoring | claude | B | 3 | 0 | 0 | 3 | 0 | 0 | 0 | |
| target-monitoring | claude | C | 3 | 0 | 1 | 2 | 0 | 0 | 0 | |
| target-monitoring | codex | A | 3 | 0 | 3 | 0 | 0 | 0 | 0 | |
| target-monitoring | codex | B | 3 | 0 | 3 | 0 | 0 | 0 | 0 | |
| target-monitoring | codex | C | 3 | 0 | 3 | 0 | 0 | 3 | 3 | |
| target-monitoring | grok | A | 3 | 0 | 0 | 3 | 0 | 0 | 0 | |
| target-monitoring | grok | B | 3 | 0 | 3 | 0 | 0 | 0 | 0 | |
| target-monitoring | grok | C | 3 | 0 | 2 | 1 | 0 | 3 | 2 | |
| target-monitoring | opencode | A | 3 | 0 | 2 | 1 | 0 | 0 | 0 | |
| target-monitoring | opencode | B | 3 | 0 | 2 | 1 | 0 | 0 | 0 | |
| target-monitoring | opencode | C | 3 | 0 | 0 | 3 | 0 | 3 | 0 | |

Pass condition (each line needs >= 2 of the valid runs, valid runs >= 3):
- claude: target discriminates (A and B LARGER) PASS; C criterion 2 FAIL; control (C) PASS
- codex: target discriminates (A and B LARGER) FAIL; C criterion 2 PASS; control (C) PASS
- grok: target discriminates (A and B LARGER) FAIL; C criterion 2 PASS; control (C) PASS
- opencode: target discriminates (A and B LARGER) FAIL; C criterion 2 FAIL; control (C) PASS
