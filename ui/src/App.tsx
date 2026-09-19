import { useCallback, useEffect, useState } from 'react'
import { getScores, getTurns, indexScores, joinRows, listGames, type Row } from './data/source'
import type { Game } from './data/types'
import { rowKey, SplitScreen } from './views/SplitScreen'

export default function App() {
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<string | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [round, setRound] = useState(1)
  const [hideRoles, setHideRoles] = useState(false)
  // delayed reveal: on by default; `revealed` holds row keys revealed in the current round
  const [delayedReveal, setDelayedReveal] = useState(true)
  const [revealed, setRevealed] = useState<Set<string>>(() => new Set())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listGames()
      .then((gs) => {
        setGames(gs)
        setGameId(gs[0]?.game_id ?? null)
      })
      .catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!gameId) return
    setRows([])
    Promise.all([getTurns(gameId), getScores(gameId)])
      .then(([turns, scores]) => {
        setRows(joinRows(turns, indexScores(scores)))
        setRound(1)
      })
      .catch((e) => setError(String(e)))
  }, [gameId])

  // reveal state resets on every round change, game change, and toggle change
  useEffect(() => {
    setRevealed(new Set())
  }, [round, gameId, delayedReveal])

  const maxRound = rows.reduce((m, r) => Math.max(m, r.turn.round), 1)

  const revealRow = useCallback((key: string) => {
    setRevealed((prev) => (prev.has(key) ? prev : new Set(prev).add(key)))
  }, [])

  const revealRound = useCallback(() => {
    setRevealed(new Set(rows.filter((r) => r.turn.round === round).map((r) => rowKey(r.turn.round, r.turn.player_id))))
  }, [rows, round])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLSelectElement || e.target instanceof HTMLInputElement) return
      if (e.key === 'ArrowRight') setRound((r) => Math.min(maxRound, r + 1))
      else if (e.key === 'ArrowLeft') setRound((r) => Math.max(1, r - 1))
      else if (e.key === 'h' || e.key === 'H') setHideRoles((h) => !h)
      else if (e.key === 'r' || e.key === 'R') setDelayedReveal((d) => !d)
      else if (e.key === ' ' || e.key === 'Spacebar' || e.code === 'Space') {
        e.preventDefault()
        revealRound()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [maxRound, revealRound])

  const game = games.find((g) => g.game_id === gameId)
  const models = game ? Array.from(new Set(game.models)) : []
  return (
    <>
      <header className="hdr">
        <span className="title">scheming</span>
        <select value={gameId ?? ''} onChange={(e) => setGameId(e.target.value)}>
          {games.map((g) => (
            <option key={g.game_id} value={g.game_id}>
              {g.game_id}
            </option>
          ))}
        </select>
        <span>{models.join(' · ')}</span>
        <span className="round">
          round {round} <span className="dim">/ {game?.rounds ?? maxRound}</span>
        </span>
        {game && <span className="winner">{game.winner}</span>}
        <span className="spacer" />
        <button
          type="button"
          className={delayedReveal ? 'toggle on' : 'toggle'}
          onClick={() => setDelayedReveal((d) => !d)}
          aria-pressed={delayedReveal}
        >
          delayed reveal {delayedReveal ? 'on' : 'off'}
        </button>
        <span>
          <kbd>←</kbd> <kbd>→</kbd> round · <kbd>space</kbd> reveal · <kbd>R</kbd> toggle · <kbd>H</kbd> roles
        </span>
      </header>
      {error && <div className="empty hot">{error}</div>}
      {!error && !rows.length && <div className="empty">loading…</div>}
      {rows.length > 0 && (
        <SplitScreen
          rows={rows}
          round={round}
          hideRoles={hideRoles}
          conceal={delayedReveal}
          revealed={revealed}
          onReveal={revealRow}
        />
      )}
    </>
  )
}
