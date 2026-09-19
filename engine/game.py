"""The state machine: setup -> (DAY -> NIGHT)* -> END.

Deterministic given the agents, the injected clock and the injected rng. Agent
misbehaviour never raises; only engine invariants do.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Callable, Mapping

from .agents import Agent, Observation
from .parsing import ParsedOutput, extract_kill, extract_vote, parse_agent_output
from .prompts import build_messages
from .records import build_game, build_turn, iso_ts
from .rules import N_WOLVES, PLAYER_IDS, check_winner, speaking_order, tally, validate_kill, validate_vote
from .sink import MemorySink, Sink
from .state import DayEntry, DayResult, GameState, NightResult, Phase, PlayerState

MISSING_VOTE_ERROR = 'it did not end with a "VOTE: pX" line'
MISSING_KILL_ERROR = 'it did not end with a "KILL: pX" line'
STAT_KEYS = ("calls", "turns", "retries", "parse_failures", "fallback_turns", "adapter_errors",
             "vote_missing", "vote_invalid", "kill_invalid")
RAW_CAP = 20_000


class EngineInvariantError(RuntimeError):
    pass


@dataclass
class GameConfig:
    max_rounds: int = 8
    max_attempts: int = 2
    retry_on_missing_vote: bool = True  # also applies to a missing KILL line at night
    win_rule: str = "majority"
    roles: dict[str, str] | None = None


@dataclass
class GameResult:
    game: dict
    turns: list[dict]
    events: list[dict]
    stats: dict
    state: GameState


def default_clock() -> datetime:
    return datetime.now(timezone.utc)


def run_game(agents: Mapping[str, Agent], config: GameConfig | None = None, *,
             clock: Callable[[], datetime] | None = None, rng: random.Random | None = None,
             game_id: str | None = None, sink: Sink | None = None) -> GameResult:
    runner = _Runner(agents, config or GameConfig(), clock or default_clock, rng or random.Random(), game_id, sink or MemorySink())
    return runner.run()


class _Runner:
    def __init__(self, agents, config, clock, rng, game_id, sink):
        if set(agents) != set(PLAYER_IDS):
            raise EngineInvariantError(f"agents must be keyed by {PLAYER_IDS}, got {sorted(agents)}")
        if config.max_rounds < 1 or config.max_attempts < 1:
            raise EngineInvariantError("max_rounds and max_attempts must be >= 1")
        self.agents = agents
        self.config = config
        self.clock = clock
        self.rng = rng
        self.sink = sink
        roles = dict(config.roles) if config.roles else self._draw_roles()
        if set(roles) != set(PLAYER_IDS) or sum(1 for r in roles.values() if r == "wolf") != N_WOLVES \
                or any(r not in ("wolf", "villager") for r in roles.values()):
            raise EngineInvariantError(f"roles must cover p0..p4 with exactly {N_WOLVES} wolves: {roles}")
        gid = game_id or f"g-{self.clock():%Y%m%d}-{uuid.uuid4().hex[:6]}"
        self.state = GameState(game_id=gid, players={p: PlayerState(p, roles[p], agents[p].model_name) for p in PLAYER_IDS})
        self.wolf_ids = [p for p in PLAYER_IDS if roles[p] == "wolf"]
        self.turns: list[dict] = []
        self.events: list[dict] = []
        self.stats: dict[str, dict[str, int]] = {}
        self.emitted: set[tuple[int, str]] = set()

    # ----- helpers -------------------------------------------------------------------
    def _draw_roles(self) -> dict[str, str]:
        wolves = set(self.rng.sample(PLAYER_IDS, N_WOLVES))
        return {p: ("wolf" if p in wolves else "villager") for p in PLAYER_IDS}

    def _stat(self, model_name: str, key: str, n: int = 1) -> None:
        bucket = self.stats.setdefault(model_name, {k: 0 for k in STAT_KEYS})
        bucket[key] += n

    def _event(self, kind: str, **data) -> dict:
        ev = {"ts": iso_ts(self.clock()), "game_id": self.state.game_id, "round": self.state.round,
              "phase": self.state.phase.value, "type": kind, **data}
        self.events.append(ev)
        self.sink.write_event(ev)
        return ev

    def _partner(self, pid: str) -> str | None:
        if self.state.players[pid].role != "wolf":
            return None
        return next(w for w in self.wolf_ids if w != pid)

    def _observe(self, pid: str, phase: str, **kw) -> Observation:
        st = self.state
        partner = self._partner(pid)
        return Observation(
            game_id=st.game_id, player_id=pid, role=st.players[pid].role, model_name=st.players[pid].model_name,
            round=st.round, phase=phase, living=st.living(), dead=[replace(p) for p in st.dead()],
            transcript=list(st.transcript), day_results=list(st.day_results), night_results=list(st.night_results),
            partner=partner, partner_alive=bool(partner and st.players[partner].alive),
            win_rule=self.config.win_rule, **kw,
        )

    def _call_agent(self, pid: str, obs: Observation, living_villagers: list[str] | None = None) -> ParsedOutput:
        agent = self.agents[pid]
        model = agent.model_name
        want_line = "vote" if obs.phase == "day" else "kill"
        best: ParsedOutput | None = None
        last_raw = ""
        error: str | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            obs.attempt, obs.error = attempt, error
            if attempt > 1:
                self._stat(model, "retries")
            messages = build_messages(obs, living_villagers)
            self._stat(model, "calls")
            try:
                raw = agent.act(obs, messages)
            except Exception as e:  # adapter failure is agent misbehaviour, never fatal
                self._stat(model, "adapter_errors")
                error = f"adapter error: {type(e).__name__}: {e}"
                self._event("agent_error", player_id=pid, attempt=attempt, error=error)
                continue
            raw = raw if isinstance(raw, str) else str(raw)
            last_raw = raw[:RAW_CAP]
            parsed = parse_agent_output(raw)
            self._event("agent_reply", player_id=pid, attempt=attempt, ok=parsed.ok, error=parsed.error,
                        warnings=parsed.warnings, raw=last_raw, messages=messages)
            if not parsed.ok:
                self._stat(model, "parse_failures")
                error = parsed.error
                continue
            found = (extract_vote if want_line == "vote" else extract_kill)(parsed.public)[2]
            if not found and self.config.retry_on_missing_vote and attempt < self.config.max_attempts:
                best = parsed
                error = MISSING_VOTE_ERROR if want_line == "vote" else MISSING_KILL_ERROR
                continue
            return parsed
        if best is not None:
            return best
        self._stat(model, "fallback_turns")
        self._event("fallback", player_id=pid, error=error)
        return ParsedOutput(private=last_raw, public="", error=error or "no usable reply")

    # ----- phases --------------------------------------------------------------------
    def _run_day(self, r: int) -> None:
        st = self.state
        order = speaking_order(st.living(), r)
        self._event("day_start", order=order, living=st.living())
        votes: dict[str, str | None] = {}
        for i, pid in enumerate(order):
            obs = self._observe(pid, "day", speakers_before=order[:i], speakers_after=order[i + 1:])
            parsed = self._call_agent(pid, obs)
            target, clean_public, found = extract_vote(parsed.public)
            vote, status = validate_vote(pid, target, st.living())
            model = st.players[pid].model_name
            if status == "missing":
                self._stat(model, "vote_missing")
            elif status not in ("ok", "abstain"):
                self._stat(model, "vote_invalid")
            key = (r, pid)
            if key in self.emitted:
                raise EngineInvariantError(f"turn already emitted for round {r} {pid}")
            rec = build_turn(game_id=st.game_id, round=r, player_id=pid, model_name=model, role=st.players[pid].role,
                             private=parsed.private, public=clean_public, vote=vote, ts=self.clock())
            self.emitted.add(key)
            self.turns.append(rec)
            self.sink.write_turn(rec)
            self._stat(model, "turns")
            st.transcript.append(DayEntry(round=r, player_id=pid, public=clean_public, vote=vote, vote_status=status))
            votes[pid] = vote
            self._event("turn", player_id=pid, vote=vote, vote_status=status, vote_token=target,
                        parse_ok=parsed.ok, warnings=parsed.warnings)
        eliminated, counts = tally(votes)
        if eliminated:
            st.kill(eliminated, r, "day")
            reason, role = "eliminated", st.players[eliminated].role
        else:
            reason, role = ("tie" if counts else "no_votes"), None
        st.day_results.append(DayResult(round=r, counts=counts, eliminated=eliminated, eliminated_role=role, reason=reason))
        self._event("day_result", counts=counts, eliminated=eliminated, eliminated_role=role, reason=reason, living=st.living())
        st.winner = check_winner(st.living_roles(), self.config.win_rule)

    def _run_night(self, r: int) -> None:
        st = self.state
        wolves = speaking_order(st.wolves(), r)
        living_roles = st.living_roles()
        villagers = [p for p, role in living_roles.items() if role == "villager"]
        self._event("night_start", wolves=wolves, living=st.living())
        proposal: str | None = None
        partner_message: str | None = None
        partner_target: str | None = None
        for wid in wolves:
            obs = self._observe(wid, "night", partner_message=partner_message, partner_target=partner_target)
            parsed = self._call_agent(wid, obs, villagers)
            target, message, found = extract_kill(parsed.public)
            valid, status = validate_kill(wid, target, living_roles)
            if status != "ok":
                self._stat(st.players[wid].model_name, "kill_invalid")
            if valid:
                proposal = valid
            partner_message, partner_target = message, valid
            self._event("night_turn", player_id=wid, private=parsed.private, message=message, kill_token=target,
                        kill=valid, kill_status=status, parse_ok=parsed.ok, warnings=parsed.warnings)
        if proposal:
            st.kill(proposal, r, "night")
            result = NightResult(round=r, killed=proposal, killed_role=st.players[proposal].role, reason="killed")
        else:
            result = NightResult(round=r, killed=None, killed_role=None, reason="no_kill")
        st.night_results.append(result)
        self._event("night_result", killed=result.killed, killed_role=result.killed_role, reason=result.reason, living=st.living())
        st.winner = check_winner(st.living_roles(), self.config.win_rule)

    # ----- loop ----------------------------------------------------------------------
    def run(self) -> GameResult:
        st = self.state
        self._event("game_start", roles={p: st.players[p].role for p in PLAYER_IDS},
                    models={p: st.players[p].model_name for p in PLAYER_IDS}, config=vars(self.config))
        for r in range(1, self.config.max_rounds + 1):
            st.round = r
            st.phase = Phase.DAY
            self._run_day(r)
            if st.winner:
                st.end_reason = "win"
                break
            st.phase = Phase.NIGHT
            self._run_night(r)
            if st.winner:
                st.end_reason = "win"
                break
        else:
            st.winner = "villagers"
            st.end_reason = "max_rounds"
            self._event("max_rounds_reached", max_rounds=self.config.max_rounds)
        st.phase = Phase.ENDED
        game = build_game(game_id=st.game_id, models=[st.players[p].model_name for p in PLAYER_IDS],
                          roles={p: st.players[p].role for p in PLAYER_IDS}, winner=st.winner,
                          rounds=st.round, ts=self.clock())
        self.sink.write_game(game)
        self.sink.write_stats(st.game_id, self.stats)
        self._event("game_end", winner=st.winner, rounds=st.round, end_reason=st.end_reason, turns=len(self.turns))
        return GameResult(game=game, turns=self.turns, events=self.events, stats=self.stats, state=st)
