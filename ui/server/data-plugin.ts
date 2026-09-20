/**
 * Dev-server backend for src/data/source.ts. Read-only. Serves JSON that the engine (turns, games)
 * and research (scores, exploits) write to disk. Nothing here writes anything.
 *
 *   GET /data/index.json      -> IndexEntry[]  every game dir under runs/ and fixtures/live/
 *                                (game_id, dir, turn_count, has_game, has_scores, has_exploits, has_events, mtime),
 *                                then fixtures/games.json entries as fallbacks (dir: "fixtures").
 *                                Deduped by game_id: runs > fixtures/live > fixtures.
 *   GET /data/file/<relpath>  -> the file, if it is under runs/ or fixtures/. 404 otherwise.
 *
 * A game dir is any directory holding turns.json, turns.jsonl or game.json. game_id comes from
 * game.json when present, else the dir name. Dirs starting with "_" or "." are skipped.
 */
import fs from 'node:fs'
import path from 'node:path'
import type { Plugin } from 'vite'

const REPO_ROOT = path.resolve(__dirname, '..', '..')
const ALLOWED_ROOTS = ['fixtures', 'runs'].map((r) => path.join(REPO_ROOT, r))
const GAME_DIR_BASES = ['runs', 'fixtures/live']

export interface IndexEntry {
  game_id: string
  /** repo-relative dir holding this game's files, or "fixtures" for the fixtures fallback */
  dir: string
  turn_count: number
  has_game: boolean
  has_scores: boolean
  has_exploits: boolean
  /** engine-local events.jsonl present (night chat, tallies, deaths). never true for fixtures/*.json games */
  has_events: boolean
  /** newest mtime (ms since epoch) across the dir's json files */
  mtime: number
}

function safeResolve(rel: string): string | null {
  const abs = path.resolve(REPO_ROOT, rel)
  return ALLOWED_ROOTS.some((root) => abs === root || abs.startsWith(root + path.sep)) ? abs : null
}

function readJson(abs: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(abs, 'utf8'))
  } catch {
    return null
  }
}

/** game.json may be an object or a one-element array */
function readGame(abs: string): { game_id?: string } | null {
  const raw = readJson(abs)
  const g = Array.isArray(raw) ? raw[0] : raw
  return g && typeof g === 'object' ? (g as { game_id?: string }) : null
}

function countTurns(dirAbs: string): number {
  const jsonl = path.join(dirAbs, 'turns.jsonl')
  if (fs.existsSync(jsonl)) {
    try {
      return fs
        .readFileSync(jsonl, 'utf8')
        .split('\n')
        .filter((l) => l.trim().startsWith('{') && l.trim().endsWith('}')).length
    } catch {
      /* fall through */
    }
  }
  const arr = readJson(path.join(dirAbs, 'turns.json'))
  return Array.isArray(arr) ? arr.length : 0
}

function dirMtime(dirAbs: string): number {
  let m = 0
  try {
    m = fs.statSync(dirAbs).mtimeMs
    for (const f of fs.readdirSync(dirAbs)) {
      if (!f.endsWith('.json') && !f.endsWith('.jsonl')) continue
      m = Math.max(m, fs.statSync(path.join(dirAbs, f)).mtimeMs)
    }
  } catch {
    /* unreadable dir: mtime 0 */
  }
  return Math.round(m)
}

function isGameDir(dirAbs: string): boolean {
  return ['turns.json', 'turns.jsonl', 'game.json'].some((f) => fs.existsSync(path.join(dirAbs, f)))
}

export function buildIndex(): IndexEntry[] {
  const seen = new Set<string>()
  const entries: IndexEntry[] = []
  for (const base of GAME_DIR_BASES) {
    const baseAbs = path.join(REPO_ROOT, base)
    if (!fs.existsSync(baseAbs)) continue
    for (const name of fs.readdirSync(baseAbs).sort()) {
      if (name.startsWith('_') || name.startsWith('.')) continue
      const dirAbs = path.join(baseAbs, name)
      try {
        if (!fs.statSync(dirAbs).isDirectory() || !isGameDir(dirAbs)) continue
      } catch {
        continue
      }
      const has_game = fs.existsSync(path.join(dirAbs, 'game.json'))
      const game = has_game ? readGame(path.join(dirAbs, 'game.json')) : null
      const game_id = game?.game_id ?? name
      if (seen.has(game_id)) continue
      seen.add(game_id)
      entries.push({
        game_id,
        dir: `${base}/${name}`,
        turn_count: countTurns(dirAbs),
        has_game,
        has_scores: fs.existsSync(path.join(dirAbs, 'scores.json')),
        has_exploits: fs.existsSync(path.join(dirAbs, 'exploits.json')),
        has_events: fs.existsSync(path.join(dirAbs, 'events.jsonl')),
        mtime: dirMtime(dirAbs),
      })
    }
  }
  // fixtures/*.json: two games per file. split by game_id, list as fallback entries.
  const fxDir = path.join(REPO_ROOT, 'fixtures')
  const games = readJson(path.join(fxDir, 'games.json'))
  const turns = readJson(path.join(fxDir, 'turns.json'))
  const scores = readJson(path.join(fxDir, 'scores.json'))
  const exploits = readJson(path.join(fxDir, 'exploits.json'))
  const idsIn = (arr: unknown): Set<string> =>
    new Set(Array.isArray(arr) ? arr.map((x) => (x as { game_id?: string })?.game_id ?? '') : [])
  const scoreIds = idsIn(scores)
  const exploitIds = idsIn(exploits)
  const fxMtime = ['games.json', 'turns.json', 'scores.json', 'exploits.json'].reduce((m, f) => {
    try {
      return Math.max(m, fs.statSync(path.join(fxDir, f)).mtimeMs)
    } catch {
      return m
    }
  }, 0)
  const fxGameIds = new Set<string>()
  for (const g of Array.isArray(games) ? games : []) {
    const id = (g as { game_id?: string })?.game_id
    if (id) fxGameIds.add(id)
  }
  for (const t of Array.isArray(turns) ? turns : []) {
    const id = (t as { game_id?: string })?.game_id
    if (id) fxGameIds.add(id)
  }
  for (const game_id of Array.from(fxGameIds).sort()) {
    if (seen.has(game_id)) continue
    seen.add(game_id)
    entries.push({
      game_id,
      dir: 'fixtures',
      turn_count: Array.isArray(turns) ? turns.filter((t) => (t as { game_id?: string })?.game_id === game_id).length : 0,
      has_game: Array.isArray(games) && games.some((g) => (g as { game_id?: string })?.game_id === game_id),
      has_scores: scoreIds.has(game_id),
      has_exploits: exploitIds.has(game_id),
      has_events: false,
      mtime: Math.round(fxMtime),
    })
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
        if (url.split('?')[0] === '/data/index.json') {
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
