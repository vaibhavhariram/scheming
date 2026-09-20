"""Tests for devin/resim.py detect_tags against the frozen live fixtures."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from devin.resim import detect_tags, new_tags, resim

ROOT = Path(__file__).resolve().parents[2]


def _live(game_id):
    d = ROOT / "fixtures" / "live" / game_id
    return (json.loads((d / "turns.json").read_text()),
            json.loads((d / "game.json").read_text()))


def test_bloc_tie_and_tie_stall():
    turns, game = _live("g-20260919-f58efc")
    tags = detect_tags(turns, game)
    assert "bloc_tie" in tags
    assert "tie_stall" in tags


def test_abstain_bloc():
    turns, game = _live("g-20260919-4a66f4")
    assert "abstain_bloc" in detect_tags(turns, game)


def test_new_tags():
    assert new_tags({"a", "b"}, {"a"}) == ["b"]
    assert new_tags({"a"}, {"a", "b"}) == []


def _turn(pid, rnd, vote, public):
    return {"game_id": "g", "round": rnd, "player_id": pid, "model_name": "m",
            "role": "villager", "private": "", "public": public, "vote": vote,
            "ts": "2026-01-01T00:00:00+00:00"}


def test_resim_reads_only_this_calls_dirs(tmp_path):
    stale = tmp_path / "stale-game"
    stale.mkdir()
    # a spray turn: names >=3 other players in public
    (stale / "turns.json").write_text(json.dumps(
        [_turn("p0", 1, "p1", "p1 p2 and p3 are all suspicious to me")]))
    calls = []

    def runner(args, cwd=None, capture_output=True, text=True):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    tags = resim(ROOT, games=2, runner=runner, out_dir=tmp_path)
    assert "spray" not in tags  # the stale dir was not produced by this call
    assert len(calls) == 2
    assert calls[0][0] == sys.executable
