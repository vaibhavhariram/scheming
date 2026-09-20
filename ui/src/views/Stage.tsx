/**
 * The stage. One beat at a time, split down the middle the way the game is:
 *
 *   left, night   what the agent wrote to itself. no other player sees it.
 *   right, day    what it said to the table.
 *
 * On a scored lie the quoted scratchpad line (Score.quote) is marked, a thread runs from it to the
 * seam, the seam turns red down to the verdict plate. At night the day side goes dark. Everything
 * shown is a Turn, a Score, a Game, an Exploit count, or an engine event; nothing is derived.
 */
import { useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { Highlight } from '../components/Highlight'
import { Moon, WolfEyes } from '../components/Glyphs'
import { fmtUsd, plural, shortModel } from '../components/names'
import { Verdict } from '../components/Verdict'
import { findQuoteRound, type Beat, type DayResultBeat, type EndBeat, type NightBeat, type TableState, type TurnBeat } from '../data/beats'
import type { Row } from '../data/source'
import { PLAYER_IDS, type Exploit, type Game, type PlayerId, type Role } from '../data/types'

const NIGHT_SIZES = [25, 23, 21, 20, 19, 18, 17, 16, 15, 14, 13]
const DAY_SIZES = [54, 48, 43, 39, 35, 32, 29, 27, 25, 23, 21, 19, 18]

/** largest size in `sizes` at which the element's text fits its box; smallest otherwise (then it scrolls) */
function fit(el: HTMLElement | null, sizes: number[]) {
  if (!el) return
  for (const s of sizes) {
    el.style.fontSize = `${s}px`
    if (el.scrollHeight <= el.clientHeight + 1) return
  }
}

/** re-run `layout` when the stage resizes or the webfonts land (metrics change) */
function useRelayout(root: RefObject<HTMLElement | null>, layout: () => void, deps: unknown[]) {
  useLayoutEffect(() => {
    layout()
    const el = root.current
    if (!el) return
    const ro = new ResizeObserver(layout)
    ro.observe(el)
    let live = true
    void document.fonts?.ready.then(() => live && layout())
    return () => {
      live = false
      ro.disconnect()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

export type SeenMap = Partial<Record<PlayerId, { role: Role; model: string }>>

interface StageProps {
  beat: Beat
  rows: Row[]
  game: Game | null
  table: TableState
  seen: SeenMap
  exploits: Exploit[]
  blind: boolean
  revealed: boolean
  hideRoles: boolean
  onReveal: () => void
  onRestart: () => void
  onExploits: () => void
}

export function Stage(p: StageProps) {
  switch (p.beat.kind) {
    case 'turn':
      return <TurnStage key={p.beat.key} {...p} beat={p.beat} />
    case 'day_result':
      return <DayResultStage key={p.beat.key} beat={p.beat} table={p.table} game={p.game} seen={p.seen} hideRoles={p.hideRoles} />
    case 'night':
      return <NightStage key={p.beat.key} beat={p.beat} hideRoles={p.hideRoles} />
    case 'end':
      return <EndStage key={p.beat.key} beat={p.beat} rows={p.rows} game={p.game} table={p.table} seen={p.seen} exploits={p.exploits} onRestart={p.onRestart} onExploits={p.onExploits} />
  }
}

function Who({ pid, role, showRole }: { pid: PlayerId; role: Role | undefined; showRole: boolean }) {
  return (
    <span className="who-pid">
      <span className="pid">{pid}</span>
      {showRole && role === 'wolf' && <WolfEyes size={30} />}
    </span>
  )
}

// ---- a turn -----------------------------------------------------------------------------------

interface Thread {
  x: number
  y: number
  w: number
  drop: number
}

function TurnStage({ beat, rows, blind, revealed, hideRoles, onReveal }: StageProps & { beat: TurnBeat }) {
  const { turn, score } = beat.row
  const concealed = blind && !revealed
  const lied = !concealed && score?.lied === true
  const quote = lied ? (score?.quote ?? null) : null
  const inTurn = quote !== null && turn.private.includes(quote)
  const earlierRound = quote !== null && !inTurn ? findQuoteRound(rows, beat.rowIdx, turn.player_id, quote) : null

  const root = useRef<HTMLElement | null>(null)
  const scratch = useRef<HTMLDivElement | null>(null)
  const statement = useRef<HTMLDivElement | null>(null)
  const mark = useRef<HTMLElement | null>(null)
  const seam = useRef<HTMLDivElement | null>(null)
  const plate = useRef<HTMLDivElement | null>(null)
  const [thread, setThread] = useState<Thread | null>(null)
  const nudged = useRef(false) // the quote is scrolled into view once per beat, then the reader owns the scroll

  const layout = () => {
    fit(scratch.current, NIGHT_SIZES)
    fit(statement.current, DAY_SIZES)
    // a scratchpad too long for even the smallest size scrolls: start it where the quoted line is visible
    const sb = scratch.current
    const mk = mark.current
    if (sb && mk && sb.contains(mk) && !nudged.current && sb.scrollHeight > sb.clientHeight + 1) {
      nudged.current = true
      const mr = mk.getClientRects()
      const br = sb.getBoundingClientRect()
      const bottom = mr.length ? mr[mr.length - 1].bottom : 0
      if (bottom > br.bottom - 10) sb.scrollTop += bottom - br.bottom + 14
    }
    const r = root.current
    const m = mark.current
    const s = seam.current
    const pl = plate.current
    if (!r || !m || !s || !pl) return setThread(null)
    const rects = m.getClientRects()
    if (!rects.length) return setThread(null)
    const last = rects[rects.length - 1]
    // run the thread under the mark's last line, in the gap between text lines, so it never strikes
    // through whatever follows the quote on that line
    const y = last.bottom + 3
    const box = scratch.current
    if (box && box.contains(m)) {
      const b = box.getBoundingClientRect()
      if (y < b.top || y > b.bottom) return setThread(null) // marked line is scrolled out of the pane
    }
    const rr = r.getBoundingClientRect()
    const sr = s.getBoundingClientRect()
    const x = last.left
    const next = { x: x - rr.left, y: y - rr.top, w: Math.max(0, sr.left + sr.width / 2 - x), drop: Math.max(0, pl.getBoundingClientRect().top - y) }
    setThread((prev) => (prev && Math.abs(prev.x - next.x) < 0.5 && Math.abs(prev.y - next.y) < 0.5 && Math.abs(prev.w - next.w) < 0.5 && Math.abs(prev.drop - next.drop) < 0.5 ? prev : next))
  }
  useRelayout(root, layout, [beat.key, concealed, quote])

  const showRole = !hideRoles && !concealed // blind mode: the role is the spoiler, keep it until the reveal
  const hasUsage = typeof turn.tokens_in === 'number' || typeof turn.tokens_out === 'number' || typeof turn.cost_usd === 'number'

  return (
    // the entrance animations translate the scratchpad and the plate while they play, so anything
    // measured mid-flight is off by that much: measure again whenever one of them lands
    <section className={`stage turn${lied ? ' is-lie' : ''}`} ref={root} aria-label={`day ${turn.round}, ${turn.player_id}`} onAnimationEnd={layout}>
      <div className="pane night">
        <header className="pane-head in in-1">
          <h2>
            <Who pid={turn.player_id} role={turn.role} showRole={showRole} />
            <span className="to">to itself</span>
          </h2>
          <p className="pane-note">
            private scratchpad. no other player sees this.
            <span className="model" title={turn.model_name}>
              {shortModel(turn.model_name)}
              {showRole ? `, ${turn.role}` : ''}
            </span>
          </p>
        </header>
        {concealed ? (
          <button type="button" className="veil in in-1" onClick={onReveal}>
            <span className="veil-h">one-way glass</span>
            <span className="veil-p">
              the statement on the right is all the other players get. press <kbd>r</kbd> to read what {turn.player_id} wrote to itself.
            </span>
          </button>
        ) : (
          <>
            <div className="scratch in in-1" ref={scratch} onScroll={layout} tabIndex={0}>
              <Highlight text={turn.private} quote={quote} markRef={inTurn ? mark : undefined} />
            </div>
            {quote !== null && !inTurn && (
              <p className="earlier in in-3">
                <span className="earlier-h">{earlierRound !== null ? `what it wrote on day ${earlierRound}` : 'what it wrote earlier'}</span>
                <mark className="quote" ref={mark}>
                  {quote}
                </mark>
              </p>
            )}
          </>
        )}
        {hasUsage && (
          <p className="usage">
            {typeof turn.tokens_in === 'number' && <span>{turn.tokens_in.toLocaleString()} tokens in</span>}
            {typeof turn.tokens_out === 'number' && <span>{turn.tokens_out.toLocaleString()} out</span>}
            {typeof turn.cost_usd === 'number' && <span>{fmtUsd(turn.cost_usd)}</span>}
          </p>
        )}
      </div>

      <div className="seam" ref={seam} aria-hidden="true" />

      <div className="pane day">
        <header className="pane-head in in-2">
          <h2>
            <span className="who-pid">
              <span className="pid">{turn.player_id}</span>
            </span>
            <span className="to">to the table</span>
          </h2>
          <p className="pane-note">public statement. everyone hears this.</p>
        </header>
        <div className="statement in in-2" ref={statement} tabIndex={0}>
          {turn.public === '' ? <span className="silence">said nothing.</span> : turn.public}
        </div>
        <p className="ballot in in-2">{turn.vote !== null ? <>votes to eliminate <b>{turn.vote}</b></> : 'names no one'}</p>
      </div>

      {thread && lied && (
        <>
          <span className="thread-h in-thread" style={{ left: thread.x, top: thread.y, width: thread.w }} aria-hidden="true" />
          <span className="thread-v in-thread" style={{ left: thread.x + thread.w, top: thread.y, height: thread.drop }} aria-hidden="true" />
        </>
      )}
      <div className="plate-slot in in-3">
        <Verdict score={score} hidden={concealed} plateRef={plate} />
      </div>
    </section>
  )
}

// ---- the vote -----------------------------------------------------------------------------------

function DayResultStage({ beat, table, game, seen, hideRoles }: { beat: DayResultBeat; table: TableState; game: Game | null; seen: SeenMap; hideRoles: boolean }) {
  const { ev } = beat
  const counts = Object.entries(ev.counts ?? {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const max = counts.reduce((m, [, n]) => Math.max(m, n), 0)
  const roleOf = (pid: PlayerId) => game?.roles?.[pid] ?? seen[pid]?.role
  let outcome: ReactNode
  if (ev.eliminated) {
    outcome = (
      <>
        {ev.eliminated} is voted out.
        {ev.eliminated_role && <span className="outcome-sub">{ev.eliminated} was a {ev.eliminated_role}.</span>}
      </>
    )
  } else if (ev.reason === 'tie') {
    outcome = <>tie. nobody is eliminated.</>
  } else {
    outcome = <>nobody is eliminated.</>
  }
  return (
    <section className="stage result" aria-label={`day ${beat.round} vote`}>
      <div className="pane night">
        <header className="pane-head in in-1">
          <h2>
            <span className="to lead">who voted for whom</span>
          </h2>
          <p className="pane-note">{hideRoles ? 'roles are hidden.' : 'the players never see each other’s roles. you do.'}</p>
        </header>
        <ul className="votelist in in-1">
          {table.votes.map((v) => (
            <li key={v.from}>
              <Who pid={v.from} role={roleOf(v.from)} showRole={!hideRoles} />
              <span className="arrow" aria-hidden="true" />
              {v.to ? <Who pid={v.to} role={roleOf(v.to)} showRole={!hideRoles} /> : <span className="nobody">no one</span>}
            </li>
          ))}
        </ul>
      </div>
      <div className="seam" aria-hidden="true" />
      <div className="pane day">
        <header className="pane-head in in-2">
          <h2>
            <span className="to lead">day {beat.round} vote</span>
          </h2>
          <p className="pane-note">what the table sees.</p>
        </header>
        <div className="tally in in-2">
          {counts.length === 0 && <p className="tally-none">no votes were cast.</p>}
          {counts.map(([pid, n]) => (
            <div className={pid === ev.eliminated ? 'tally-row out' : 'tally-row'} key={pid}>
              <span className="pid">{pid}</span>
              <span className="tally-bar">
                <span style={{ width: `${max ? (n / max) * 100 : 0}%` }} />
              </span>
              <span className="tally-n">{n}</span>
            </div>
          ))}
        </div>
        <p className="outcome in in-3">{outcome}</p>
      </div>
    </section>
  )
}

// ---- the night ----------------------------------------------------------------------------------

function NightStage({ beat, hideRoles }: { beat: NightBeat; hideRoles: boolean }) {
  const root = useRef<HTMLElement | null>(null)
  const left = useRef<HTMLDivElement | null>(null)
  const right = useRef<HTMLDivElement | null>(null)
  useRelayout(
    root,
    () => {
      fit(left.current, [22, 20, 19, 18, 17, 16, 15, 14])
      fit(right.current, [34, 31, 28, 26, 24, 22, 20, 18])
    },
    [beat.key, beat.chat.length, beat.result?.killed],
  )
  const killed = beat.result?.killed ?? null
  return (
    <section className="stage nightfall" ref={root} aria-label={`night ${beat.round}`}>
      <div className="pane night">
        <header className="pane-head in in-1">
          <h2>
            <span className="to lead">the wolves, to themselves</span>
          </h2>
          <p className="pane-note">night scratchpads, from the engine log. not scored.</p>
        </header>
        <div className="nightpads in in-1" ref={left} tabIndex={0}>
          {beat.chat.length === 0 && <p className="dim">{hideRoles ? 'roles are hidden.' : 'nothing logged for this night.'}</p>}
          {!hideRoles &&
            beat.chat.map((c, i) => (
              <div className="nightpad" key={`${c.player_id}-${i}`}>
                <Who pid={c.player_id} role="wolf" showRole />
                <p>{c.private}</p>
              </div>
            ))}
        </div>
      </div>
      <div className="seam" aria-hidden="true" />
      <div className="pane day dark">
        <header className="pane-head in in-2">
          <h2>
            <span className="moon">
              <Moon size={26} />
            </span>
            <span className="to lead">night {beat.round}. the table is asleep.</span>
          </h2>
          <p className="pane-note">{hideRoles ? 'someone is awake.' : 'what the wolves said to each other.'}</p>
        </header>
        <div className="whispers in in-2" ref={right} tabIndex={0}>
          {!hideRoles &&
            beat.chat.map((c, i) => (
              <p className="whisper" key={`${c.player_id}-${i}`}>
                <span className="pid">{c.player_id}</span>
                {c.message}
                {c.kill && <span className="pick">picks {c.kill}</span>}
              </p>
            ))}
        </div>
        <p className="outcome in in-3">
          {beat.result === null ? (
            <>the wolves are choosing.</>
          ) : killed ? (
            <>
              {killed} is killed.
              {beat.result.killed_role && <span className="outcome-sub">{killed} was a {beat.result.killed_role}.</span>}
            </>
          ) : (
            <>nobody dies tonight.</>
          )}
        </p>
      </div>
    </section>
  )
}

// ---- the end ------------------------------------------------------------------------------------

function EndStage({ beat, rows, game, table, seen, exploits, onRestart, onExploits }: { beat: EndBeat; rows: Row[]; game: Game | null; table: TableState; seen: SeenMap; exploits: Exploit[]; onRestart: () => void; onExploits: () => void }) {
  const scored = rows.filter((r) => r.score !== null).length
  const lies = rows.filter((r) => r.score?.lied === true).length
  const undesigned = exploits.filter((x) => !x.designed).length
  const cost = rows.reduce((s, r) => s + (r.turn.cost_usd ?? 0), 0)
  const hasCost = rows.some((r) => typeof r.turn.cost_usd === 'number')
  return (
    <section className={`stage end ${beat.winner}`} aria-label="game over">
      <div className="end-inner in in-1">
        <h2 className="end-title">{beat.winner === 'wolves' ? 'the wolves win.' : 'the village wins.'}</h2>
        <p className="end-sub">
          {plural(beat.round, 'round')}, {plural(rows.length, 'turn')}
          {beat.endReason === 'max_rounds' ? ', stopped at the round cap' : ''}.
        </p>
        <ul className="end-roles">
          {PLAYER_IDS.map((pid, i) => {
            const role = game?.roles?.[pid] ?? seen[pid]?.role
            const d = table.deaths.get(pid)
            return (
              <li key={pid} className={d ? 'dead' : ''}>
                <Who pid={pid} role={role} showRole />
                <span className="end-role">{role ?? ''}</span>
                <span className="end-model">{shortModel(game?.models?.[i] ?? seen[pid]?.model ?? '')}</span>
                <span className="end-fate">{d ? (d.cause === 'night' ? `killed, night ${d.round}` : d.cause === 'vote' ? `voted out, day ${d.round}` : 'out') : 'survived'}</span>
              </li>
            )
          })}
        </ul>
        <dl className="end-stats">
          <div>
            <dt>scored lies</dt>
            <dd className={lies ? 'hot' : ''}>{scored ? lies : '—'}</dd>
            <dd className="of">{scored ? `of ${plural(scored, 'scored turn')}` : 'not scored yet'}</dd>
          </div>
          <div>
            <dt>exploits in this game</dt>
            <dd className={undesigned ? 'hot' : ''}>{exploits.length}</dd>
            <dd className="of">{undesigned ? `${undesigned} we did not design` : exploits.length ? 'all designed traps' : 'none logged'}</dd>
          </div>
          {hasCost && (
            <div>
              <dt>cost of this game</dt>
              <dd>{fmtUsd(cost)}</dd>
              <dd className="of">model calls, all five players</dd>
            </div>
          )}
        </dl>
        <div className="end-actions">
          <button type="button" className="btn" onClick={onRestart}>
            replay from the start
          </button>
          <button type="button" className="btn ghost" onClick={onExploits}>
            see the exploits
          </button>
        </div>
      </div>
    </section>
  )
}
