/**
 * Every game on disk, newest first. One card per game: who played, who won, how much of it is
 * scored. Read off the data index, each game's Game record and the exploit list; no aggregates.
 */
import type { ExploitsData, GameMetas, IndexEntry } from '../data/source'
import { plural, shortModel } from '../components/names'

export function Games({ entries, metas, exploits, current, onOpen }: { entries: IndexEntry[]; metas: GameMetas; exploits: ExploitsData | null; current: string | null; onOpen: (gameId: string) => void }) {
  if (!entries.length)
    return (
      <div className="empty">
        no games on disk yet.
        <span>run the engine with --out runs/ and they appear here as they are written.</span>
      </div>
    )
  const real = entries.filter((e) => e.dir !== 'fixtures')
  const nFixtures = entries.length - real.length
  const xBy = new Map<string, number>()
  for (const x of exploits?.exploits ?? []) xBy.set(x.game_id, (xBy.get(x.game_id) ?? 0) + 1)
  return (
    <div className="games">
      <header className="board-head">
        <h1>
          <span className="board-n">{real.length}</span>
          <span className="board-t">
            real {real.length === 1 ? 'game' : 'games'} on disk
            <small>
              {plural(real.filter((e) => e.has_scores).length, 'game')} scored, {plural(real.reduce((s, e) => s + e.turn_count, 0), 'turn')} logged.
              {nFixtures > 0 ? ` plus ${plural(nFixtures, 'synthetic fixture')}, not counted.` : ''}
            </small>
          </span>
        </h1>
      </header>
      <ul className="game-grid">
        {entries.map((e) => {
          const g = metas.get(e.game_id)
          const models = g ? Array.from(new Set(g.models.map(shortModel))) : []
          const nx = xBy.get(e.game_id) ?? 0
          return (
            <li key={e.game_id}>
              <button type="button" className={['game-card', e.game_id === current ? 'on' : '', e.dir === 'fixtures' ? 'fixture' : ''].filter(Boolean).join(' ')} onClick={() => onOpen(e.game_id)}>
                <span className="gc-id">{e.game_id}</span>
                <span className={g ? `gc-win ${g.winner}` : 'gc-win live'}>{g ? (g.winner === 'wolves' ? 'wolves won' : 'village won') : 'in progress'}</span>
                <span className="gc-models" title={g?.models.join(', ')}>
                  {models.join(', ') || ' '}
                </span>
                <span className="gc-meta">
                  <span>{plural(e.turn_count, 'turn')}</span>
                  {g && <span>{plural(g.rounds, 'round')}</span>}
                  <span className={e.has_scores ? '' : 'dim'}>{e.has_scores ? 'scored' : 'not scored'}</span>
                  {nx > 0 && <span className="hot">{plural(nx, 'exploit')}</span>}
                  {e.dir === 'fixtures' && <span className="fx">synthetic fixture</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
