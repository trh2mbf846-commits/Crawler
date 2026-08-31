function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

interface HighlightProps {
  text: string
  query: string
}

export function Highlight({ text, query }: HighlightProps) {
  const trimmed = query.trim()
  if (!trimmed) return <>{text}</>

  const pattern = new RegExp(`(${escapeRegExp(trimmed)})`, 'ig')
  const parts = text.split(pattern)

  return (
    <>
      {parts.map((part, index) =>
        part.toLowerCase() === trimmed.toLowerCase() ? (
          <mark key={index} className="bg-amber-200 text-ink rounded-sm px-0.5">
            {part}
          </mark>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  )
}
