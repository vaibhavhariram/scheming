# task: mongo — Turn and Game records into the two collections lane A owns

lane A (engine). python 3.13. no live mongo in tests: a fake database object is injected. the
acceptance test `engine/tests/test_mongo_sink.py` is the spec of record: read it first, never edit it.

## goal

LANES.md build order item 4: "mongo writes conforming to CONTRACT.md". a `Sink` (see
`engine/sink.py`) that mirrors every `Turn` into collection `turns` and every `Game` into
collection `games`, idempotently, with the record dicts exactly as `engine/records.py` builds
them. lane A writes `turns` and `games` and nothing else, ever (CONTRACT.md "collection write
ownership"). `events` and `stats` are engine-local and stay in `JsonDirSink`; this sink ignores them.

## scope (the only paths you may create or change)

- `engine/mongo_sink.py` (new)
- `engine/tasks/mongo.blocked.md`, `engine/tasks/mongo.deps.md`
- `pyproject.toml`, `uv.lock` (only via `uv add`; `pymongo` is already there)

frozen for this task: `engine/sink.py`, `engine/cli.py`, `engine/README.md`, `engine/game.py`,
`engine/records.py`, fixtures, other lanes, `CONTRACT.md`. the CLI flag comes in task `wire`.

## interfaces that must not change

- `engine.sink.Sink` protocol: `write_turn(rec)`, `write_game(rec)`, `write_event(ev)`,
  `write_stats(game_id, stats)`. `MongoSink` implements all four; the last two are no-ops.
- record shape: `engine.records.TURN_KEYS` / `GAME_KEYS`, in that order, validated by
  `validate_turn` / `validate_game`. the sink validates before writing and raises `RecordError`
  on a bad record without touching the database.
- the caller's dict is never mutated. `pymongo`'s `insert_one` adds `_id` to the dict you pass;
  the same dict is shared with the other sinks in a `MultiSink`, so use
  `update_one(filter, {"$set": copy}, upsert=True)` (or `replace_one(filter, copy, upsert=True)`).

## `engine/mongo_sink.py`

```python
from pymongo import MongoClient          # module-level name; tests assert it is pymongo's

class MongoConfigError(RuntimeError): ...

class MongoSink:
    TURNS = "turns"
    GAMES = "games"
    def __init__(self, db): ...          # db: pymongo Database, or anything with db[name] -> collection
    db: ...                              # exposed
    @classmethod
    def from_env(cls, env=None, *, client_factory=MongoClient) -> "MongoSink": ...
    def ensure_indexes(self) -> None: ...
    def write_turn(self, rec: dict) -> None: ...   # upsert on (game_id, round, player_id)
    def write_game(self, rec: dict) -> None: ...   # upsert on game_id
    def write_event(self, ev: dict) -> None: ...   # no-op: not a contract collection
    def write_stats(self, game_id: str, stats: dict) -> None: ...   # no-op
```

- `from_env(env=None, client_factory=MongoClient)`: `env` is a mapping; `None` means
  `os.environ`. when `env` is given, read only from it (never fall back to the process
  environment). `MONGODB_URI` required -> otherwise raise `MongoConfigError` whose message
  contains `MONGODB_URI`. `MONGODB_DB` optional, default `"scheming"` (matches `.env.example`).
  build `client_factory(uri, serverSelectionTimeoutMS=5000)` (extra kwargs are fine) and return
  `cls(client[db_name])`. no ping, no network at construction.
- `ensure_indexes()`: unique index on `turns` `[("game_id", 1), ("round", 1), ("player_id", 1)]`,
  unique index on `games` `[("game_id", 1)]`. safe to call repeatedly.
- errors from the driver propagate (the CLI decides what to do); do not swallow them.
- never log the URI (it can carry a password).

## contract fields involved

all of `Turn` and all of `Game`, unchanged. collections `turns` and `games` only. never write
`scores` or `exploits`, never create any other collection.

## acceptance

- `scheming_root=<main checkout> bash engine/tasks/mongo.check.sh` exits 0 in your worktree.
- `engine/tasks/mongo.deps.md`: `pymongo` (Apache-2.0, https://github.com/mongodb/mongo-python-driver)
  plus anything else you add. if nothing new: say so.
- everything committed on this branch. do not merge, do not push main.
