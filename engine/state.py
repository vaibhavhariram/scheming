"""Mutable game state. Nothing here talks to agents or storage."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .rules import PLAYER_IDS


class Phase(str, Enum):
    DAY = "day"
    NIGHT = "night"
    ENDED = "ended"


@dataclass
class PlayerState:
    player_id: str
    role: str
    model_name: str
    alive: bool = True
    died_round: int | None = None
    died_in: str | None = None  # "day" | "night"


@dataclass
class DayEntry:
    """One spoken statement in the public transcript (vote line already stripped)."""

    round: int
    player_id: str
    public: str
    vote: str | None
    vote_status: str


@dataclass
class DayResult:
    round: int
    counts: dict[str, int]
    eliminated: str | None
    eliminated_role: str | None
    reason: str  # "eliminated" | "tie" | "no_votes"


@dataclass
class NightResult:
    round: int
    killed: str | None
    killed_role: str | None
    reason: str  # "killed" | "no_kill"


@dataclass
class GameState:
    game_id: str
    players: dict[str, PlayerState]
    round: int = 0
    phase: Phase = Phase.DAY
    transcript: list[DayEntry] = field(default_factory=list)
    day_results: list[DayResult] = field(default_factory=list)
    night_results: list[NightResult] = field(default_factory=list)
    winner: str | None = None
    end_reason: str | None = None  # "win" | "max_rounds"

    def living(self) -> list[str]:
        return [p for p in PLAYER_IDS if self.players[p].alive]

    def living_roles(self) -> dict[str, str]:
        return {p: self.players[p].role for p in self.living()}

    def wolves(self) -> list[str]:
        return [p for p in self.living() if self.players[p].role == "wolf"]

    def dead(self) -> list[PlayerState]:
        return [self.players[p] for p in PLAYER_IDS if not self.players[p].alive]

    def kill(self, player_id: str, round_no: int, phase: str) -> None:
        ps = self.players[player_id]
        if not ps.alive:
            raise RuntimeError(f"{player_id} is already dead")
        ps.alive = False
        ps.died_round = round_no
        ps.died_in = phase
