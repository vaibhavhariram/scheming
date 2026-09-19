# task: wire — CLI flags for per-player model config and the mongo mirror, docs, citations

lane A (engine). python 3.13. no network, no live mongo, no keys in tests. starts only after
tasks `adapters` and `mongo` have landed on main (their modules must exist in your worktree). the
acceptance test `engine/tests/test_cli_wire.py` is the spec of record: read it first, never edit it.

## goal

close LANES.md items 3 and 4 at the command line: `python -m engine.cli run --config players.json`
assigns a model per player; when `MONGODB_URI` is set the two contract collections are mirrored to
mongo in addition to `runs/<game_id>/`. document it. cite every dependency.

## scope (the only paths you may create or change)

- `engine/cli.py`
- `engine/README.md`
- `engine/deps.md` (create or extend; keep existing lines)
- `engine/tasks/wire.blocked.md`, `engine/tasks/wire.deps.md`
- `pyproject.toml`, `uv.lock` (only via `uv add`)

frozen: everything else, in particular `engine/adapters/**`, `engine/mongo_sink.py`,
`engine/game.py`, `engine/sink.py`, fixtures, other lanes, `CONTRACT.md`.

## interfaces you consume (do not change them)

- `engine.mongo_sink.MongoSink`: `from_env(env=None, *, client_factory=...)`, `ensure_indexes()`,
  and the `Sink` protocol. import it at module level in `engine/cli.py` as the name `MongoSink`
  (the test monkeypatches `engine.cli.MongoSink`).
- `engine.adapters.registry.make_agent(name)`: hugging-face style ids (with `/`) build an open-model
  agent whose `preflight()` raises `MissingCredentialsError` naming `RUNPOD_ENDPOINT_URL` /
  `RUNPOD_API_KEY` when they are unset. the existing preflight loop in `_cmd_run` already handles
  that; keep it.
- `engine.cli.load_dotenv` stays a module-level function called by `_cmd_run` (the test replaces it).
- `validate` subcommand: unchanged.

## behaviour

`run` gains:

- `--config PATH`: json `{"players": {"p0": "<model>", ..., "p4": "<model>"}}`. all five ids
  required, values are model names accepted by `make_agent`. mutually exclusive with `--models`
  (both given -> stderr, exit 2). `--wolf-model` / `--villager-model` still override by role on
  top of it. a malformed or incomplete file -> stderr names the problem, exit 2, no `runs/` dir.
- `--mongo {auto,on,off}`, default `auto`. after `load_dotenv()`: `off` -> never touch mongo.
  `on` -> `MONGODB_URI` must be in `os.environ`, else stderr names `MONGODB_URI`, exit 2, before any
  game and before creating the `runs/` dir. `auto` -> behaves as `on` when `MONGODB_URI` is set,
  else `off`. when active: `sink = MultiSink(JsonDirSink(args.out), mongo)` where
  `mongo = MongoSink.from_env()` followed by `mongo.ensure_indexes()`, created once per `run`
  invocation, before the first game. never print the URI.
- `engine/README.md`: document `--config` (with the json shape), `--mongo`, `MONGODB_URI`,
  `MONGODB_DB`, `RUNPOD_ENDPOINT_URL`, `RUNPOD_API_KEY`, and that hugging-face style ids route to
  the OpenAI-compatible adapter. keep the existing sections.
- `engine/deps.md`: one line per third-party dependency with name, license, url:
  `anthropic` (MIT), `httpx` (BSD-3-Clause), `pymongo` (Apache-2.0), `pytest` (MIT), plus anything
  in `engine/tasks/*.deps.md`. required at submission.

## contract fields involved

`Game.models` reflects the config (aligned to p0..p4). nothing else changes. never write
`scores` or `exploits`.

## acceptance

- `scheming_root=<main checkout> bash engine/tasks/wire.check.sh` exits 0 in your worktree.
- everything committed on this branch. do not merge, do not push main.
