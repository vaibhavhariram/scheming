"""python -m devin.loop — the repair loop entry point.

`--dry-run` builds briefs, prompts and would-be API requests under the state dir, no
network beyond an optional mongo ping. `--once` dispatches each new exploit to a Devin
session, gates any resulting PR in a scratch worktree, optionally resims, and appends a
repairs.jsonl row. `--watch` repeats `--once` every --interval seconds.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from engine.cli import load_dotenv

from . import api_shapes, gate, ledger as repairs, resim, session
from .evidence import Corpus, build_brief, write_brief
from .watcher import Ledger, exploit_id, poll_once, source_from_env

REPO_ROOT = Path(__file__).resolve().parents[1]
REPAIR_PROMPT = REPO_ROOT / "devin" / "prompts" / "repair.md"


def _title(rec: dict) -> str:
    return f"repair: {rec['tag']} ({rec['game_id']} r{rec['round']} {rec['player_id']})"


def _tags(rec: dict) -> list[str]:
    return ["scheming", "spec-repair", rec["tag"]]


def _prepare(args):
    """Shared front half: source, corpus, ledger, new exploits with briefs+prompts written."""
    state_dir = Path(args.state_dir)
    fixtures = Path(args.fixtures_root)
    source, kind = source_from_env(fixtures_path=fixtures / "exploits.json")
    corpus = Corpus.from_mongo(source.db) if kind == "mongo" else Corpus.from_fixtures(fixtures)
    ledger = Ledger(state_dir / "processed.json")
    rules_md = (REPO_ROOT / "design" / "rules.md").read_text(encoding="utf-8")
    contract_md = (REPO_ROOT / "CONTRACT.md").read_text(encoding="utf-8")
    template = REPAIR_PROMPT.read_text(encoding="utf-8")
    batch = poll_once(source, ledger)
    if args.limit is not None:
        batch = batch[: args.limit]
    items = []
    for rec in batch:
        brief = build_brief(rec, corpus, rules_md, contract_md, token_budget=args.token_budget)
        brief_path = write_brief(rec, brief, out_dir=state_dir / "briefs")
        prompt = template.replace("{{BRIEF}}", brief)
        (state_dir / "prompts").mkdir(parents=True, exist_ok=True)
        (state_dir / "prompts" / f"{exploit_id(rec)}.md").write_text(prompt, encoding="utf-8")
        items.append({"rec": rec, "brief_path": brief_path, "prompt": prompt,
                      "brief_tokens": len(brief) // 4})
    return source, kind, ledger, state_dir, items


def _cmd_dry_run(args) -> int:
    source, kind, ledger, state_dir, items = _prepare(args)
    for it in items:
        rec = it["rec"]
        req_path = session.dry_run_request(exploit_id(rec), it["prompt"],
                                           _title(rec), _tags(rec), state_dir,
                                           base=api_shapes.base_url())
        ledger.mark(rec)
        print(f"dry-run  {exploit_id(rec)}  {rec['tag']}  game={rec['game_id']} "
              f"r={rec['round']} {rec['player_id']}  brief={it['brief_path']} "
              f"({it['brief_tokens']} tokens est)  request={req_path}")
    print(f"done: {len(items)} processed, source={kind}, ledger={len(ledger)} total")
    return 0


def _run_once(args) -> int:
    try:
        api_key = session.api_key_from_env()
    except session.MissingApiKey as e:
        print(str(e), file=sys.stderr)
        return 2
    source, kind, ledger, state_dir, items = _prepare(args)
    if not items:
        print(f"done: 0 processed, source={kind}")
        return 0
    # baseline for the resim diff: lane-B tags plus a scripted-game sim on the
    # PRE-patch ruleset (main). Only computed when --resim is on.
    baseline = (resim.baseline_tags(source)
                | resim.resim(REPO_ROOT, out_dir=state_dir / "resim" / "baseline")) \
        if args.resim else set()

    prompts = [(exploit_id(it["rec"]),
                {"prompt": it["prompt"], "title": _title(it["rec"]),
                 "tags": _tags(it["rec"]), "max_acu_limit": args.max_acu})
               for it in items]
    results = asyncio.run(session.run_many(
        prompts, concurrency=args.concurrency, api_key=api_key,
        base_url=api_shapes.base_url(), timeout_s=args.timeout))

    repairs_path = state_dir / "repairs.jsonl"
    all_terminal = True
    for it, res in zip(items, results):
        rec = it["rec"]
        row = {"exploit_tag": rec["tag"], "game_id": rec["game_id"], "round": rec["round"],
               "player_id": rec["player_id"], "devin_session_url": res.get("session_url"),
               "pr_url": res.get("pr_url"),
               "wall_clock_seconds": res.get("wall_clock_seconds"),
               "new_exploit_tags_after_resim": None}
        gate_passed = None
        if res.get("pr_url"):
            if args.no_gate:
                print(f"gate skipped (--no-gate) for {res['pr_url']}", file=sys.stderr)
            else:
                g = gate.run_gate(res["pr_url"], REPO_ROOT, state_dir=state_dir,
                                  keep_worktree=args.resim)
                gate_passed = g["gate_passed"]
                if g.get("error"):
                    print(f"gate error for {res['pr_url']}: {g['error']}", file=sys.stderr)
            fields = repairs.extract_pr_fields(repairs.pr_body(res["pr_url"]))
            row.update(fields)
            if gate_passed and args.resim and g.get("worktree"):
                try:
                    # resim on the PATCHED ruleset: the PR branch's worktree
                    wt = Path(g["worktree"])
                    after = resim.resim(wt, out_dir=state_dir / "resim" / exploit_id(rec))
                    row["new_exploit_tags_after_resim"] = resim.new_tags(after, baseline)
                finally:
                    gate.remove_worktree(REPO_ROOT, g["worktree"])
        row["gate_passed"] = gate_passed
        repairs.append_repair(repairs_path, row)
        ledger.mark(rec)
        status = res.get("status", "error")
        if status not in api_shapes.TERMINAL:
            all_terminal = False
        print(f"{exploit_id(rec)}  {rec['tag']}  status={status}  "
              f"session={res.get('session_url')}  pr={res.get('pr_url')}  gate={gate_passed}")
    print(f"done: {len(results)} dispatched, source={kind}")
    return 0 if all_terminal else 1


def _cmd_watch(args) -> int:
    try:
        while True:
            _run_once(args)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m devin.loop")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="build briefs+prompts+requests locally, no API calls")
    mode.add_argument("--once", action="store_true", help="one poll, dispatch via Devin API")
    mode.add_argument("--watch", action="store_true", help="repeat --once every --interval seconds")
    p.add_argument("--interval", type=float, default=30.0)
    p.add_argument("--fixtures-root", default=str(REPO_ROOT / "fixtures"))
    p.add_argument("--state-dir", default=str(REPO_ROOT / "devin" / "state"))
    p.add_argument("--token-budget", type=int, default=6000)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--timeout", type=float, default=1200, help="per-session wall-clock cap, seconds")
    p.add_argument("--max-acu", type=int, default=None, help="per-session ACU limit")
    p.add_argument("--no-gate", action="store_true", help="skip the post-PR gate")
    p.add_argument("--resim", action="store_true", help="resim scripted games after a passing gate")
    args = p.parse_args(argv)

    load_dotenv()  # repo-root .env, never overrides what is already set

    if args.dry_run:
        return _cmd_dry_run(args)
    if args.once:
        return _run_once(args)
    if args.watch:
        return _cmd_watch(args)
    p.error("pick a mode: --dry-run, --once, --watch")


if __name__ == "__main__":
    sys.exit(main())
