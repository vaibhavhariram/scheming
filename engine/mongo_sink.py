"""MongoSink: mirror Turn and Game records into the two collections lane A owns.

`turns` and `games` only (CONTRACT.md "collection write ownership"). Events and stats are
engine-local and stay in JsonDirSink, so here they are no-ops and never create a collection.

Every record is validated with the CONTRACT validators before any write and is never mutated:
pymongo's insert_one adds `_id` to the dict it is handed, and the same dict is shared with the
other sinks in a MultiSink, so each write is an upsert of a copy under a single `$set`.
Construction does no network I/O (no ping, no index build); call `ensure_indexes()` explicitly.
Driver errors propagate to the caller. The connection URI is never logged or echoed.
"""
from __future__ import annotations

import copy
import os
from collections.abc import Mapping
from typing import Any

from pymongo import MongoClient

from .records import validate_game, validate_turn

TURN_ID_FIELDS = ("game_id", "round", "player_id")
GAME_ID_FIELDS = ("game_id",)
DEFAULT_DB = "scheming"  # matches .env.example
SERVER_SELECTION_TIMEOUT_MS = 5000


class MongoConfigError(RuntimeError):
    """Raised by `MongoSink.from_env` when the environment cannot describe a database."""


class MongoSink:
    TURNS = "turns"
    GAMES = "games"

    def __init__(self, db: Any) -> None:
        # db: a pymongo Database, or anything where db[name] yields a collection with
        # update_one(filter, update, upsert=...) and create_index(keys, unique=...).
        self.db = db

    def __repr__(self) -> str:
        return f"MongoSink(db={getattr(self.db, 'name', '?')!r})"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, client_factory=MongoClient) -> "MongoSink":
        """Build a sink from `MONGODB_URI` (required) and `MONGODB_DB` (default "scheming").

        Reads only the mapping given; `None` means the process environment. No network at
        construction: the driver connects lazily on the first operation.
        """
        source: Mapping[str, str] = os.environ if env is None else env
        uri = (source.get("MONGODB_URI") or "").strip()
        if not uri:
            raise MongoConfigError("MONGODB_URI is not set; copy .env.example to .env and fill it in")
        db_name = (source.get("MONGODB_DB") or "").strip() or DEFAULT_DB
        client = client_factory(uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS)
        return cls(client[db_name])

    def ensure_indexes(self) -> None:
        """Unique indexes on the contract keys. Safe to call repeatedly."""
        self.db[self.TURNS].create_index([(k, 1) for k in TURN_ID_FIELDS], unique=True)
        self.db[self.GAMES].create_index([(k, 1) for k in GAME_ID_FIELDS], unique=True)

    def write_turn(self, rec: dict) -> None:
        validate_turn(rec)  # raises RecordError before the database is touched
        self._upsert(self.TURNS, TURN_ID_FIELDS, rec)

    def write_game(self, rec: dict) -> None:
        validate_game(rec)
        self._upsert(self.GAMES, GAME_ID_FIELDS, rec)

    def write_event(self, ev: dict) -> None:
        """No-op: events are not a contract collection (they live in JsonDirSink)."""

    def write_stats(self, game_id: str, stats: dict) -> None:
        """No-op: stats are not a contract collection (they live in JsonDirSink)."""

    def _upsert(self, collection: str, key: tuple[str, ...], rec: dict) -> None:
        flt = {k: rec[k] for k in key}
        # deep copy: the driver must never see the caller's dict, and nested Game.roles/models
        # must not alias it either
        self.db[collection].update_one(flt, {"$set": copy.deepcopy(rec)}, upsert=True)
