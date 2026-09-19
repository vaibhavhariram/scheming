"""Acceptance test for task `mongo`: Turn and Game records land in the two collections lane A owns,
through a Sink that plugs into run_game. No live mongo: a fake pymongo-shaped database is injected."""
import random

import pytest

from engine.agents import ScriptedAgent, simple_policy
from engine.game import run_game
from engine.mongo_sink import MongoSink
from engine.records import GAME_KEYS, TURN_KEYS, RecordError, build_game, build_turn
from engine.rules import PLAYER_IDS
from engine.sink import MemorySink, MultiSink

TS = "2026-09-19T11:31:05+00:00"


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.docs: dict[tuple, dict] = {}
        self.indexes: list[tuple[tuple, bool]] = []

    @staticmethod
    def _key(flt):
        return tuple(sorted(flt.items()))

    def update_one(self, flt, update, upsert=False, **kw):
        assert set(update) == {"$set"}, "upsert with a single $set"
        key = self._key(flt)
        if key not in self.docs and not upsert:
            return None
        self.docs[key] = {**self.docs.get(key, {}), **dict(update["$set"])}
        return None

    def replace_one(self, flt, doc, upsert=False, **kw):
        key = self._key(flt)
        if key not in self.docs and not upsert:
            return None
        self.docs[key] = dict(doc)
        return None

    def insert_one(self, doc, **kw):
        raise AssertionError("insert_one mutates the caller's dict and is not idempotent; upsert instead")

    def insert_many(self, docs, **kw):
        raise AssertionError("insert_many mutates the caller's dicts and is not idempotent; upsert instead")

    def create_index(self, keys, unique=False, **kw):
        if isinstance(keys, str):
            keys = [keys]
        self.indexes.append((tuple(k if isinstance(k, str) else k[0] for k in keys), bool(unique)))
        return "idx"

    def find(self, flt=None, *a, **kw):
        return [dict(d) for d in self.docs.values()]

    def count_documents(self, flt=None, **kw):
        return len(self.docs)


class FakeDB:
    def __init__(self, name="scheming"):
        self.name = name
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection(name))

    def get_collection(self, name, *a, **kw):
        return self[name]


class FakeClient:
    instances: list = []

    def __init__(self, uri, **kw):
        self.uri, self.kw, self.dbs = uri, kw, {}
        FakeClient.instances.append(self)

    def __getitem__(self, name):
        return self.dbs.setdefault(name, FakeDB(name))

    def get_database(self, name=None, *a, **kw):
        return self[name or "test"]


def turn(**over):
    base = dict(game_id="g1", round=1, player_id="p0", model_name="m", role="villager",
                private="a", public="b", vote="p1", ts=TS)
    base.update(over)
    return build_turn(**base)


def game(**over):
    base = dict(game_id="g1", models=["m"] * 5,
                roles={"p0": "wolf", "p1": "wolf", "p2": "villager", "p3": "villager", "p4": "villager"},
                winner="wolves", rounds=2, ts=TS)
    base.update(over)
    return build_game(**base)


def test_write_turn_upserts_on_the_contract_key_and_never_mutates_the_record():
    db = FakeDB()
    sink = MongoSink(db)
    t = turn()
    sink.write_turn(t)
    sink.write_turn({**t, "public": "edited"})
    sink.write_turn(turn(player_id="p1"))
    sink.write_turn(turn(round=2))
    sink.write_turn(turn(game_id="g2"))
    col = db["turns"]
    assert col.count_documents() == 4
    stored = {(d["game_id"], d["round"], d["player_id"]): d for d in col.find()}
    assert stored[("g1", 1, "p0")]["public"] == "edited"
    assert list(t.keys()) == list(TURN_KEYS) and "_id" not in t
    assert all(set(d) >= set(TURN_KEYS) for d in col.find())


def test_write_game_upserts_on_game_id():
    db = FakeDB()
    sink = MongoSink(db)
    g = game()
    sink.write_game(g)
    sink.write_game({**g, "winner": "villagers"})
    sink.write_game(game(game_id="g2"))
    col = db["games"]
    assert col.count_documents() == 2
    assert {d["game_id"]: d["winner"] for d in col.find()} == {"g1": "villagers", "g2": "wolves"}
    assert list(g.keys()) == list(GAME_KEYS) and "_id" not in g


def test_invalid_records_are_rejected_before_any_write():
    db = FakeDB()
    sink = MongoSink(db)
    with pytest.raises(RecordError):
        sink.write_turn({**turn(), "phase": "day"})
    with pytest.raises(RecordError):
        sink.write_turn({**turn(), "vote": "p9"})
    with pytest.raises(RecordError):
        sink.write_game({"game_id": "g"})
    assert all(c.count_documents() == 0 for c in db.collections.values())


def test_events_and_stats_touch_no_collection():
    db = FakeDB()
    sink = MongoSink(db)
    sink.write_event({"game_id": "g1", "type": "day_start"})
    sink.write_stats("g1", {"scripted": {"calls": 1}})
    assert all(c.count_documents() == 0 for c in db.collections.values())


def test_only_turns_and_games_are_written_over_a_full_game(clock):
    db = FakeDB()
    mem = MemorySink()
    sink = MultiSink(mem, MongoSink(db))
    agents = {p: ScriptedAgent("scripted", simple_policy) for p in PLAYER_IDS}
    result = run_game(agents, rng=random.Random(1), clock=clock, sink=sink)
    assert {name for name, c in db.collections.items() if c.count_documents()} == {"turns", "games"}
    assert db["turns"].count_documents() == len(result.turns) == len(mem.turns) > 0
    assert db["games"].count_documents() == 1
    stored = sorted(db["turns"].find(), key=lambda d: (d["ts"], d["round"], d["player_id"]))
    assert [{k: d[k] for k in TURN_KEYS} for d in stored] == result.turns
    assert {k: db["games"].find()[0][k] for k in GAME_KEYS} == result.game
    assert all(list(t.keys()) == list(TURN_KEYS) for t in mem.turns)  # shared dicts not polluted
    assert list(result.game.keys()) == list(GAME_KEYS)


def test_ensure_indexes_are_unique_on_the_contract_keys():
    db = FakeDB()
    sink = MongoSink(db)
    sink.ensure_indexes()
    sink.ensure_indexes()  # idempotent
    assert (("game_id", "round", "player_id"), True) in db["turns"].indexes
    assert (("game_id",), True) in db["games"].indexes
    assert set(db.collections) <= {"turns", "games"}


def test_from_env_requires_the_uri_and_defaults_the_db_name():
    FakeClient.instances.clear()
    with pytest.raises(Exception, match="MONGODB_URI"):
        MongoSink.from_env(env={}, client_factory=FakeClient)
    assert FakeClient.instances == []
    sink = MongoSink.from_env(env={"MONGODB_URI": "mongodb://fake:27017"}, client_factory=FakeClient)
    assert FakeClient.instances[-1].uri == "mongodb://fake:27017"
    assert sink.db.name == "scheming"
    sink2 = MongoSink.from_env(env={"MONGODB_URI": "mongodb://fake:27017", "MONGODB_DB": "other"},
                               client_factory=FakeClient)
    assert sink2.db.name == "other"
    sink2.write_turn(turn())
    assert sink2.db["turns"].count_documents() == 1


def test_from_env_reads_only_the_given_mapping(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "mongodb://must-not-be-used")
    with pytest.raises(Exception, match="MONGODB_URI"):
        MongoSink.from_env(env={}, client_factory=FakeClient)
    monkeypatch.delenv("MONGODB_URI")
    monkeypatch.setenv("MONGODB_DB", "fromenv")
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake:1")
    sink = MongoSink.from_env(client_factory=FakeClient)  # env=None -> process environment
    assert sink.db.name == "fromenv"


def test_default_client_factory_is_pymongo():
    import pymongo

    import engine.mongo_sink as m

    assert m.MongoClient is pymongo.MongoClient
