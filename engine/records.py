"""Turn and Game records exactly as CONTRACT.md defines them, plus schema-only validation.

Nothing here judges whether a statement is a lie. That is lane B.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .rules import PLAYER_IDS, ROLES, WINNERS, check_winner, tally

TURN_KEYS = ("game_id", "round", "player_id", "model_name", "role", "private", "public", "vote", "ts")
GAME_KEYS = ("game_id", "models", "roles", "winner", "rounds", "ts")


class RecordError(ValueError):
    pass


def iso_ts(dt: datetime) -> str:
    """tz-aware UTC ISO 8601 with second precision, e.g. 2026-09-19T11:31:05+00:00."""
    if dt.tzinfo is None:
        raise RecordError("timestamps must be tz-aware")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def build_turn(*, game_id: str, round: int, player_id: str, model_name: str, role: str,
               private: str, public: str, vote: str | None, ts: datetime | str) -> dict:
    rec = {
        "game_id": game_id,
        "round": round,
        "player_id": player_id,
        "model_name": model_name,
        "role": role,
        "private": private,
        "public": public,
        "vote": vote,
        "ts": ts if isinstance(ts, str) else iso_ts(ts),
    }
    validate_turn(rec)
    return rec


def build_game(*, game_id: str, models: list[str], roles: dict[str, str], winner: str,
               rounds: int, ts: datetime | str) -> dict:
    rec = {
        "game_id": game_id,
        "models": list(models),
        "roles": dict(roles),
        "winner": winner,
        "rounds": rounds,
        "ts": ts if isinstance(ts, str) else iso_ts(ts),
    }
    validate_game(rec)
    return rec


def _check_keys(rec, keys: tuple[str, ...], what: str) -> None:
    if not isinstance(rec, dict):
        raise RecordError(f"{what} must be an object, got {type(rec).__name__}")
    missing = [k for k in keys if k not in rec]
    extra = [k for k in rec if k not in keys]
    if missing or extra:
        raise RecordError(f"{what} keys wrong: missing={missing} extra={extra}")
    if list(rec.keys()) != list(keys):
        raise RecordError(f"{what} keys out of contract order: {list(rec.keys())}")


def _check_ts(value, what: str) -> datetime:
    if not isinstance(value, str):
        raise RecordError(f"{what}.ts must be a string")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as e:
        raise RecordError(f"{what}.ts is not iso8601: {value!r}") from e
    if dt.tzinfo is None:
        raise RecordError(f"{what}.ts must carry a timezone: {value!r}")
    return dt


def validate_turn(rec) -> None:
    _check_keys(rec, TURN_KEYS, "Turn")
    if not isinstance(rec["game_id"], str) or not rec["game_id"]:
        raise RecordError("Turn.game_id must be a non-empty string")
    if not isinstance(rec["round"], int) or isinstance(rec["round"], bool) or rec["round"] < 1:
        raise RecordError(f"Turn.round must be an int >= 1, got {rec['round']!r}")
    if rec["player_id"] not in PLAYER_IDS:
        raise RecordError(f"Turn.player_id must be one of {PLAYER_IDS}, got {rec['player_id']!r}")
    if not isinstance(rec["model_name"], str) or not rec["model_name"]:
        raise RecordError("Turn.model_name must be a non-empty string")
    if rec["role"] not in ROLES:
        raise RecordError(f"Turn.role must be one of {ROLES}, got {rec['role']!r}")
    for k in ("private", "public"):
        if not isinstance(rec[k], str):
            raise RecordError(f"Turn.{k} must be a string")
    if rec["vote"] is not None and rec["vote"] not in PLAYER_IDS:
        raise RecordError(f"Turn.vote must be null or a player id, got {rec['vote']!r}")
    _check_ts(rec["ts"], "Turn")


def validate_game(rec) -> None:
    _check_keys(rec, GAME_KEYS, "Game")
    if not isinstance(rec["game_id"], str) or not rec["game_id"]:
        raise RecordError("Game.game_id must be a non-empty string")
    models = rec["models"]
    if not isinstance(models, list) or len(models) != len(PLAYER_IDS) or not all(isinstance(m, str) and m for m in models):
        raise RecordError("Game.models must be a list of 5 model names aligned to p0..p4")
    roles = rec["roles"]
    if not isinstance(roles, dict) or set(roles) != set(PLAYER_IDS) or any(r not in ROLES for r in roles.values()):
        raise RecordError("Game.roles must map every p0..p4 to wolf|villager")
    if rec["winner"] not in WINNERS:
        raise RecordError(f"Game.winner must be one of {WINNERS}, got {rec['winner']!r}")
    if not isinstance(rec["rounds"], int) or isinstance(rec["rounds"], bool) or rec["rounds"] < 1:
        raise RecordError("Game.rounds must be an int >= 1")
    _check_ts(rec["ts"], "Game")


def validate_fixture(turns: Iterable[dict], games: Iterable[dict] | dict | None = None,
                     win_rule: str = "majority") -> dict:
    """Structural checks over a set of Turn records (and optionally Game records).

    Checks shape, uniqueness of (game_id, round, player_id), timestamp order, that every
    vote targets a player alive that round and not self, that each round's tally explains
    who is missing next round (one day elimination plus at most one night death), and that
    the Game winner matches the rules. Counts wolf-on-wolf votes. Never judges lies.
    """
    turns = list(turns)
    games_by_id = {}
    if games is not None:
        if isinstance(games, dict):
            games = [games]
        for g in games:
            validate_game(g)
            games_by_id[g["game_id"]] = g
    seen = set()
    for t in turns:
        validate_turn(t)
        key = (t["game_id"], t["round"], t["player_id"])
        if key in seen:
            raise RecordError(f"duplicate (game_id, round, player_id): {key}")
        seen.add(key)
    game_ids = sorted({t["game_id"] for t in turns})
    wolf_vs_wolf = 0
    for gid in game_ids:
        gt = [t for t in turns if t["game_id"] == gid]
        rounds = sorted({t["round"] for t in gt})
        if rounds != list(range(1, len(rounds) + 1)):
            raise RecordError(f"{gid}: rounds must be contiguous from 1, got {rounds}")
        roles = {}
        for t in gt:
            roles.setdefault(t["player_id"], t["role"])
            if roles[t["player_id"]] != t["role"]:
                raise RecordError(f"{gid}: {t['player_id']} changes role between turns")
        if gid in games_by_id:
            g = games_by_id[gid]
            for p, r in roles.items():
                if g["roles"][p] != r:
                    raise RecordError(f"{gid}: roles disagree with games record for {p}")
            roles = dict(g["roles"])
            if g["rounds"] != rounds[-1]:
                raise RecordError(f"{gid}: Game.rounds={g['rounds']} but turns reach round {rounds[-1]}")
        prev_ts = None
        alive = {t["player_id"] for t in gt if t["round"] == 1}
        if gid in games_by_id and alive != set(PLAYER_IDS):
            raise RecordError(f"{gid}: round 1 must include all five players")
        winner = None
        for r in rounds:
            rt = sorted((t for t in gt if t["round"] == r), key=lambda t: t["ts"])
            speakers = {t["player_id"] for t in rt}
            if speakers != alive:
                raise RecordError(f"{gid} round {r}: speakers {sorted(speakers)} != living {sorted(alive)}")
            votes = {}
            for t in rt:
                ts = datetime.fromisoformat(t["ts"])
                if prev_ts is not None and ts < prev_ts:
                    raise RecordError(f"{gid} round {r}: timestamps go backwards at {t['player_id']}")
                prev_ts = ts
                v = t["vote"]
                if v is not None:
                    if v == t["player_id"]:
                        raise RecordError(f"{gid} round {r}: {t['player_id']} votes for self")
                    if v not in alive:
                        raise RecordError(f"{gid} round {r}: {t['player_id']} votes for dead player {v}")
                    if roles.get(v) == "wolf" and t["role"] == "wolf":
                        wolf_vs_wolf += 1
                votes[t["player_id"]] = v
            eliminated, _counts = tally(votes)
            if eliminated:
                alive.discard(eliminated)
            winner = check_winner({p: roles[p] for p in alive}, win_rule)
            if winner:
                if r != rounds[-1]:
                    raise RecordError(f"{gid}: game is decided in round {r} but turns continue")
                break
            if r != rounds[-1]:
                next_alive = {t["player_id"] for t in gt if t["round"] == r + 1}
                gone = alive - next_alive
                if not next_alive <= alive or len(gone) > 1:
                    raise RecordError(f"{gid} round {r}->{r + 1}: living set changes by {sorted(gone)}, expected at most one night death")
                if gone and roles[next(iter(gone))] != "villager":
                    raise RecordError(f"{gid} round {r}: night victim {gone} is not a villager")
                alive = next_alive
            else:
                # last round with no decision after the vote: the night must decide it
                victims = [p for p in alive if roles[p] == "villager"]
                if not victims:
                    raise RecordError(f"{gid}: undecided after the last round and nobody left to kill")
                alive.discard(victims[0])
                winner = check_winner({p: roles[p] for p in alive}, win_rule)
                if winner is None:
                    raise RecordError(f"{gid}: undecided after the last recorded round")
        if gid in games_by_id and games_by_id[gid]["winner"] != winner:
            raise RecordError(f"{gid}: Game.winner={games_by_id[gid]['winner']} but rules give {winner}")
    return {
        "records": len(turns),
        "game_ids": game_ids,
        "wolf_vs_wolf_votes": wolf_vs_wolf,
        "lie_check": "not performed here (lane B)",
    }
