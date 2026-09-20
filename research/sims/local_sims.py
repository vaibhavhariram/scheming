"""Local parallel sims: lane A's engine cli, run many times on the machines we have.

    python3 -m research.sims.local_sims run --models claude-haiku-4-5,claude-sonnet-5
    python3 -m research.sims.local_sims plot

Replaces the cut modal sims. Nothing here reimplements game logic and nothing here
writes `turns` or `games`: every game is played by a `python3 -m engine.cli run`
subprocess, so those writes stay inside lane A's own code and one-writer-per-collection
still holds even though lane B launches the runs. Lane B writes only what it owns --
`scores` (via research.score), the batch manifest under research/results/sims/, and
the plot under research/plots/.

Two things the engine cannot do today, and what this module does instead:

1. `game_id` prefix. `engine.game` mints `g-<date>-<hex6>` and `engine.cli` exposes no
   flag to change it, so a `localsim-` game_id would need an edit to engine/ (lane A).
   Instead the whole batch lands in one directory named `runs/localsim-<batch_id>/`,
   and `research/results/sims/<batch_id>.json` records every game_id in it. The batch
   is filterable by path and by manifest; nothing needed a schema change.

2. Cost. CONTRACT.md's Turn has nine keys and no `cost_usd`; `engine.records` rejects
   any extra key, so there is no per-turn cost to sum. `engine.cli` does print a
   per-game `tokens: input=... output=... requests=...` line, which this module parses
   and prices with `research.score.PRICES` -- lane B's own table, already used by the
   scorer. Same number, derived one level up. A model missing from that table is
   counted as $0 and reported as unpriced rather than silently dropped.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

from ..score import PRICES, cost_usd

REPO_ROOT = Path(__file__).resolve().parents[2]
SIMS_DIR = REPO_ROOT / "research" / "results" / "sims"
PLOTS_DIR = REPO_ROOT / "research" / "plots"
PLOT_PATH = PLOTS_DIR / "lie_rate_by_model.png"
RUNS_ROOT = REPO_ROOT / "runs"
BATCH_PREFIX = "localsim-"

DEFAULT_TOTAL_GAMES = 24
DEFAULT_MAX_PARALLEL = 4
DEFAULT_BUDGET_USD = 8.0
# below this many games a per-model lie rate is noise, not a measurement
MIN_GAMES_PER_MODEL = 4

# engine/cli.py `_cmd_run` stdout, one block per game
RE_GAME = re.compile(r"^(?P<game_id>\S+): winner=(?P<winner>\S+) rounds=(?P<rounds>\d+) turns=(?P<turns>\d+)")
RE_TOKENS = re.compile(r"^\s+tokens: input=(?P<input>\d+) output=(?P<output>\d+) requests=(?P<requests>\d+)\s*$")
RE_WRITTEN = re.compile(r"^\s+written to (?P<path>.+?)\s*$")
RE_STATS = re.compile(r"^\s+stats (?P<model>\S+): (?P<kv>.+?)\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------- model roster

def known_model_hint() -> str:
    return ("real ids come from engine/adapters/registry.py: 'scripted' (free, no API), any claude-* id "
            "(Anthropic), or an org/model id served on runpod. Measured-good players: claude-haiku-4-5, "
            "claude-sonnet-5, claude-opus-4-8. claude-opus-5 / claude-fable* / claude-mythos* refuse the "
            "werewolf prompt and the registry rejects them.")


def validate_models(names: list[str]) -> None:
    """Reject a typo before we launch dozens of subprocesses. Uses lane A's registry as the
    single source of truth; builds an adapter object and throws it away -- no key, no network."""
    from engine.adapters.registry import make_agent

    bad = []
    for name in names:
        try:
            make_agent(name)
        except ValueError as e:
            bad.append(f"  {name}: {e}")
    if bad:
        raise SystemExit("--models: lane A's adapter registry rejects:\n" + "\n".join(bad)
                         + f"\n{known_model_hint()}")


def allocate(models: list[str], total: int) -> list[str]:
    """One entry per game, round-robin over the roster so every model gets the same count
    give or take one. Round-robin rather than blocked so an interrupted batch is still
    balanced across models."""
    if total < len(models):
        raise SystemExit(f"--total-games {total} is fewer than the {len(models)} models in --models; "
                         "every listed model must get at least one game")
    return [models[i % len(models)] for i in range(total)]


# ----------------------------------------------------------------------------- one game

class GameOutcome:
    """One `engine.cli run --games 1` subprocess and what it produced."""

    def __init__(self, index: int, model: str, seed: int | None) -> None:
        self.index = index
        self.model = model
        self.seed = seed
        self.game_id: str | None = None
        self.run_dir: str | None = None
        self.winner: str | None = None
        self.rounds: int | None = None
        self.turns: int | None = None
        self.tokens: dict | None = None
        self.cost: float | None = None       # None = model not in PRICES (unpriced, counted as 0)
        self.stats: dict = {}
        self.returncode: int | None = None
        self.error: str | None = None
        self.adapter_error: str | None = None
        self.seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.game_id is not None and self.error is None

    @property
    def degraded(self) -> bool:
        """A game where the adapter fell back or errored. Its turns look like silence to the
        scorer, so counting them would drag the lie rate toward zero for reasons that have
        nothing to do with the model."""
        return bool(self.stats.get("fallback_turns") or self.stats.get("adapter_errors")
                    or self.stats.get("parse_failures"))

    @property
    def fully_degraded(self) -> bool:
        """Every turn is a fallback: the model never answered once. engine.cli still exits 0 and
        still declares a winner, so without this check a dead key or an empty account produces a
        full batch of plausible-looking games worth nothing."""
        return bool(self.turns) and self.stats.get("fallback_turns", 0) >= self.turns

    def as_record(self) -> dict:
        return {
            "index": self.index, "model": self.model, "seed": self.seed, "game_id": self.game_id,
            "run_dir": self.run_dir, "winner": self.winner, "rounds": self.rounds, "turns": self.turns,
            "tokens": self.tokens, "cost_usd": self.cost, "unpriced": self.tokens is not None and self.cost is None,
            "stats": self.stats, "degraded": self.degraded, "fully_degraded": self.fully_degraded,
            "adapter_error": self.adapter_error, "returncode": self.returncode,
            "error": self.error, "seconds": round(self.seconds, 1),
        }


def parse_run_stdout(text: str) -> list[dict]:
    """Pull one block per game out of `engine.cli run` stdout. The blocks are
    `<game_id>: winner=...` then indented `stats`, `tokens` and `written to` lines."""
    games: list[dict] = []
    for line in text.splitlines():
        m = RE_GAME.match(line)
        if m:
            games.append({"game_id": m["game_id"], "winner": m["winner"],
                          "rounds": int(m["rounds"]), "turns": int(m["turns"]),
                          "tokens": None, "run_dir": None, "stats": {}})
            continue
        if not games:
            continue
        cur = games[-1]
        if m := RE_TOKENS.match(line):
            cur["tokens"] = {"input_tokens": int(m["input"]), "output_tokens": int(m["output"]),
                             "requests": int(m["requests"])}
        elif m := RE_WRITTEN.match(line):
            cur["run_dir"] = m["path"]
        elif m := RE_STATS.match(line):
            # `stats <model>: k=v k=v` -- the cli prints only non-zero counters
            stats = {}
            for pair in m["kv"].split():
                k, _, v = pair.partition("=")
                stats[k] = int(v) if v.isdigit() else v
            cur["stats"].update(stats)
    return games


def play_one(out_dir: Path, model: str, index: int, seed: int | None, max_rounds: int,
             win_rule: str, timeout: float) -> GameOutcome:
    """Shell out to lane A. One game per subprocess, so cost is attributable per game and
    the batch can stop between games rather than mid-run.

    `--models <one name>` gives all five seats that model (engine/cli.py duplicates a single
    name across p0..p4). Homogeneous games are what makes a per-model lie rate mean anything
    and what makes the single printed `tokens:` line attributable to one model.
    """
    outcome = GameOutcome(index, model, seed)
    cmd = [sys.executable, "-m", "engine.cli", "run",
           "--models", model, "--games", "1", "--quiet", "--mongo", "off",
           "--out", str(out_dir), "--max-rounds", str(max_rounds), "--win-rule", win_rule]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    t0 = time.monotonic()
    try:
        # env is inherited: ANTHROPIC_API_KEY stays in the environment and never reaches argv
        proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        outcome.seconds = time.monotonic() - t0
        outcome.returncode = -1
        outcome.error = f"timed out after {timeout:.0f}s"
        return outcome
    outcome.seconds = time.monotonic() - t0
    outcome.returncode = proc.returncode
    parsed = parse_run_stdout(proc.stdout)
    if proc.returncode != 0 or not parsed:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        outcome.error = tail[-1][:300] if tail else f"no game parsed (exit {proc.returncode})"
        return outcome
    g = parsed[0]
    outcome.game_id, outcome.run_dir = g["game_id"], g["run_dir"]
    outcome.winner, outcome.rounds, outcome.turns = g["winner"], g["rounds"], g["turns"]
    outcome.stats = g["stats"]
    outcome.tokens = g["tokens"]
    if g["tokens"]:
        outcome.cost = cost_usd(model, g["tokens"])
    else:
        outcome.cost = 0.0 if model == "scripted" else None
    if outcome.degraded and g["run_dir"]:
        outcome.adapter_error = first_adapter_error(Path(g["run_dir"]))
    return outcome


def first_adapter_error(run_dir: Path) -> str | None:
    """The reason behind a fallback, out of lane A's events.jsonl. The cli prints counters but
    not causes, and 'every call failed' is not actionable without the cause -- a dead key, an
    empty account and a rate limit all look identical in the counters."""
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            ev = json.loads(line)
            if ev.get("error"):
                return _tidy_adapter_error(str(ev["error"]))
    except (OSError, json.JSONDecodeError):
        return None
    return None


_RE_API_MESSAGE = re.compile(r"'message': '([^']+)'")


def _tidy_adapter_error(text: str) -> str:
    """Keep the sentence a human can act on. The raw event carries the whole serialised API body,
    whose request_id differs per call -- left in, four copies of one problem print as four."""
    text = text.removeprefix("adapter error: ").strip()
    exc, _, rest = text.partition(":")
    if m := _RE_API_MESSAGE.search(rest):
        return f"{exc.strip()}: {m.group(1)}"
    return text[:300]


# ----------------------------------------------------------------------------- the batch

def run_batch(models: list[str], total_games: int, max_parallel: int, budget_usd: float,
              out_root: Path, seed: int | None, max_rounds: int, win_rule: str,
              timeout: float) -> dict:
    """Launch games across a thread pool, stop launching once the budget is spent.

    Each unit of work is an external subprocess, so threads are the right tool: they block
    in `subprocess.run` and release the GIL. Work is submitted a slot at a time rather than
    all at once, so the budget check sees every completed game's real cost before the next
    game starts.
    """
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = out_root / f"{BATCH_PREFIX}{batch_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    roster = allocate(models, total_games)

    lock = threading.Lock()
    spent = 0.0
    unpriced_games = 0
    results: list[GameOutcome] = []
    stopped_for_budget = False
    stopped_dead = False
    pending = iter(list(enumerate(roster)))
    t0 = time.monotonic()
    # a batch where the first few games saw no model output at all is a broken key, an empty
    # account or a dead endpoint. Burning the other twenty games' wall clock to confirm it is
    # the expensive way to learn that.
    dead_batch_after = max(2, min(3, total_games))

    def submit_next(ex: ThreadPoolExecutor):
        try:
            i, model = next(pending)
        except StopIteration:
            return None
        return ex.submit(play_one, out_dir, model, i, None if seed is None else seed + i,
                         max_rounds, win_rule, timeout)

    _log(f"batch {batch_id}: {total_games} games over {len(models)} model(s), "
         f"{max_parallel} at a time, budget ${budget_usd:.2f}")
    _log(f"  games -> {out_dir}")
    for m in models:
        _log(f"    {m}: {roster.count(m)} games")

    with ThreadPoolExecutor(max_workers=max_parallel) as ex:
        futures = set()
        for _ in range(max_parallel):
            f = submit_next(ex)
            if f is None:
                break
            futures.add(f)
        while futures:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done:
                outcome = fut.result()
                with lock:
                    results.append(outcome)
                    if outcome.ok:
                        if outcome.cost is None:
                            unpriced_games += 1
                        else:
                            spent += outcome.cost
                    n = len(results)
                if outcome.ok:
                    cost_str = "unpriced" if outcome.cost is None else f"${outcome.cost:.4f}"
                    flag = "  NO MODEL OUTPUT" if outcome.fully_degraded else ("  DEGRADED" if outcome.degraded else "")
                    _log(f"  [{n}/{total_games}] {outcome.model} {outcome.game_id} "
                         f"winner={outcome.winner} turns={outcome.turns} {cost_str} "
                         f"({outcome.seconds:.0f}s) spent=${spent:.2f}{flag}")
                    if outcome.adapter_error:
                        _log(f"        adapter: {outcome.adapter_error}")
                else:
                    _log(f"  [{n}/{total_games}] FAILED {outcome.model} (exit {outcome.returncode}): "
                         f"{outcome.error}")
            with lock:
                over = spent >= budget_usd
                done_ok = [r for r in results if r.ok]
                dead = len(done_ok) >= dead_batch_after and all(r.fully_degraded for r in done_ok)
            if dead:
                if not stopped_dead:
                    stopped_dead = True
                    _log(f"  STOPPING: the first {len(done_ok)} games produced no model output at all. "
                         "Every turn is a fallback, so nothing here can be scored.")
                continue
            if over:
                if not stopped_for_budget:
                    stopped_for_budget = True
                    _log(f"  budget ${budget_usd:.2f} reached (spent ${spent:.2f}); "
                         "letting in-flight games finish, launching no more")
                continue
            while len(futures) < max_parallel:
                f = submit_next(ex)
                if f is None:
                    break
                futures.add(f)

    elapsed = time.monotonic() - t0
    ok = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    degraded = [r for r in ok if r.degraded]
    dead = [r for r in ok if r.fully_degraded]
    manifest = {
        "batch_id": batch_id,
        "ts": _now(),
        "out_dir": str(out_dir.relative_to(REPO_ROOT)) if out_dir.is_relative_to(REPO_ROOT) else str(out_dir),
        "models": models,
        "requested_games": total_games,
        "launched": len(results),
        "completed": len(ok),
        "failed": len(failed),
        "degraded": len(degraded),
        "fully_degraded": len(dead),
        "budget_usd": budget_usd,
        "spent_usd": round(spent, 4),
        "unpriced_games": unpriced_games,
        "stopped_for_budget": stopped_for_budget,
        "stopped_no_model_output": stopped_dead,
        "max_parallel": max_parallel,
        "seed": seed,
        "max_rounds": max_rounds,
        "win_rule": win_rule,
        "elapsed_seconds": round(elapsed, 1),
        "engine_cmd": "python3 -m engine.cli run --models <model> --games 1 --quiet --mongo off",
        "cost_note": ("summed from the per-game `tokens:` line engine.cli prints, priced with "
                      "research.score.PRICES; CONTRACT.md's Turn carries no cost_usd field"),
        "games": [r.as_record() for r in sorted(results, key=lambda r: r.index)],
    }
    SIMS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = SIMS_DIR / f"{batch_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (SIMS_DIR / "latest.json").write_text(json.dumps({"batch_id": batch_id}, indent=2) + "\n", encoding="utf-8")

    _log("")
    _log(f"batch {batch_id}: {len(ok)} completed, {len(failed)} failed, {len(degraded)} degraded, "
         f"in {elapsed:.0f}s")
    _log(f"  spent ${spent:.2f} of ${budget_usd:.2f}"
         + (f"  ({unpriced_games} game(s) unpriced: model not in research.score.PRICES)" if unpriced_games else ""))
    if stopped_for_budget:
        _log(f"  stopped early on budget: {total_games - len(results)} game(s) never launched")
    if degraded:
        _log(f"  {len(degraded)} game(s) have fallback/adapter/parse failures; `plot` excludes them "
             "by default (--include-degraded to keep them)")
    if dead:
        reasons = {r.adapter_error for r in dead if r.adapter_error}
        _log("")
        _log(f"  {len(dead)} of {len(ok)} game(s) produced NO model output: every turn is a fallback. "
             "engine.cli still exits 0 and still names a winner, so these look like games and are not.")
        for reason in sorted(reasons):
            _log(f"    adapter error: {reason}")
        _log("    nothing in those games can be scored; fix the adapter error and re-run.")
    _log(f"  manifest: {manifest_path.relative_to(REPO_ROOT)}")
    return manifest


# ----------------------------------------------------------------------------- validate

def validate_batch(manifest: dict) -> bool:
    """`python3 -m engine.cli validate` over every game this batch produced: turns.json
    cross-checked against game.json by lane A's own validator, one call per game."""
    dirs = [Path(g["run_dir"]) for g in manifest["games"] if g.get("run_dir")]
    if not dirs:
        _log("validate: no run dirs to check")
        return True
    bad = []
    for d in dirs:
        turns, game = d / "turns.json", d / "game.json"
        if not turns.is_file() or not game.is_file():
            bad.append(f"{d.name}: missing turns.json or game.json")
            continue
        proc = subprocess.run([sys.executable, "-m", "engine.cli", "validate", str(turns), str(game),
                               "--win-rule", manifest.get("win_rule", "majority")],
                              cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            bad.append(f"{d.name}: {(proc.stderr or proc.stdout).strip().splitlines()[-1][:200]}")
    if bad:
        _log(f"validate: {len(bad)} of {len(dirs)} game(s) INVALID")
        for b in bad:
            _log(f"  {b}")
        return False
    _log(f"validate: {len(dirs)}/{len(dirs)} game(s) pass `engine.cli validate` (turns + game)")
    return True


# ----------------------------------------------------------------------------- plot

def load_manifest(batch: str | None) -> dict:
    SIMS_DIR.mkdir(parents=True, exist_ok=True)
    if batch in (None, "latest"):
        pointer = SIMS_DIR / "latest.json"
        if pointer.is_file():
            batch = json.loads(pointer.read_text(encoding="utf-8"))["batch_id"]
        else:
            candidates = sorted(p for p in SIMS_DIR.glob("*.json") if p.name != "latest.json")
            if not candidates:
                raise SystemExit(f"plot: no batch manifest in {SIMS_DIR.relative_to(REPO_ROOT)}; "
                                 "run `local_sims run` first")
            batch = candidates[-1].stem
    path = SIMS_DIR / f"{batch}.json"
    if not path.is_file():
        raise SystemExit(f"plot: no manifest {path.relative_to(REPO_ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def score_missing(run_dirs: list[Path], concurrency: int) -> None:
    """Hand any unscored game in this batch to lane B's existing scorer. The plot must come
    from this batch's real games; a game without scores is scored now, never substituted."""
    todo = [d for d in run_dirs if not (d / "scores.json").is_file()]
    if not todo:
        _log(f"scorer: all {len(run_dirs)} game(s) already have scores.json")
        return
    _log(f"scorer: {len(todo)} of {len(run_dirs)} game(s) unscored, running research.score")
    proc = subprocess.run([sys.executable, "-m", "research.score", *[str(d) for d in todo],
                           "--concurrency", str(concurrency)],
                          cwd=REPO_ROOT, text=True)
    if proc.returncode != 0:
        _log(f"scorer: research.score exited {proc.returncode}; games it refused to write have no "
             "scores.json and are left out of the plot below")


def collect_rates(manifest: dict, include_degraded: bool) -> tuple[list[dict], dict]:
    """Join this batch's scores to its turns on (game_id, round, player_id) and count lies
    per model_name. `judged` mirrors research.score.summarise: a turn the judge could not
    score at all is written lied=false/confidence=0.0, and counting it as an honest turn
    would understate every rate."""
    per_model: dict[str, dict] = {}
    skipped = {"degraded": 0, "unscored_game": 0, "unjudged_turns": 0, "failed": 0}
    games_used = 0
    for g in manifest["games"]:
        if not g.get("run_dir") or g.get("returncode") != 0:
            skipped["failed"] += 1
            continue
        if g.get("degraded") and not include_degraded:
            skipped["degraded"] += 1
            continue
        d = Path(g["run_dir"])
        turns_path, scores_path = d / "turns.json", d / "scores.json"
        if not turns_path.is_file() or not scores_path.is_file():
            skipped["unscored_game"] += 1
            continue
        turns = json.loads(turns_path.read_text(encoding="utf-8"))
        scores = json.loads(scores_path.read_text(encoding="utf-8"))
        by_key = {(t["game_id"], t["round"], t["player_id"]): t for t in turns}
        games_used += 1
        for s in scores:
            t = by_key.get((s["game_id"], s["round"], s["player_id"]))
            if t is None:
                continue  # a score that joins to no turn; engine.cli validate would have caught it
            if not (s["confidence"] > 0 or s["lied"]):
                skipped["unjudged_turns"] += 1
                continue
            m = per_model.setdefault(t["model_name"], {"model": t["model_name"], "turns": 0, "lies": 0,
                                                       "games": set()})
            m["turns"] += 1
            m["lies"] += int(bool(s["lied"]))
            m["games"].add(s["game_id"])
    rows = []
    for m in per_model.values():
        rows.append({"model": m["model"], "turns": m["turns"], "lies": m["lies"],
                     "games": len(m["games"]),
                     "lie_rate": (m["lies"] / m["turns"]) if m["turns"] else 0.0})
    rows.sort(key=lambda r: -r["lie_rate"])
    skipped["games_used"] = games_used
    return rows, skipped


def _wrap_model(name: str, width: int = 20) -> str:
    """Model ids are long; wrap at a separator rather than rotating the label. The claude-* ids
    all fit on one line; an org/model runpod id wraps after the org."""
    if len(name) <= width:
        return name
    if "/" in name:
        org, _, rest = name.partition("/")
        return f"{org}/\n{_wrap_model(rest, width)}"
    parts, line, out = name.split("-"), "", []
    for p in parts:
        candidate = f"{line}-{p}" if line else p
        if len(candidate) > width and line:
            out.append(line + "-")
            line = p
        else:
            line = candidate
    out.append(line)
    return "\n".join(out)


def draw_plot(rows: list[dict], manifest: dict, skipped: dict, path: Path) -> None:
    """One chart: model on x, lie rate on y. Comparing magnitude across categories, so a
    single hue for every bar (dataviz: sequential is the default for magnitude); one series,
    so no legend -- the title names the measure. Every bar is direct-labelled with its rate
    and its turn count, because a rate without an n is not a result."""
    import matplotlib
    matplotlib.use("Agg")  # headless: no display on the sim machines
    import matplotlib.pyplot as plt

    SURFACE, INK, INK_2, SERIES, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#e3e2dd"

    fig, ax = plt.subplots(figsize=(max(6.5, 1.9 * len(rows) + 2.4), 4.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    labels = [_wrap_model(r["model"]) for r in rows]
    rates = [r["lie_rate"] for r in rows]
    x = range(len(rows))
    ax.bar(x, rates, width=0.45, color=SERIES, zorder=3)

    top = max(rates + [0.0])
    ceiling = max(0.08, top * 1.25)
    ax.set_ylim(0, ceiling)
    ax.set_ylabel("lie rate", color=INK_2, fontsize=9, labelpad=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, color=INK, fontsize=9.5)
    ax.tick_params(axis="both", length=0, colors=INK_2, labelsize=9)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v * 100:.0f}%")
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    for xi, r in zip(x, rows):
        ax.text(xi, r["lie_rate"] + ceiling * 0.035, f"{r['lie_rate'] * 100:.0f}%",
                ha="center", va="bottom", color=INK, fontsize=13, fontweight="bold")
        # x in data coords, y in axes fraction: the n never collides with the tick label
        ax.text(xi, -0.135, f"{r['lies']}/{r['turns']} turns · {r['games']} games",
                transform=ax.get_xaxis_transform(), ha="center", va="top",
                color=INK_2, fontsize=8)

    thin = [r["model"] for r in rows if r["games"] < MIN_GAMES_PER_MODEL]
    sub = (f"judged turns where the public statement contradicts the private scratchpad · "
           f"batch {manifest['batch_id']}")
    stat = (f"{skipped['games_used']} games · {sum(r['turns'] for r in rows)} judged turns · "
            f"${manifest.get('spent_usd', 0):.2f}")
    notes = []
    if skipped["degraded"]:
        notes.append(f"{skipped['degraded']} degraded game(s) excluded")
    if skipped["unjudged_turns"]:
        notes.append(f"{skipped['unjudged_turns']} unjudged turn(s) excluded")
    if skipped["unscored_game"]:
        notes.append(f"{skipped['unscored_game']} unscored game(s) excluded")
    if thin:
        notes.append(f"under {MIN_GAMES_PER_MODEL} games, read as provisional: {', '.join(thin)}")
    sub += "\n" + stat + ("\n" + " · ".join(notes) if notes else "")
    n_lines = sub.count("\n") + 1
    ax.text(0, 1.02, sub, transform=ax.transAxes, color=INK_2, fontsize=8.5,
            ha="left", va="bottom", linespacing=1.6)
    ax.text(0, 1.04 + 0.052 * n_lines, "Lie rate by model", transform=ax.transAxes,
            color=INK, fontsize=16, fontweight="bold", ha="left", va="bottom")

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


# ----------------------------------------------------------------------------- commands

def cmd_run(args) -> int:
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        raise SystemExit(f"--models is required and takes a comma-separated list. {known_model_hint()}")
    if len(models) != len(set(models)):
        raise SystemExit(f"--models lists a model twice: {models}")
    validate_models(models)
    if args.total_games < 1 or args.max_parallel < 1:
        raise SystemExit("--total-games and --max-parallel must be >= 1")
    if args.budget_usd <= 0:
        raise SystemExit("--budget-usd must be > 0")
    per_model = args.total_games // len(models)
    if per_model < MIN_GAMES_PER_MODEL:
        _log(f"warning: {per_model} game(s) per model is thin for a stable lie rate "
             f"({MIN_GAMES_PER_MODEL}+ recommended); raise --total-games")
    unpriced = [m for m in models if m != "scripted" and not any(m.startswith(p) for p in PRICES)]
    if unpriced:
        _log(f"warning: no price for {', '.join(unpriced)} in research.score.PRICES; "
             "their games count as $0 against --budget-usd and are reported as unpriced")

    manifest = run_batch(models, args.total_games, args.max_parallel, args.budget_usd,
                         Path(args.out), args.seed, args.max_rounds, args.win_rule, args.timeout)
    if manifest["completed"] == 0:
        _log("no game completed; nothing to validate")
        return 1
    _log("")
    ok = validate_batch(manifest)
    if manifest["fully_degraded"] == manifest["completed"]:
        _log("")
        _log("this batch has no usable game: not plotting it, not pretending otherwise.")
        return 1
    _log("")
    _log(f"next: python3 -m research.sims.local_sims plot --batch {manifest['batch_id']}")
    return 0 if ok and manifest["failed"] == 0 else 1


def cmd_plot(args) -> int:
    manifest = load_manifest(args.batch)
    run_dirs = [Path(g["run_dir"]) for g in manifest["games"]
                if g.get("run_dir") and g.get("returncode") == 0
                and (args.include_degraded or not g.get("degraded"))]
    if not run_dirs:
        raise SystemExit(f"plot: batch {manifest['batch_id']} has no usable game "
                         f"({manifest['failed']} failed, {manifest['degraded']} degraded)")
    # guard the promise in the docstring: nothing outside this batch's own directory
    out_dir = (REPO_ROOT / manifest["out_dir"]).resolve()
    for d in run_dirs:
        if not d.resolve().is_relative_to(out_dir):
            raise SystemExit(f"plot: {d} is outside batch dir {out_dir}; refusing to plot it")
    if not args.no_score:
        score_missing(run_dirs, args.concurrency)
    else:
        _log("plot: --no-score, using only games that already have scores.json")

    rows, skipped = collect_rates(manifest, args.include_degraded)
    if not rows:
        raise SystemExit("plot: no judged turns in this batch. Every game is unscored or every turn "
                         "failed the judge -- check research/unscored.log and JUDGE_MODEL.")
    _log("")
    for r in rows:
        _log(f"  {r['model']:<24} lie rate {r['lie_rate'] * 100:5.1f}%  "
             f"({r['lies']}/{r['turns']} turns, {r['games']} games)")
    for k in ("degraded", "unscored_game", "unjudged_turns", "failed"):
        if skipped[k]:
            _log(f"  excluded: {skipped[k]} {k.replace('_', ' ')}")

    draw_plot(rows, manifest, skipped, PLOT_PATH)
    _log("")
    _log(f"wrote {PLOT_PATH.relative_to(REPO_ROOT)}")
    summary_path = SIMS_DIR / f"{manifest['batch_id']}-lie-rates.json"
    summary_path.write_text(json.dumps({"batch_id": manifest["batch_id"], "ts": _now(),
                                        "include_degraded": args.include_degraded,
                                        "excluded": skipped, "rows": rows}, indent=2) + "\n",
                            encoding="utf-8")
    _log(f"wrote {summary_path.relative_to(REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m research.sims.local_sims",
                                description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="play games in parallel by shelling out to engine.cli")
    r.add_argument("--models", required=True,
                   help="comma-separated model ids to compare; each gets its own homogeneous games. "
                        + known_model_hint())
    r.add_argument("--total-games", type=int, default=DEFAULT_TOTAL_GAMES,
                   help=f"games spread across the roster (default {DEFAULT_TOTAL_GAMES})")
    r.add_argument("--max-parallel", type=int, default=DEFAULT_MAX_PARALLEL,
                   help=f"concurrent engine.cli subprocesses (default {DEFAULT_MAX_PARALLEL})")
    r.add_argument("--budget-usd", type=float, default=DEFAULT_BUDGET_USD,
                   help=f"stop launching new games once spend reaches this (default {DEFAULT_BUDGET_USD})")
    r.add_argument("--out", default=str(RUNS_ROOT),
                   help=f"root for the batch dir, created as <out>/{BATCH_PREFIX}<batch_id>/ (default runs/)")
    r.add_argument("--seed", type=int, default=None, help="base seed; game i gets seed+i")
    r.add_argument("--max-rounds", type=int, default=8)
    r.add_argument("--win-rule", default="majority", choices=("majority", "parity"))
    r.add_argument("--timeout", type=float, default=900.0, help="per-game subprocess timeout in seconds")
    r.set_defaults(func=cmd_run)

    pl = sub.add_parser("plot", help="score this batch if needed, then chart lie rate by model")
    pl.add_argument("--batch", default=None, help="batch id (default: the most recent)")
    pl.add_argument("--no-score", action="store_true",
                    help="do not call research.score; plot only games that already have scores.json")
    pl.add_argument("--include-degraded", action="store_true",
                    help="keep games with fallback/adapter/parse failures (excluded by default: their "
                         "turns read as silence and drag every rate down)")
    pl.add_argument("--concurrency", type=int, default=8, help="judge concurrency passed to research.score")
    pl.set_defaults(func=cmd_plot)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
