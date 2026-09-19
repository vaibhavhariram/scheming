"""Acceptance test for task `wire`: the CLI takes a per-player model config and mirrors the two
contract collections to mongo when configured. No network, no live mongo, no keys."""
import json
from pathlib import Path

import pytest

import engine.cli as cli
from engine.records import GAME_KEYS, TURN_KEYS
from engine.sink import MemorySink

ROOT = Path(__file__).resolve().parents[2]
FIVE = {p: "scripted" for p in ("p0", "p1", "p2", "p3", "p4")}


class FakeMongoSink(MemorySink):
    calls: list = []
    last = None

    def __init__(self):
        super().__init__()
        self.indexed = 0

    @classmethod
    def from_env(cls, env=None, **kw):
        cls.calls.append(dict(env) if env is not None else None)
        inst = cls()
        cls.last = inst
        return inst

    def ensure_indexes(self):
        self.indexed += 1


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    monkeypatch.setattr(cli, "MongoSink", FakeMongoSink)
    FakeMongoSink.calls = []
    FakeMongoSink.last = None
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: 0)  # the repo-root .env never leaks in
    for var in ("MONGODB_URI", "MONGODB_DB", "RUNPOD_ENDPOINT_URL", "RUNPOD_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    yield


def run(*argv, out):
    return cli.main(["run", "--out", str(out), "--quiet", *argv])


def written(out):
    (gdir,) = [p for p in Path(out).iterdir() if p.is_dir()]
    return json.loads((gdir / "turns.json").read_text()), json.loads((gdir / "game.json").read_text())


def config(tmp_path, players):
    path = tmp_path / "players.json"
    path.write_text(json.dumps({"players": players}))
    return str(path)


def test_config_file_assigns_a_model_per_player(tmp_path):
    cfg = config(tmp_path, FIVE)
    assert run("--config", cfg, "--seed", "1", out=tmp_path / "runs") == 0
    turns, game = written(tmp_path / "runs")
    assert game["models"] == ["scripted"] * 5 and len(turns) >= 5
    assert all(list(t.keys()) == list(TURN_KEYS) for t in turns)


def test_config_with_an_open_model_stops_before_the_game_without_runpod_env(tmp_path, capsys):
    cfg = config(tmp_path, {**FIVE, "p2": "meta-llama/Llama-3.1-8B-Instruct"})
    rc = run("--config", cfg, out=tmp_path / "runs")
    assert rc == 2 and "RUNPOD_ENDPOINT_URL" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_config_must_name_all_five_players_and_excludes_models_flag(tmp_path, capsys):
    cfg = config(tmp_path, {"p0": "scripted"})
    assert run("--config", cfg, out=tmp_path / "a") == 2
    assert not (tmp_path / "a").exists()
    cfg = config(tmp_path, FIVE)
    assert run("--config", cfg, "--models", "scripted", out=tmp_path / "b") == 2
    assert not (tmp_path / "b").exists()
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert run("--config", str(bad), out=tmp_path / "c") == 2
    assert not (tmp_path / "c").exists()


def test_mongo_auto_is_off_without_a_uri_and_on_with_one(tmp_path, monkeypatch):
    assert run("--seed", "1", out=tmp_path / "a") == 0
    assert FakeMongoSink.calls == []
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake:27017")
    assert run("--seed", "1", "--games", "2", out=tmp_path / "b") == 0
    assert len(FakeMongoSink.calls) == 1  # one sink per run invocation, not per game
    sink = FakeMongoSink.last
    assert sink.indexed == 1
    dirs = [p for p in (tmp_path / "b").iterdir() if p.is_dir()]
    assert len(dirs) == 2 and len(sink.games) == 2
    on_disk = sorted((json.loads((d / "turns.json").read_text()) for d in dirs), key=lambda ts: ts[0]["game_id"])
    assert sorted(sink.turns, key=lambda t: (t["game_id"], t["ts"], t["player_id"])) == \
        sorted((t for ts in on_disk for t in ts), key=lambda t: (t["game_id"], t["ts"], t["player_id"]))
    assert all(list(t.keys()) == list(TURN_KEYS) for t in sink.turns)
    assert all(list(g.keys()) == list(GAME_KEYS) for g in sink.games)


def test_mongo_on_requires_a_uri_and_off_never_connects(tmp_path, monkeypatch, capsys):
    rc = run("--mongo", "on", out=tmp_path / "a")
    assert rc == 2 and "MONGODB_URI" in capsys.readouterr().err
    assert not (tmp_path / "a").exists()
    assert FakeMongoSink.calls == []
    monkeypatch.setenv("MONGODB_URI", "mongodb://fake:27017")
    assert run("--mongo", "off", "--seed", "1", out=tmp_path / "b") == 0
    assert FakeMongoSink.calls == []
    assert run("--mongo", "on", "--seed", "1", out=tmp_path / "c") == 0
    assert len(FakeMongoSink.calls) == 1 and len(FakeMongoSink.last.games) == 1


def test_readme_documents_the_flags_and_deps_are_cited():
    readme = (ROOT / "engine" / "README.md").read_text(encoding="utf-8")
    for needle in ("--config", "--mongo", "MONGODB_URI", "MONGODB_DB", "RUNPOD_ENDPOINT_URL", "RUNPOD_API_KEY"):
        assert needle in readme, needle
    deps = (ROOT / "engine" / "deps.md").read_text(encoding="utf-8")
    for needle in ("anthropic", "httpx", "pymongo", "pytest", "MIT", "BSD", "Apache"):
        assert needle in deps, needle
