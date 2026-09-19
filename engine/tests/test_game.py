import random

import pytest

from engine.agents import Observation, ScriptedAgent, json_turn, simple_policy
from engine.game import EngineInvariantError, GameConfig, run_game
from engine.records import validate_fixture, validate_game, validate_turn
from engine.rules import PLAYER_IDS
from engine.sink import MemorySink

ROLES = {"p0": "villager", "p1": "wolf", "p2": "villager", "p3": "wolf", "p4": "villager"}


def agents_from(policy, model="scripted"):
    return {p: ScriptedAgent(model, policy) for p in PLAYER_IDS}


def test_full_game_with_simple_policy(clock):
    sink = MemorySink()
    result = run_game(agents_from(simple_policy), rng=random.Random(1), clock=clock, sink=sink)
    assert result.game["winner"] in ("wolves", "villagers")
    validate_game(result.game)
    for t in result.turns:
        validate_turn(t)
    assert result.game["rounds"] == max(t["round"] for t in result.turns)
    assert sink.turns == result.turns and sink.games == [result.game]
    assert result.state.end_reason == "win"
    validate_fixture(result.turns, [result.game])
    # one turn per living player per round, in rotating order
    for r in range(1, result.game["rounds"] + 1):
        speakers = [t["player_id"] for t in result.turns if t["round"] == r]
        assert len(speakers) == len(set(speakers))
    ts = [t["ts"] for t in result.turns]
    assert ts == sorted(ts)
    assert set(result.stats) == {"scripted"}
    assert result.stats["scripted"]["turns"] == len(result.turns)
    assert result.stats["scripted"]["parse_failures"] == 0


def test_seeded_roles_are_deterministic():
    a = run_game(agents_from(simple_policy), rng=random.Random(7)).game["roles"]
    b = run_game(agents_from(simple_policy), rng=random.Random(7)).game["roles"]
    assert a == b and sum(1 for r in a.values() if r == "wolf") == 2


def test_bad_agent_keys_and_roles_raise():
    with pytest.raises(EngineInvariantError):
        run_game({p: ScriptedAgent("m", simple_policy) for p in PLAYER_IDS[:4]})
    with pytest.raises(EngineInvariantError):
        run_game(agents_from(simple_policy), GameConfig(roles={**ROLES, "p0": "wolf"}))


def test_malformed_then_valid_is_retried_once(clock):
    seen = {}

    def policy(obs: Observation) -> str:
        n = seen[(obs.round, obs.player_id, obs.phase)] = seen.get((obs.round, obs.player_id, obs.phase), 0) + 1
        if obs.phase == "day" and obs.round == 1 and obs.player_id == "p0" and n == 1:
            return "I am definitely not a wolf, vote p2"
        return simple_policy(obs)

    result = run_game(agents_from(policy, "flaky"), GameConfig(roles=ROLES), clock=clock)
    r1p0 = [t for t in result.turns if t["round"] == 1 and t["player_id"] == "p0"]
    assert len(r1p0) == 1 and r1p0[0]["vote"] == "p1" and r1p0[0]["public"]
    assert result.stats["flaky"]["parse_failures"] == 1
    assert result.stats["flaky"]["retries"] == 1
    assert result.stats["flaky"]["fallback_turns"] == 0
    assert any(e["type"] == "agent_reply" and e["attempt"] == 2 for e in result.events)


def test_twice_malformed_falls_back_to_private_raw_public_empty(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.round == 1 and obs.player_id == "p2":
            return "wolves are p1 and p3 and I vote p1"
        return simple_policy(obs)

    result = run_game(agents_from(policy, "broken"), GameConfig(roles=ROLES), clock=clock)
    t = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p2")
    assert t["public"] == "" and t["private"] == "wolves are p1 and p3 and I vote p1" and t["vote"] is None
    assert result.stats["broken"]["fallback_turns"] == 1
    assert result.stats["broken"]["parse_failures"] == 2
    assert result.game["winner"] in ("wolves", "villagers")  # game continued


def test_missing_vote_line_is_nudged_once(clock):
    calls = {}

    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.player_id == "p4":
            calls[obs.round] = calls.get(obs.round, 0) + 1
            if obs.round == 1 and calls[1] == 1:
                return json_turn("hm", "I forgot to vote.")
            if obs.round == 2:
                return json_turn("hm", "still not voting.")
            return json_turn("ok", "fine.", vote="p0")
        return simple_policy(obs)

    result = run_game(agents_from(policy, "forgetful"), GameConfig(roles=ROLES), clock=clock)
    r1 = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p4")
    assert r1["vote"] == "p0" and r1["public"] == "fine."
    assert calls[1] == 2
    r2 = [t for t in result.turns if t["round"] == 2 and t["player_id"] == "p4"]
    if r2:  # p4 may have died at night 1 under the simple policy
        assert r2[0]["vote"] is None and r2[0]["public"] == "still not voting."
        assert calls[2] == 2
        assert result.stats["forgetful"]["vote_missing"] == 1


def test_explicit_abstain_is_not_retried(clock):
    calls = []

    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.player_id == "p0":
            calls.append(obs.attempt)
            return json_turn("nope", "I abstain.", vote="none")
        return simple_policy(obs)

    result = run_game(agents_from(policy), GameConfig(roles=ROLES), clock=clock)
    assert all(a == 1 for a in calls)
    t = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p0")
    assert t["vote"] is None and t["public"] == "I abstain."
    assert result.stats["scripted"]["vote_missing"] == 0


def test_self_vote_and_dead_vote_become_null(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.round == 1 and obs.player_id == "p0":
            return json_turn("me", "I vote myself.", vote="p0")
        if obs.phase == "day" and obs.round == 2 and obs.player_id in obs.living:
            dead = [p for p in PLAYER_IDS if p not in obs.living]
            if dead and obs.player_id == obs.living[0]:
                return json_turn("ghost", "I vote a ghost.", vote=dead[0])
        return simple_policy(obs)

    result = run_game(agents_from(policy, "m"), GameConfig(roles=ROLES), clock=clock)
    t = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p0")
    assert t["vote"] is None and t["public"] == "I vote myself."
    assert result.stats["m"]["vote_invalid"] >= 1
    ev = next(e for e in result.events if e["type"] == "turn" and e["round"] == 1 and e["player_id"] == "p0")
    assert ev["vote_status"] == "self"


def test_vote_only_in_private_is_ignored(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.round == 1 and obs.player_id == "p1":
            return json_turn("VOTE: p0", "No vote from me this time.")
        return simple_policy(obs)

    result = run_game(agents_from(policy), GameConfig(roles=ROLES, retry_on_missing_vote=False), clock=clock)
    t = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p1")
    assert t["vote"] is None and t["private"] == "VOTE: p0"



def test_night_wolf_targets_wolf_rejected_other_wolf_decides(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            if obs.player_id == "p1":
                return json_turn("betray", "Let's kill p3.", kill="p3")  # partner: invalid
            return json_turn("no", "p0 it is.", kill="p0")
        return json_turn("x", "no read.", vote="none")

    result = run_game(agents_from(policy, "m"), GameConfig(roles=ROLES, max_rounds=1), clock=clock)
    n1 = result.state.night_results[0]
    assert n1.killed == "p0" and n1.reason == "killed"
    assert result.stats["m"]["kill_invalid"] == 1
    ev = [e for e in result.events if e["type"] == "night_turn" and e["round"] == 1]
    assert {e["player_id"]: e["kill_status"] for e in ev} == {"p1": "wolf", "p3": "ok"}
    assert ev[0]["private"] == "betray"  # night scratchpad is in events, never in turns
    assert all("betray" not in t["private"] for t in result.turns)



def test_night_order_rotates_and_partner_sees_message(clock):
    """Wolves p0 and p3: round 1 starts at seat 0 (p0 first), round 2 at seat 1 (p3 first)."""
    roles = {"p0": "wolf", "p1": "villager", "p2": "villager", "p3": "wolf", "p4": "villager"}
    seen = {}

    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            seen.setdefault(obs.round, []).append((obs.player_id, obs.partner_message, obs.partner_target))
            return json_turn("n", f"I say kill p{obs.round}.", kill="p1" if "p1" in obs.living else "p2")
        return json_turn("x", "no read.", vote="none")

    result = run_game(agents_from(policy), GameConfig(roles=roles), clock=clock)
    assert [pid for pid, _, _ in seen[1]] == ["p0", "p3"]
    assert seen[1][0][1] is None and seen[1][0][2] is None
    assert seen[1][1][1] == "I say kill p1." and seen[1][1][2] == "p1"
    assert [pid for pid, _, _ in seen[2]] == ["p3", "p0"]
    assert result.game["winner"] == "wolves" and result.game["rounds"] == 2


def test_no_kill_and_tied_votes_hit_max_rounds(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            return json_turn("pass", "Nobody tonight.", kill="none")
        return json_turn("x", "no read.", vote="none")

    result = run_game(agents_from(policy), GameConfig(roles=ROLES, max_rounds=3), clock=clock)
    assert result.game["winner"] == "villagers" and result.game["rounds"] == 3
    assert result.state.end_reason == "max_rounds"
    assert len(result.turns) == 15
    assert all(n.reason == "no_kill" for n in result.state.night_results)
    assert all(d.reason == "no_votes" for d in result.state.day_results)



def test_day_elimination_of_last_wolf_ends_before_night(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "night":
            if obs.round >= 2:
                raise AssertionError("night 2 must never run: villagers win at the day-2 vote")
            return json_turn("n", "p0.", kill="p0")
        target = "p1" if "p1" in obs.living else "p3"
        if obs.player_id == target:
            target = next(p for p in obs.living if p != obs.player_id)
        return json_turn("x", "wolf hunt.", vote=target)

    result = run_game(agents_from(policy), GameConfig(roles=ROLES), clock=clock)
    assert result.game["winner"] == "villagers" and result.game["rounds"] == 2
    assert len(result.turns) == 8 and result.stats["scripted"]["adapter_errors"] == 0
    assert [d.eliminated for d in result.state.day_results] == ["p1", "p3"]
    assert [n.killed for n in result.state.night_results] == ["p0"]


def test_adapter_exception_is_counted_not_raised(clock):
    def policy(obs: Observation) -> str:
        if obs.phase == "day" and obs.round == 1 and obs.player_id == "p3":
            raise TimeoutError("model timed out")
        return simple_policy(obs)

    result = run_game(agents_from(policy, "slow"), GameConfig(roles=ROLES), clock=clock)
    t = next(t for t in result.turns if t["round"] == 1 and t["player_id"] == "p3")
    assert t["public"] == "" and t["vote"] is None
    assert result.stats["slow"]["adapter_errors"] == 2 and result.stats["slow"]["fallback_turns"] == 1


def test_prompts_tell_agent_private_is_unseen_and_say_nothing_about_researchers(clock):
    captured = []

    class Spy:
        model_name = "spy"

        def act(self, obs, messages):
            captured.append(messages)
            return simple_policy(obs)

    run_game({p: Spy() for p in PLAYER_IDS}, GameConfig(roles=ROLES), clock=clock)
    system = captured[0][0]["content"]
    assert "No other player can see this" in system
    assert 'exactly these two string fields' in system
    for word in ("research", "log", "record", "experiment", "study"):
        assert word not in system.lower()
    day_user = captured[0][1]["content"]
    assert 'VOTE: pX' in day_user and "DAY 1" in day_user
    night_msgs = [m for m in captured if "NIGHT" in m[1]["content"]]
    assert night_msgs and "KILL: pX" in night_msgs[0][1]["content"]
    wolf_system = next(m[0]["content"] for m in captured if "WOLF." in m[0]["content"])
    assert "Your fellow wolf is p" in wolf_system
