# ui

The split screen. Read-only over the engine's and research's JSON on disk; no mongo, no backend.

```bash
cd ui && npm install && npm run dev      # http://127.0.0.1:5173
cd ui && npm run build                   # tsc --noEmit + vite build
cd ui && npm run smoke                   # boots the dev server in-process, checks /data/ shapes
```

## data

`server/data-plugin.ts` (vite `configureServer`) serves `../runs` and `../fixtures` read-only under `/data/`:

- `GET /data/index.json` — every game dir under `runs/` and `fixtures/live/` (`game_id`, `dir`, `turn_count`,
  `has_game`, `has_scores`, `has_exploits`, `mtime`), then `fixtures/*.json` split by `game_id` as fallback entries.
- `GET /data/file/<relpath>` — the file. 404 outside those two roots. Every other method is 405.

`src/data/source.ts` is the only module that fetches. A game's turns come from `<dir>/turns.jsonl` (appended per
turn by the engine) or `<dir>/turns.json`; `game.json` may be an object or a one-element array; `scores.json` and
`exploits.json` are optional and rendered as "unscored" / empty state when absent. The page polls `index.json` and
the open game's files every 1000ms, so turns appear as they land.

## keys

`space` play/pause · `←` `→` step · `l` next lied turn · `f` follow live (always newest) · `e` toggle exploit tab

## contract

`src/data/types.ts` is CONTRACT.md plus optional engine extras (`tokens_in`, `tokens_out`, `cost_usd`,
`death_cause`, `trust`) that render as "—" when absent. Nothing is computed from scores here.
