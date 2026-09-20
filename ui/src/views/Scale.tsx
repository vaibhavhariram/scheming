/**
 * Closing slide: lie rate by model, from research/results/sims/*-lie-rates.json.
 * CSS bars so it matches the dark UI. The UI displays research output; it does not recompute rates.
 */
import { useEffect, useState } from 'react'
import { fetchPlot, type PlotData } from '../data/source'
import { plural, shortModel } from '../components/names'

export function Scale() {
  const [data, setData] = useState<PlotData | null | undefined>(undefined)

  useEffect(() => {
    let stop = false
    void fetchPlot()
      .then((p) => {
        if (!stop) setData(p)
      })
      .catch(() => {
        if (!stop) setData(null)
      })
    return () => {
      stop = true
    }
  }, [])

  if (data === undefined) return <div className="empty">loading the scale plot.</div>
  if (data === null || !data.rows.length) {
    return (
      <div className="empty">
        no lie-rate plot yet.
        <span>research.sims.local_sims plot writes research/results/sims/*-lie-rates.json. this tab fills itself in when it lands.</span>
      </div>
    )
  }

  const max = Math.max(...data.rows.map((r) => r.lie_rate), 0.01)
  const degraded = data.excluded?.degraded ?? 0
  const gamesUsed = data.excluded?.games_used ?? data.rows.reduce((n, r) => n + r.games, 0)

  return (
    <div className="board scale">
      <header className="board-head">
        <h1>
          <span className="board-n">{Math.round(data.rows[0].lie_rate * 100)}</span>
          <span className="board-t">
            % peak lie rate
            <small>
              between-game, not within-game. every game is single-model.
              {data.rows.map((r) => ` ${r.games} ${shortModel(r.model)}`).join(' /')} games.
              {degraded > 0 ? ` ${plural(degraded, 'degraded run')} excluded.` : ''} {gamesUsed} games used.
            </small>
          </span>
        </h1>
      </header>
      <ul className="scale-bars" aria-label="lie rate by model">
        {data.rows.map((r) => {
          const pct = Math.round(r.lie_rate * 100)
          const height = `${(r.lie_rate / max) * 100}%`
          return (
            <li className="scale-col" key={r.model}>
              <div className="scale-pct">{pct}%</div>
              <div className="scale-track">
                <div className="scale-fill" style={{ height }} title={`${r.lies}/${r.turns} turns`} />
              </div>
              <div className="scale-lab" title={r.model}>
                {shortModel(r.model)}
              </div>
              <div className="scale-n">
                {r.lies}/{r.turns} turns · {plural(r.games, 'game')}
              </div>
            </li>
          )
        })}
      </ul>
      <p className="scale-caption">
        say on stage: this is a <b>between-game</b> comparison. a judge will ask.
      </p>
    </div>
  )
}
