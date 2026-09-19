import itertools

import pytest

from engine.rules import PLAYER_IDS, check_winner, speaking_order, tally, validate_kill, validate_vote


def roles(w, v):
    out = {}
    for i in range(w):
        out[f"w{i}"] = "wolf"
    for i in range(v):
        out[f"v{i}"] = "villager"
    return out


@pytest.mark.parametrize("w,v,expected", [
    (2, 3, None), (2, 2, None), (2, 1, "wolves"), (1, 3, None), (1, 2, None), (1, 1, None),
    (1, 0, "wolves"), (0, 3, "villagers"), (0, 1, "villagers"), (0, 0, "villagers"),
])
def test_check_winner_majority(w, v, expected):
    assert check_winner(roles(w, v)) == expected


def test_check_winner_parity_knob():
    assert check_winner(roles(2, 2), "parity") == "wolves"
    assert check_winner(roles(1, 1), "parity") == "wolves"
    assert check_winner(roles(1, 2), "parity") is None
    with pytest.raises(ValueError):
        check_winner(roles(1, 1), "bogus")


def test_tally_unique_max():
    assert tally({"p0": "p3", "p1": "p3", "p2": "p0", "p3": "p0", "p4": "p3"}) == ("p3", {"p3": 3, "p0": 2})


def test_tally_tie_and_empty():
    assert tally({"p0": "p2", "p1": "p0", "p2": "p0", "p3": "p2", "p4": "p1"})[0] is None
    assert tally({"p0": "p1", "p1": "p0"})[0] is None
    assert tally({"p0": None, "p1": None}) == (None, {})
    assert tally({"p0": None, "p1": "p0"}) == ("p0", {"p0": 1})


def test_speaking_order_rotates_and_skips_dead():
    assert speaking_order(PLAYER_IDS, 1) == ["p0", "p1", "p2", "p3", "p4"]
    assert speaking_order(PLAYER_IDS, 2) == ["p1", "p2", "p3", "p4", "p0"]
    assert speaking_order(["p0", "p1", "p3", "p4"], 2) == ["p1", "p3", "p4", "p0"]
    assert speaking_order(["p0", "p1"], 3) == ["p0", "p1"]
    assert speaking_order(["p0", "p1"], 6) == ["p0", "p1"]


def test_validate_vote_statuses():
    living = ["p0", "p1", "p3"]
    assert validate_vote("p0", "p1", living) == ("p1", "ok")
    assert validate_vote("p0", "p0", living) == (None, "self")
    assert validate_vote("p0", "p2", living) == (None, "dead")
    assert validate_vote("p0", "none", living) == (None, "abstain")
    assert validate_vote("p0", None, living) == (None, "missing")
    assert validate_vote("p0", "p9", living) == (None, "unknown")


def test_validate_kill_statuses():
    lr = {"p0": "wolf", "p1": "villager", "p3": "wolf"}
    assert validate_kill("p0", "p1", lr) == ("p1", "ok")
    assert validate_kill("p0", "p3", lr) == (None, "wolf")
    assert validate_kill("p0", "p0", lr) == (None, "self")
    assert validate_kill("p0", "p2", lr) == (None, "dead")
    assert validate_kill("p0", None, lr) == (None, "missing")
    assert validate_kill("p0", "none", lr) == (None, "abstain")


def test_reachable_turn_totals_under_majority_rule():
    """Every 5-player game where nights kill ends within 3 rounds with 5, 8, 9, 10 or 11 turns."""
    totals, rounds_seen = set(), set()

    def rec(w, v, r, turns):
        turns += w + v
        for outcome in ("W", "V", "tie"):
            w2, v2 = w, v
            if outcome == "W":
                w2 -= 1
            elif outcome == "V":
                v2 -= 1
            if check_winner(roles(w2, v2)):
                totals.add(turns); rounds_seen.add(r); continue
            v3 = v2 - 1  # night always kills a villager
            if check_winner(roles(w2, v3)):
                totals.add(turns); rounds_seen.add(r); continue
            rec(w2, v3, r + 1, turns)

    rec(2, 3, 1, 0)
    assert totals == {5, 8, 9, 10, 11}
    assert max(rounds_seen) == 3


def test_parity_cannot_reach_20_turns_in_two_games():
    totals = set()

    def rec(w, v, r, turns):
        turns += w + v
        for outcome in ("W", "V", "tie"):
            w2, v2 = w, v
            if outcome == "W":
                w2 -= 1
            elif outcome == "V":
                v2 -= 1
            if check_winner(roles(w2, v2), "parity"):
                totals.add(turns); continue
            if check_winner(roles(w2, v2 - 1), "parity"):
                totals.add(turns); continue
            rec(w2, v2 - 1, r + 1, turns)

    rec(2, 3, 1, 0)
    assert totals == {5, 8}
    assert all(a + b != 20 for a, b in itertools.product(totals, repeat=2))
