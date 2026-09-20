/**
 * The only module in the app that touches fetch. Read-only, against server/data-plugin.ts.
 *
 *   fetchIndex()           -> IndexEntry[]   every game dir in runs/ + fixtures/live/, then fixtures/*.json fallbacks
 *   loadGame(entry)        -> GameData       game.json (object or [object]), turns in ts order, scores or null
 *   loadExploits(entries)  -> ExploitsData   fixtures/exploits.json + every <dir>/exploits.json; anyFile=false when none exist
 *
 * Scores and exploits may be missing. Callers render without them. Nothing is computed here.
 */
import { PLAYER_IDS, type EngineEvent, type Exploit, type Game, type PlayerId, type Score, type Turn } from './types'

const BASE = '/data'

export interface IndexEntry {
  game_id: string
  dir: string
  turn_count: number
  has_game: boolean
  has_scores: boolean
  has_exploits: boolean
  /** engine-local events.jsonl sits in the dir. optional: older index builds omit it. */
  has_events?: boolean
  mtime: number
}

export interface GameData {
  entry: IndexEntry
  game: Game | null
  turns: Turn[]
  /** null = no scores file for this game (render no meters). [] = file exists, nothing for this game. */
  scores: Score[] | null
}

/** one game's Game record per game_id, for views that list many games (leaderboard, picker). */
export type GameMetas = Map<string, Game>

export interface ExploitsData {
  exploits: Exploit[]
  /** false when no exploits.json exists anywhere -> empty state */
  anyFile: boolean
}

export async function fetchIndex(): Promise<IndexEntry[]> {
  const res = await fetch(`${BASE}/index.json`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`data index unavailable: ${res.status}`)
  return (await res.json()) as IndexEntry[]
}

async function fetchText(rel: string): Promise<string | null> {
  const res = await fetch(`${BASE}/file/${rel}`, { cache: 'no-store' })
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`${rel}: ${res.status}`)
  return res.text()
}

/** null = no file. object -> [object]. unparsable -> [] (a half-written file must not crash the view). */
async function fetchJsonArray<T>(rel: string): Promise<T[] | null> {
  const text = await fetchText(rel)
  if (text === null) return null
  try {
    const data = JSON.parse(text)
    return Array.isArray(data) ? (data as T[]) : [data as T]
  } catch {
    return []
  }
}

/** null = no file. Lines that do not parse (a partial trailing write) are skipped. */
async function fetchJsonl<T>(rel: string): Promise<T[] | null> {
  const text = await fetchText(rel)
  if (text === null) return null
  const out: T[] = []
  for (const line of text.split('\n')) {
    if (!line.trim()) continue
    try {
      out.push(JSON.parse(line) as T)
    } catch {
      /* skip */
    }
  }
  return out
}

function isPlayerId(x: unknown): x is PlayerId {
  return typeof x === 'string' && (PLAYER_IDS as readonly string[]).includes(x)
}

/** Keep only turns with the contract's load-bearing fields. Coerce a null public to "" (silence) rather than crash. */
function sanitizeTurn(raw: unknown): Turn | null {
  if (!raw || typeof raw !== 'object') return null
  const t = raw as Record<string, unknown>
  if (typeof t.game_id !== 'string' || !isPlayerId(t.player_id)) return null
  if (!Number.isInteger(t.round)) return null
  return {
    game_id: t.game_id,
    round: t.round as number,
    player_id: t.player_id,
    model_name: typeof t.model_name === 'string' ? t.model_name : '?',
    role: t.role === 'wolf' ? 'wolf' : 'villager',
    private: typeof t.private === 'string' ? t.private : '',
    public: typeof t.public === 'string' ? t.public : '',
    vote: isPlayerId(t.vote) ? t.vote : null,
    ts: typeof t.ts === 'string' ? t.ts : '',
    ...(typeof t.tokens_in === 'number' ? { tokens_in: t.tokens_in } : {}),
    ...(typeof t.tokens_out === 'number' ? { tokens_out: t.tokens_out } : {}),
    ...(typeof t.cost_usd === 'number' ? { cost_usd: t.cost_usd } : {}),
  }
}

export function sortTurns(turns: Turn[]): Turn[] {
  return [...turns].sort((a, b) => a.round - b.round || a.ts.localeCompare(b.ts))
}

export async function loadGame(entry: IndexEntry): Promise<GameData> {
  const isFx = entry.dir === 'fixtures'
  const [gamesRaw, turnsRaw, scoresRaw] = await Promise.all([
    isFx ? fetchJsonArray<Game>('fixtures/games.json') : entry.has_game ? fetchJsonArray<Game>(`${entry.dir}/game.json`) : Promise.resolve(null),
    isFx
      ? fetchJsonArray<unknown>('fixtures/turns.json')
      : fetchJsonl<unknown>(`${entry.dir}/turns.jsonl`).then((j) => j ?? fetchJsonArray<unknown>(`${entry.dir}/turns.json`)),
    isFx ? fetchJsonArray<Score>('fixtures/scores.json') : entry.has_scores ? fetchJsonArray<Score>(`${entry.dir}/scores.json`) : Promise.resolve(null),
  ])
  const game = (gamesRaw ?? []).find((g) => g && g.game_id === entry.game_id) ?? null
  const turns = sortTurns(
    (turnsRaw ?? [])
      .map(sanitizeTurn)
      .filter((t): t is Turn => t !== null && t.game_id === entry.game_id),
  )
  const scores = scoresRaw === null ? null : scoresRaw.filter((s) => s && s.game_id === entry.game_id)
  return { entry, game, turns, scores }
}

export async function loadExploits(entries: IndexEntry[]): Promise<ExploitsData> {
  const paths = ['fixtures/exploits.json', ...entries.filter((e) => e.dir !== 'fixtures' && e.has_exploits).map((e) => `${e.dir}/exploits.json`)]
  const files = await Promise.all(paths.map((p) => fetchJsonArray<Exploit>(p)))
  const seen = new Set<string>()
  const exploits: Exploit[] = []
  let anyFile = false
  for (const arr of files) {
    if (arr === null) continue
    anyFile = true
    for (const x of arr) {
      if (!x || typeof x !== 'object') continue
      const key = `${x.game_id}|${x.round}|${x.player_id}|${x.tag}|${x.ts}`
      if (seen.has(key)) continue
      seen.add(key)
      exploits.push(x)
    }
  }
  return { exploits, anyFile }
}

const EVENT_TYPES = new Set(['day_start', 'turn', 'day_result', 'night_start', 'night_turn', 'night_result', 'game_end'])

/**
 * Engine-local event log, when the game dir has one. null = none (fixtures/*.json games, old runs).
 * `agent_reply` events carry whole prompts and are dropped. Read-only, never required.
 */
export async function loadEvents(entry: IndexEntry): Promise<EngineEvent[] | null> {
  if (entry.dir === 'fixtures' || entry.has_events === false) return null
  const raw = await fetchJsonl<Record<string, unknown>>(`${entry.dir}/events.jsonl`)
  if (raw === null) return null
  return raw.filter(
    (e) => e && typeof e.type === 'string' && EVENT_TYPES.has(e.type) && e.game_id === entry.game_id && Number.isInteger(e.round),
  ) as unknown as EngineEvent[]
}

const metaCache = new Map<string, Game | null>()

/** Game records for every indexed game. Cached per (game_id, mtime) so a poll only fetches what changed. */
export async function loadGameMetas(entries: IndexEntry[]): Promise<GameMetas> {
  const out: GameMetas = new Map()
  let fxGames: Game[] | null | undefined
  await Promise.all(
    entries.map(async (e) => {
      if (!e.has_game) return
      const ck = `${e.game_id}|${e.dir}|${e.mtime}`
      if (!metaCache.has(ck)) {
        let g: Game | null = null
        try {
          if (e.dir === 'fixtures') {
            if (fxGames === undefined) fxGames = await fetchJsonArray<Game>('fixtures/games.json')
            g = (fxGames ?? []).find((x) => x && x.game_id === e.game_id) ?? null
          } else {
            g = ((await fetchJsonArray<Game>(`${e.dir}/game.json`)) ?? []).find((x) => x && x.game_id === e.game_id) ?? null
          }
        } catch {
          g = null
        }
        metaCache.set(ck, g)
      }
      const g = metaCache.get(ck)
      if (g) out.set(e.game_id, g)
    }),
  )
  return out
}

// ---- join --------------------------------------------------------------------------

export function scoreKey(gameId: string, round: number, playerId: string): string {
  return `${gameId}|${round}|${playerId}`
}

export function indexScores(scores: Score[] | null): Map<string, Score> {
  const m = new Map<string, Score>()
  for (const s of scores ?? []) m.set(scoreKey(s.game_id, s.round, s.player_id), s)
  return m
}

/** A turn joined to its score. `score: null` = unscored (no file, or no row for this turn). */
export interface Row {
  turn: Turn
  score: Score | null
}

export function joinRows(turns: Turn[], scores: Score[] | null): Row[] {
  const idx = indexScores(scores)
  return turns.map((turn) => ({ turn, score: idx.get(scoreKey(turn.game_id, turn.round, turn.player_id)) ?? null }))
}
