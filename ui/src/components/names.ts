import type { LieKind } from '../data/types'

/** `meta-llama/Llama-3.1-8B-Instruct` -> `Llama-3.1-8B-Instruct`. display only; the full id stays in the title attr. */
export function shortModel(id: string): string {
  const cut = id.lastIndexOf('/')
  return cut >= 0 && cut < id.length - 1 ? id.slice(cut + 1) : id
}

/** display words for the contract's lie_kind values */
export const LIE_KIND_WORDS: Record<LieKind, string> = {
  deflect: 'deflection',
  false_claim: 'false claim',
  omit: 'omission',
}

export function fmtUsd(n: number): string {
  return n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}
