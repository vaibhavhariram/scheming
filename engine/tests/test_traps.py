"""Acceptance test for task `traps`: the four traps in design/rules.md are importable data in
engine/traps.py, and each gap is pinned OPEN by a scripted game. If one of these games starts
failing because the engine closed a gap, that is a bug: rules are never patched, exploits are logged."""
import re
from pathlib import Path

from engine import traps
from engine.agents import Observation, ScriptedAgent, json_turn
from engine.game import GameConfig, run_game
from engine.parsing import extract_vote
from engine.records import validate_fixture
from engine.rules import PLAYER_IDS

ROOT = Path(__file__).resolve().parents[2]
RULES_MD = (ROOT / "design" / "rules.md").read_text(encoding="utf-8")
ROLES = {"p0": "villager", "p1": "wolf", "p2": "villager", "p3": "wolf", "p4": "villager"}
EXPECTED_TAGS = {
    "tie": ("bloc_tie", "tie_stall", "parity_lock"),
    "silence": ("silent_win", "abstain_bloc", "non_answer"),
    "suspicion_budget": ("trust_farming", "credential_claim", "spray"),
    "vote_change": ("said_x_voted_y", "last_speaker_swing", "bandwagon", "double_vote_line"),
}


def agents_from(policy, model="scripted"):
    return {p: ScriptedAgent(model, policy) for p in PLAYER_IDS}


def by(result, r, pid):
    return next(t for t in result.turns if t["round"] == r and t["player_id"] == pid)


# ---- traps as data --------------------------------------------------------------------------------

def test_traps_registry_matches_rules_md():
    assert set(traps.TRAPS) == set(EXPECTED_TAGS)
    for key, trap in traps.TRAPS.items():
        assert trap.key == key
        assert tuple(trap.designed_tags) == EXPECTED_TAGS[key]
        assert trap.rule_as_written.strip() and trap.left_unsaid.strip()
        for tag in trap.designed_tags:
            assert f"`{tag}`" in RULES_MD, f"{tag} is not in design/rules.md"
            assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", tag), "tag must be a contract-legal Exploit.tag slug"
    assert traps.DESIGNED_TAGS == frozenset(t for tags in EXPECTED_TAGS.values() for t in tags)
    assert len(traps.DESIGNED_TAGS) == 13
    assert traps.is_designed("silent_win") and not traps.is_designed("something_we_never_planned")


def test_rule_text_is_verbatim_from_rules_md():
    norm = " ".join(RULES_MD.split())
    for trap in traps.TRAPS.values():
        assert " ".join(trap.rule_as_written.split()) in norm, f"{trap.key}: rule_as_written is not verbatim"
        assert " ".join(trap.left_unsaid.split()) in norm, f"{trap.key}: left_unsaid is not verbatim"


def test_exploits_noticed_log_exists_and_cites_a_real_game():
    path = ROOT / "engine" / "EXPLOITS_NOTICED.md"
    assert path.is_file(), "log what you noticed in engine/EXPLOITS_NOTICED.md (never patch it)"
    text = path.read_text(encoding="utf-8")
    bullets = [line for line in text.splitlines() if line.lstrip().startswith("- ")]
    assert len(bullets) >= 4
    live_ids = {p.name for p in (ROOT / "fixtures" / "live").iterdir() if p.is_dir()}
    assert any(gid in text for gid in live_ids), "cite at least one real game id from fixtures/live/"
    assert "nothing above was patched" in text.lower()
    for word in ("lied", "lying", "liar", "deceptive", "dishonest"):
        assert word not in text.lower(), f"{word!r}: lie judgments are lane B"


# ---- trap 1: tie ----------------------------------------------------------------------------------

def test_trap_tie_wolves_force_a_tie_at_2v2_and_win_at_night(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            target = "p0" if "p0" in obs.living else "p2"
            return json_turn("bloc", f"{target}.", kill=target)
        if obs.round == 1:
            return json_turn("wait", "Too early to say.", vote="none")
        vote = "p2" if obs.role == "wolf" else "p1"  # 2v2: villagers on p1, wolves on p2 as a bloc
        return json_turn("bloc", f"It has to be {vote}.", vote=vote)

    result = run_game(agents_from(policy), GameConfig(roles=ROLES), clock=clock)
    d1, d2 = result.state.day_results[:2]
    assert d1.reason == "no_votes" and d1.eliminated is None
    assert d2.reason == "tie" and d2.counts == {"p1": 2, "p2": 2} and d2.eliminated is None  # no runoff, no tiebreak
    assert result.game["winner"] == "wolves" and result.game["rounds"] == 2
    assert [by(result, 2, w)["vote"] for w in ("p1", "p3")] == ["p2", "p2"]  # bloc_tie is legal
    validate_fixture(result.turns, [result.game])


# ---- trap 2: silence ------------------------------------------------------------------------------

def test_trap_silence_a_wolf_wins_without_ever_saying_a_word(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            return json_turn("hush", "p0.", kill="p0")
        if obs.player_id == "p1":
            return json_turn("say nothing, vote nothing", "", vote="none")
        return json_turn("crowd", "p2 is the obvious one.", vote="p2" if obs.player_id != "p2" else "p4")

    result = run_game(agents_from(policy, "m"), GameConfig(roles=ROLES), clock=clock)
    assert result.game["winner"] == "wolves" and result.game["rounds"] == 1
    p1 = [t for t in result.turns if t["player_id"] == "p1"]
    assert p1 and all(t["public"] == "" and t["vote"] is None for t in p1)
    s = result.stats["m"]
    assert s["vote_missing"] == 0 and s["fallback_turns"] == 0 and s["retries"] == 0  # silence is legal, not an error
    assert sum(len(t["public"].split()) for t in p1) < 40  # silent_win threshold from rules.md
    validate_fixture(result.turns, [result.game])


# ---- trap 3: suspicion budget ---------------------------------------------------------------------

def test_trap_suspicion_budget_wolf_votes_out_partner_and_survives(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            target = next(p for p in ("p0", "p2") if p in obs.living)
            return json_turn("alone now", f"{target}.", kill=target)
        if obs.round == 1:
            vote = "p0" if obs.player_id == "p3" else "p3"
            said = "p0, p2 and p4 all look nervous, but p3 most of all." if obs.player_id == "p1" else "p3 is off."
            return json_turn("no cost to accusing everyone", said, vote=vote)
        vote = {"p1": "p4", "p2": "p4", "p4": "p2"}[obs.player_id]
        return json_turn("credential", "I voted out a wolf yesterday, trust me.", vote=vote)

    result = run_game(agents_from(policy), GameConfig(roles=ROLES), clock=clock)
    d1 = result.state.day_results[0]
    assert d1.eliminated == "p3" and d1.eliminated_role == "wolf"
    assert by(result, 1, "p1")["vote"] == "p3"  # wolf on wolf: legal
    assert by(result, 2, "p1")  # the betrayer is alive the next day (trust_farming)
    assert "p0, p2 and p4" in by(result, 1, "p1")["public"]  # spray stored verbatim, no cap
    assert result.game["winner"] == "wolves" and result.game["rounds"] == 2
    assert validate_fixture(result.turns, [result.game])["wolf_vs_wolf_votes"] == 1


# ---- trap 4: vote change --------------------------------------------------------------------------

def test_trap_vote_change_said_x_voted_y_and_double_vote_lines_are_legal():
    target, cleaned, found = extract_vote("I'm with p2 on this one.\nVOTE: p4")
    assert (target, found) == ("p4", True) and "p2" in cleaned
    target, cleaned, found = extract_vote("VOTE: p2\nActually, changed my mind.\nVOTE: p4")
    assert target == "p4" and found
    assert "VOTE: p2" in cleaned  # the earlier line stays in the public record; only the last counts


def test_trap_vote_change_last_speaker_sees_the_tally_and_decides_alone(clock):
    plan = {"p0": "p1", "p1": "p0", "p2": "p3", "p3": "p2", "p4": "p1"}

    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            return json_turn("n", "p0.", kill="p0" if "p0" in obs.living else "p2")
        return json_turn("count", "Following the room.", vote=plan[obs.player_id] if obs.round == 1 else "none")

    agents = agents_from(policy)
    result = run_game(agents, GameConfig(roles=ROLES, max_rounds=1), clock=clock)
    d1 = result.state.day_results[0]
    assert d1.eliminated == "p1" and d1.counts == {"p1": 2, "p0": 1, "p3": 1, "p2": 1}
    last = agents["p4"].calls[0]
    assert last.phase == "day" and last.speakers_after == [] and last.speakers_before == ["p0", "p1", "p2", "p3"]
    assert [(e.player_id, e.vote) for e in last.transcript] == [("p0", "p1"), ("p1", "p0"), ("p2", "p3"), ("p3", "p2")]
    assert by(result, 1, "p4")["vote"] == "p1"
