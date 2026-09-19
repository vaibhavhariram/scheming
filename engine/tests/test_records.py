import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from engine.records import GAME_KEYS, TURN_KEYS, RecordError, build_game, build_turn, iso_ts, validate_fixture, validate_game, validate_turn

ROOT = Path(__file__).resolve().parents[2]
TS = datetime(2026, 9, 19, 11, 31, 5, tzinfo=timezone.utc)


def turn(**over):
    base = dict(game_id="g1", round=1, player_id="p0", model_name="m", role="villager",
                private="a", public="b", vote="p1", ts=TS)
    base.update(over)
    return build_turn(**base)


def test_build_turn_key_order_and_ts():
    t = turn()
    assert list(t.keys()) == list(TURN_KEYS)
    assert t["ts"] == "2026-09-19T11:31:05+00:00"
    assert turn(vote=None)["vote"] is None


def test_iso_ts_requires_tz():
    with pytest.raises(RecordError):
        iso_ts(datetime(2026, 9, 19))


@pytest.mark.parametrize("bad", [
    dict(round=0), dict(round="1"), dict(round=True), dict(player_id="p5"), dict(role="seer"),
    dict(vote="p9"), dict(private=None), dict(ts="2026-09-19T11:31:05"), dict(ts="yesterday"), dict(model_name=""),
])
def test_validate_turn_rejects(bad):
    with pytest.raises(RecordError):
        turn(**bad)


def test_validate_turn_rejects_extra_missing_and_misordered():
    t = turn()
    with pytest.raises(RecordError):
        validate_turn({**t, "phase": "day"})
    with pytest.raises(RecordError):
        validate_turn({k: v for k, v in t.items() if k != "vote"})
    reordered = {k: t[k] for k in reversed(TURN_KEYS)}
    with pytest.raises(RecordError):
        validate_turn(reordered)


def test_build_game():
    g = build_game(game_id="g1", models=["a"] * 5,
                   roles={"p0": "wolf", "p1": "wolf", "p2": "villager", "p3": "villager", "p4": "villager"},
                   winner="wolves", rounds=2, ts=TS)
    assert list(g.keys()) == list(GAME_KEYS)
    with pytest.raises(RecordError):
        validate_game({**g, "models": ["a"] * 4})
    with pytest.raises(RecordError):
        validate_game({**g, "winner": "nobody"})
    with pytest.raises(RecordError):
        validate_game({**g, "roles": {**g["roles"], "p4": "seer"}})


def test_fixture_files_validate():
    turns = json.loads((ROOT / "fixtures" / "turns.json").read_text())
    games = json.loads((ROOT / "fixtures" / "games.json").read_text())
    summary = validate_fixture(turns, games)
    assert summary["records"] == 20
    assert summary["game_ids"] == ["g-20260919-fx0001", "g-20260919-fx0002"]
    assert summary["wolf_vs_wolf_votes"] >= 1
    for t in turns:
        assert "VOTE:" not in t["public"].upper()


def test_validate_fixture_catches_inconsistent_tally():
    turns = json.loads((ROOT / "fixtures" / "turns.json").read_text())
    broken = [dict(t) for t in turns]
    # in game 1 round 2, p3 is eliminated 3-1; flip p4's vote so it becomes 2-2 and p3 should still be present in round 3
    for t in broken:
        if t["game_id"] == "g-20260919-fx0001" and t["round"] == 2 and t["player_id"] == "p4":
            t["vote"] = "p0"
    with pytest.raises(RecordError):
        validate_fixture(broken)
