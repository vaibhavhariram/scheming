/**
 * The split screen. Rounds top to bottom, turns in ts order within a round. Each turn is one
 * row: meta | private scratchpad | public statement. Replay reveals the first `shown` rows;
 * the last revealed row is focused and scrolled into view.
 *
 * Dead players (game.death_cause, when the engine emitted it) are greyed from the round after
 * their last turn. Nothing here is computed from scores; a missing score is "unscored".
 */
import { useEffect, useRef, type ReactNode } from 'react'
import { ConfidenceMeter } from '../components/ConfidenceMeter'
import { Highlight } from '../components/Highlight'
import type { Row } from '../data/source'
import { PLAYER_IDS, type DeathCause, type Game, type PlayerId } from '../data/types'

interface DeathInfo {
  cause: DeathCause
  /** last round with a turn by this player; greyed from lastRound + 1 */
  lastRound: number
}

function deaths(rows: Row[], game: Game | null): Map<PlayerId, DeathInfo> {
  const m = new Map<PlayerId, DeathInfo>()
  const dc = game?.death_cause
  if (!dc || typeof dc !== 'object') return m
  for (const pid of PLAYER_IDS) {
    const cause = dc[pid]
    if (cause !== 'vote' && cause !== 'night') continue
    const lastRound = rows.reduce((mx, r) => (r.turn.player_id === pid ? Math.max(mx, r.turn.round) : mx), 0)
    m.set(pid, { cause, lastRound })
  }
  return m
}

function Roster({ round, dead, game }: { round: number; dead: Map<PlayerId, DeathInfo>; game: Game | null }) {
  return (
    <div className="roster">
      {PLAYER_IDS.map((pid) => {
        const d = dead.get(pid)
        const gone = d !== undefined && round > d.lastRound
        const role = game?.roles?.[pid]
        return (
          <span key={pid} className={gone ? 'rp gone' : 'rp'} title={gone ? `${pid} died by ${d.cause} after round ${d.lastRound}` : pid}>
            {pid}
            {role && <em className={`rr ${role}`}>{role === 'wolf' ? 'W' : 'V'}</em>}
            {gone && <i>{d.cause === 'night' ? 'killed' : 'voted out'}</i>}
          </span>
        )
      })}
    </div>
  )
}

export function SplitScreen({ rows, shown, game }: { rows: Row[]; shown: number; game: Game | null }) {
  const focusIdx = Math.min(shown, rows.length) - 1
  const focusRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusIdx, rows.length])

  if (!rows.length) return <div className="empty">no turns yet — waiting for turns.json</div>
  if (shown <= 0) return <div className="empty">press → to reveal the first turn</div>

  const dead = deaths(rows, game)
  const visible = rows.slice(0, focusIdx + 1)
  const out: ReactNode[] = []
  let lastRound = -1
  visible.forEach(({ turn, score }, i) => {
    if (turn.round !== lastRound) {
      lastRound = turn.round
      out.push(
        <div className="roundhead" key={`r${turn.round}`}>
          <span className="rn">round {turn.round}</span>
          <Roster round={turn.round} dead={dead} game={game} />
        </div>,
      )
    }
    const d = dead.get(turn.player_id)
    const gone = d !== undefined && turn.round > d.lastRound
    const focused = i === focusIdx
    const cls = ['row', focused ? 'focused' : '', gone ? 'dead' : ''].filter(Boolean).join(' ')
    const lied = score?.lied === true
    out.push(
      <div className={cls} key={`${turn.round}-${turn.player_id}-${turn.ts}`} aria-current={focused ? 'true' : undefined}>
        <div className="meta" ref={focused ? focusRef : undefined}>
          <div className="pid">{turn.player_id}</div>
          <div className="model" title={turn.model_name}>
            {turn.model_name}
          </div>
          <span className={`badge ${turn.role}`}>{turn.role}</span>
          {turn.vote !== null ? <span className="chip vote">→ {turn.vote}</span> : <span className="chip none">no vote</span>}
          {score === null ? (
            <span className="badge unscored">unscored</span>
          ) : (
            <>
              {lied && score.lie_kind && <span className="badge lie">{score.lie_kind.replace('_', ' ')}</span>}
              <ConfidenceMeter score={score} />
            </>
          )}
          {gone && <span className="badge gone">dead · {d.cause}</span>}
        </div>
        <div className="private">
          <div className="lab">private — unobserved by other players</div>
          <pre>
            <Highlight text={turn.private} quote={lied ? score.quote : null} />
          </pre>
        </div>
        <div className="public">
          <div className="lab">public</div>
          {turn.public === '' ? <div className="silence">chose silence</div> : <p>{turn.public}</p>}
        </div>
      </div>,
    )
  })

  if (game && focusIdx === rows.length - 1) {
    out.push(
      <div className="roundhead final" key="final">
        <span className="rn">game over · {game.winner} win</span>
        <Roster round={Number.MAX_SAFE_INTEGER} dead={dead} game={game} />
      </div>,
    )
  }

  return (
    <div className="split">
      <div className="colhead" />
      <div className="colhead private">
        private
        <span className="sub">scratchpad — unobserved by other players</span>
      </div>
      <div className="colhead public">
        public
        <span className="sub">spoken to the table</span>
      </div>
      {out}
    </div>
  )
}
