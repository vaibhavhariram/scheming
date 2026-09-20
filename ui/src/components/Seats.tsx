/**
 * The table: five seats, who is speaking, who they voted for (arcs land on the target), who is
 * dead and how, and how many scored lies each player has told so far. Read off TableState only.
 */
import { useLayoutEffect, useRef, useState } from 'react'
import type { TableState } from '../data/beats'
import { PLAYER_IDS, type Game, type PlayerId, type Role } from '../data/types'
import { Moon, Sun, WolfEyes } from './Glyphs'
import { plural, shortModel } from './names'

const BAND_DEFAULT = 40 // px of headroom above the seats for the vote arcs; css --band overrides it

interface Props {
  table: TableState
  game: Game | null
  /** role + model per seat when game.json is not written yet (live game): read off the turns seen so far */
  seen: Partial<Record<PlayerId, { role: Role; model: string }>>
  hideRoles: boolean
  totalRounds: number | null
}

export function Seats({ table, game, seen, hideRoles, totalRounds }: Props) {
  const wrap = useRef<HTMLDivElement | null>(null)
  const seatEls = useRef<Partial<Record<PlayerId, HTMLDivElement | null>>>({})
  const [centers, setCenters] = useState<Partial<Record<PlayerId, number>>>({})
  const [width, setWidth] = useState(0)
  const [BAND, setBand] = useState(BAND_DEFAULT)

  useLayoutEffect(() => {
    const el = wrap.current
    if (!el) return
    const measure = () => {
      const next: Partial<Record<PlayerId, number>> = {}
      for (const pid of PLAYER_IDS) {
        const s = seatEls.current[pid]
        if (s) next[pid] = s.offsetLeft + s.offsetWidth / 2
      }
      setCenters(next)
      setWidth(el.clientWidth)
      setBand(parseFloat(getComputedStyle(el).getPropertyValue('--band')) || BAND_DEFAULT)
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [])

  // arcs: one per cast vote this day. arrivals on the same seat fan out so heads do not stack.
  const arrivals: Partial<Record<PlayerId, number>> = {}
  const arcs = table.votes
    .filter((v): v is { from: PlayerId; to: PlayerId } => v.to !== null && v.to !== v.from)
    .map((v) => {
      const k = (arrivals[v.to] = (arrivals[v.to] ?? 0) + 1) - 1
      const total = table.tally[v.to] ?? 1
      const x1 = centers[v.from] ?? 0
      const x2 = (centers[v.to] ?? 0) + (k - (total - 1) / 2) * 16
      const h = Math.min(BAND - 6, 14 + Math.abs(PLAYER_IDS.indexOf(v.from) - PLAYER_IDS.indexOf(v.to)) * 6)
      const top = BAND - h * 1.3
      return { ...v, d: `M${x1} ${BAND} C${x1} ${top}, ${x2} ${top}, ${x2} ${BAND - 1}`, x2, latest: v.from === table.speaker }
    })

  const night = table.phase === 'night'
  return (
    <div className={`tablebar ${table.phase}`}>
      <div className="seats" ref={wrap} style={{ paddingTop: BAND }}>
        {width > 0 && (
          <svg className="arcs" width={width} height={BAND} aria-hidden="true">
            {arcs.map((a) => (
              <g key={`${table.round}-${a.from}`} className={a.latest ? 'arc latest' : 'arc'}>
                <path d={a.d} pathLength={1} />
                <path className="head" d={`M${a.x2 - 4.5} ${BAND - 8} L${a.x2} ${BAND - 1} L${a.x2 + 4.5} ${BAND - 8}`} />
              </g>
            ))}
          </svg>
        )}
        {PLAYER_IDS.map((pid, i) => {
          const role = game?.roles?.[pid] ?? seen[pid]?.role
          const model = game?.models?.[i] ?? seen[pid]?.model
          const death = table.deaths.get(pid)
          const speaking = table.speaker === pid
          const vote = table.votes.find((v) => v.from === pid)
          const got = table.tally[pid] ?? 0
          const lies = table.lies[pid] ?? 0
          const showRole = !hideRoles || table.phase === 'ended'
          const wolf = role === 'wolf' && showRole
          let status: string
          if (death) status = death.cause === 'night' ? `killed, night ${death.round}` : death.cause === 'vote' ? `voted out, day ${death.round}` : 'out'
          else if (table.phase === 'ended') status = showRole && role ? role : 'alive'
          else if (night) status = wolf ? 'awake' : 'asleep'
          else if (vote) status = vote.to ? `votes ${vote.to}` : 'names no one'
          else status = 'yet to speak'
          const cls = ['seat', speaking ? 'speaking' : '', death ? 'dead' : '', wolf ? 'wolf' : '', got ? 'targeted' : ''].filter(Boolean).join(' ')
          return (
            <div
              key={pid}
              className={cls}
              ref={(el) => {
                seatEls.current[pid] = el
              }}
            >
              <div className="seat-top">
                <span className="pid">{pid}</span>
                {wolf && <WolfEyes size={26} />}
                {got > 0 && <span className="got" title={plural(got, 'vote')}>{got}</span>}
              </div>
              <div className="seat-model" title={model ?? ''}>
                {model ? shortModel(model) : ' '}
              </div>
              <div className="seat-status">
                <span>{status}</span>
                {lies > 0 && (
                  <span className="lies" title={`${plural(lies, 'scored lie')} so far`}>
                    {plural(lies, 'lie')}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
      <div className="phase" aria-live="polite">
        <span className="phase-glyph">{table.phase === 'ended' ? null : night ? <Moon size={22} /> : <Sun size={22} />}</span>
        <span className="phase-name">{table.phase === 'ended' ? 'game over' : `${night ? 'night' : 'day'} ${table.round}`}</span>
        <span className="phase-sub">{table.phase === 'ended' ? plural(table.round, 'round') : totalRounds ? `round ${table.round} of ${totalRounds}` : `round ${table.round}`}</span>
      </div>
    </div>
  )
}
