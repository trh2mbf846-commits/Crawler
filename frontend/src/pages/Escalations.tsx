import { useCallback, useState } from 'react'
import { ApiError, fetchEscalations, resolveEscalation } from '../api/client'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { useAsync } from '../hooks/useAsync'
import type { Escalation, EscalationStatus } from '../api/types'
import { formatDateTime } from '../utils/format'
import { escalationKategorieLabel } from '../utils/tender'

const statusTabs: { value: EscalationStatus | 'alle'; label: string }[] = [
  { value: 'offen', label: 'Offen' },
  { value: 'beantwortet', label: 'Beantwortet' },
  { value: 'geparkt', label: 'Geparkt' },
  { value: 'alle', label: 'Alle' },
]

function EscalationCard({ escalation, onResolved }: { escalation: Escalation; onResolved: (updated: Escalation) => void }) {
  const [selectedOption, setSelectedOption] = useState('')
  const [freitext, setFreitext] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isOpen = escalation.status === 'offen'
  const decision = selectedOption || freitext.trim()

  const submit = useCallback(async () => {
    if (!decision) return
    setSubmitting(true)
    setError(null)
    try {
      const updated = await resolveEscalation(escalation.id, decision)
      onResolved(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Entscheidung konnte nicht gespeichert werden.')
    } finally {
      setSubmitting(false)
    }
  }, [decision, escalation.id, onResolved])

  return (
    <div className="rounded-lg border border-line bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="inline-flex items-center rounded-full bg-surface-sunken px-2.5 py-1 text-xs font-medium text-ink-muted">
          {escalationKategorieLabel[escalation.kategorie]}
        </span>
        <span className="text-xs text-ink-faint">{formatDateTime(escalation.erstellt_am)}</span>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-ink">{escalation.kontext}</p>

      {escalation.empfehlung ? (
        <p className="mt-3 rounded-md bg-brand-light px-3 py-2 text-sm text-brand">
          <span className="font-semibold">Empfehlung:</span> {escalation.empfehlung}
        </p>
      ) : null}

      {isOpen ? (
        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
          {escalation.optionen.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {escalation.optionen.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    setSelectedOption(option)
                    setFreitext('')
                  }}
                  className={`focus-ring rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    selectedOption === option ? 'border-brand bg-brand-light text-brand' : 'border-line text-ink-muted hover:bg-surface-sunken'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          ) : null}

          <textarea
            value={freitext}
            onChange={(event) => {
              setFreitext(event.target.value)
              setSelectedOption('')
            }}
            placeholder="Eigene Entscheidung als Freitext…"
            rows={2}
            className="focus-ring w-full resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
          />

          {error ? <p className="text-xs text-urgent-red">{error}</p> : null}

          <div>
            <button
              type="button"
              disabled={!decision || submitting}
              onClick={() => void submit()}
              className="focus-ring rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? 'Speichert…' : 'Entscheidung übernehmen'}
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 rounded-md bg-surface-sunken px-3 py-2 text-sm text-ink-muted">
          <span className="font-medium text-ink">Entscheidung:</span> {escalation.entscheidung ?? '–'}
          {escalation.beantwortet_am ? <span className="ml-2 text-xs text-ink-faint">({formatDateTime(escalation.beantwortet_am)})</span> : null}
        </div>
      )}
    </div>
  )
}

export function Escalations() {
  const [tab, setTab] = useState<EscalationStatus | 'alle'>('offen')
  const fetcher = useCallback(() => fetchEscalations(tab === 'alle' ? undefined : tab), [tab])
  const { data, loading, error, reload } = useAsync(fetcher, [fetcher])
  const [overrides, setOverrides] = useState<Record<string, Escalation>>({})

  const items = (data ?? []).map((item) => overrides[item.id] ?? item)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Entscheidungs-Posteingang</h1>
        <p className="mt-0.5 text-sm text-ink-muted">Eskalationen aus der Crawler-Pipeline, die eine manuelle Entscheidung benötigen.</p>
      </div>

      <div className="flex gap-1 border-b border-line">
        {statusTabs.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            className={`focus-ring -mb-px rounded-t-md border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === item.value ? 'border-brand text-brand' : 'border-transparent text-ink-muted hover:text-ink'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? <LoadingView label="Lade Eskalationen…" /> : null}
      {!loading && error ? (
        <ErrorView title="Eskalationen konnten nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyView title="Keine Eskalationen" description="In dieser Kategorie liegen aktuell keine Einträge vor." />
      ) : null}

      {!loading && !error && items.length > 0 ? (
        <div className="flex flex-col gap-4">
          {items.map((escalation) => (
            <EscalationCard
              key={escalation.id}
              escalation={escalation}
              onResolved={(updated) => setOverrides((prev) => ({ ...prev, [updated.id]: updated }))}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}
