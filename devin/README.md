# devin — closed-loop spec repair harness

Watches the `exploits` collection (or `fixtures/exploits.json`) for `designed: false`
records, builds a self-contained markdown repair brief per exploit, and dispatches each
brief as a Devin session carrying `devin/prompts/repair.md`. When a session returns a PR,
the gate replays `engine.cli validate` + the full pytest suite against the PR branch in a
scratch worktree; a passing gate can be followed by a scripted-game resim that diffs
detected exploit tags against the pre-repair baseline. Every attempt — including
timed-out and errored sessions — lands as one JSONL row in `state/repairs.jsonl`.

## files

| file | what it does |
|---|---|
| `devin/api_shapes.py` | the only place Devin API paths/fields are encoded (docs.devin.ai shapes) |
| `devin/session.py` | async httpx session runner: create, backoff-poll to terminal, fan-out, dry-run request writer |
| `devin/watcher.py` | exploit sources (fixtures/mongo, read-only), dedupe ledger, `poll_once`/`watch` |
| `devin/evidence.py` | `Corpus` over fixtures/mongo and `build_brief` → `state/briefs/<id>.md` |
| `devin/gate.py` | PR gate: worktree + validate + pytest, `devin:rejected` label on failure |
| `devin/ledger.py` | `repairs.jsonl` rows; PR-body field extraction (`## Rule before`/`## Rule after`/`## Test`) |
| `devin/resim.py` | scripted-game resim + structural `detect_tags` stand-in (lane B's detector is the real one) |
| `devin/loop.py` | CLI entry: `--dry-run` / `--once` / `--watch` |
| `devin/prompts/repair.md` | the repair task template; `{{BRIEF}}` is replaced per exploit |
| `devin/state/` | runtime state: `processed.json`, `briefs/`, `prompts/`, `requests/`, `repairs.jsonl`, `gate/`, `resim/` (gitignored) |

## env vars

| var | meaning |
|---|---|
| `DEVIN_API_KEY` | Bearer token for api.devin.ai; required for `--once`/`--watch`, checked before anything is written |
| `DEVIN_API_BASE` | override the default `https://api.devin.ai/v1` |
| `MONGODB_URI` | set → read exploits/turns/games from mongo (ping-probed, falls back to fixtures); unset → fixtures |
| `MONGODB_DB` | database name, default `scheming` |

A repo-root `.env` is loaded for any variable not already set.

## run

```bash
# milestone 1 path: briefs + prompts + would-be requests under the state dir, no API calls
uv run python -m devin.loop --dry-run --state-dir devin/state

# live: dispatch every new undesigned exploit as a Devin session
uv run python -m devin.loop --once [--concurrency 3] [--timeout 1200] [--max-acu N] \
    [--no-gate] [--resim] [--limit N]

# repeat --once every --interval seconds (default 30)
uv run python -m devin.loop --watch --interval 60
```

shared flags: `--interval`, `--fixtures-root` (default repo `fixtures/`), `--state-dir`
(default `devin/state`), `--token-budget` (brief cap, default 6000 est. tokens), `--limit`.

## repairs.jsonl row

```json
{"exploit_tag": str, "game_id": str, "round": int, "player_id": str,
 "devin_session_url": str|null, "pr_url": str|null,
 "rule_before": str|null, "rule_after": str|null, "test_name": str|null,
 "gate_passed": bool|null, "wall_clock_seconds": float|null,
 "new_exploit_tags_after_resim": [str]|null, "ts": iso8601}
```

## gate behaviour

`gh pr view` gets the branch; `git worktree add /tmp/devin-gate-<number> origin/<branch>`;
then `python -m engine.cli validate` over the worktree's `fixtures/` and
`python -m pytest -q -rfE --tb=no` in BOTH the worktree and `main` (run with the venv's
interpreter via `sys.executable`). The pytest criterion is **no new failures relative to
main** — `branch_failures ⊆ main_failures` — because main already carries known-broken
tests; `pytest_rc` is recorded for information only. The branch must also contain a
collected `test_repair_*` node under `engine/tests` (checked via `pytest
--collect-only`), which the repair prompt mandates. `gate_passed = validate_rc == 0 and
no new failures and has_repair_test`; `new_failures` and `main_failures_count` land in
the result and `state/gate/<number>.log`. Any failure labels the PR `devin:rejected`.
`gh` missing/unauthenticated → `gate_passed: null`, never a raise.

With `--resim`, a passing gate keeps the worktree alive and scripted games are replayed
against the PR's PATCHED ruleset in that worktree (`--resim` off = no scripted games at
all). The baseline is computed once before dispatch as `lane-B exploit tags ∪
detect_tags(scripted sims on main)`; the repairs row records `sorted(after − baseline)`.
The worktree is removed after the resim (and always removed on gate failure).

## Sessions produced

filled from `state/repairs.jsonl` as sessions complete.

| # | exploit tag | session url | pr | gate | new tags after resim |
|---|---|---|---|---|---|

## Ownership

`devin/` is not a lane and owns no collection: it is read-only against `turns`, `games`,
`scores`, and `exploits` alike. It never edits `engine/` or `design/rules.md` directly —
changes to those are proposed only via pull requests opened by the spawned repair
sessions, each of which is bound by the repo's own rules (`CLAUDE.md`, `CONTRACT.md`,
`LANES.md`) through the repair prompt.
