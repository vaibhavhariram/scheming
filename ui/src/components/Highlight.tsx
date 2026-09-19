/** Case-sensitive, first occurrence only. Not found -> plain text, never throws. */
export function Highlight({ text, quote }: { text: string; quote: string | null | undefined }) {
  if (!quote) return <>{text}</>
  const i = text.indexOf(quote)
  if (i < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, i)}
      <mark className="quote">{text.slice(i, i + quote.length)}</mark>
      {text.slice(i + quote.length)}
    </>
  )
}
