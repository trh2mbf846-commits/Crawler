import { useState } from 'react'
import type { PortalHealth } from '../api/types'
import { AmpelDot } from './Badges'

export function SourcesSummary({ portals }: { portals: PortalHealth[] }) {
  const [open, setOpen] = useState(false)

  if (portals.length === 0) return null

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-ink-muted hover:border-brand hover:text-ink"
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        aria-expanded={open}
      >
        {portals.length} Quellen
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>

      {open ? (
        <div className="absolute left-0 top-full z-30 mt-2 w-80 rounded-lg border border-line bg-surface p-3 shadow-lg">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">Alle konfigurierten Quellen</p>
          <ul className="flex flex-col gap-1.5">
            {portals.map((portal) => (
              <li key={portal.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="truncate text-ink-muted" title={portal.name}>
                  {portal.name}
                </span>
                <AmpelDot status={portal.status_ampel} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
