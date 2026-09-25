interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-center gap-2 py-4">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-sunken disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
      >
        Zurück
      </button>
      <span className="text-sm text-ink-muted">
        Seite {page} von {totalPages}
      </span>
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-sunken disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-40"
      >
        Weiter
      </button>
    </div>
  )
}
