"""python -m engine.cli run|validate ..."""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

from pymongo.errors import PyMongoError

from .adapters.anthropic_adapter import MissingCredentialsError
from .adapters.registry import make_agent
from .game import GameConfig, run_game
from .mongo_sink import DEFAULT_DB, MongoConfigError, MongoSink
from .records import RecordError, detect_kind, validate_collection
from .rules import N_WOLVES, PLAYER_IDS
from .sink import JsonDirSink, MultiSink

MODEL_IDS = ("'scripted', a claude-* id (Anthropic), or an org/model id served on runpod "
             "(OpenAI-compatible endpoint)")


def load_dotenv(path: Path | None = None) -> int:
    """Set environment variables from a repo-root .env (KEY=VALUE lines). Never overrides a
    variable that is already set, never prints anything. Returns the number of keys applied."""
    path = path or Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return 0
    applied = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value
            applied += 1
    return applied


def _player_models_from_config(path: str) -> list[str]:
    """Read `{"players": {"p0": "<model>", ..., "p4": "<model>"}}` into a list aligned to
    p0..p4. Raises ValueError with a message naming the problem. Touches nothing else: no
    agent is built, no network, no `runs/` directory."""
    where = f"--config {path}"
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"{where}: cannot read file ({e.strerror or e})") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{where}: not valid json ({e.msg} at line {e.lineno} column {e.colno})") from e
    if not isinstance(data, dict) or not isinstance(data.get("players"), dict):
        raise ValueError(f'{where}: expected an object of the form '
                         f'{{"players": {{"p0": "<model>", ..., "p4": "<model>"}}}}')
    players = data["players"]
    missing = [p for p in PLAYER_IDS if p not in players]
    if missing:
        raise ValueError(f"{where}: players missing {', '.join(missing)} "
                         f"(all of {', '.join(PLAYER_IDS)} are required)")
    unknown = sorted(set(players) - set(PLAYER_IDS))
    if unknown:
        raise ValueError(f"{where}: unknown players {', '.join(unknown)} (only {', '.join(PLAYER_IDS)})")
    for p in PLAYER_IDS:
        v = players[p]
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{where}: players.{p} must be a non-empty model name string, got {v!r}")
    return [players[p].strip() for p in PLAYER_IDS]


def _redact_uri(text: str) -> str:
    """A driver error may quote what it tried to reach; a connection URI is never echoed."""
    return re.sub(r"mongodb(\+srv)?://\S+", "mongodb://<redacted>", text)


def _cmd_run(args) -> int:
    load_dotenv()
    if args.config and args.models:
        print("--config and --models are mutually exclusive; give one of them", file=sys.stderr)
        return 2
    if args.config:
        try:
            names = _player_models_from_config(args.config)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
    else:
        names = (args.models or "scripted").split(",")
        if len(names) == 1:
            names = names * len(PLAYER_IDS)
        if len(names) != len(PLAYER_IDS):
            print(f"--models needs 1 or {len(PLAYER_IDS)} names, got {len(names)}", file=sys.stderr)
            return 2
    # the mongo decision comes from the environment (after load_dotenv) and is made before any
    # agent is built or any directory is written
    uri_set = bool((os.environ.get("MONGODB_URI") or "").strip())
    if args.mongo == "on" and not uri_set:
        print("--mongo on: MONGODB_URI is not set; put it in the repo-root .env (see .env.example) "
              "or pass --mongo off", file=sys.stderr)
        return 2
    use_mongo = args.mongo == "on" or (args.mongo == "auto" and uri_set)
    all_names = set(names) | {n for n in (args.wolf_model, args.villager_model) if n}
    try:
        for n in sorted(all_names):
            probe = make_agent(n)
            if hasattr(probe, "preflight"):
                probe.preflight()
    except MissingCredentialsError as e:
        print(f"cannot start a live game: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    sink = JsonDirSink(args.out)
    if use_mongo:
        # one sink per invocation, shared by every game of this run; indexes built once, before
        # the first game. only turns and games go to mongo; events and stats stay in runs/.
        try:
            mongo = MongoSink.from_env()
            mongo.ensure_indexes()
        except (MongoConfigError, PyMongoError) as e:
            print(f"cannot start the mongo mirror: {type(e).__name__}: {_redact_uri(str(e))}", file=sys.stderr)
            return 2
        sink = MultiSink(sink, mongo)
        db_name = (os.environ.get("MONGODB_DB") or "").strip() or DEFAULT_DB
        print(f"mongo: mirroring turns and games to database {db_name!r}")
    elif args.mongo == "auto":
        print("mongo: off (MONGODB_URI not set; writing runs/ only)")
    for i in range(args.games):
        rng = random.Random(None if args.seed is None else args.seed + i)
        roles = None
        seat_names = list(names)
        if args.wolf_model or args.villager_model:
            # draw roles here so a model can be assigned by role, not by seat
            wolves = set(rng.sample(PLAYER_IDS, N_WOLVES))
            roles = {p: ("wolf" if p in wolves else "villager") for p in PLAYER_IDS}
            seat_names = [(args.wolf_model or n) if roles[p] == "wolf" else (args.villager_model or n)
                          for p, n in zip(PLAYER_IDS, names)]
        config = GameConfig(max_rounds=args.max_rounds, win_rule=args.win_rule, roles=roles)
        agents = {p: make_agent(n) for p, n in zip(PLAYER_IDS, seat_names)}
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


def _load(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def _cmd_validate(args) -> int:
    """Validate any contract collection files (turns, games, scores, exploits), auto-detected by
    key set. Files are cross-checked: scores must join to turns, exploits must name known games."""
    loaded: dict[str, list[dict]] = {}
    try:
        for path in args.files:
            records = _load(path)
            if not records:
                raise RecordError(f"{path}: empty")
            kinds = {detect_kind(r) for r in records}
            if len(kinds) != 1:
                raise RecordError(f"{path}: mixes collections {sorted(kinds)}")
            kind = kinds.pop()
            if kind in loaded:
                raise RecordError(f"{path}: a {kind} file was already given")
            loaded[kind] = records
            print(f"{path}: {kind}, {len(records)} records")
        summaries = []
        for kind in ("turns", "games", "scores", "exploits"):
            if kind in loaded:
                summaries.append(validate_collection(kind, loaded[kind], turns=loaded.get("turns"),
                                                     games=loaded.get("games"), win_rule=args.win_rule))
    except RecordError as e:
        print(f"INVALID: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summaries if len(summaries) > 1 else summaries[0], indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="play one or more games and write runs/<game_id>/")
    run.add_argument("--seed", type=int, default=None)
    run.add_argument("--out", default="runs")
    run.add_argument("--models", default=None,
                     help=f"one name for all, or 5 comma-separated names aligned to p0..p4; each is {MODEL_IDS}. "
                          "mutually exclusive with --config")
    run.add_argument("--config", default=None, metavar="PATH",
                     help='json file {"players": {"p0": "<model>", ..., "p4": "<model>"}}: one model id per seat, '
                          f"all five required; each is {MODEL_IDS}. mutually exclusive with --models")
    run.add_argument("--wolf-model", default=None,
                     help="model for the two wolves (roles drawn per game); overrides --models/--config on wolf seats")
    run.add_argument("--villager-model", default=None,
                     help="model for the three villagers; overrides --models/--config on villager seats")
    run.add_argument("--mongo", default="auto", choices=("auto", "on", "off"),
                     help="mirror turns and games to mongo (MONGODB_URI, MONGODB_DB) in addition to runs/: "
                          "auto = on when MONGODB_URI is set (default), on = require it, off = never connect")
    run.add_argument("--games", type=int, default=1)
    run.add_argument("--max-rounds", type=int, default=8)
    run.add_argument("--win-rule", default="majority", choices=("majority", "parity"))
    run.add_argument("--quiet", action="store_true")
    run.set_defaults(func=_cmd_run)
    val = sub.add_parser("validate", help="structural check of turns/games/scores/exploits json files (kind auto-detected)")
    val.add_argument("files", nargs="+", metavar="FILE")
    val.add_argument("--win-rule", default="majority", choices=("majority", "parity"))
    val.set_defaults(func=_cmd_validate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
