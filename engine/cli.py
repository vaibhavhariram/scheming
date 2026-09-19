"""python -m engine.cli run|validate ..."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from .adapters.registry import make_agent
from .game import GameConfig, run_game
from .records import RecordError, validate_fixture
from .rules import PLAYER_IDS
from .sink import JsonDirSink


def _cmd_run(args) -> int:
    names = (args.models or "scripted").split(",")
    if len(names) == 1:
        names = names * len(PLAYER_IDS)
    if len(names) != len(PLAYER_IDS):
        print(f"--models needs 1 or {len(PLAYER_IDS)} names, got {len(names)}", file=sys.stderr)
        return 2
    config = GameConfig(max_rounds=args.max_rounds, win_rule=args.win_rule)
    sink = JsonDirSink(args.out)
    for i in range(args.games):
        rng = random.Random(None if args.seed is None else args.seed + i)
        agents = {p: make_agent(n) for p, n in zip(PLAYER_IDS, names)}
        result = run_game(agents, config, rng=rng, sink=sink)
        g = result.game
        print(f"{g['game_id']}: winner={g['winner']} rounds={g['rounds']} turns={len(result.turns)} "
              f"roles={{{', '.join(f'{p}:{r[0]}' for p, r in g['roles'].items())}}}")
        if not args.quiet:
            for t in result.turns:
                vote = t["vote"] or "-"
                print(f"  [R{t['round']}] {t['player_id']} ({t['role'][0]}, {t['model_name']}) -> {vote}: {t['public'][:110]!r}")
            for n in result.state.night_results:
                print(f"  [N{n.round}] {n.reason}: {n.killed or ''} {('(' + n.killed_role + ')') if n.killed_role else ''}")
        for model, s in result.stats.items():
            print(f"  stats {model}: " + " ".join(f"{k}={v}" for k, v in s.items() if v))
        usage = {p: a.usage for p, a in agents.items() if getattr(a, "usage", None)}
        if usage:
            tot_in = sum(u["input_tokens"] for u in usage.values())
            tot_out = sum(u["output_tokens"] for u in usage.values())
            print(f"  tokens: input={tot_in} output={tot_out} requests={sum(u['requests'] for u in usage.values())}")
        print(f"  written to {Path(args.out) / g['game_id']}")
    return 0


def _cmd_validate(args) -> int:
    turns = json.loads(Path(args.turns).read_text(encoding="utf-8"))
    games = json.loads(Path(args.games).read_text(encoding="utf-8")) if args.games else None
    try:
        summary = validate_fixture(turns, games, win_rule=args.win_rule)
    except RecordError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="play one or more games and write runs/<game_id>/")
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--out", default="runs")
    run.add_argument("--models", default=None, help="one name for all, or 5 comma-separated names aligned to p0..p4 ('scripted' or claude-* ids)")
    run.add_argument("--games", type=int, default=1)
    run.add_argument("--max-rounds", type=int, default=8)
    run.add_argument("--win-rule", default="majority", choices=("majority", "parity"))
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(func=_cmd_run)
    val = sub.add_parser("validate", help="structural check of Turn (and Game) json files")
    val.add_argument("turns")
    val.add_argument("games", nargs="?")
    val.add_argument("--win-rule", default="majority", choices=("majority", "parity"))
    val.set_defaults(func=_cmd_validate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
