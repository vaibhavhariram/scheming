import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchIndex, joinRows, loadExploits, loadGame, type ExploitsData, type GameData, type IndexEntry } from './data/source'
import { Exploits } from './views/Exploits'
import { SplitScreen } from './views/SplitScreen'

const POLL_MS = 1000
const PLAY_MS = 1800

type Tab = 'game' | 'exploits'

function fmtUsd(n: number): string {
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}

export default function App() {
  const [index, setIndex] = useState<IndexEntry[]>([])
  const [gameId, setGameId] = useState<string | null>(null)
  const [data, setData] = useState<GameData | null>(null)
  const [exploits, setExploits] = useState<ExploitsData | null>(null)
  const [tab, setTab] = useState<Tab>('game')
  const [error, setError] = useState<string | null>(null)

  // replay: `follow` pins the cursor to the newest turn; otherwise `cursor` = number of turns revealed
  const [follow, setFollow] = useState(true)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)

  // ---- poll index + exploits every second -------------------------------------------------
  const indexJson = useRef('')
  const exploitsJson = useRef('')
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

  // ---- poll the open game's files every second ---------------------------------------------
  const dataJson = useRef('')
  useEffect(() => {
    if (!entry) return
    let stop = false
    const e = entry
    const tick = async () => {
      try {
        const d = await loadGame(e)
        if (stop) return
        const j = JSON.stringify(d)
        if (j !== dataJson.current) {
          dataJson.current = j
          setData(d)
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
  }, [entry?.game_id, entry?.dir, entry?.has_scores, entry?.has_game])

  const selectGame = useCallback((id: string) => {
    dataJson.current = ''
    setData(null)
    setGameId(id)
    setFollow(true)
    setPlaying(false)
    setCursor(0)
  }, [])

  const rows = useMemo(() => (data ? joinRows(data.turns, data.scores) : []), [data])
  const n = rows.length
  const shown = follow ? n : Math.max(n ? 1 : 0, Math.min(cursor, n))
  const shownRef = useRef(shown)
  shownRef.current = shown

  const step = useCallback(
    (delta: number) => {
      setFollow(false)
      setCursor(Math.max(1, Math.min(n, shownRef.current + delta)))
    },
    [n],
  )
  const nextLie = useCallback(() => {
    if (!n) return
    const from = shownRef.current // index of the first not-yet-shown row
    const order = [...rows.keys()]
    const idx = order.slice(from).concat(order.slice(0, from)).find((i) => rows[i].score?.lied === true)
    if (idx === undefined) return
    setFollow(false)
    setPlaying(false)
    setCursor(idx + 1)
  }, [rows, n])

  // autoplay
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      if (shownRef.current >= n) {
        setPlaying(false)
        return
      }
      setFollow(false)
      setCursor(shownRef.current + 1)
    }, PLAY_MS)
    return () => clearInterval(id)
  }, [playing, n])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLSelectElement || e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      switch (e.code === 'Space' ? ' ' : e.key) {
        case ' ':
        case 'Spacebar':
          e.preventDefault()
          setTab('game')
          setFollow(false)
          if (shownRef.current >= n && n > 0) setCursor(1) // at the end: rewind, then play
          setPlaying((p) => !p)
          break
        case 'ArrowRight':
          e.preventDefault()
          setPlaying(false)
          step(1)
          break
        case 'ArrowLeft':
          e.preventDefault()
          setPlaying(false)
          step(-1)
          break
        case 'l':
        case 'L':
          setTab('game')
          nextLie()
          break
        case 'f':
        case 'F':
          setPlaying(false)
          setFollow((f) => !f)
          break
        case 'e':
        case 'E':
          setTab((t) => (t === 'game' ? 'exploits' : 'game'))
          break
        default:
          return
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step, nextLie, n])

  const game = data?.game ?? null
  const models = game ? Array.from(new Set(game.models)) : Array.from(new Set(rows.map((r) => r.turn.model_name)))
  const maxRound = rows.reduce((m, r) => Math.max(m, r.turn.round), 0)
  const turns = data?.turns ?? []
  const hasTokens = turns.some((t) => typeof t.tokens_in === 'number' || typeof t.tokens_out === 'number')
  const totalTokens = turns.reduce((s, t) => s + (t.tokens_in ?? 0) + (t.tokens_out ?? 0), 0)
  const hasCost = turns.some((t) => typeof t.cost_usd === 'number')
  const totalCost = turns.reduce((s, t) => s + (t.cost_usd ?? 0), 0)
  const liedCount = rows.filter((r) => r.score?.lied === true).length

  return (
    <>
      <header className="hdr">
        <span className="title">scheming</span>
        <select value={gameId ?? ''} onChange={(e) => selectGame(e.target.value)} aria-label="game">
          {picker.map((e) => (
            <option key={e.game_id} value={e.game_id}>
              {e.game_id} · {e.turn_count}t{e.has_scores ? ' · scored' : ''}
              {e.dir === 'fixtures' ? ' · fixture' : ''}
            </option>
          ))}
        </select>
        <nav className="tabs">
          <button type="button" className={tab === 'game' ? 'on' : ''} onClick={() => setTab('game')}>
            split screen
          </button>
          <button type="button" className={tab === 'exploits' ? 'on' : ''} onClick={() => setTab('exploits')}>
            exploits{exploits ? ` (${exploits.exploits.filter((x) => !x.designed).length})` : ''}
          </button>
        </nav>
        <span className="spacer" />
        <span className="hint">
          <kbd>space</kbd> play · <kbd>←</kbd><kbd>→</kbd> step · <kbd>l</kbd> next lie · <kbd>f</kbd> follow · <kbd>e</kbd> tab
        </span>
      </header>
      {tab === 'game' && (
        <div className="gamebar">
          <span className="gid">{gameId ?? '—'}</span>
          <span className="models" title={models.join(', ')}>
            {models.join(' · ') || '—'}
          </span>
          <span className={game ? 'winner' : 'winner live'}>{game ? `${game.winner} win` : 'in progress'}</span>
          <span>
            rounds <b>{game?.rounds ?? maxRound}</b>
          </span>
          <span>
            turns <b>{n}</b>
          </span>
          <span>
            tokens <b>{hasTokens ? totalTokens.toLocaleString() : '—'}</b>
          </span>
          <span>
            cost <b>{hasCost ? fmtUsd(totalCost) : '—'}</b>
          </span>
          <span>
            lies <b className={liedCount ? 'hot' : ''}>{data?.scores === null ? 'unscored' : liedCount}</b>
          </span>
          <span className="spacer" />
          <span className="replay">
            <b>{shown}</b> / {n}
            <i className={playing ? 'st on' : 'st'}>{playing ? 'playing' : 'paused'}</i>
            <i className={follow ? 'st on' : 'st'}>{follow ? 'following live' : 'replay'}</i>
          </span>
        </div>
      )}
      {error && <div className="empty hot">{error}</div>}
      {tab === 'game' && !error && data === null && <div className="empty">loading…</div>}
      {tab === 'game' && data !== null && <SplitScreen rows={rows} shown={shown} game={game} />}
      {tab === 'exploits' && <Exploits data={exploits} />}
    </>
  )
}
