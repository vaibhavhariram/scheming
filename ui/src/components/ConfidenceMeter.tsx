import type { Score } from '../data/types'

/** Driven only by score.confidence. Cool at 0, hot at 1. No score -> explicit unscored, never lied:false. */
export function ConfidenceMeter({ score }: { score: Score | null }) {
  if (score === null) {
    return (
      <div className="meter">
        <div className="track empty" />
        <div className="lab">unscored</div>
      </div>
    )
  }
  const c = Math.max(0, Math.min(1, score.confidence))
  const pct = Math.round(c * 100)
  const fill = `color-mix(in oklab, var(--cool) ${100 - pct}%, var(--hot) ${pct}%)`
  return (
    <div className="meter" title={`confidence ${c.toFixed(2)}`}>
      <div className="track">
        <div className="fill" style={{ width: `${pct}%`, background: fill }} />
      </div>
      <div className="lab">
        confidence <span className={c >= 0.7 ? 'hot' : ''}>{c.toFixed(2)}</span>
      </div>
    </div>
  )
}
