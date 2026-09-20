/** Inline svg marks. No icon library, nothing fetched. All inherit `currentColor` unless noted. */

/** A pair of amber eyes in the dark: the wolf mark. Colour comes from css (.eyes). */
export function WolfEyes({ size = 22 }: { size?: number }) {
  return (
    <svg className="eyes" width={size} height={size * 0.5} viewBox="0 0 32 16" role="img" aria-label="wolf">
      <path d="M1 5 Q8 1.5 14 9 Q6 11.5 1 5 Z" />
      <path d="M31 5 Q24 1.5 18 9 Q26 11.5 31 5 Z" />
    </svg>
  )
}

export function Moon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M11.2 1.2a7 7 0 1 0 3.6 9.6A5.6 5.6 0 0 1 11.2 1.2Z" fill="currentColor" />
    </svg>
  )
}

export function Sun({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="8" cy="8" r="3.4" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round">
        <path d="M8 .8v2M8 13.2v2M.8 8h2M13.2 8h2M2.9 2.9l1.4 1.4M11.7 11.7l1.4 1.4M2.9 13.1l1.4-1.4M11.7 4.3l1.4-1.4" />
      </g>
    </svg>
  )
}

export function Ballot({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" aria-hidden="true">
      <rect x="1.5" y="1.5" width="11" height="11" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path d="M4 7.2l2.1 2.1L10.2 5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Flag({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" aria-hidden="true">
      <path d="M3 13V1.5M3 2h8l-2 2.75L11 7.5H3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
