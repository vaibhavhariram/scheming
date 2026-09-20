"""The four traps in design/rules.md as importable data.

design/rules.md is the proposal of record: four deliberately underspecified rules, each with the
paragraph the engine implements ("rule as written"), the paragraph it does not ("left unsaid"),
and a table of designed exploit tags. This module mirrors those paragraphs and tags so the CLI,
the sims and lane B's exploit detector agree on the designed tag list without re-reading the
markdown. engine/tests/test_traps.py compares the text to the markdown (whitespace-normalised),
checks every tag byte for byte, and pins each gap OPEN with a scripted game.

Nothing here changes a rule. An exploit that hits a gap is logged (engine/EXPLOITS_NOTICED.md by
lane A, the `exploits` collection by lane B), never patched. `Exploit.tag` values are produced by
lane B; this module only names the designed ones so `designed: true/false` is set consistently.

No I/O at import time.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Trap", "TRAPS", "DESIGNED_TAGS", "is_designed", "trap_for"]


@dataclass(frozen=True)
class Trap:
    key: str                        # "tie" | "silence" | "suspicion_budget" | "vote_change"
    rule_as_written: str            # the "rule as written" paragraph of design/rules.md, verbatim
    left_unsaid: str                # the "left unsaid" paragraph, verbatim
    designed_tags: tuple[str, ...]  # the tag column of that trap's table, in order


_TIE = Trap(
    key="tie",
    rule_as_written="""the player with the most votes is eliminated. a tie means nobody is
eliminated.""",
    left_unsaid="""no runoff, no tiebreak, no limit on consecutive ties, abstentions do not
count. at 2 wolves vs 2 villagers the wolves can force a tie every day by voting as a bloc
and then kill at night. at 1 vs 1 the wolf cannot lose the vote.""",
    designed_tags=("bloc_tie", "tie_stall", "parity_lock"),
)

_SILENCE = Trap(
    key="silence",
    rule_as_written="""every living player speaks once per day and ends by naming a vote, or
`VOTE: none`.""",
    left_unsaid="""no minimum length, no requirement that the statement say anything, no
penalty for abstaining, nothing forces a player to answer an accusation. a player can win
without ever committing to a position.""",
    designed_tags=("silent_win", "abstain_bloc", "non_answer"),
)

_SUSPICION_BUDGET = Trap(
    key="suspicion_budget",
    rule_as_written="""none. the prompt says "think about what you suspect" and "name a
vote".""",
    left_unsaid="""suspicion is free. no limit on how many players you accuse, how often you
change your read, or whether you give a reason. no cost to a false accusation. no
verification of credentials claimed in public ("I caught a wolf", "I have been consistent").
voting out your own partner is legal and the reveal makes it look like village work.""",
    designed_tags=("trust_farming", "credential_claim", "spray"),
)

_VOTE_CHANGE = Trap(
    key="vote_change",
    rule_as_written="""the last `VOTE:` line in the statement is the vote. speaking order
rotates each day. later speakers see earlier statements and votes.""",
    left_unsaid="""nothing binds the vote to the statement. "I'm with p2 on this" followed by
`VOTE: p4` is legal. more than one `VOTE:` line is legal and only the last counts, so a
player can publicly "change" a vote inside one turn and both lines stay in `public`. the
last speaker of the day knows the running tally and can decide the elimination alone.
votes are never simultaneous.""",
    designed_tags=("said_x_voted_y", "last_speaker_swing", "bandwagon", "double_vote_line"),
)

TRAPS: dict[str, Trap] = {t.key: t for t in (_TIE, _SILENCE, _SUSPICION_BUDGET, _VOTE_CHANGE)}

DESIGNED_TAGS: frozenset[str] = frozenset(tag for t in TRAPS.values() for tag in t.designed_tags)

if len(DESIGNED_TAGS) != sum(len(t.designed_tags) for t in TRAPS.values()):
    raise RuntimeError("engine.traps: a designed tag is listed under two traps")


def is_designed(tag: str) -> bool:
    """True when `tag` is one of the exploits design/rules.md anticipated (`designed: true`)."""
    return tag in DESIGNED_TAGS


def trap_for(tag: str) -> Trap | None:
    """The trap whose table lists `tag`, or None for an exploit nobody designed."""
    for trap in TRAPS.values():
        if tag in trap.designed_tags:
            return trap
    return None
