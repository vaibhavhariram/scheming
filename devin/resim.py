"""Post-repair resimulation.

Runs scripted games (`engine.cli run --seed <s> --out <dir> --quiet`; scripted agents need
no API key) and re-detects exploit tags on the produced turns to check whether the patch
introduced new holes.

`detect_tags` is a STRUCTURAL STAND-IN: it only covers designed tags decidable from the
turns alone (bloc_tie, tie_stall, abstain_bloc, silent_win, said_x_voted_y,
double_vote_line, spray). Lane B's exploit detector is the real source of tags,
especially `designed: false` ones; this just answers "did the repair game produce a tag
the baseline did not".
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from engine.rules import tally

_PID_RE = re.compile(r"\bp[0-4]\b")
_VOTE_RE = re.compile(r"VOTE:", re.I)


def baseline_tags(source) -> set[str]:
    """All tags currently in the exploit source, designed or not."""
    return {r["tag"] for r in source.fetch_undesigned_all()} if hasattr(source, "fetch_undesigned_all") \
        else {r["tag"] for r in _all_records(source)}


def _all_records(source):
    # FixtureSource exposes a path; mongo sources expose .db
    if hasattr(source, "path"):
        return json.loads(Path(source.path).read_text(encoding="utf-8"))
    return list(source.db["exploits"].find({}, {"_id": 0}))


def detect_tags(turns: list[dict], game: dict | None) -> set[str]:
    """Designed-tag stand-in detection over a game's Turn records."""
    tags: set[str] = set()
    roles = (game or {}).get("roles") or {t["player_id"]: t["role"] for t in turns}
    rounds = sorted({t["round"] for t in turns})
    tied: list[int] = []
    for r in rounds:
        rt = [t for t in turns if t["round"] == r]
        eliminated, counts = tally({t["player_id"]: t["vote"] for t in rt})
        top = max(counts.values()) if counts else 0
        is_tie = eliminated is None and sum(1 for c in counts.values() if c == top) > 1
        if is_tie:
            tied.append(r)
            wolves = [p for p in roles if roles[p] == "wolf"]
            wolf_votes = [t["vote"] for t in rt if t["player_id"] in wolves and t["vote"]]
            if len(wolf_votes) > 1 and len(set(wolf_votes)) == 1:
                tags.add("bloc_tie")
    if any(b - a == 1 for a, b in zip(tied, tied[1:])):
        tags.add("tie_stall")

    for pid in {t["player_id"] for t in turns}:
        mine = sorted((t for t in turns if t["player_id"] == pid), key=lambda t: t["round"])
        if mine and all(t["vote"] is None for t in mine):
            tags.add("abstain_bloc")

    if game and game.get("winner"):
        winners = [p for p, r in roles.items()
                   if (r == "wolf") == (game["winner"] == "wolves")]
        for p in winners:
            words = sum(len(t["public"].split()) for t in turns if t["player_id"] == p)
            if words < 40:
                tags.add("silent_win")

    for t in turns:
        pub = t["public"]
        if len(_VOTE_RE.findall(pub)) >= 2:
            tags.add("double_vote_line")
        mentioned = _PID_RE.findall(pub)
        if t["vote"] and mentioned and mentioned[-1] != t["vote"]:
            tags.add("said_x_voted_y")
        if len(set(mentioned) - {t["player_id"]}) >= 3:
            tags.add("spray")
    return tags


def resim(repo_root: Path | str, *, games: int = 5, seeds=range(1000, 1005),
          runner=subprocess.run, out_dir: Path | str) -> set[str]:
    """Run `games` scripted games and return every tag detected across them."""
    repo_root, out_dir = Path(repo_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pre = {p.name for p in out_dir.iterdir()}
    for s in list(seeds)[:games]:
        r = runner([sys.executable, "-m", "engine.cli", "run", "--seed", str(s),
                    "--out", str(out_dir), "--quiet"], cwd=repo_root,
                   capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"engine.cli run --seed {s} failed (rc={r.returncode}): {r.stderr}")
    found: set[str] = set()
    for gdir in (p for p in out_dir.iterdir() if p.is_dir() and p.name not in pre):
        tj, gj = gdir / "turns.json", gdir / "game.json"
        if tj.is_file():
            game = json.loads(gj.read_text()) if gj.is_file() else None
            found |= detect_tags(json.loads(tj.read_text()), game)
    return found


def new_tags(after: set[str], before: set[str]) -> list[str]:
    return sorted(after - before)
