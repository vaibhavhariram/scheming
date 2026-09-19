/**
 * Dev-server backend for src/data/source.ts. Read-only. Serves JSON that lane A (turns, games)
 * and lane B (scores, exploits) write to disk. Nothing here writes anything.
 *
 *   GET /data/index.json          -> [{ dir, game }]  every game.json under fixtures/live, runs,
 *                                    plus fixtures/games.json (fallback). live > runs > fixtures.
 *   GET /data/file/<relpath>      -> the file, if it is under an allowed root.
 *
 * A mongo backend replaces this plugin and source.ts's fetches; no component changes.
 */
import fs from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

const REPO_ROOT = path.resolve(__dirname, '..', '..')
const ALLOWED_ROOTS = ['fixtures', 'runs', 'research/results'].map((r) => path.join(REPO_ROOT, r))

function safeResolve(rel: string): string | null {
  const abs = path.resolve(REPO_ROOT, rel)
  return ALLOWED_ROOTS.some((root) => abs === root || abs.startsWith(root + path.sep)) ? abs : null
}

function readJson(abs: string): unknown | null {
  try {
    return JSON.parse(fs.readFileSync(abs, 'utf8'))
  } catch {
    return null
  }
}

function gameDirs(): string[] {
  const out: string[] = []
  for (const base of ['fixtures/live', 'runs']) {
    const abs = path.join(REPO_ROOT, base)
    if (!fs.existsSync(abs)) continue
    for (const name of fs.readdirSync(abs).sort()) {
      if (name.startsWith('_') || name.startsWith('.')) continue
      if (fs.existsSync(path.join(abs, name, 'game.json'))) out.push(`${base}/${name}`)
    }
  }
  return out
}

function buildIndex(): Array<{ dir: string; game: unknown }> {
  const seen = new Set<string>()
  const entries: Array<{ dir: string; game: unknown }> = []
  for (const dir of gameDirs()) {
    const game = readJson(path.join(REPO_ROOT, dir, 'game.json')) as { game_id?: string } | null
    if (game?.game_id && !seen.has(game.game_id)) {
      seen.add(game.game_id)
      entries.push({ dir, game })
    }
  }
  const fallback = readJson(path.join(REPO_ROOT, 'fixtures/games.json'))
  if (Array.isArray(fallback)) {
    for (const game of fallback as Array<{ game_id?: string }>) {
      if (game?.game_id && !seen.has(game.game_id)) {
        seen.add(game.game_id)
        entries.push({ dir: 'fixtures', game })
      }
    }
  }
  return entries
}

export function dataPlugin(): Plugin {
  return {
    name: 'scheming-data',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url ?? ''
        if (!url.startsWith('/data/')) return next()
        if (req.method !== 'GET') {
          res.statusCode = 405
          return res.end('read-only')
        }
        res.setHeader('Cache-Control', 'no-store')
        if (url === '/data/index.json') {
          res.setHeader('Content-Type', 'application/json')
          return res.end(JSON.stringify(buildIndex()))
        }
        if (url.startsWith('/data/file/')) {
          const rel = decodeURIComponent(url.slice('/data/file/'.length).split('?')[0])
          const abs = safeResolve(rel)
          if (!abs || !fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
            res.statusCode = 404
            return res.end('not found')
          }
          res.setHeader('Content-Type', abs.endsWith('.json') ? 'application/json' : 'text/plain; charset=utf-8')
          return fs.createReadStream(abs).pipe(res)
        }
        res.statusCode = 404
        res.end('not found')
      })
    },
  }
}
