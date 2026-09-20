import type { Score } from '../data/types'

/**
 * Deception meter, compact form (transcript rows). Driven only by score.lied and score.confidence.
 *   lied true  -> red fill, width = confidence
 *   lied false -> neutral fill, width = confidence
 *   no score   -> renders nothing (caller shows "not scored")
 */
export function ConfidenceMeter({ score }: { score: Score | null }) {
  if (score === null) return null
  const c = Math.max(0, Math.min(1, Number(score.confidence) || 0))
  const pct = Math.round(c * 100)
  return (
    <span className={score.lied ? 'meter lied' : 'meter honest'} title={`judge confidence ${c.toFixed(2)}`}>
      <span className="track">
        <span className="fill" style={{ width: `${pct}%` }} />
      </span>
      <span className="lab">
        {score.lied ? 'lied' : 'no lie'} {c.toFixed(2)}
      </span>
    </span>
  )
}
