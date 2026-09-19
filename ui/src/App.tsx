/** Checkpoint 1: proof of load. Raw rows straight from source.ts + the join index. */
import { useEffect, useState } from 'react'
import { getExploits, getScores, getTurns, indexScores, joinRows, listGames, type Row } from './data/source'
import type { Exploit, Game } from './data/types'

export default function App() {
  const [games, setGames] = useState<Game[]>([])
  const [gameId, setGameId] = useState<string | null>(null)
  const [rows, setRows] = useState<Row[]>([])
  const [exploits, setExploits] = useState<Exploit[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listGames()
      .then((gs) => {
        setGames(gs)
        setGameId(gs[0]?.game_id ?? null)
      })
      .catch((e) => setError(String(e)))
    getExploits().then(setExploits).catch((e) => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!gameId) return
    Promise.all([getTurns(gameId), getScores(gameId)])
      .then(([turns, scores]) => setRows(joinRows(turns, indexScores(scores))))
      .catch((e) => setError(String(e)))
  }, [gameId])

  const game = games.find((g) => g.game_id === gameId)
  return (
    <div style={{ padding: 16 }}>
      <h1 style={{ fontSize: 18, margin: '0 0 12px' }}>scheming — checkpoint 1: raw load</h1>
      {error && <p className="hot">{error}</p>}
      <p className="dim">
        games: {games.length} · exploits: {exploits.length} ·{' '}
        <select value={gameId ?? ''} onChange={(e) => setGameId(e.target.value)}>
          {games.map((g) => (
            <option key={g.game_id} value={g.game_id}>
              {g.game_id} — {g.models[0]} — {g.winner} in {g.rounds}
            </option>
          ))}
        </select>
      </p>
      {game && (
        <p className="mono dim">
          roles {JSON.stringify(game.roles)} · models {JSON.stringify(game.models)} · ts {game.ts}
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>round</th><th>player</th><th>role</th><th>model</th><th>vote</th><th>score</th><th>private</th><th>public</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ turn, score }) => (
            <tr key={`${turn.round}-${turn.player_id}`}>
              <td>{turn.round}</td>
              <td className="mono">{turn.player_id}</td>
              <td>{turn.role}</td>
              <td className="mono dim">{turn.model_name}</td>
              <td className="mono">{turn.vote ?? '—'}</td>
              <td className="mono">
                {score === null ? (
                  <span className="dim">unscored</span>
                ) : (
                  <span className={score.lied ? 'hot' : ''}>
                    {score.lied ? `lied/${score.lie_kind}` : 'ok'} {score.confidence.toFixed(2)}
                    {score.quote ? ` “${score.quote.slice(0, 40)}…”` : ''}
                  </span>
                )}
              </td>
              <td className="mono" style={{ maxWidth: 380 }}>{turn.private.slice(0, 160)}…</td>
              <td style={{ maxWidth: 380 }}>{turn.public === '' ? <span className="hot">[ SILENT ]</span> : turn.public.slice(0, 160) + '…'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
