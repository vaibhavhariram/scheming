// One smoke test. Boots the vite dev server in-process, hits the read-only data endpoints,
// checks the shapes the split screen depends on, exits non-zero on any failure.
//   node scripts/smoke.mjs
import { createServer } from 'vite'

const server = await createServer({ configFile: new URL('../vite.config.ts', import.meta.url).pathname, server: { port: Number(process.env.SMOKE_PORT ?? 5199), strictPort: true, host: '127.0.0.1' }, logLevel: 'error', optimizeDeps: { noDiscovery: true, include: [] } })
await server.listen()
const base = `http://127.0.0.1:${server.httpServer.address().port}`
let failed = 0
const check = (ok, msg) => { console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); if (!ok) failed++ }
try {
  const idx = await (await fetch(`${base}/data/index.json`)).json()
  check(Array.isArray(idx) && idx.length > 0, `index.json lists ${idx.length} games`)
  for (const k of ['game_id', 'dir', 'turn_count', 'spoken_turns', 'has_scores', 'has_exploits', 'has_events', 'mtime']) check(idx.every((e) => k in e), `every index entry has ${k}`)
  check(idx.every((e) => typeof e.spoken_turns === 'number' && e.spoken_turns <= e.turn_count), 'spoken_turns is a count and never exceeds turn_count')
  const fx = idx.filter((e) => e.dir === 'fixtures')
  check(fx.length === 2, `fixtures fallback split into 2 games (${fx.map((e) => e.game_id).join(', ')})`)
  check(fx.reduce((n, e) => n + e.turn_count, 0) === 20 && fx.every((e) => e.has_scores), 'fixture games: 20 turns between them, both scored')
  const turns = await (await fetch(`${base}/data/file/fixtures/turns.json`)).json()
  const scores = await (await fetch(`${base}/data/file/fixtures/scores.json`)).json()
  check(turns.length === 20 && scores.filter((s) => s.lied).length === 8, 'fixtures: 20 turns, 8 lied scores')
  const byKey = new Map(turns.map((t) => [`${t.game_id}|${t.round}|${t.player_id}`, t]))
  const lied = scores.filter((s) => s.lied)
  const inTurn = lied.filter((s) => s.quote && byKey.get(`${s.game_id}|${s.round}|${s.player_id}`)?.private.includes(s.quote)).length
  check(inTurn >= 1 && lied.every((s) => s.quote !== undefined), `lied quotes: ${inTurn}/${lied.length} verbatim in the same turn's private (the rest quote an earlier day; shown under the scratchpad with the day they came from)`)
  const run = idx.find((e) => e.game_id === 'g-20260920-6f7625')
  if (run) {
    check(run.turn_count === 9 && run.dir.startsWith('runs/'), 'runs/g-20260920-6f7625 indexed with 9 turns')
    const g = await (await fetch(`${base}/data/file/${run.dir}/game.json`)).json()
    check((Array.isArray(g) ? g[0] : g).game_id === run.game_id, 'game.json (object or [object]) resolves')
    const sc = await fetch(`${base}/data/file/${run.dir}/scores.json`)
    check(sc.status === 404 || sc.ok, `scores.json for the run is ${sc.status === 404 ? 'absent (ok, renders unscored)' : 'present'}`)
  } else {
    console.log('skip runs/g-20260920-6f7625 not on disk (runs/ is gitignored)')
  }
  const dead = idx.find((e) => e.game_id === 'g-20260920-de4498')
  if (dead) {
    check(dead.turn_count > 0 && dead.spoken_turns === 0, 'de4498 is indexed as a dead game (spoken_turns 0)')
  }
  check((await fetch(`${base}/data/file/../CONTRACT.md`)).status === 404, 'path traversal outside runs/ and fixtures/ is 404')
  check((await fetch(`${base}/data/file/research/plots/lie_rate_by_model.png`)).status === 404, 'research/ is not opened via /data/file/')
  const plot = await fetch(`${base}/data/plot.json`)
  check(plot.status === 200, 'plot.json is 200')
  if (plot.ok) {
    const pj = await plot.json()
    check(Array.isArray(pj.rows) && pj.rows.length > 0 && pj.rows.every((r) => r.turns > 0), `plot.json has ${pj.rows?.length ?? 0} rows with non-zero n`)
  }
  check((await fetch(`${base}/data/plot.png`)).status === 200, 'plot.png is 200')
  check((await fetch(`${base}/data/file/fixtures/turns.json`, { method: 'POST' })).status === 405, 'writes are 405')
  const html = await (await fetch(`${base}/`)).text()
  check(html.includes('/src/main.tsx'), 'index.html serves the app')
} catch (e) {
  check(false, String(e))
} finally {
  await server.close()
}
console.log(failed ? `${failed} failed` : 'smoke ok')
process.exit(failed ? 1 : 0)
