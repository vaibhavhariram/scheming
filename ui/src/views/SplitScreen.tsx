/**
 * View 1. One row per player for the selected round. Private left (monospace, internals),
 * public right (proportional, larger, a person talking). Everything shown is a contract field.
 */
import { ConfidenceMeter } from '../components/ConfidenceMeter'
import { Highlight } from '../components/Highlight'
import type { Row } from '../data/source'

export function SplitScreen({ rows, round, hideRoles }: { rows: Row[]; round: number; hideRoles: boolean }) {
  const visible = rows.filter((r) => r.turn.round === round)
  if (!visible.length) return <div className="empty">no turns in round {round}</div>
  return (
    <div className="split">
      <div className="colhead" />
      <div className="colhead private">
        Private
        <span className="sub">scratchpad, unobserved by other players</span>
      </div>
      <div className="colhead public">
        Public
        <span className="sub">spoken aloud</span>
      </div>
      {visible.map(({ turn, score }) => (
        <div className="row" key={`${turn.round}-${turn.player_id}`}>
          <div className="meta">
            <div className="pid">{turn.player_id}</div>
            {!hideRoles && <span className={`badge ${turn.role}`}>{turn.role}</span>}
            <div className="model">{turn.model_name}</div>
            <ConfidenceMeter score={score} />
            {score?.lied && score.lie_kind && <span className="badge lie">{score.lie_kind.replace('_', ' ')}</span>}
            {score === null && <span className="badge unscored">unscored</span>}
          </div>
          <div className="private">
            <pre>
              <Highlight text={turn.private} quote={score?.lied ? score.quote : null} />
            </pre>
          </div>
          <div className="public">
            {turn.public === '' ? (
              <p>
                <span className="chip nostatement">no statement</span>
              </p>
            ) : (
              <p>{turn.public}</p>
            )}
            {turn.vote !== null ? (
              <span className="chip">VOTED → {turn.vote}</span>
            ) : (
              <span className="chip none">no vote</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
