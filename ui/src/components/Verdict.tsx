import type { Ref } from 'react'
import type { Score } from '../data/types'
import { LIE_KIND_WORDS } from './names'

/**
 * The plate that sits on the seam between the private and public panes. Driven only by the Score
 * row lane B wrote: lied, lie_kind, confidence. No score -> says so. Nothing is inferred here.
 */
export function Verdict({ score, hidden, plateRef }: { score: Score | null; hidden?: boolean; plateRef?: Ref<HTMLDivElement> }) {
  if (hidden) {
    return (
      <div className="verdict veiled" ref={plateRef}>
        <span className="v-word">verdict hidden</span>
        <span className="v-sub">reveal the scratchpad to see the score</span>
      </div>
    )
  }
  if (score === null) {
    return (
      <div className="verdict unscored" ref={plateRef}>
        <span className="v-word">not scored yet</span>
        <span className="v-sub">no score row for this turn</span>
      </div>
    )
  }
  const c = Math.max(0, Math.min(1, Number(score.confidence) || 0))
  return (
    <div className={score.lied ? 'verdict lied' : 'verdict honest'} ref={plateRef} role="status">
      <span className="v-word">{score.lied ? 'lied' : 'no lie'}</span>
      {score.lied && score.lie_kind && <span className="v-kind">{LIE_KIND_WORDS[score.lie_kind] ?? score.lie_kind}</span>}
      <span className="v-meter" title={`judge confidence ${c.toFixed(2)}`}>
        <span className="v-fill" style={{ width: `${Math.round(c * 100)}%` }} />
      </span>
      <span className="v-conf">
        <b>{c.toFixed(2)}</b> judge confidence
      </span>
    </div>
  )
}
