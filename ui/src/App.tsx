import { useEffect, useState } from 'react'
import { getScores, getTurns, indexScores, joinRows, listGames, type Row } from './data/source'
import type { Game } from './data/types'
import { SplitScreen } from './views/SplitScreen'

export default function App() {
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<string | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [round, setRound] = useState(1)
  const [hideRoles, setHideRoles] = useState(false)
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

  const maxRound = rows.reduce((m, r) => Math.max(m, r.turn.round), 1)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowRight') setRound((r) => Math.min(maxRound, r + 1))
      if (e.key === 'ArrowLeft') setRound((r) => Math.max(1, r - 1))
      if (e.key === 'h' || e.key === 'H') setHideRoles((h) => !h)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [maxRound])

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
        <span>
          <kbd>←</kbd> <kbd>→</kbd> round · <kbd>H</kbd> roles
        </span>
      </header>
      {error && <div className="empty hot">{error}</div>}
      {!error && !rows.length && <div className="empty">loading…</div>}
      {rows.length > 0 && <SplitScreen rows={rows} round={round} hideRoles={hideRoles} />}
    </>
  )
}
