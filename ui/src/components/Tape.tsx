/**
 * The tape: every beat of the game as one tick, left to right. A scored lie is a red spike whose
 * height is the judge's confidence (Score.confidence, as written by lane B). No lie is a short
 * tick, no score is a hollow one. Doubles as the scrubber: click a tick to go there.
 */
import type { Beat } from '../data/beats'
import { Ballot, Flag, Moon } from './Glyphs'

interface Props {
  beats: Beat[]
  /** index of the beat on stage */
  at: number
  onSeek: (idx: number) => void
  /** blind mode: beats at or after this index keep their score to themselves */
  concealFrom: number | null
}

export function Tape({ beats, at, onSeek, concealFrom }: Props) {
  // group consecutive beats by round so the tape reads day 1 | day 2 | ...
  const groups: { round: number; items: { beat: Beat; idx: number }[] }[] = []
  beats.forEach((beat, idx) => {
    const last = groups[groups.length - 1]
    if (beat.kind !== 'end' && last && last.round === beat.round) last.items.push({ beat, idx })
    else groups.push({ round: beat.kind === 'end' ? -1 : beat.round, items: [{ beat, idx }] })
  })
  const dense = beats.length > 34

  return (
    <div className={dense ? 'tape dense' : 'tape'} role="group" aria-label="game timeline">
      {groups.map((g) => (
        <div className="tape-group" key={g.round} style={{ flexGrow: g.items.length }}>
          <div className="tape-ticks">
            {g.items.map(({ beat, idx }) => {
              const state = idx === at ? 'now' : idx < at ? 'past' : 'future'
              if (beat.kind === 'turn') {
                const { turn, score } = beat.row
                const concealed = concealFrom !== null && idx >= concealFrom
                const lied = !concealed && score?.lied === true
                const conf = Math.max(0, Math.min(1, Number(score?.confidence) || 0))
                const h = lied ? 30 + conf * 70 : 14
                const kind = concealed || score === null ? 'unscored' : lied ? 'lied' : 'honest'
                return (
                  <button
                    type="button"
                    key={beat.key}
                    className={`tick ${kind} ${state}`}
                    onClick={() => onSeek(idx)}
                    title={`day ${turn.round} · ${turn.player_id}${lied ? ` · lied ${conf.toFixed(2)}` : ''}`}
                    aria-current={idx === at ? 'step' : undefined}
                  >
                    <span className="bar" style={{ height: `${h}%` }} />
                    <span className="who">{turn.player_id}</span>
                  </button>
                )
              }
              const label = beat.kind === 'night' ? `night ${beat.round}` : beat.kind === 'day_result' ? `day ${beat.round} vote` : 'game over'
              return (
                <button type="button" key={beat.key} className={`tick mark ${beat.kind} ${state}`} onClick={() => onSeek(idx)} title={label} aria-current={idx === at ? 'step' : undefined}>
                  <span className="glyph">{beat.kind === 'night' ? <Moon size={15} /> : beat.kind === 'day_result' ? <Ballot size={14} /> : <Flag size={14} />}</span>
                  <span className="who">{beat.kind === 'night' ? 'night' : beat.kind === 'day_result' ? 'vote' : 'end'}</span>
                </button>
              )
            })}
          </div>
          <div className="tape-label">{g.round < 0 ? '' : `round ${g.round}`}</div>
        </div>
      ))}
    </div>
  )
}
