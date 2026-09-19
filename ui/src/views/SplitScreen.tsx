/**
 * View 1. One row per player for the selected round. Private left (monospace, internals),
 * public right (proportional, larger, a person talking). Everything shown is a contract field.
 *
 * Delayed reveal: when `conceal` is on, a row hides its private panel and every score-derived
 * or role-derived signal (role badge, lie badge, confidence meter) until revealed. Player id,
 * model name, the public column and the vote / no-statement chips are always visible.
 * Reveal is instant and keeps the layout footprint: hidden content stays in flow.
 */
import { ConfidenceMeter } from '../components/ConfidenceMeter'
import { Highlight } from '../components/Highlight'
import type { Row } from '../data/source'

export function rowKey(round: number, playerId: string): string {
  return `${round}-${playerId}`
}

export function SplitScreen({
  rows,
  round,
  hideRoles,
  conceal,
  revealed,
  onReveal,
}: {
  rows: Row[]
  round: number
  hideRoles: boolean
  conceal: boolean
  revealed: ReadonlySet<string>
  onReveal: (key: string) => void
}) {
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
      {visible.map(({ turn, score }) => {
        const key = rowKey(turn.round, turn.player_id)
        const concealed = conceal && !revealed.has(key)
        const gated = concealed ? 'gated concealed' : 'gated'
        return (
          <div className="row" key={key}>
            <div className="meta">
              <div className="pid">{turn.player_id}</div>
              <div className="model">{turn.model_name}</div>
              <div className={gated}>
                {!hideRoles && <span className={`badge ${turn.role}`}>{turn.role}</span>}
              </div>
              <div className={gated}>
                <ConfidenceMeter score={score} />
              </div>
              <div className={gated}>
                {score?.lied && score.lie_kind && <span className="badge lie">{score.lie_kind.replace('_', ' ')}</span>}
                {score === null && <span className="badge unscored">unscored</span>}
              </div>
            </div>
            <div
              className={concealed ? 'private concealed' : 'private'}
              onClick={concealed ? () => onReveal(key) : undefined}
              role={concealed ? 'button' : undefined}
              aria-label={concealed ? `reveal ${turn.player_id} private` : undefined}
            >
              <pre>
                <Highlight text={turn.private} quote={score?.lied ? score.quote : null} />
              </pre>
              {concealed && <div className="veil">concealed</div>}
            </div>
            <div className="public">
              {turn.public === '' ? (
                <p>
                  <span className="chip nostatement">no statement</span>
                </p>
              ) : (
                <p>{turn.public}</p>
              )}
              {turn.vote !== null ? <span className="chip">VOTED → {turn.vote}</span> : <span className="chip none">no vote</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
