/**
 * The transcript: every revealed turn, top to bottom, in the same night | day split as the stage.
 * Rounds top to bottom, turns in ts order within a round. Each turn is one row:
 * meta | private scratchpad | public statement. The row on stage is focused and scrolled into view;
 * clicking a row puts it on stage.
 *
 * Nothing here is computed from scores; a missing score is "not scored".
 */
import { useEffect, useRef, type ReactNode } from 'react'
import { ConfidenceMeter } from '../components/ConfidenceMeter'
import { WolfEyes } from '../components/Glyphs'
import { Highlight } from '../components/Highlight'
import { LIE_KIND_WORDS, shortModel } from '../components/names'
import type { Row } from '../data/source'

interface Props {
  rows: Row[]
  /** number of rows revealed by the replay cursor */
  shown: number
  /** index of the row on stage, or -1 when the stage shows something that is not a turn */
  focusIdx: number
  hideRoles: boolean
  onPick: (rowIdx: number) => void
}

export function SplitScreen({ rows, shown, focusIdx, hideRoles, onPick }: Props) {
  const focusRef = useRef<HTMLButtonElement | null>(null)
  useEffect(() => {
    focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [focusIdx, shown])

  if (!rows.length)
    return (
      <div className="empty">
        no turns yet.
        <span>waiting for the engine to write turns.jsonl for this game.</span>
      </div>
    )

  const out: ReactNode[] = []
  let lastRound = -1
  rows.slice(0, Math.max(1, shown)).forEach(({ turn, score }, i) => {
    if (turn.round !== lastRound) {
      lastRound = turn.round
      out.push(
        <div className="t-round" key={`r${turn.round}`}>
          day {turn.round}
        </div>,
      )
    }
    const focused = i === focusIdx
    const lied = score?.lied === true
    out.push(
      <button
        type="button"
        className={['t-row', focused ? 'focused' : '', lied ? 'is-lie' : ''].filter(Boolean).join(' ')}
        key={`${turn.round}-${turn.player_id}-${turn.ts}`}
        ref={focused ? focusRef : undefined}
        aria-current={focused ? 'true' : undefined}
        onClick={() => onPick(i)}
        title="open on stage"
      >
        <span className="t-meta">
          <span className="t-who">
            <span className="pid">{turn.player_id}</span>
            {!hideRoles && turn.role === 'wolf' && <WolfEyes size={22} />}
          </span>
          <span className="t-model" title={turn.model_name}>
            {shortModel(turn.model_name)}
          </span>
          <span className="t-vote">{turn.vote !== null ? `votes ${turn.vote}` : 'names no one'}</span>
          {score === null ? (
            <span className="t-unscored">not scored</span>
          ) : (
            <>
              {lied && score.lie_kind && <span className="t-kind">{LIE_KIND_WORDS[score.lie_kind] ?? score.lie_kind}</span>}
              <ConfidenceMeter score={score} />
            </>
          )}
        </span>
        <span className="t-private">
          <Highlight text={turn.private} quote={lied ? score.quote : null} />
        </span>
        <span className="t-public">{turn.public === '' ? <span className="silence">said nothing.</span> : turn.public}</span>
      </button>,
    )
  })

  return (
    <div className="transcript">
      <div className="t-head">
        <span />
        <span className="t-h night">to itself</span>
        <span className="t-h day">to the table</span>
      </div>
      {out}
    </div>
  )
}
