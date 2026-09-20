"""Build self-contained markdown repair briefs for undesigned exploits.

A brief packs everything a repair session needs into one document: the exploit record,
the game it happened in, the behavioural evidence (turns around the exploit round), the
current rules text, the matching designed trap if any, and the Turn schema from
CONTRACT.md (quoted read-only). Output is devin/state/briefs/<exploit_id>.md.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.traps import trap_for

from .watcher import exploit_id

BRIEFS_DIR = Path("devin/state/briefs")


class Corpus:
    """Turns and games from fixtures, filtered in memory per game."""

    def __init__(self, turns: list[dict], games: list[dict]) -> None:
        self.turns = turns
        self.games = games

    @classmethod
    def from_fixtures(cls, root: Path | str) -> "Corpus":
        root = Path(root)
        turns = json.loads((root / "turns.json").read_text(encoding="utf-8"))
        games = json.loads((root / "games.json").read_text(encoding="utf-8"))
        for live in sorted((root / "live").glob("*")):
            t, g = live / "turns.json", live / "game.json"
            if t.is_file():
                turns += json.loads(t.read_text(encoding="utf-8"))
            if g.is_file():
                games.append(json.loads(g.read_text(encoding="utf-8")))
        return cls(turns, games)

    @classmethod
    def from_mongo(cls, db: Any) -> "MongoCorpus":
        return MongoCorpus(db)

    def for_game(self, game_id: str) -> tuple[list[dict], dict | None]:
        turns = [t for t in self.turns if t["game_id"] == game_id]
        game = next((g for g in self.games if g["game_id"] == game_id), None)
        return turns, game


class MongoCorpus:
    """Same interface, reading the `turns`/`games` collections (lane A owns both)."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def for_game(self, game_id: str) -> tuple[list[dict], dict | None]:
        turns = list(self.db["turns"].find({"game_id": game_id}, {"_id": 0}))
        game = self.db["games"].find_one({"game_id": game_id}, {"_id": 0})
        return turns, game


def _tokens(text: str) -> int:
    return len(text) // 4


def _turn_block(t: dict, exploiting: bool) -> str:
    marker = " ← exploiting player" if exploiting else ""
    return (f"### round {t['round']} — {t['player_id']} ({t['role']}, {t['model_name']}) "
            f"vote={t['vote']}{marker}\n\n"
            f"**private**\n\n```\n{t['private']}\n```\n\n"
            f"**public**\n\n```\n{t['public']}\n```\n")


def _turn_schema(contract_md: str) -> str:
    """The `## Turn` section of CONTRACT.md, verbatim, up to the next `## ` heading."""
    lines = contract_md.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "## Turn")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip()


def build_brief(exploit: dict, corpus, rules_md: str, contract_md: str,
                *, token_budget: int = 6000) -> str:
    eid = exploit_id(exploit)
    turns, game = corpus.for_game(exploit["game_id"])
    r = exploit["round"]
    window = sorted((t for t in turns if max(1, r - 2) <= t["round"] <= r),
                    key=lambda t: (t["round"], t["player_id"]))

    head = [
        f"# Repair brief: {exploit['tag']}",
        "",
        "| field | value |",
        "|---|---|",
        f"| exploit_id | `{eid}` |",
        f"| game_id | `{exploit['game_id']}` |",
        f"| round | {exploit['round']} |",
        f"| player_id | `{exploit['player_id']}` |",
        f"| designed | {exploit['designed']} |",
        f"| ts | {exploit['ts']} |",
        "",
        "## Exploit record",
        "",
        "```json",
        json.dumps(exploit, indent=2),
        "```",
        "",
        "## Game",
        "",
    ]
    if game is None:
        head.append(f"_no Game record found for {exploit['game_id']}_")
    else:
        for k in ("game_id", "models", "roles", "winner", "rounds"):
            head.append(f"- {k}: `{json.dumps(game[k])}`")
        for k in ("death_cause", "trust"):
            if k in game:
                head.append(f"- {k}: `{json.dumps(game[k])}`")
            else:
                head.append(f"- {k}: _not in record (proposed, not in CONTRACT.md)_")

    evidence_head = f"## Behavioural evidence (rounds {max(1, r - 2)}..{r})"

    tail = ["## Current rules (design/rules.md)", "", "```markdown", rules_md.rstrip(), "```", "",
            "## Matching trap", ""]
    trap = trap_for(exploit["tag"])
    if trap is None:
        tail.append(f"_no designed trap matches tag `{exploit['tag']}`; this is an undesigned hole_")
    else:
        tail += [f"trap: `{trap.key}`", "",
                 f"**rule as written:** {trap.rule_as_written}", "",
                 f"**left unsaid:** {trap.left_unsaid}", "",
                 "| designed tag |", "|---|"]
        tail += [f"| `{t}` |" for t in trap.designed_tags]
    tail += ["", "## Turn schema (CONTRACT.md, READ-ONLY — never edit CONTRACT.md)", "",
             _turn_schema(contract_md)]

    def assemble(turn_list: list[dict], truncated: int) -> str:
        parts = ["\n".join(head), "", evidence_head, ""]
        if truncated:
            parts.append(f"_truncated {truncated} turns to fit token budget_\n")
        parts += [_turn_block(t, t["player_id"] == exploit["player_id"]) for t in turn_list]
        parts.append("\n".join(tail))
        return "\n".join(parts).rstrip() + "\n"

    kept = list(window)
    brief = assemble(kept, 0)
    dropped = 0
    while _tokens(brief) > token_budget:
        idx = next((i for i, t in enumerate(kept) if t["player_id"] != exploit["player_id"]), None)
        if idx is None:
            break
        kept.pop(idx)  # sorted already: index 0 is the oldest round
        dropped += 1
        brief = assemble(kept, dropped)
    return brief


def write_brief(exploit: dict, brief_md: str, out_dir: Path | str = BRIEFS_DIR) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{exploit_id(exploit)}.md"
    path.write_text(brief_md, encoding="utf-8")
    return path
