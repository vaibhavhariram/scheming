"""player_id -> elevenlabs voice id.

ROLE-BLIND BY CONSTRUCTION. every function here takes a bare `player_id: str`.
none of them accept a Turn, so `role` is not reachable from this module — a
sinister-wolf mapping is unrepresentable, not merely discouraged.

override the pool without editing code:
    SCHEMING_VOICE_IDS=id1,id2,id3,id4,id5
verify the ids against the account with:
    python3 -m voice.synthesize --list-voices
"""
from __future__ import annotations

import os

__all__ = ["DEFAULT_VOICE_IDS", "voice_pool", "voice_for", "seat_index"]

# elevenlabs premade voices. distinct timbre and gender spread so five speakers
# stay tellable apart over a room mic. confirm with --list-voices before the demo.
DEFAULT_VOICE_IDS: tuple[str, ...] = (
    "21m00Tcm4TlvDq8ikWAM",  # Rachel  — warm female
    "ErXwobaYiN019PkySvjV",  # Antoni  — measured male
    "EXAVITQu4vr4xnSDxMaL",  # Bella   — bright female
    "VR6AewLTigWG4xSOukaG",  # Arnold  — gravelly male
    "MF3mGyEYCl7XYWbV9V6O",  # Elli    — young female
)


def voice_pool() -> tuple[str, ...]:
    raw = (os.environ.get("SCHEMING_VOICE_IDS") or "").strip()
    if not raw:
        return DEFAULT_VOICE_IDS
    ids = tuple(p.strip() for p in raw.split(",") if p.strip())
    if not ids:
        raise ValueError("SCHEMING_VOICE_IDS is set but empty after parsing")
    return ids


def seat_index(player_id: str) -> int:
    """'p3' -> 3. falls back to a stable hash for non-pN ids."""
    digits = "".join(c for c in player_id if c.isdigit())
    if digits:
        return int(digits)
    return sum(ord(c) for c in player_id)


def voice_for(player_id: str) -> str:
    """deterministic, stable across runs, independent of role and of speech order."""
    if not isinstance(player_id, str) or not player_id:
        raise TypeError("voice_for takes a non-empty player_id string, not a Turn")
    pool = voice_pool()
    return pool[seat_index(player_id) % len(pool)]
