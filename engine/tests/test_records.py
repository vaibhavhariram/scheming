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


# ---------------- lane B collections: shape only ----------------
from engine.records import detect_kind, validate_collection, validate_exploit, validate_score  # noqa: E402


def score(**over):
    base = dict(game_id="g-20260919-fx0001", round=1, player_id="p1", lied=True, lie_kind="deflect", confidence=0.83)
    base.update(over)
    return base


def exploit(**over):
    base = dict(game_id="g-20260919-fx0001", round=2, player_id="p1", tag="wolf_betrays_wolf",
                description="p1 voted out fellow wolf p3 to buy trust", designed=False, ts="2026-09-19T12:00:00+00:00")
    base.update(over)
    return base


def test_detect_kind():
    assert detect_kind(score()) == "scores"
    assert detect_kind(exploit()) == "exploits"
    assert detect_kind(turn()) == "turns"
    with pytest.raises(RecordError):
        detect_kind({"game_id": "g", "round": 1})


@pytest.mark.parametrize("bad", [
    dict(lied="yes"), dict(lied=1), dict(lie_kind="lie"), dict(confidence=1.5), dict(confidence=True),
    dict(confidence="0.5"), dict(round=0), dict(player_id="p7"),
])
def test_validate_score_rejects(bad):
    with pytest.raises(RecordError):
        validate_score(score(**bad))


def test_validate_score_accepts_null_kind_and_int_confidence():
    validate_score(score(lied=False, lie_kind=None, confidence=0))
    validate_score(score(confidence=1))


@pytest.mark.parametrize("bad", [
    dict(tag="Silent Win"), dict(tag=""), dict(designed="no"), dict(description="  "), dict(round=-1),
    dict(ts="2026-09-19T12:00:00"), dict(player_id="p9"),
])
def test_validate_exploit_rejects(bad):
    with pytest.raises(RecordError):
        validate_exploit(exploit(**bad))


def test_validate_exploit_allows_game_level_round_zero():
    validate_exploit(exploit(round=0, tag="silent_win"))


def test_scores_must_join_to_turns_and_be_unique():
    turns = json.loads((ROOT / "fixtures" / "turns.json").read_text())
    ok = validate_collection("scores", [score()], turns=turns)
    assert ok["records"] == 1 and ok["lied"] == 1 and ok["joined_to_turns"] is True
    with pytest.raises(RecordError, match="joins to no Turn"):
        validate_collection("scores", [score(round=9)], turns=turns)
    with pytest.raises(RecordError, match="duplicate Score"):
        validate_collection("scores", [score(), score()], turns=turns)
    # without turns, only shape is checked
    assert validate_collection("scores", [score(round=9)])["joined_to_turns"] is False


def test_exploits_must_name_known_game():
    games = json.loads((ROOT / "fixtures" / "games.json").read_text())
    assert validate_collection("exploits", [exploit()], games=games)["undesigned"] == 1
    with pytest.raises(RecordError, match="unknown game_id"):
        validate_collection("exploits", [exploit(game_id="g-nope")], games=games)


def test_cli_validate_mixed_files(tmp_path, capsys):
    from engine.cli import main

    sp = tmp_path / "scores.json"
    ep = tmp_path / "exploits.json"
    sp.write_text(json.dumps([score(), score(round=2, player_id="p3", lied=False, lie_kind=None, confidence=0.2)]))
    ep.write_text(json.dumps(exploit()))  # single object is fine
    rc = main(["validate", str(ROOT / "fixtures" / "turns.json"), str(ROOT / "fixtures" / "games.json"), str(sp), str(ep)])
    out = capsys.readouterr()
    assert rc == 0, out.err
    assert '"kind": "scores"' in out.out and '"kind": "exploits"' in out.out
    sp.write_text(json.dumps([score(round=7)]))
    rc = main(["validate", str(ROOT / "fixtures" / "turns.json"), str(sp)])
    assert rc == 1 and "joins to no Turn" in capsys.readouterr().err
