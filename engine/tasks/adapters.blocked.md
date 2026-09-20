# blocked — task adapters

items the builder could not resolve inside the task's scope. nothing here stopped the gate.

| what | owning lane | what it blocks | since |
|---|---|---|---|
| `RUNPOD_ENDPOINT_URL` + `RUNPOD_API_KEY` absent from `.env`, no open model deployed, and this build session has no network. the adapter is verified only against `httpx.MockTransport` (protocol shape, auth header, 400 fallback, 401/403, usage accounting, a full no-network game). the first live turn against a real vLLM/TGI endpoint is still unmeasured. | human (A) | live open-model games; per-turn latency / token numbers for the README table | 2026-09-19 (already in `engine/tasks/blocked.md`) |
| `engine/cli.py` `--models` help text and `engine/README.md` still say "'scripted' or claude-* ids"; both are frozen for this task. the registry now also accepts an `org/model` id (routed to `OpenAICompatAgent`), so those two strings are stale. one-line doc fix for whoever next owns `cli.py` / the README (task `wire`). | A (task wire / README) | nothing functional; discoverability only | 2026-09-19 |
