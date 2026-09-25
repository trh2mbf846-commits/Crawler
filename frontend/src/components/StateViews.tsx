interface MessageViewProps {
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}

export function LoadingView({ label = 'Lade Daten…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 rounded-lg border border-line bg-surface py-16 text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-brand" aria-hidden />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorView({ title, description, action }: MessageViewProps) {
  return (
    <div className="rounded-lg border border-urgent-redBg bg-urgent-redBg/40 px-6 py-10 text-center">
      <p className="text-sm font-semibold text-urgent-red">{title}</p>
      {description ? <p className="mx-auto mt-1 max-w-md text-sm text-ink-muted">{description}</p> : null}
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="focus-ring mt-4 rounded-md border border-urgent-red/30 bg-surface px-4 py-1.5 text-sm font-medium text-urgent-red hover:bg-urgent-redBg"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  )
}

export function EmptyView({ title, description, action }: MessageViewProps) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface px-6 py-14 text-center">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description ? <p className="mx-auto mt-1 max-w-md text-sm text-ink-muted">{description}</p> : null}
      {action ? (
        <button
          type="button"
          onClick={action.onClick}
          className="focus-ring mt-4 rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand/90"
        >
          {action.label}
        </button>
      ) : null}
    </div>
  )
}
