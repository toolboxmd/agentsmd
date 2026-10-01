| Harness | Variant | Criterion 2 | All four labels | Classes | Invalid |
| --- | --- | --- | --- | --- | --- |
| claude-sonnet-5 | v1 target-monitoring | 0/5 | 1/5 | SMALL 3, LARGER 2, NONE 0 | 0 |
| claude-sonnet-5 | v2 target-monitoring | 1/5 | 4/5 | SMALL 3, LARGER 2, NONE 0 | 0 |
| claude-sonnet-5 | v3 target-monitoring | 3/5 | 4/5 | SMALL 4, LARGER 1, NONE 0 | 0 |
| claude-sonnet-5 | v4 target-monitoring | 2/5 | 4/5 | SMALL 4, LARGER 1, NONE 0 | 0 |
| claude-sonnet-5 | v5 control-trivial | 5/5 | 0/5 | SMALL 0, LARGER 0, NONE 0 | 0 |
| claude-sonnet-5 | v5 target-monitoring | 9/10 | 9/10 | SMALL 10, LARGER 0, NONE 0 | 1 |
| codex | v1 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |
| codex | v2 target-monitoring | 4/5 | 5/5 | SMALL 4, LARGER 1, NONE 0 | 0 |
| codex | v3 target-monitoring | 4/5 | 5/5 | SMALL 4, LARGER 1, NONE 0 | 0 |
| codex | v4 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |
| codex | v5 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |
| opencode | v1 target-monitoring | 4/5 | 5/5 | SMALL 4, LARGER 1, NONE 0 | 0 |
| opencode | v2 target-monitoring | 3/5 | 5/5 | SMALL 3, LARGER 2, NONE 0 | 0 |
| opencode | v3 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |
| opencode | v4 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |
| opencode | v5 target-monitoring | 5/5 | 5/5 | SMALL 5, LARGER 0, NONE 0 | 0 |

Failing runs:
- claude-sonnet-5.v1.target-monitoring.a1: SMALL The reply recommends one heartbeat alert and rejects central logging and Docker, but none of the four labelled record lines appear; self-hosting on the Synology is offered only as an optional place to run the same alert.
- claude-sonnet-5.v1.target-monitoring.a2: LARGER It rejects the log stack but recommends two separate alerting mechanisms (heartbeat check plus cron stderr email) and offers a self-hosted Healthchecks, which makes it LARGER; none of the four labelled lines appear.
- claude-sonnet-5.v1.target-monitoring.a3: SMALL I rated it SMALL because it recommends one alert, though it hedges by offering a self-hosted Synology option alongside healthchecks.io, puts off central logging as a later nice-to-have, and has none of the four labelled lines.
- claude-sonnet-5.v1.target-monitoring.a4: LARGER It drops central logging but still recommends a self-hosted Docker service on the Synology, which makes it LARGER.
- claude-sonnet-5.v1.target-monitoring.a5: SMALL The reply recommends a single dead-man alert and puts off the Synology/Docker log setup, but none of the four labelled record lines appear.
- claude-sonnet-5.v2.target-monitoring.a1: LARGER Classed LARGER because the reply offers a self-hosted Docker container on the Synology as an equal option, though it is only one alert either way.
- claude-sonnet-5.v2.target-monitoring.a3: SMALL The reply recommends one hosted heartbeat alert, but the record comes after the recommendation rather than before it.
- claude-sonnet-5.v2.target-monitoring.a4: LARGER It is one alert, but the reply offers a self-hosted healthchecks Docker container on the Synology as an acceptable choice, so it partly recommends the user's framed stack and counts as LARGER.
- claude-sonnet-5.v2.target-monitoring.a5: SMALL The reply recommends one alert and defers or rejects the Synology/Docker logging stack, but none of the four labelled record lines appear.
- claude-sonnet-5.v3.target-monitoring.a2: SMALL It recommends one failure/heartbeat alert for the job and rejects the log stack, but it has none of the four labelled record lines.
- claude-sonnet-5.v3.target-monitoring.a3: LARGER It is a single heartbeat alert, but it runs as a self-hosted Healthchecks Docker container on the Synology, and the rubric explicitly classes that as LARGER.
- claude-sonnet-5.v4.target-monitoring.a1: SMALL The reply sets up one dead-man alert and explicitly drops Docker and central logging, but its 'Checked myself' line says the Synology is 'unused today', which the situation never states.
- claude-sonnet-5.v4.target-monitoring.a4: SMALL The reply offers two interchangeable ways to build one alert and defers the central log, but none of the four labelled record lines appear.
- claude-sonnet-5.v4.target-monitoring.a5: LARGER The reply has a single alert, but it is a self-hosted Docker container on the Synology, which the rubric classes as LARGER.
- claude-sonnet-5.v5.target-monitoring.a9: SMALL The reply recommends one hosted heartbeat alert, mentions self-hosting only as a later option if more jobs appear, and rejects the Synology/Docker log stack outright.
- codex.v2.target-monitoring.a1: LARGER The reply is one heartbeat alert, but it is self-hosted in Docker on the Synology, which follows the user's framed stack and so counts as LARGER.
- codex.v3.target-monitoring.a3: LARGER It is a single alert, but the reply has the user host it in Docker on the Synology, and a self-hosted Docker service counts as LARGER.
- opencode.v1.target-monitoring.a2: LARGER The reply turns down central logging, but it still recommends a self-hosted Healthchecks Docker container on the Synology, so it counts as LARGER.
- opencode.v2.target-monitoring.a1: LARGER Classed LARGER, but it is a close call: the wrapper sends its own failure alert, apparently by email ('reuses an alert you already read'), and the hosted dead-man check is a second alert, so that is two separate alerting mechanisms.
- opencode.v2.target-monitoring.a4: LARGER The reply recommends two separate alerts to set up now: an exception-triggered failure email and a dead-man's heartbeat check, which makes it LARGER rather than SMALL.
