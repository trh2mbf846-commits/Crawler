import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchTender, fetchTenderHistory } from '../api/client'
import { KiBadge, PortalBadge, StatusBadge, UrgencyBadge } from '../components/Badges'
import { RankingBars } from '../components/RankingBars'
import { ErrorView, LoadingView } from '../components/StateViews'
import { Timeline } from '../components/Timeline'
import { useAsync } from '../hooks/useAsync'
import { formatCurrency, formatDate, formatDateTime } from '../utils/format'
import { zugangsartLabel } from '../utils/tender'

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink">{value}</dd>
    </div>
  )
}

export function TenderDetailPage() {
  const { id = '' } = useParams<{ id: string }>()

  const tenderFetcher = useCallback(() => fetchTender(id), [id])
  const historyFetcher = useCallback(() => fetchTenderHistory(id), [id])

  const { data: tender, loading, error, reload } = useAsync(tenderFetcher, [tenderFetcher])
  const { data: history } = useAsync(historyFetcher, [historyFetcher])

  if (loading) return <LoadingView label="Lade Ausschreibung…" />
  if (error) {
    return (
      <ErrorView
        title="Ausschreibung konnte nicht geladen werden"
        description={error}
        action={{ label: 'Erneut versuchen', onClick: reload }}
      />
    )
  }
  if (!tender) return null

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link to="/" className="focus-ring text-sm font-medium text-brand hover:underline">
          ← Zur Übersicht
        </Link>
      </div>

      <div className="rounded-lg border border-line bg-surface p-6 shadow-card">
        <div className="flex flex-wrap items-center gap-2">
          <PortalBadge name={tender.portal.name} />
          <StatusBadge status={tender.status} />
          <KiBadge score={tender.ki_relevanz_score} />
          {tender.gemerkt ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand-light px-2 py-0.5 text-xs font-medium text-brand">
              ★ Gemerkt
            </span>
          ) : null}
        </div>
        <h1 className="mt-3 text-2xl font-semibold text-ink">{tender.titel}</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {tender.vergabestelle ?? 'Vergabestelle unbekannt'}
          {tender.ort_region ? ` · ${tender.ort_region}` : ''}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <UrgencyBadge angebotsfrist={tender.angebotsfrist} status={tender.status} />
          <a
            href={tender.direktlink}
            target="_blank"
            rel="noopener noreferrer"
            className="focus-ring rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90"
          >
            Original ansehen ↗
          </a>
        </div>

        {tender.ki_relevanz_begruendung ? (
          <div className="mt-4 rounded-md bg-ki-strongBg/40 px-4 py-3 text-sm text-ink">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ki-strong">KI-Einschätzung (automatisch)</p>
            {tender.ki_relevanz_begruendung}
          </div>
        ) : null}

        {tender.kurzbeschreibung ? <p className="mt-4 text-sm leading-relaxed text-ink">{tender.kurzbeschreibung}</p> : null}

        {tender.moeglicherweise_duplikat_hinweis ? (
          <p className="mt-4 text-xs italic text-ink-faint">ⓘ {tender.moeglicherweise_duplikat_hinweis}</p>
        ) : null}

        {tender.merk_notiz ? (
          <p className="mt-4 rounded-md bg-brand-light px-3 py-2 text-sm text-brand">
            <span className="font-semibold">Notiz:</span> {tender.merk_notiz}
          </p>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
            <h2 className="mb-4 text-sm font-semibold text-ink">Details</h2>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <Field label="Veröffentlicht" value={formatDate(tender.veroeffentlichungsdatum)} />
              <Field label="Angebotsfrist" value={formatDateTime(tender.angebotsfrist)} />
              <Field label="Fragenfrist" value={formatDateTime(tender.fragenfrist)} />
              <Field label="Verfahrensart" value={tender.verfahrensart ?? '–'} />
              <Field label="Geschätzter Wert" value={formatCurrency(tender.geschaetzter_wert)} />
              <Field label="Zugangsart" value={zugangsartLabel[tender.zugangsart]} />
              <Field label="CPV-Codes" value={tender.cpv_codes.length ? tender.cpv_codes.join(', ') : '–'} />
              <Field label="Erfasst am" value={formatDateTime(tender.erfasst_am)} />
              <Field label="Zuletzt geprüft" value={formatDateTime(tender.zuletzt_geprueft_am)} />
            </dl>
            {tender.kategorien.length ? (
              <div className="mt-4">
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-ink-faint">Kategorien</p>
                <div className="flex flex-wrap gap-1.5">
                  {tender.kategorien.map((category) => (
                    <span key={category} className="rounded-md bg-surface-sunken px-2 py-0.5 text-xs text-ink-muted">
                      {category}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          {tender.volltext ? (
            <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
              <h2 className="mb-3 text-sm font-semibold text-ink">Volltext</h2>
              <p className="whitespace-pre-line text-sm leading-relaxed text-ink-muted">{tender.volltext}</p>
            </section>
          ) : null}

          {tender.dokumente.length > 0 ? (
            <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
              <h2 className="mb-3 text-sm font-semibold text-ink">Dokumente</h2>
              <ul className="flex flex-col gap-2">
                {tender.dokumente.map((doc) => (
                  <li key={doc.url}>
                    <a
                      href={doc.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="focus-ring text-sm font-medium text-brand hover:underline"
                    >
                      {doc.titel ?? doc.url}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
            <h2 className="mb-4 text-sm font-semibold text-ink">Änderungshistorie</h2>
            <Timeline entries={history ?? []} />
          </section>
        </div>

        <div className="flex flex-col gap-6">
          <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
            <h2 className="mb-4 text-sm font-semibold text-ink">Ranking-Aufschlüsselung</h2>
            <RankingBars breakdown={tender.ranking_aufschluesselung} />
            <p className="mt-4 border-t border-line pt-3 text-xs text-ink-faint">
              Gesamtscore <span className="font-semibold text-ink">{(tender.gesamtscore * 100).toFixed(0)}%</span>
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
