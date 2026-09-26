import { Link } from 'react-router-dom'
import { FRISTEN_ICS_URL, fetchFristen } from '../api/client'
import type { Frist } from '../api/types'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { useAsync } from '../hooks/useAsync'
import { formatDateTime } from '../utils/format'

// Fristen-Kalender (26.09.2026): alle Angebots- und Fragenfristen der Ausschreibungen, an denen du
// arbeitest (gemerkt, bewertet oder mit Checkliste) - plus Export für den Mac-Kalender.

function tageBis(datum: string): number {
  const ms = new Date(datum).getTime() - Date.now()
  return Math.ceil(ms / 86_400_000)
}

function Dringlichkeit({ tage }: { tage: number }) {
  const klasse =
    tage <= 3 ? 'bg-urgent-redBg text-urgent-red' : tage <= 7 ? 'bg-urgent-yellowBg text-urgent-yellow' : 'bg-surface-sunken text-ink-muted'
  const text = tage < 0 ? 'vorbei' : tage === 0 ? 'heute' : tage === 1 ? 'morgen' : `in ${tage} Tagen`
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${klasse}`}>{text}</span>
}

function wocheVon(datum: string): string {
  const tage = tageBis(datum)
  if (tage <= 7) return 'Diese Woche'
  if (tage <= 14) return 'Nächste Woche'
  if (tage <= 31) return 'In den nächsten 4 Wochen'
  return 'Später'
}

export function Fristen() {
  const { data, loading, error, reload } = useAsync(() => fetchFristen(120), [])

  if (loading) return <LoadingView label="Lade Fristen…" />
  if (error) return <ErrorView title="Fristen konnten nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />

  const gruppen = new Map<string, Frist[]>()
  for (const frist of data ?? []) {
    const g = wocheVon(frist.datum)
    gruppen.set(g, [...(gruppen.get(g) ?? []), frist])
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Fristen</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Angebots- und Fragenfristen aller Ausschreibungen, an denen du arbeitest – gemerkt (★), von Kevin bewertet oder
            mit Checkliste.
          </p>
        </div>
        <a
          href={FRISTEN_ICS_URL}
          className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink"
          title="Lädt eine Kalenderdatei; per Doppelklick in den Mac-Kalender übernehmen (mit Erinnerung 3 Tage vorher)"
        >
          📅 In Kalender übernehmen (.ics)
        </a>
      </div>

      {!data?.length ? (
        <EmptyView
          title="Keine anstehenden Fristen"
          description="Merk dir Ausschreibungen (★) oder lass sie von Kevin bewerten – dann erscheinen ihre Fristen hier."
        />
      ) : (
        [...gruppen.entries()].map(([gruppe, fristen]) => (
          <section key={gruppe} className="rounded-lg border border-line bg-surface p-4 shadow-card">
            <h2 className="mb-2 text-sm font-semibold text-ink">{gruppe}</h2>
            <ul className="flex flex-col divide-y divide-line">
              {fristen.map((f) => (
                <li key={`${f.tender_id}-${f.art}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <Link to={`/tenders/${f.tender_id}`} className="focus-ring text-sm font-medium text-ink hover:text-brand hover:underline">
                      {f.titel}
                    </Link>
                    <p className="text-xs text-ink-muted">
                      {f.art} · {formatDateTime(f.datum)}
                      {f.vergabestelle ? ` · ${f.vergabestelle}` : ''} · {f.grund}
                    </p>
                  </div>
                  <Dringlichkeit tage={tageBis(f.datum)} />
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
