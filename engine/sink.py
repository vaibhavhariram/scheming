"""Where records go. Turn/Game dicts are the contract; events and stats are engine-local."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class Sink(Protocol):
    def write_turn(self, rec: dict) -> None: ...
    def write_game(self, rec: dict) -> None: ...
    def write_event(self, ev: dict) -> None: ...
    def write_stats(self, game_id: str, stats: dict) -> None: ...


class MemorySink:
    def __init__(self) -> None:
        self.turns: list[dict] = []
        self.games: list[dict] = []
        self.events: list[dict] = []
        self.stats: dict[str, dict] = {}

    def write_turn(self, rec: dict) -> None:
        self.turns.append(rec)

    def write_game(self, rec: dict) -> None:
        self.games.append(rec)

    def write_event(self, ev: dict) -> None:
        self.events.append(ev)

    def write_stats(self, game_id: str, stats: dict) -> None:
        self.stats[game_id] = stats


class JsonDirSink:
    """runs/<game_id>/turns.jsonl (append, crash-safe), turns.json (array, same shape as the
    fixture, written at game end), game.json, events.jsonl, stats.json."""

    def __init__(self, out_dir: str | Path) -> None:
        self.out_dir = Path(out_dir)
        self._turns: dict[str, list[dict]] = {}

    def _dir(self, game_id: str) -> Path:
        d = self.out_dir / game_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _append(path: Path, rec: dict) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def write_turn(self, rec: dict) -> None:
        self._turns.setdefault(rec["game_id"], []).append(rec)
        self._append(self._dir(rec["game_id"]) / "turns.jsonl", rec)

    def write_game(self, rec: dict) -> None:
        d = self._dir(rec["game_id"])
        (d / "game.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (d / "turns.json").write_text(json.dumps(self._turns.get(rec["game_id"], []), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def write_event(self, ev: dict) -> None:
        self._append(self._dir(ev["game_id"]) / "events.jsonl", ev)

    def write_stats(self, game_id: str, stats: dict) -> None:
        (self._dir(game_id) / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")


class MultiSink:
    def __init__(self, *sinks: Sink) -> None:
        self.sinks = sinks

    def write_turn(self, rec: dict) -> None:
        for s in self.sinks:
            s.write_turn(rec)

    def write_game(self, rec: dict) -> None:
        for s in self.sinks:
            s.write_game(rec)

    def write_event(self, ev: dict) -> None:
        for s in self.sinks:
            s.write_event(ev)

    def write_stats(self, game_id: str, stats: dict) -> None:
        for s in self.sinks:
            s.write_stats(game_id, stats)
