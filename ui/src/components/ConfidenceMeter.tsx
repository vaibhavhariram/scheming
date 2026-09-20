import type { Score } from '../data/types'

/**
 * Deception meter. Driven only by score.lied and score.confidence.
 *   lied true  -> red fill, width = confidence
 *   lied false -> neutral (grey) fill, width = confidence
 *   no score   -> renders nothing (caller shows "unscored")
 */
export function ConfidenceMeter({ score }: { score: Score | null }) {
  if (score === null) return null
  const c = Math.max(0, Math.min(1, Number(score.confidence) || 0))
  const pct = Math.round(c * 100)
  return (
    <div className={score.lied ? 'meter lied' : 'meter honest'} title={`confidence ${c.toFixed(2)}`}>
      <div className="track">
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="lab">
        {score.lied ? <span className="hot">lied</span> : <span>no lie</span>} · {c.toFixed(2)}
      </div>
    </div>
  )
}
