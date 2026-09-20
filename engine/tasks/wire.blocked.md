# blocked — task wire

none. the acceptance test passed against the spec as written; no frozen file needed a change.

closed by this task (listed under "adapters" in `engine/tasks/blocked.md`): the stale `--models`
help text in `engine/cli.py` now names all three accepted id forms (`scripted`, `claude-*`,
`org/model` on runpod), and `engine/README.md` documents them under "Model ids". the README
itself never contained the literal "'scripted' or claude-* ids" sentence; only the cli help did.

still human, already in `engine/tasks/blocked.md`, not a blocker for the gate: `MONGODB_URI` and
`RUNPOD_ENDPOINT_URL` / `RUNPOD_API_KEY` are absent from `.env`, so `--mongo on` and an
`org/model` seat were exercised here only against the test's fake sink and the adapter's
`preflight`, never live.
