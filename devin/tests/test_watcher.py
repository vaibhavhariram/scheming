"""Tests for devin/watcher.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from devin.watcher import (FixtureSource, Ledger, exploit_id, poll_once,
                           source_from_env)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def _exploit(**over):
    rec = {"game_id": "g-1", "round": 2, "player_id": "p1", "tag": "some_hole",
           "description": "did a thing", "designed": False,
           "ts": "2026-09-19T12:00:00+00:00"}
    rec.update(over)
    return rec


def test_exploit_id_deterministic():
    rec = _exploit()
    assert exploit_id(rec) == exploit_id(dict(rec))
    assert len(exploit_id(rec)) == 12
    assert exploit_id(rec) != exploit_id(_exploit(tag="other"))


def test_fixture_source_yields_only_undesigned():
    recs = FixtureSource(FIXTURES / "exploits.json").fetch_undesigned()
    assert len(recs) == 2
    assert all(r["designed"] is False for r in recs)


def test_poll_once_filters_ledger_seen(tmp_path):
    ledger = Ledger(tmp_path / "processed.json")
    rec = _exploit()
    ledger.mark(rec)
    src = FixtureSource(FIXTURES / "exploits.json")
    # fixture records are not in the ledger; a seeded dupe of `rec` must drop
    out = poll_once(src, ledger)
    assert all(exploit_id(r) != exploit_id(rec) for r in out)

    class Two:
        def fetch_undesigned(self):
            return [rec, _exploit(tag="fresh_hole")]

    out = poll_once(Two(), ledger)
    assert [exploit_id(r) for r in out] == [exploit_id(_exploit(tag="fresh_hole"))]


def test_ledger_round_trips(tmp_path):
    path = tmp_path / "state" / "processed.json"
    ledger = Ledger(path)
    rec = _exploit()
    assert not ledger.seen(exploit_id(rec))
    ledger.mark(rec)
    again = Ledger(path)
    assert again.seen(exploit_id(rec))
    stored = json.loads(path.read_text())
    assert stored[exploit_id(rec)]["tag"] == "some_hole"


def test_poll_once_dedupes_within_batch():
    rec = _exploit()

    class Dupes:
        def fetch_undesigned(self):
            return [rec, dict(rec), _exploit(tag="second_hole")]

    out = poll_once(Dupes(), Ledger(Path("/nonexistent/processed.json")))
    assert len(out) == 2


def test_source_from_env_no_uri_is_fixtures(tmp_path):
    source, kind = source_from_env({"MONGODB_URI": ""}, fixtures_path=tmp_path / "x.json")
    assert kind == "fixtures"
    assert isinstance(source, FixtureSource)


def test_source_from_env_unreachable_mongo_falls_back(tmp_path, capsys):
    source, kind = source_from_env({"MONGODB_URI": "mongodb://127.0.0.1:1"},
                                   fixtures_path=tmp_path / "x.json",
                                   server_selection_timeout_ms=1000)
    assert kind == "fixtures"
    assert isinstance(source, FixtureSource)
    assert "falling back to fixtures" in capsys.readouterr().err
