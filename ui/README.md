# ui (lane C)

Read-only front end over the contract collections. Reads JSON from disk; no mongo.

```bash
cd ui && npm install && npm run dev      # http://127.0.0.1:5173
cd ui && npm run build                   # typecheck + bundle
```

All data access is `src/data/source.ts` (`listGames`, `getTurns`, `getScores`, `getExploits`,
plus the score join index). The dev server plugin `server/data-plugin.ts` serves
`fixtures/`, `runs/` and `research/results/` read-only under `/data/`. Swap both for mongo
without touching a component.

Games are discovered from `fixtures/live/*/game.json` (primary), `runs/*/game.json` (live),
then `fixtures/games.json` (fallback). Scores for a game are looked up in
`<game dir>/scores.json`, `research/results/scores.json`, `fixtures/scores.json`; exploits in
`fixtures/exploits.json`, `research/results/exploits.json`, `<game dir>/exploits.json`.

Types in `src/data/types.ts` are CONTRACT.md and nothing more. Not in the contract, so not
rendered: `Turn.tokens_in`, `Turn.tokens_out`, `Turn.cost_usd`, `Game.trust`,
`Game.death_cause`.
