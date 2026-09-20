import type { Ref } from 'react'

/**
 * Marks Score.quote inside a scratchpad. Case-sensitive, first occurrence only. Not found -> plain
 * text, never throws. `markRef` lets the stage find the mark on screen to anchor the thread to it.
 */
export function Highlight({ text, quote, markRef }: { text: string; quote: string | null | undefined; markRef?: Ref<HTMLElement> }) {
  if (!quote) return <>{text}</>
  const i = text.indexOf(quote)
  if (i < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, i)}
      <mark className="quote" ref={markRef}>
        {text.slice(i, i + quote.length)}
      </mark>
      {text.slice(i + quote.length)}
    </>
  )
}
