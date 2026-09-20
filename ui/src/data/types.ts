/**
 * Types from CONTRACT.md, plus the engine-emitted extras the split screen renders when present.
 * Fields below marked `optional` are NOT in CONTRACT.md (frozen); real runs may omit them and the
 * UI renders a "—" instead. Never computed here, never written anywhere.
 */
export type PlayerId = 'p0' | 'p1' | 'p2' | 'p3' | 'p4'
export const PLAYER_IDS: readonly PlayerId[] = ['p0', 'p1', 'p2', 'p3', 'p4']
export type Role = 'wolf' | 'villager'
export type Winner = 'wolves' | 'villagers'
export type LieKind = 'deflect' | 'false_claim' | 'omit'
export type DeathCause = 'vote' | 'night' | null

export interface Turn {
  game_id: string
  round: number
  player_id: PlayerId
  model_name: string
  role: Role
  /** scratchpad, hidden from other players */
  private: string
  /** spoken statement. "" means the agent chose silence. Never null per contract. */
  public: string
  vote: PlayerId | null
  ts: string
  /** optional: not in CONTRACT.md */
  tokens_in?: number
  tokens_out?: number
  cost_usd?: number
}

export interface Score {
  game_id: string
  round: number
  player_id: PlayerId
  lied: boolean
  lie_kind: LieKind | null
  /** 0.0 - 1.0 */
  confidence: number
  /** optional. verbatim sentence from the player's scratchpad; null when lied is false */
  quote?: string | null
}

export interface Exploit {
  game_id: string
  round: number
  player_id: PlayerId
  tag: string
  description: string
  /** false = we did not anticipate this. these are the demo. */
  designed: boolean
  ts: string
}

export interface Game {
  game_id: string
  /** per player, aligned to p0..p4 */
  models: string[]
  roles: Record<PlayerId, Role>
  winner: Winner
  rounds: number
  ts: string
  /** optional: not in CONTRACT.md */
  trust?: unknown
  /** optional: not in CONTRACT.md. design/rules.md: {player_id: "vote" | "night" | null} */
  death_cause?: Partial<Record<PlayerId, DeathCause>>
}

// ---- engine-local event log (runs/<game_id>/events.jsonl) --------------------------------
// NOT a contract collection. The engine writes it next to turns.jsonl; the ui reads it, when it
// exists, for things the contract has no field for: who was living each day, the vote tally, the
// night chat between wolves, who was killed. Every consumer must render without it. Only the
// fields the ui reads are typed; `agent_reply` events (full prompts) are dropped at load.

interface EvBase {
  game_id: string
  round: number
  ts: string
}
export interface EvDayStart extends EvBase {
  type: 'day_start'
  order: PlayerId[]
  living: PlayerId[]
}
export interface EvTurn extends EvBase {
  type: 'turn'
  player_id: PlayerId
}
export interface EvDayResult extends EvBase {
  type: 'day_result'
  counts: Record<string, number>
  eliminated: PlayerId | null
  eliminated_role: Role | null
  reason: string
  living: PlayerId[]
}
export interface EvNightStart extends EvBase {
  type: 'night_start'
  wolves: PlayerId[]
  living: PlayerId[]
}
export interface EvNightTurn extends EvBase {
  type: 'night_turn'
  player_id: PlayerId
  /** the wolf's own scratchpad for the night */
  private: string
  /** what it said to its partner */
  message: string
  kill: PlayerId | null
}
export interface EvNightResult extends EvBase {
  type: 'night_result'
  killed: PlayerId | null
  killed_role: Role | null
  reason: string
  living: PlayerId[]
}
export interface EvGameEnd extends EvBase {
  type: 'game_end'
  winner: Winner
  rounds: number
  end_reason: string
}
export type EngineEvent = EvDayStart | EvTurn | EvDayResult | EvNightStart | EvNightTurn | EvNightResult | EvGameEnd
