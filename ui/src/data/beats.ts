/**
 * Beats: the ordered list of things the stage shows one at a time.
 *
 *   turn        one Turn record joined to its Score (contract data)
 *   day_result  the vote tally and who was eliminated        (engine events.jsonl, optional)
 *   night       the wolves' night chat and who was killed    (engine events.jsonl, optional)
 *   end         the winner                                   (game.json, or the game_end event)
 *
 * With no events file the list is just the turns plus an end beat, and everything still renders.
 * Nothing here judges anything: no lie is derived, scores are only carried along.
 */
import type { Row } from './source'
import { PLAYER_IDS, type EngineEvent, type EvDayResult, type EvNightResult, type EvNightTurn, type Game, type PlayerId, type Winner } from './types'

export interface TurnBeat {
  kind: 'turn'
  key: string
  round: number
  row: Row
  rowIdx: number
}
export interface DayResultBeat {
  kind: 'day_result'
  key: string
  round: number
  ev: EvDayResult
}
export interface NightBeat {
  kind: 'night'
  key: string
  round: number
  wolves: PlayerId[]
  chat: EvNightTurn[]
  /** null while the wolves are still choosing (live game) */
  result: EvNightResult | null
}
export interface EndBeat {
  kind: 'end'
  key: string
  round: number
  winner: Winner
  endReason: string | null
}
export type Beat = TurnBeat | DayResultBeat | NightBeat | EndBeat

export function buildBeats(rows: Row[], events: EngineEvent[] | null, game: Game | null): Beat[] {
  const beats: Beat[] = []
  const used = new Set<number>()
  const idxOf = new Map<string, number>()
  rows.forEach((r, i) => {
    const k = `${r.turn.round}|${r.turn.player_id}`
    if (!idxOf.has(k)) idxOf.set(k, i)
  })
  const turnBeat = (i: number): TurnBeat => ({
    kind: 'turn',
    key: `t|${rows[i].turn.round}|${rows[i].turn.player_id}|${rows[i].turn.ts}`,
    round: rows[i].turn.round,
    row: rows[i],
    rowIdx: i,
  })

  let ended = false
  if (events) {
    let night: NightBeat | null = null
    for (const ev of events) {
      switch (ev.type) {
        case 'turn': {
          const i = idxOf.get(`${ev.round}|${ev.player_id}`)
          if (i !== undefined && !used.has(i)) {
            used.add(i)
            beats.push(turnBeat(i))
          }
          break
        }
        case 'day_result':
          beats.push({ kind: 'day_result', key: `d|${ev.round}`, round: ev.round, ev })
          break
        case 'night_start':
          night = { kind: 'night', key: `n|${ev.round}`, round: ev.round, wolves: ev.wolves ?? [], chat: [], result: null }
          beats.push(night)
          break
        case 'night_turn':
          if (night && night.round === ev.round) night.chat.push(ev)
          break
        case 'night_result':
          if (night && night.round === ev.round) night.result = ev
          else beats.push({ kind: 'night', key: `n|${ev.round}`, round: ev.round, wolves: [], chat: [], result: ev })
          night = null
          break
        case 'game_end':
          ended = true
          beats.push({ kind: 'end', key: 'end', round: ev.round, winner: ev.winner, endReason: ev.end_reason ?? null })
          break
        default:
          break
      }
    }
  }

  // turns the event log has not caught up with yet (or every turn, when there is no log)
  rows.forEach((r, i) => {
    if (used.has(i)) return
    const at = beats.findIndex((b) => b.kind === 'end' || b.round > r.turn.round || (b.round === r.turn.round && b.kind !== 'turn'))
    if (at < 0) beats.push(turnBeat(i))
    else beats.splice(at, 0, turnBeat(i))
  })

  if (!ended && game) beats.push({ kind: 'end', key: 'end', round: game.rounds, winner: game.winner, endReason: null })
  return beats
}

// ---- table state at a beat ------------------------------------------------------------------

export interface Death {
  cause: 'vote' | 'night' | 'unknown'
  round: number
}

export interface TableState {
  round: number
  phase: 'day' | 'night' | 'ended'
  speaker: PlayerId | null
  /** votes cast so far in the current day, in speaking order. null target = named no one */
  votes: { from: PlayerId; to: PlayerId | null }[]
  /** votes received so far in the current day */
  tally: Partial<Record<PlayerId, number>>
  deaths: Map<PlayerId, Death>
  /** turns so far that the scorer marked lied, per player. a count of rows, nothing more */
  lies: Partial<Record<PlayerId, number>>
  /** players with a turn this day, so a seat can say "yet to speak" */
  spoke: Set<PlayerId>
}

/** Everything the seats need, read off beats[0..at]. `hideCurrentScore` keeps blind mode honest. */
export function tableAt(beats: Beat[], at: number, game: Game | null, hideCurrentScore: boolean): TableState {
  const cur = beats[at]
  const st: TableState = {
    round: cur?.round ?? 0,
    phase: cur?.kind === 'night' ? 'night' : cur?.kind === 'end' ? 'ended' : 'day',
    speaker: cur?.kind === 'turn' ? cur.row.turn.player_id : null,
    votes: [],
    tally: {},
    deaths: new Map(),
    lies: {},
    spoke: new Set(),
  }
  if (!cur) return st
  const hasLog = beats.some((b) => b.kind === 'day_result' || b.kind === 'night')

  for (let i = 0; i <= at; i++) {
    const b = beats[i]
    if (b.kind === 'turn') {
      const { turn, score } = b.row
      if (score?.lied === true && !(hideCurrentScore && i === at)) st.lies[turn.player_id] = (st.lies[turn.player_id] ?? 0) + 1
      if (b.round === cur.round && cur.kind !== 'night' && cur.kind !== 'end') {
        st.spoke.add(turn.player_id)
        st.votes.push({ from: turn.player_id, to: turn.vote })
        if (turn.vote) st.tally[turn.vote] = (st.tally[turn.vote] ?? 0) + 1
      }
    } else if (b.kind === 'day_result' && b.ev.eliminated) {
      st.deaths.set(b.ev.eliminated, { cause: 'vote', round: b.round })
    } else if (b.kind === 'night' && b.result?.killed) {
      st.deaths.set(b.result.killed, { cause: 'night', round: b.round })
    }
  }

  // no event log: a player with no turn this round or later is out. cause only if game.json says so.
  if (!hasLog) {
    const last: Partial<Record<PlayerId, number>> = {}
    for (const b of beats) if (b.kind === 'turn') last[b.row.turn.player_id] = Math.max(last[b.row.turn.player_id] ?? 0, b.round)
    for (const pid of PLAYER_IDS) {
      const lr = last[pid]
      if (lr === undefined || lr >= cur.round) continue
      const dc = game?.death_cause?.[pid]
      st.deaths.set(pid, { cause: dc === 'vote' || dc === 'night' ? dc : 'unknown', round: lr })
    }
  }
  return st
}

/** Where an earlier-day quote sits: the scorer may quote the same player's scratchpad from a previous day. */
export function findQuoteRound(rows: Row[], uptoIdx: number, pid: PlayerId, quote: string): number | null {
  for (let i = uptoIdx - 1; i >= 0; i--) {
    const t = rows[i].turn
    if (t.player_id === pid && t.private.includes(quote)) return t.round
  }
  return null
}
