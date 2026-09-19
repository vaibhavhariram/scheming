"""Pure game rules. No I/O, no agents, no timestamps.

Rule set (see engine/README.md):
- 5 players p0..p4, 2 wolves, 3 villagers.
- Round r = DAY r (speak + vote, elimination, win check) then NIGHT r (kill, win check).
- Vote tally: plurality over valid votes; a shared maximum (tie) eliminates nobody.
- Night kill target must be a living villager.
- Win: villagers when no wolves remain; wolves when wolves strictly outnumber villagers
  ("majority", default) or reach parity ("parity", config knob).
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

PLAYER_IDS: tuple[str, ...] = ("p0", "p1", "p2", "p3", "p4")
N_WOLVES = 2
ROLES = ("wolf", "villager")
WINNERS = ("wolves", "villagers")
WIN_RULES = ("majority", "parity")


def check_winner(living_roles: Mapping[str, str], win_rule: str = "majority") -> str | None:
    """Return "wolves", "villagers" or None (game continues)."""
    wolves = sum(1 for r in living_roles.values() if r == "wolf")
    villagers = len(living_roles) - wolves
    if wolves == 0:
        return "villagers"
    if win_rule == "majority":
        return "wolves" if wolves > villagers else None
    if win_rule == "parity":
        return "wolves" if wolves >= villagers else None
    raise ValueError(f"unknown win_rule {win_rule!r}; expected one of {WIN_RULES}")


def tally(votes: Mapping[str, str | None]) -> tuple[str | None, dict[str, int]]:
    """Plurality tally of already-validated votes (None = no vote).

    Returns (eliminated_player_or_None, counts). A shared maximum eliminates nobody.
    """
    counts = Counter(v for v in votes.values() if v)
    if not counts:
        return None, {}
    top = max(counts.values())
    leaders = [p for p, c in counts.items() if c == top]
    return (leaders[0] if len(leaders) == 1 else None), dict(counts)


def validate_vote(voter: str, target: str | None, living: Iterable[str]) -> tuple[str | None, str]:
    """Normalise a parsed vote target. Returns (valid_target_or_None, status).

    status in {"ok", "abstain", "missing", "self", "dead", "unknown"}.
    """
    if target is None:
        return None, "missing"
    if target == "none":
        return None, "abstain"
    if target not in PLAYER_IDS:
        return None, "unknown"
    if target == voter:
        return None, "self"
    if target not in set(living):
        return None, "dead"
    return target, "ok"


def validate_kill(wolf: str, target: str | None, living_roles: Mapping[str, str]) -> tuple[str | None, str]:
    """Night target must be a living villager. Returns (valid_target_or_None, status).

    status in {"ok", "abstain", "missing", "self", "dead", "wolf", "unknown"}.
    """
    if target is None:
        return None, "missing"
    if target == "none":
        return None, "abstain"
    if target not in PLAYER_IDS:
        return None, "unknown"
    if target == wolf:
        return None, "self"
    if target not in living_roles:
        return None, "dead"
    if living_roles[target] == "wolf":
        return None, "wolf"
    return target, "ok"


def speaking_order(living: Iterable[str], round_no: int) -> list[str]:
    """p0..p4 rotated to start at index (round_no - 1) % 5, dead players skipped.

    Used for the day discussion and for the wolves' night order.
    """
    living_set = set(living)
    n = len(PLAYER_IDS)
    start = (round_no - 1) % n
    return [PLAYER_IDS[(start + i) % n] for i in range(n) if PLAYER_IDS[(start + i) % n] in living_set]
