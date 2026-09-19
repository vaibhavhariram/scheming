"""What an agent sees (Observation), what it must implement (Agent), and scripted agents.

Real model adapters live in engine/adapters/. They only render `messages` and return raw
text; the engine does all parsing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .rules import PLAYER_IDS
from .state import DayEntry, DayResult, NightResult, PlayerState


@dataclass
class Observation:
    game_id: str
    player_id: str
    role: str
    model_name: str
    round: int
    phase: str  # "day" | "night"
    living: list[str]
    dead: list[PlayerState]
    transcript: list[DayEntry]
    day_results: list[DayResult]
    night_results: list[NightResult]
    speakers_before: list[str] = field(default_factory=list)
    speakers_after: list[str] = field(default_factory=list)
    partner: str | None = None
    partner_alive: bool = False
    partner_message: str | None = None
    partner_target: str | None = None
    win_rule: str = "majority"
    attempt: int = 1
    error: str | None = None

    def living_villagers(self, roles: dict[str, str] | None = None) -> list[str]:
        if roles is None:
            return [p for p in self.living if p != self.player_id and p != self.partner]
        return [p for p in self.living if roles[p] == "villager"]


class Agent(Protocol):
    model_name: str

    def act(self, obs: Observation, messages: list[dict]) -> str:
        """Return the model's raw text reply. The engine parses it."""
        ...


def json_turn(private: str, public: str, vote: str | None = None, kill: str | None = None) -> str:
    """Build a well-formed raw reply, appending the VOTE:/KILL: line the engine expects."""
    pub = public
    if vote is not None:
        pub = pub.rstrip() + f"\nVOTE: {vote}"
    if kill is not None:
        pub = pub.rstrip() + f"\nKILL: {kill}"
    return json.dumps({"private": private, "public": pub}, ensure_ascii=False)


class ScriptedAgent:
    """Deterministic agent driven by a policy(Observation) -> raw text. No network."""

    def __init__(self, model_name: str, policy: Callable[[Observation], str]):
        self.model_name = model_name
        self.policy = policy
        self.calls: list[Observation] = []

    def act(self, obs: Observation, messages: list[dict]) -> str:
        self.calls.append(obs)
        return self.policy(obs)


def simple_policy(obs: Observation) -> str:
    """Dry-run heuristic: vote for the next living player after you; wolves kill the first villager."""
    others = [p for p in obs.living if p != obs.player_id]
    if obs.phase == "night":
        target = obs.partner_target
        if target is None:
            candidates = [p for p in others if p != obs.partner]
            target = candidates[0] if candidates else None
        return json_turn(
            f"scripted wolf {obs.player_id}: night {obs.round}, picking {target}",
            f"Let's go with {target}." if target else "Nobody left to pick.",
            kill=target,
        )
    idx = PLAYER_IDS.index(obs.player_id)
    ordered = [p for p in PLAYER_IDS[idx + 1 :] + PLAYER_IDS[:idx] if p in others]
    target = ordered[0] if ordered else None
    if obs.role == "wolf" and obs.partner in others and target == obs.partner and len(ordered) > 1:
        target = ordered[1]
    return json_turn(
        f"scripted {obs.role} {obs.player_id}: day {obs.round}, no real read, voting {target}",
        f"I don't have much to go on. I'll put my vote on {target} for now." if target else "Nothing to say.",
        vote=target,
    )


def replay_policy(turns: list[dict], kills: dict[tuple[int, str], str] | None = None) -> Callable[[Observation], str]:
    """Policy that replays recorded Turn records (e.g. the fixtures) through the engine.

    `kills` maps (round, wolf_id) -> night target for the night calls.
    """
    by_key = {(t["round"], t["player_id"]): t for t in turns}
    kills = kills or {}

    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            target = kills.get((obs.round, obs.player_id))
            return json_turn(f"replay night {obs.round}", f"kill {target}" if target else "no pick", kill=target)
        rec = by_key[(obs.round, obs.player_id)]
        return json_turn(rec["private"], rec["public"], vote=rec["vote"])

    return policy
