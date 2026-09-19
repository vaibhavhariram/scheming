/**
 * The only module in the app that touches fetch. Everything reads through these four calls.
 * Today they read JSON that lanes A and B write to disk (via server/data-plugin.ts). A mongo
 * backend swaps the bodies of these functions and nothing else.
 *
 *   listGames()          -> Game[]        (fixtures/live first, then runs/, then fixtures/games.json)
 *   getTurns(gameId)     -> Turn[]        sorted by round then ts
 *   getScores(gameId)    -> Score[]       from <game dir>/scores.json, research/results/scores.json, fixtures/scores.json
 *   getExploits()        -> Exploit[]     from fixtures/exploits.json, research/results/exploits.json, <game dir>/exploits.json
 *
 * Plus the join index: scores keyed by (game_id, round, player_id), built once per load.
 */
import { PLAYER_IDS, type Exploit, type Game, type Score, type Turn } from './types'

const BASE = '/data'

interface IndexEntry {
  dir: string
  game: Game
  /** json/jsonl files present in dir (empty for the fixtures fallback) */
  files: string[]
}

let index: IndexEntry[] = []

async function fetchIndex(): Promise<IndexEntry[]> {
  const res = await fetch(`${BASE}/index.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`data index unavailable: ${res.status}`)
  index = (await res.json()) as IndexEntry[]
  return index
}

async function fetchText(rel: string): Promise<string | null> {
  const res = await fetch(`${BASE}/file/${rel}`, { cache: 'no-store' })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`${rel}: ${res.status}`)
  return res.text()
}

async function fetchJsonArray<T>(rel: string): Promise<T[]> {
  const text = await fetchText(rel)
  if (text === null) return []
  const data = JSON.parse(text)
  return Array.isArray(data) ? (data as T[]) : [data as T]
}

async function fetchJsonl<T>(rel: string): Promise<T[] | null> {
  const text = await fetchText(rel)
  if (text === null) return null
  return text
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as T)
}

function entryFor(gameId: string): IndexEntry | undefined {
  return index.find((e) => e.game.game_id === gameId)
}

/** A Turn must match CONTRACT.md. `public` must be a string: "" is silence, null is an engine failure. */
function assertTurn(t: Turn, where: string): void {
  const bad = (msg: string) => {
    throw new Error(`${where}: ${msg} in turn ${t.game_id}/${t.round}/${t.player_id}`)
  }
  if (typeof t.private !== 'string') bad(`private is ${t.private === null ? 'null (engine failure)' : typeof t.private}`)
  if (typeof t.public !== 'string') bad(`public is ${t.public === null ? 'null (engine failure)' : typeof t.public}`)
  if (!PLAYER_IDS.includes(t.player_id)) bad(`player_id ${String(t.player_id)}`)
  if (t.role !== 'wolf' && t.role !== 'villager') bad(`role ${String(t.role)}`)
  if (t.vote !== null && !PLAYER_IDS.includes(t.vote)) bad(`vote ${String(t.vote)}`)
  if (!Number.isInteger(t.round) || t.round < 1) bad(`round ${String(t.round)}`)
}

export async function listGames(): Promise<Game[]> {
  const entries = await fetchIndex()
  return entries.map((e) => e.game)
}

export async function getTurns(gameId: string): Promise<Turn[]> {
  if (!index.length) await fetchIndex()
  const entry = entryFor(gameId)
  if (!entry) throw new Error(`unknown game ${gameId}`)
  let turns: Turn[]
  if (entry.dir === 'fixtures') {
    turns = (await fetchJsonArray<Turn>('fixtures/turns.json')).filter((t) => t.game_id === gameId)
  } else {
    // turns.jsonl is appended per turn while a game is running; turns.json is written at game end
    turns = entry.files.includes('turns.jsonl')
      ? ((await fetchJsonl<Turn>(`${entry.dir}/turns.jsonl`)) ?? [])
      : await fetchJsonArray<Turn>(`${entry.dir}/turns.json`)
  }
  turns.forEach((t) => assertTurn(t, entry.dir))
  return turns.sort((a, b) => a.round - b.round || a.ts.localeCompare(b.ts))
}

export async function getScores(gameId: string): Promise<Score[]> {
  if (!index.length) await fetchIndex()
  const entry = entryFor(gameId)
  // primary: <game dir>/scores.json (agreed drop location for lane B); the other two are fallbacks
  const paths = [
    ...(entry && entry.files.includes('scores.json') ? [`${entry.dir}/scores.json`] : []),
    'research/results/scores.json',
    'fixtures/scores.json',
  ]
  const seen = new Set<string>()
  const out: Score[] = []
  for (const p of paths) {
    for (const s of await fetchJsonArray<Score>(p)) {
      if (s.game_id !== gameId) continue
      const key = scoreKey(s.game_id, s.round, s.player_id)
      if (seen.has(key)) continue
      seen.add(key)
      out.push(s)
    }
  }
  return out
}

export async function getExploits(): Promise<Exploit[]> {
  if (!index.length) await fetchIndex()
  const paths = [
    'fixtures/exploits.json',
    'research/results/exploits.json',
    ...index.filter((e) => e.files.includes('exploits.json')).map((e) => `${e.dir}/exploits.json`),
  ]
  const seen = new Set<string>()
  const out: Exploit[] = []
  for (const p of paths) {
    for (const x of await fetchJsonArray<Exploit>(p)) {
      const key = `${x.game_id}|${x.round}|${x.player_id}|${x.tag}|${x.ts}`
      if (seen.has(key)) continue
      seen.add(key)
      out.push(x)
    }
  }
  return out
}

// ---- join index --------------------------------------------------------------------

export type ScoreIndex = Map<string, Score>

export function scoreKey(gameId: string, round: number, playerId: string): string {
  return `${gameId}|${round}|${playerId}`
}

export function indexScores(scores: Score[]): ScoreIndex {
  const m: ScoreIndex = new Map()
  for (const s of scores) m.set(scoreKey(s.game_id, s.round, s.player_id), s)
  return m
}

/** A turn joined to its score, or `score: null` = unscored. Never a fabricated lied:false. */
export interface Row {
  turn: Turn
  score: Score | null
}

export function joinRows(turns: Turn[], scoreIndex: ScoreIndex): Row[] {
  return turns.map((turn) => ({ turn, score: scoreIndex.get(scoreKey(turn.game_id, turn.round, turn.player_id)) ?? null }))
}
