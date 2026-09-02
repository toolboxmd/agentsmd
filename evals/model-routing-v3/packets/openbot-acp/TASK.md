# Task: Bound ACP Output Between Active Turns

An ACP child already has aggregate safeguards during one active prompt, but it
can emit unlimited individually valid output during startup, session
attachment, or idle time. Generalize aggregate accounting so every child
lifecycle interval is bounded.

Required behavior:

- use explicit bounded lifecycle phases for startup, session attachment,
  active Turn including cancellation drain, and idle between Turns;
- preserve the existing per-phase ceilings of 16 MiB combined stdout and
  stderr wire bytes and 4,096 complete transport items;
- reset a phase budget only after its predecessor has truthfully settled;
- charge split stdout frames, delayed stderr `\r` and `\r\n` delimiters, and
  same-chunk boundary output exactly once to the originating phase;
- keep the independent 60-second startup and attachment deadlines;
- do not add a normal wall-clock timeout to a healthy active Turn;
- on overflow, expose the existing sanitized ACP transport error exactly once,
  reap the owned process group, and make that client unusable; and
- preserve healthy startup, attachment, idle time, later Turns, and fresh-client
  recovery.

Allowed path:

- `daemon/src/acp.ts`

Public verifier:

```bash
node --import ./node_modules/tsx/dist/loader.mjs --test \
  .benchmark/public/openbot_acp_public.test.ts
```

The supplied Node and TypeScript runtime plus public verifier are read-only
benchmark inputs. Do not change tests, runtime files, package metadata, or any
production file outside `daemon/src/acp.ts`.
