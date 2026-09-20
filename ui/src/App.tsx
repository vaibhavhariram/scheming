import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Seats } from './components/Seats'
import { Tape } from './components/Tape'
import { buildBeats, tableAt } from './data/beats'
import { fetchIndex, joinRows, loadEvents, loadExploits, loadGame, loadGameMetas, type ExploitsData, type GameData, type GameMetas, type IndexEntry } from './data/source'
import type { EngineEvent, Exploit } from './data/types'
import { Exploits } from './views/Exploits'
import { Games } from './views/Games'
import { SplitScreen } from './views/SplitScreen'
import { Stage, type SeenMap } from './views/Stage'

const POLL_MS = 1000

type Tab = 'stage' | 'transcript' | 'exploits' | 'games'

interface Loaded {
  data: GameData
  events: EngineEvent[] | null
}

const KEYS: [string, string][] = [
  ['space', 'play or pause'],
  ['← →', 'step one beat'],
  ['l', 'next scored lie'],
  ['f', 'follow the live game'],
  ['home / end', 'first or last beat'],
  ['b', 'blind mode: statement first, scratchpad on r'],
  ['r', 'reveal the scratchpad (blind mode)'],
  ['h', 'hide or show roles'],
  ['s  t  e  g', 'stage, transcript, exploits, games'],
  ['?', 'this list'],
]

export default function App() {
  const [index, setIndex] = useState<IndexEntry[]>([])
  const [gameId, setGameId] = useState<string | null>(null)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [exploits, setExploits] = useState<ExploitsData | null>(null)
  const [metas, setMetas] = useState<GameMetas>(() => new Map())
  const [tab, setTab] = useState<Tab>('stage')
  const [error, setError] = useState<string | null>(null)

  // replay: `follow` pins the cursor to the newest beat; otherwise `cursor` = number of beats revealed
  const [follow, setFollow] = useState(true)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)

  // presentation toggles
  const [blind, setBlind] = useState(false)
  const [revealedKey, setRevealedKey] = useState<string | null>(null)
  const [hideRoles, setHideRoles] = useState(false)
  const [help, setHelp] = useState(false)
  const [fresh, setFresh] = useState<string | null>(null) // a live game that appeared while another was open

  // ---- poll index + exploits + game records every second ---------------------------------------
  const indexJson = useRef('')
  const exploitsJson = useRef('')
  const knownIds = useRef<Set<string> | null>(null)
  useEffect(() => {
    let stop = false
    const tick = async () => {
      try {
        const idx = await fetchIndex()
        if (stop) return
        const j = JSON.stringify(idx)
        if (j !== indexJson.current) {
          indexJson.current = j
          setIndex(idx)
          const m = await loadGameMetas(idx)
          if (stop) return
          setMetas(m)
          // a game dir that was not there a second ago and is still being written: offer it
          const before = knownIds.current
          if (before) {
            const born = idx.filter((e) => !before.has(e.game_id) && !e.has_game && e.dir !== 'fixtures')
            if (born.length) setFresh(born.sort((a, b) => b.mtime - a.mtime)[0].game_id)
          }
          knownIds.current = new Set(idx.map((e) => e.game_id))
        }
        const ex = await loadExploits(idx)
        if (stop) return
        const ej = JSON.stringify(ex)
        if (ej !== exploitsJson.current) {
          exploitsJson.current = ej
          setExploits(ex)
        }
        setError(null)
      } catch (e) {
        if (!stop) setError(String(e))
      }
    }
    void tick()
    const id = setInterval(tick, POLL_MS)
    return () => {
      stop = true
      clearInterval(id)
    }
  }, [])

  // newest game first in the picker; default to it
  const picker = useMemo(() => [...index].sort((a, b) => b.mtime - a.mtime || a.game_id.localeCompare(b.game_id)), [index])
  useEffect(() => {
    if (gameId === null && picker.length) setGameId(picker[0].game_id)
  }, [picker, gameId])
  const entry = useMemo(() => index.find((e) => e.game_id === gameId) ?? null, [index, gameId])

  // ---- poll the open game's files every second -------------------------------------------------
  const loadedJson = useRef('')
  useEffect(() => {
    if (!entry) return
    let stop = false
    const e = entry
    const tick = async () => {
      try {
        const [data, events] = await Promise.all([loadGame(e), loadEvents(e).catch(() => null)])
        if (stop) return
        const j = JSON.stringify([data, events])
        if (j !== loadedJson.current) {
          loadedJson.current = j
          setLoaded({ data, events })
        }
      } catch (err) {
        if (!stop) setError(String(err))
      }
    }
    void tick()
    const id = setInterval(tick, POLL_MS)
    return () => {
      stop = true
      clearInterval(id)
    }
    // re-run only when the game changes, not on every index refresh
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entry?.game_id, entry?.dir, entry?.has_scores, entry?.has_game, entry?.has_events])

  const pendingJump = useRef<{ gameId: string; round: number; pid: string } | null>(null)
  const initFor = useRef<string | null>(null)
  const [jumpTick, setJumpTick] = useState(0)

  const selectGame = useCallback((id: string) => {
    loadedJson.current = ''
    initFor.current = null
    setLoaded(null)
    setGameId(id)
    setFollow(true)
    setPlaying(false)
    setCursor(0)
    setRevealedKey(null)
    setFresh((f) => (f === id ? null : f))
  }, [])

  const data = loaded?.data ?? null
  const game = data?.game ?? null
  const events = loaded?.events ?? null
  const rows = useMemo(() => (data ? joinRows(data.turns, data.scores) : []), [data])
  const beats = useMemo(() => buildBeats(rows, events, game), [rows, events, game])
  const n = beats.length
  const shown = follow ? n : Math.max(n ? 1 : 0, Math.min(cursor, n))
  const at = shown - 1
  const beat = at >= 0 ? beats[at] : null
  const shownRef = useRef(shown)
  shownRef.current = shown

  // a finished game opens at its first beat, paused. a game still being written opens following live.
  useEffect(() => {
    if (!data || initFor.current === data.entry.game_id) return
    initFor.current = data.entry.game_id
    if (pendingJump.current?.gameId === data.entry.game_id) return
    if (data.game) {
      setFollow(false)
      setCursor(1)
    }
  }, [data])

  // "open the turn" from the leaderboard: resolve once that game's beats are here
  useEffect(() => {
    const pj = pendingJump.current
    if (!pj || !data || data.entry.game_id !== pj.gameId || !n) return
    const i = beats.findIndex((b) => b.kind === 'turn' && b.round === pj.round && b.row.turn.player_id === pj.pid)
    pendingJump.current = null
    setFollow(false)
    setPlaying(false)
    setCursor(i >= 0 ? i + 1 : 1)
  }, [beats, data, n, jumpTick])

  // a new live game appeared: open it, unless someone is mid-way through watching another one
  useEffect(() => {
    if (!fresh || fresh === gameId) return
    if (follow || shown >= n) selectGame(fresh)
  }, [fresh, gameId, follow, shown, n, selectGame])

  const seek = useCallback(
    (to: number) => {
      setFollow(false)
      setPlaying(false)
      setCursor(Math.max(1, Math.min(n, to)))
    },
    [n],
  )
  const step = useCallback((delta: number) => seek(shownRef.current + delta), [seek])
  const nextLie = useCallback(() => {
    if (!n) return
    const from = shownRef.current // index of the first not-yet-shown beat
    const order = [...beats.keys()]
    const idx = order
      .slice(from)
      .concat(order.slice(0, from))
      .find((i) => {
        const b = beats[i]
        return b.kind === 'turn' && b.row.score?.lied === true
      })
    if (idx === undefined) return
    setTab('stage')
    seek(idx + 1)
  }, [beats, n, seek])
  const reveal = useCallback(() => {
    if (beat) setRevealedKey(beat.key)
  }, [beat])

  // autoplay: dwell on a beat in proportion to how much there is to read
  useEffect(() => {
    if (!playing) return
    if (shown >= n) {
      setPlaying(false)
      return
    }
    const b = beats[at]
    const chars = b?.kind === 'turn' ? b.row.turn.public.length + b.row.turn.private.length * 0.6 : 260
    const ms = Math.min(15000, 2600 + chars * 20)
    const timers = [
      setTimeout(() => {
        setFollow(false)
        setCursor(shownRef.current + 1)
      }, ms),
    ]
    if (blind && b) timers.push(setTimeout(() => setRevealedKey(b.key), ms * 0.5))
    return () => timers.forEach(clearTimeout)
  }, [playing, shown, n, at, beats, blind])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLSelectElement || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      switch (e.code === 'Space' ? ' ' : e.key) {
        case ' ':
        case 'Spacebar':
          e.preventDefault()
          setTab('stage')
          setFollow(false)
          setCursor(shownRef.current >= n && n > 0 ? 1 : shownRef.current) // at the end: rewind, then play
          setPlaying((p) => !p)
          break
        case 'ArrowRight':
          e.preventDefault()
          step(1)
          break
        case 'ArrowLeft':
          e.preventDefault()
          step(-1)
          break
        case 'Home':
          e.preventDefault()
          seek(1)
          break
        case 'End':
          e.preventDefault()
          seek(n)
          break
        case 'l':
        case 'L':
          nextLie()
          break
        case 'f':
        case 'F':
          setPlaying(false)
          setCursor(shownRef.current)
          setFollow((f) => !f)
          break
        case 'b':
        case 'B':
          setBlind((v) => !v)
          setRevealedKey(null)
          break
        case 'r':
        case 'R':
          reveal()
          break
        case 'h':
        case 'H':
          setHideRoles((v) => !v)
          break
        case 's':
        case 'S':
          setTab('stage')
          break
        case 't':
        case 'T':
          setTab('transcript')
          break
        case 'e':
        case 'E':
          setTab((t) => (t === 'exploits' ? 'stage' : 'exploits'))
          break
        case 'g':
        case 'G':
          setTab((t) => (t === 'games' ? 'stage' : 'games'))
          break
        case '?':
          setHelp((v) => !v)
          break
        case 'Escape':
          setHelp(false)
          break
        default:
          return
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, seek, nextLie, reveal, n])

  const revealed = beat !== null && revealedKey === beat.key
  const concealing = blind && !revealed && beat?.kind === 'turn'
  const table = useMemo(() => tableAt(beats, Math.max(0, at), game, concealing), [beats, at, game, concealing])

  // role + model per seat before game.json exists: read off the turns revealed so far
  const seen = useMemo(() => {
    const m: SeenMap = {}
    for (const b of beats.slice(0, Math.max(0, shown))) if (b.kind === 'turn') m[b.row.turn.player_id] = { role: b.row.turn.role, model: b.row.turn.model_name }
    return m
  }, [beats, shown])

  const gameExploits = useMemo(() => (exploits?.exploits ?? []).filter((x) => x.game_id === gameId), [exploits, gameId])
  // synthetic fixture games never count toward anything a judge reads as a result
  const fixtureIds = useMemo(() => new Set(index.filter((e) => e.dir === 'fixtures').map((e) => e.game_id)), [index])
  const undesignedAll = (exploits?.exploits ?? []).filter((x) => !x.designed && !fixtureIds.has(x.game_id)).length
  const realGames = index.filter((e) => e.dir !== 'fixtures').length
  const known = useMemo(() => new Set(index.map((e) => e.game_id)), [index])
  const openTurn = useCallback(
    (x: Exploit) => {
      pendingJump.current = { gameId: x.game_id, round: x.round, pid: x.player_id }
      setTab('stage')
      if (x.game_id !== gameId) selectGame(x.game_id)
      else setJumpTick((t) => t + 1) // same game is already loaded: run the resolver now
    },
    [gameId, selectGame],
  )

  const inProgress = data !== null && game === null
  const rowsShown = beats.slice(0, Math.max(0, shown)).reduce((c, b) => c + (b.kind === 'turn' ? 1 : 0), 0)
  const focusRow = beat?.kind === 'turn' ? beat.rowIdx : -1
  const isFixture = entry?.dir === 'fixtures'
  const onStage = tab === 'stage' || tab === 'transcript'

  return (
    <div className={`app tab-${tab}`}>
      <header className="top">
        <div className="brand">
          <span className="brand-name">scheming</span>
          <span className="brand-tag">a deception eval that looks like a party game</span>
        </div>
        <nav className="tabs" aria-label="views">
          {(
            [
              ['stage', 'stage', null],
              ['transcript', 'transcript', null],
              ['exploits', 'exploits', exploits ? undesignedAll : null],
              ['games', 'games', realGames],
            ] as [Tab, string, number | null][]
          ).map(([t, label, count]) => (
            <button type="button" key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)} aria-current={tab === t ? 'page' : undefined}>
              {label}
              {count !== null && <span className={t === 'exploits' && count > 0 ? 'count hot' : 'count'}>{count}</span>}
            </button>
          ))}
        </nav>
        <span className="spacer" />
        {fresh && fresh !== gameId && (
          <button type="button" className="btn fresh" onClick={() => selectGame(fresh)}>
            a new game is live. watch it
          </button>
        )}
        {isFixture && (
          <span className="flag-fixture" title="hand-written fixture, not a real game. real games live under runs/ and fixtures/live/">
            synthetic fixture
          </span>
        )}
        <select className="picker" value={gameId ?? ''} onChange={(e) => selectGame(e.target.value)} aria-label="game">
          {picker.map((e) => (
            <option key={e.game_id} value={e.game_id}>
              {e.game_id}, {e.turn_count} turns{e.has_scores ? ', scored' : ''}
              {e.dir === 'fixtures' ? ', fixture' : ''}
            </option>
          ))}
        </select>
        <span className={inProgress ? 'status live' : 'status'}>
          <i aria-hidden="true" />
          {inProgress ? (follow ? 'live' : 'live, you are behind') : data ? 'recorded' : 'no game'}
        </span>
      </header>

      {error && (
        <div className="empty hot">
          the data server is not answering.
          <span>{error}</span>
        </div>
      )}

      {onStage && !error && data === null && <div className="empty">loading the game.</div>}
      {onStage && !error && data !== null && n === 0 && (
        <div className="empty">
          no turns yet.
          <span>the first statement appears here the moment the engine writes it.</span>
        </div>
      )}

      {onStage && data !== null && n > 0 && beat && (
        <>
          <Seats table={table} game={game} seen={seen} hideRoles={hideRoles} totalRounds={game?.rounds ?? null} />
          {tab === 'stage' ? (
            <Stage
              beat={beat}
              rows={rows}
              game={game}
              table={table}
              seen={seen}
              exploits={gameExploits}
              blind={blind}
              revealed={revealed}
              hideRoles={hideRoles}
              onReveal={reveal}
              onRestart={() => seek(1)}
              onExploits={() => setTab('exploits')}
            />
          ) : (
            <SplitScreen
              rows={rows}
              shown={rowsShown}
              focusIdx={focusRow}
              hideRoles={hideRoles}
              onPick={(rowIdx) => {
                const i = beats.findIndex((b) => b.kind === 'turn' && b.rowIdx === rowIdx)
                if (i >= 0) seek(i + 1)
                setTab('stage')
              }}
            />
          )}
          <footer className="deck">
            <div className="transport">
              <button
                type="button"
                className="btn play"
                onClick={() => {
                  setFollow(false)
                  setCursor(shown >= n ? 1 : shown)
                  setPlaying((p) => !p)
                }}
                aria-pressed={playing}
              >
                {playing ? 'pause' : 'play'}
              </button>
              <button type="button" className="btn ghost sq" onClick={() => step(-1)} aria-label="previous beat" disabled={shown <= 1}>
                ‹
              </button>
              <button type="button" className="btn ghost sq" onClick={() => step(1)} aria-label="next beat" disabled={shown >= n}>
                ›
              </button>
              <button type="button" className="btn ghost" onClick={nextLie}>
                next lie
              </button>
              <span className="pos">
                <b>{shown}</b> of {n}
              </span>
            </div>
            <Tape beats={beats} at={at} onSeek={(i) => seek(i + 1)} concealFrom={blind ? (revealed ? at + 1 : at) : null} />
            <div className="toggles">
              <button
                type="button"
                className={follow ? 'btn ghost on' : 'btn ghost'}
                onClick={() => {
                  setPlaying(false)
                  setCursor(shown)
                  setFollow((f) => !f)
                }}
                aria-pressed={follow}
              >
                follow live
              </button>
              <button
                type="button"
                className={blind ? 'btn ghost on' : 'btn ghost'}
                onClick={() => {
                  setBlind((v) => !v)
                  setRevealedKey(null)
                }}
                aria-pressed={blind}
              >
                blind
              </button>
              <button type="button" className={hideRoles ? 'btn ghost on' : 'btn ghost'} onClick={() => setHideRoles((v) => !v)} aria-pressed={hideRoles}>
                hide roles
              </button>
              <button type="button" className="btn ghost sq" onClick={() => setHelp((v) => !v)} aria-label="keyboard shortcuts" aria-expanded={help}>
                ?
              </button>
            </div>
          </footer>
        </>
      )}

      {tab === 'exploits' && <Exploits data={exploits} metas={metas} fixtureIds={fixtureIds} canOpen={(x) => known.has(x.game_id)} onOpen={openTurn} />}
      {tab === 'games' && (
        <Games
          entries={picker}
          metas={metas}
          exploits={exploits}
          current={gameId}
          onOpen={(id) => {
            if (id !== gameId) selectGame(id)
            setTab('stage')
          }}
        />
      )}

      {help && (
        <div className="help" role="dialog" aria-label="keyboard shortcuts" onClick={() => setHelp(false)}>
          <dl>
            {KEYS.map(([k, what]) => (
              <div key={k}>
                <dt>
                  <kbd>{k}</kbd>
                </dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}
