import { useCallback, useState } from 'react'
import { ApiError, fetchPortals, runPortalTest } from '../api/client'
import { AmpelDot } from '../components/Badges'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { useAsync } from '../hooks/useAsync'
import { formatDateTime } from '../utils/format'
import { robotsStatusLabel } from '../utils/tender'

const ampelCardBorder: Record<string, string> = {
  gruen: 'border-l-ki-strong',
  gelb: 'border-l-urgent-yellow',
  rot: 'border-l-urgent-red',
}

function ErrorRateBar({ rate }: { rate: number | null }) {
  if (rate === null) return <span className="text-xs text-ink-faint">Keine Daten</span>
  const percent = Math.round(rate * 100)
  const color = rate < 0.1 ? 'bg-ki-strong' : rate < 0.3 ? 'bg-urgent-yellow' : 'bg-urgent-red'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-sunken">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${percent}%` }} />
      </div>
      <span className="text-xs tabular-nums text-ink-muted">{percent}%</span>
    </div>
  )
}


// Datenqualität je Lauf (backend app/datenqualitaet.py) - Einbruch deutet auf Layout-Änderung hin.
const QUALITAETSFELDER: Record<string, string> = {
  angebotsfrist: 'Frist',
  vergabestelle: 'Vergabestelle',
  kurzbeschreibung: 'Beschreibung',
  ort_region: 'Ort',
  direktlink: 'Verfahrenslink',
}

export function PortalStatus() {
  const { data: portals, loading, error, reload } = useAsync(fetchPortals, [])
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set())
  const [feedback, setFeedback] = useState<Record<string, string>>({})

  const startRun = useCallback(async (id: string) => {
    setRunningIds((prev) => new Set(prev).add(id))
    setFeedback((prev) => ({ ...prev, [id]: '' }))
    try {
      await runPortalTest(id)
      setFeedback((prev) => ({ ...prev, [id]: 'Testlauf gestartet.' }))
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Testlauf konnte nicht gestartet werden.'
      setFeedback((prev) => ({ ...prev, [id]: message }))
    } finally {
      setRunningIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    }
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Quellstatus-Dashboard</h1>
        <p className="mt-0.5 text-sm text-ink-muted">
          Betriebszustand aller angebundenen Vergabeportale, robots.txt/ToS-Prüfung und letzter Lauf.
        </p>
      </div>

      {loading ? <LoadingView label="Lade Portalstatus…" /> : null}
      {!loading && error ? (
        <ErrorView title="Portalstatus konnte nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />
      ) : null}
      {!loading && !error && portals && portals.length === 0 ? (
        <EmptyView title="Keine Portale konfiguriert" description="Es sind noch keine Quellen angebunden." />
      ) : null}

      {!loading && !error && portals && portals.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {portals.map((portal) => (
            <div
              key={portal.id}
              className={`flex flex-col gap-3 rounded-lg border border-l-4 border-line bg-surface p-4 shadow-card ${ampelCardBorder[portal.status_ampel]}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-ink">{portal.name}</h2>
                  <p className="text-xs text-ink-faint">{portal.betreiber ?? portal.base_url}</p>
                </div>
                <AmpelDot status={portal.status_ampel} />
              </div>

              {portal.meldung ? (
                <p className="rounded-md bg-surface-sunken px-3 py-2 text-xs text-ink-muted">{portal.meldung}</p>
              ) : null}

              <dl className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <dt className="text-ink-faint">Letzter erfolgreicher Lauf</dt>
                  <dd className="mt-0.5 text-ink">{formatDateTime(portal.letzter_erfolgreicher_lauf)}</dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Letzte Trefferzahl</dt>
                  <dd className="mt-0.5 text-ink">{portal.letzte_trefferzahl ?? '–'}</dd>
                </div>
                <div>
                  <dt className="text-ink-faint">robots.txt / ToS</dt>
                  <dd className="mt-0.5 text-ink">{robotsStatusLabel[portal.robots_status]}</dd>
                </div>
                <div>
                  <dt className="text-ink-faint">Fehlerrate (gleitend)</dt>
                  <dd className="mt-0.5">
                    <ErrorRateBar rate={portal.fehlerrate_gleitend} />
                  </dd>
                </div>
              </dl>

              {portal.qualitaet ? (
                <div className="text-xs">
                  <p className="mb-1 text-ink-faint">Datenqualität letzter Lauf ({portal.qualitaet.anzahl} Ausschreibungen)</p>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(QUALITAETSFELDER).map(([feld, label]) => {
                      const quote = portal.qualitaet?.quoten[feld] ?? 0
                      const klasse = quote >= 0.8 ? 'bg-ki-strongBg text-ki-strong' : quote >= 0.5 ? 'bg-urgent-yellowBg text-urgent-yellow' : 'bg-urgent-redBg text-urgent-red'
                      return (
                        <span key={feld} className={`rounded-md px-1.5 py-0.5 ${klasse}`} title={`Anteil der Ausschreibungen mit ${label}`}>
                          {label} {Math.round(quote * 100)} %
                        </span>
                      )
                    })}
                  </div>
                </div>
              ) : null}

              {portal.tos_hinweis ? <p className="text-xs italic text-ink-faint">{portal.tos_hinweis}</p> : null}

              <div className="mt-1 flex items-center gap-3 border-t border-line pt-3">
                <button
                  type="button"
                  disabled={runningIds.has(portal.id)}
                  onClick={() => void startRun(portal.id)}
                  className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {runningIds.has(portal.id) ? 'Startet…' : 'Testlauf starten'}
                </button>
                {feedback[portal.id] ? <span className="text-xs text-ink-muted">{feedback[portal.id]}</span> : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
