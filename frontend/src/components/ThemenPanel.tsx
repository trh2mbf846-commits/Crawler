import { useEffect, useState } from 'react'
import { ApiError, fetchThemen, loescheThema, speichereThema } from '../api/client'
import type { Thema, ThemaInput } from '../api/types'

// Themen pflegen (26.09.2026): neue Kategorien/Suchbegriffe ohne Code-Änderung (backend app/themen.py).

const LEER: ThemaInput = { name: '', stichworte: [], ki_bezogen: true, aktiv: true }
const feld = 'focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm placeholder:text-ink-faint'

export function ThemenPanel() {
  const [themen, setThemen] = useState<Thema[]>([])
  const [entwurf, setEntwurf] = useState<ThemaInput>(LEER)
  const [stichwortText, setStichwortText] = useState('')
  const [bearbeitet, setBearbeitet] = useState<string | null>(null)
  const [meldung, setMeldung] = useState<string | null>(null)

  const laden = () => {
    fetchThemen().then(setThemen).catch(() => setMeldung('Themen konnten nicht geladen werden.'))
  }
  useEffect(laden, [])

  const bearbeiten = (t: Thema) => {
    setEntwurf({ name: t.name, stichworte: t.stichworte, ki_bezogen: t.ki_bezogen, aktiv: t.aktiv })
    setStichwortText(t.stichworte.join(', '))
    setBearbeitet(t.id)
  }

  const speichern = async (eingabe: ThemaInput, id?: string) => {
    try {
      await speichereThema(eingabe, id)
      setMeldung('Gespeichert – offene Ausschreibungen werden im Hintergrund neu eingeordnet.')
      setEntwurf(LEER)
      setStichwortText('')
      setBearbeitet(null)
      laden()
    } catch (err) {
      setMeldung(err instanceof ApiError ? err.message : 'Speichern fehlgeschlagen.')
    }
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-5 shadow-card">
      <h2 className="text-sm font-semibold text-ink">Themen</h2>
      <p className="mb-3 mt-0.5 text-xs text-ink-muted">
        Jedes Thema wird zur Kategorie in der Übersicht. Ausschreibungen, in denen eines der Stichworte vorkommt, werden
        automatisch zugeordnet. „KI-bezogen“: zusätzlich als KI-relevant prüfen und bei TED danach suchen.
        Kombi-Stichwort mit „+“: <code>schulung + ki</code> trifft, wenn beide Begriffe vorkommen. Neue Themen kannst du
        auch einfach Kevin sagen („Nimm auch das Thema Robotik auf“).
      </p>
      {meldung ? <p className="mb-2 text-xs text-ink-muted">{meldung}</p> : null}

      <div className="mb-4 grid gap-2">
        <input value={entwurf.name} onChange={(e) => setEntwurf({ ...entwurf, name: e.target.value })} placeholder="Name, z. B. Robotik" className={feld} />
        <textarea
          value={stichwortText}
          onChange={(e) => setStichwortText(e.target.value)}
          rows={2}
          placeholder="Stichworte, mit Komma getrennt – z. B. robotik, serviceroboter, roboter + pflege"
          className={`${feld} resize-y`}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-ink-muted">
            <input type="checkbox" checked={entwurf.ki_bezogen} onChange={(e) => setEntwurf({ ...entwurf, ki_bezogen: e.target.checked })} />
            KI-bezogen
          </label>
          <button
            type="button"
            disabled={!entwurf.name.trim() || !stichwortText.trim()}
            onClick={() =>
              speichern(
                { ...entwurf, stichworte: stichwortText.split(',').map((s) => s.trim()).filter(Boolean) },
                bearbeitet ?? undefined,
              )
            }
            className="focus-ring rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {bearbeitet ? 'Änderung speichern' : 'Thema hinzufügen'}
          </button>
          {bearbeitet ? (
            <button type="button" onClick={() => { setEntwurf(LEER); setStichwortText(''); setBearbeitet(null) }} className="focus-ring text-sm text-ink-muted hover:text-ink">
              Abbrechen
            </button>
          ) : null}
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {themen.map((t) => (
          <li key={t.id} className="rounded-md border border-line px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className={`text-sm font-medium ${t.aktiv ? 'text-ink' : 'text-ink-faint'}`}>
                {t.name}
                {t.ki_bezogen ? <span className="ml-2 rounded bg-ki-strongBg px-1.5 py-0.5 text-xs text-ki-strong">KI</span> : null}
                {!t.aktiv ? <span className="ml-2 text-xs">(pausiert)</span> : null}
              </span>
              <div className="flex gap-3 text-xs">
                <button type="button" onClick={() => bearbeiten(t)} className="focus-ring text-brand hover:underline">
                  Bearbeiten
                </button>
                <button
                  type="button"
                  onClick={() => speichern({ name: t.name, stichworte: t.stichworte, ki_bezogen: t.ki_bezogen, aktiv: !t.aktiv }, t.id)}
                  className="focus-ring text-ink-muted hover:text-ink"
                >
                  {t.aktiv ? 'Pausieren' : 'Aktivieren'}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    if (!window.confirm(`Thema „${t.name}“ löschen?`)) return
                    await loescheThema(t.id).catch(() => setMeldung('Löschen fehlgeschlagen.'))
                    laden()
                  }}
                  className="focus-ring text-ink-muted hover:text-urgent-red"
                >
                  Löschen
                </button>
              </div>
            </div>
            <p className="mt-1 text-xs text-ink-muted">{t.stichworte.join(' · ')}</p>
          </li>
        ))}
      </ul>
    </section>
  )
}
