# blocked — human items only (loops never touch these)

| what | owning lane | what it blocks | since |
|---|---|---|---|
| standalone `claude` CLI login expired ("OAuth session expired and could not be refreshed"); fix: run `claude login` in a terminal (browser flow) | human (A's machine) | every `engine/tasks/loop.sh` pass; the six `-p` passes per task at 19:50 all died before the first model call. work continued through in-session builders instead | 2026-09-19 19:55 |
| `MONGODB_URI` (and optional `MONGODB_DB`) absent from `.env` | human (whoever owns the atlas/cluster) | live mongo mirror of `turns`/`games` for lane C; code ships against a fake | 2026-09-19 19:35 |
| `RUNPOD_ENDPOINT_URL` + `RUNPOD_API_KEY` absent from `.env`; no open model deployed yet | human (A) | live games with an open model; adapter ships against a mock endpoint | 2026-09-19 19:35 |
| stale `~/.pyenv/shims/.pyenv-shim` lock (dated 2026-04-06) makes every new login shell wait 60s | human (A's machine) | terminal-panel launches; nothing in the repo | 2026-09-19 19:49 |
| plume project, NOW.md hour-12 block, contract acks for `Game.death_cause` | D / all | judging slot; standup state | standing |
