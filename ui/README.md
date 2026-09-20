# ui

The split screen. Read-only over the engine's and research's JSON on disk; no mongo, no backend.

```bash
cd ui && npm install && npm run dev      # http://127.0.0.1:5173
cd ui && npm run build                   # tsc --noEmit + vite build
cd ui && npm run smoke                   # boots the dev server in-process, checks /data/ shapes
```

## the idea

The screen is split the way the game is. **Night, left:** what the agent wrote to itself, mono, dark. **Day,
right:** what it said to the table, serif, the only lit surface on screen. Red means exactly one thing: lane B
scored the turn as a lie. Amber is the wolf, the live game and the playhead.

## views

- **stage** (`s`) one beat at a time, type auto-fits the pane. Reveal order: scratchpad, then statement, then the
  verdict plate on the seam (`Score.lied`, `lie_kind`, `confidence`). On a lie, `Score.quote` is marked in the
  scratchpad and a thread runs from it to the seam and down to the plate. A quote from an earlier day (allowed by
  the contract) is shown under the scratchpad with the day it came from.
- **the table** five seats above the stage: speaker, vote arcs landing on their target, votes received, deaths,
  scored lies so far per player.
- **the tape** one tick per beat. A scored lie is a red spike, height = `Score.confidence`. Click to seek.
- **transcript** (`t`) every revealed turn in the same night | day split. Click a row to put it on stage.
- **exploits** (`e`) leaderboard, `designed: false` first then `ts`. Names the model that found it
  (`Game.models` joined on `game_id`). "open the turn" jumps to that game, day and player on the stage.
- **games** (`g`) every game on disk, newest first.

Beats that are not turns (the day's vote tally, the night, the end) come from the engine's `events.jsonl` when
the game dir has one. That file is engine-local, **not a contract collection**; the ui renders fully without it
(`fixtures/*.json` games have none) and nothing in it is scored. At night the day pane goes dark and shows what
the wolves said to each other.

## synthetic fixtures are always labelled

`fixtures/*.json` is hand-written. A fixture game shows a "synthetic fixture" flag in the top bar, fixture rows on
the exploit board sit under their own rule, and **no headline count includes them** (exploits tab badge, board
headline, games count). What a judge reads as a number is real games only: `runs/` and `fixtures/live/`.

## data

`server/data-plugin.ts` (vite `configureServer`) serves `../runs` and `../fixtures` read-only under `/data/`:

- `GET /data/index.json` every game dir under `runs/` and `fixtures/live/` (`game_id`, `dir`, `turn_count`,
  `has_game`, `has_scores`, `has_exploits`, `has_events`, `mtime`), then `fixtures/*.json` split by `game_id` as
  fallback entries.
- `GET /data/file/<relpath>` the file. 404 outside those two roots. Every other method is 405.

`src/data/source.ts` is the only module that fetches. A game's turns come from `<dir>/turns.jsonl` (appended per
turn by the engine) or `<dir>/turns.json`; `game.json` may be an object or a one-element array; `scores.json`,
`exploits.json` and `events.jsonl` are optional and render as "not scored" / empty / no interstitial beats when
absent. The page polls `index.json` and the open game's files every 1000ms, so turns appear as they land.
`src/data/beats.ts` orders turns and engine events into the list the stage steps through.

To get the red on a real game: `python3 -m research.score runs/<game_id>` writes `scores.json` beside the turns
and the ui picks it up on the next poll.

A finished game opens paused on its first beat. A game still being written opens following live. A game dir that
appears while the ui is open is offered in the top bar, and opened automatically if nothing is mid-replay.

## keys

`space` play/pause · `←` `→` step · `home` `end` · `l` next scored lie · `f` follow live ·
`b` blind mode (statement first; `r` reveals the scratchpad and the verdict) · `h` hide roles ·
`s` `t` `e` `g` views · `?` key list

## contract

`src/data/types.ts` is CONTRACT.md plus optional engine extras (`tokens_in`, `tokens_out`, `cost_usd`,
`death_cause`, `trust`, and the event log types) that are simply not rendered when absent. Nothing is computed
from scores here: the ui counts rows lane B marked `lied`, it never decides what a lie is.
