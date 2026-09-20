# blocked — human items only (loops never touch these)

| what | owning lane | what it blocks | since |
|---|---|---|---|
| standalone `claude` CLI login expired ("OAuth session expired and could not be refreshed"); fix: run `claude login` in a terminal (browser flow) | human (A's machine) | every `engine/tasks/loop.sh` pass; the six `-p` passes per task at 19:50 all died before the first model call. work continued through in-session builders instead | 2026-09-19 19:55 |
| `MONGODB_URI` (and optional `MONGODB_DB`) absent from `.env` | human (whoever owns the atlas/cluster) | live mongo mirror of `turns`/`games` for lane C; code ships against a fake | 2026-09-19 19:35 |
| `RUNPOD_ENDPOINT_URL` + `RUNPOD_API_KEY` absent from `.env`; no open model deployed yet | human (A) | live games with an open model; adapter ships against a mock endpoint | 2026-09-19 19:35 |
| stale `~/.pyenv/shims/.pyenv-shim` lock (dated 2026-04-06) makes every new login shell wait 60s | human (A's machine) | terminal-panel launches; nothing in the repo | 2026-09-19 19:49 |
| plume project, NOW.md hour-12 block, contract acks for `Game.death_cause` | D / all | judging slot; standup state | standing |

## from task builders (verbatim, folded 20:03)

### adapters

# blocked — task adapters

items the builder could not resolve inside the task's scope. nothing here stopped the gate.

| what | owning lane | what it blocks | since |
|---|---|---|---|
| `RUNPOD_ENDPOINT_URL` + `RUNPOD_API_KEY` absent from `.env`, no open model deployed, and this build session has no network. the adapter is verified only against `httpx.MockTransport` (protocol shape, auth header, 400 fallback, 401/403, usage accounting, a full no-network game). the first live turn against a real vLLM/TGI endpoint is still unmeasured. | human (A) | live open-model games; per-turn latency / token numbers for the README table | 2026-09-19 (already in `engine/tasks/blocked.md`) |
| `engine/cli.py` `--models` help text and `engine/README.md` still say "'scripted' or claude-* ids"; both are frozen for this task. the registry now also accepts an `org/model` id (routed to `OpenAICompatAgent`), so those two strings are stale. one-line doc fix for whoever next owns `cli.py` / the README (task `wire`). | A (task wire / README) | nothing functional; discoverability only | 2026-09-19 |

### mongo

# blocked — task mongo

none. the acceptance test passed against the spec as written; no frozen file needed a change.

not a blocker for this task, already tracked in `engine/tasks/blocked.md`: `MONGODB_URI` is absent
from `.env`, so the live mirror cannot be exercised here. tests inject a fake database by design;
the CLI flag that turns the sink on comes in task `wire`.

### traps

# traps — blocked

nothing blocked. every test in `engine/tests/test_traps.py` passed against the frozen engine as
it stands; no gap needed closing and none was closed.
