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
