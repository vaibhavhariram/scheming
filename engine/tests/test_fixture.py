"""Replay the shipped fixtures through the engine and demand identical records."""
import json
from pathlib import Path

import pytest

from engine.agents import ScriptedAgent, replay_policy
from engine.game import GameConfig, run_game
from engine.rules import PLAYER_IDS

ROOT = Path(__file__).resolve().parents[2]
TURNS = json.loads((ROOT / "fixtures" / "turns.json").read_text())
GAMES = json.loads((ROOT / "fixtures" / "games.json").read_text())
NIGHT_KILLS = {
    "g-20260919-fx0001": {(1, "p1"): "p2", (1, "p3"): "p2", (2, "p1"): "p4", (3, "p1"): "p0"},
    "g-20260919-fx0002": {(1, "p0"): "p3", (1, "p4"): "p3"},
}


def strip_ts(rec):
    return {k: v for k, v in rec.items() if k != "ts"}


@pytest.mark.parametrize("game", GAMES, ids=[g["game_id"] for g in GAMES])
def test_fixture_game_replays_exactly(game, clock):
    gid = game["game_id"]
    turns = [t for t in TURNS if t["game_id"] == gid]
    policy = replay_policy(turns, NIGHT_KILLS[gid])
    agents = {p: ScriptedAgent(game["models"][i], policy) for i, p in enumerate(PLAYER_IDS)}
    result = run_game(agents, GameConfig(roles=game["roles"]), clock=clock, game_id=gid)
    assert [strip_ts(t) for t in result.turns] == [strip_ts(t) for t in turns]
    assert strip_ts(result.game) == strip_ts(game)
    assert result.state.end_reason == "win"
    assert all(s["parse_failures"] == 0 and s["fallback_turns"] == 0 for s in result.stats.values())


def test_fixture_has_required_properties():
    assert len(TURNS) == 20
    assert len({t["game_id"] for t in TURNS}) == 2
    roles = {(g["game_id"], p): r for g in GAMES for p, r in g["roles"].items()}
    wolf_vs_wolf = [t for t in TURNS if t["role"] == "wolf" and t["vote"] and roles[(t["game_id"], t["vote"])] == "wolf"]
    assert len(wolf_vs_wolf) >= 1
    assert wolf_vs_wolf[0]["game_id"] == "g-20260919-fx0001" and wolf_vs_wolf[0]["player_id"] == "p1"
