"""python -m devin.loop — the repair loop entry point.

Milestone 1 is dry-run only: poll for undesigned Exploit records, build a repair brief
and a full prompt per exploit under devin/state/, mark the ledger, exit. No Devin API
calls yet. The only network touch is a mongo ping when MONGODB_URI is set.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.cli import load_dotenv

from .evidence import Corpus, build_brief, write_brief
from .watcher import Ledger, exploit_id, poll_once, source_from_env

REPO_ROOT = Path(__file__).resolve().parents[1]
REPAIR_PROMPT = REPO_ROOT / "devin" / "prompts" / "repair.md"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m devin.loop")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="build briefs+prompts locally, no API calls")
    mode.add_argument("--once", action="store_true", help="one poll, dispatch via Devin API")
    mode.add_argument("--watch", action="store_true", help="poll forever, dispatch via Devin API")
    p.add_argument("--interval", type=float, default=30.0)
    p.add_argument("--fixtures-root", default=str(REPO_ROOT / "fixtures"))
    p.add_argument("--state-dir", default=str(REPO_ROOT / "devin" / "state"))
    p.add_argument("--token-budget", type=int, default=6000)
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args(argv)

    if args.once or args.watch:
        print("not implemented yet in milestone 1", file=sys.stderr)
        return 2
    if not args.dry_run:
        p.error("pick a mode: --dry-run (only milestone-1 mode)")

    load_dotenv()  # repo-root .env, never overrides what is already set

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

    prompts_dir = state_dir / "prompts"
    briefs_dir = state_dir / "briefs"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for rec in batch:
        brief = build_brief(rec, corpus, rules_md, contract_md, token_budget=args.token_budget)
        brief_path = write_brief(rec, brief, out_dir=briefs_dir)
        prompt_path = prompts_dir / f"{exploit_id(rec)}.md"
        prompt_path.write_text(template.replace("{{BRIEF}}", brief), encoding="utf-8")
        ledger.mark(rec)
        print(f"dry-run  {exploit_id(rec)}  {rec['tag']}  game={rec['game_id']} "
              f"r={rec['round']} {rec['player_id']}  brief={brief_path} ({len(brief) // 4} tokens est)")
    print(f"done: {len(batch)} processed, source={kind}, ledger={len(ledger)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
