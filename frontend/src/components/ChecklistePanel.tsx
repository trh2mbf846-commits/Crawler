import { useState } from 'react'
import { ApiError, checklisteAusBewertung, speichereCheckliste } from '../api/client'
import type { ChecklistenPunkt } from '../api/types'

// Abgabe-Checkliste pro Ausschreibung (26.09.2026, siehe backend app/bewerbung.py).

const STATUS: { wert: ChecklistenPunkt['status']; label: string; klasse: string }[] = [
  { wert: 'offen', label: 'Offen', klasse: 'text-ink-muted' },
  { wert: 'vorhanden', label: 'Vorhanden', klasse: 'text-ki-strong' },
  { wert: 'erledigt', label: 'Erledigt', klasse: 'text-ki-strong' },
  { wert: 'fehlt', label: 'Fehlt', klasse: 'text-urgent-red' },
]

export function ChecklistePanel({
  tenderId,
  anfangs,
  hatBewertung,
}: {
  tenderId: string
  anfangs: ChecklistenPunkt[]
  hatBewertung: boolean
}) {
  const [punkte, setPunkte] = useState<ChecklistenPunkt[]>(anfangs)
  const [neu, setNeu] = useState('')
  const [fehler, setFehler] = useState<string | null>(null)

  const speichern = async (naechste: ChecklistenPunkt[]) => {
    setPunkte(naechste)
    setFehler(null)
    try {
      setPunkte(await speichereCheckliste(tenderId, naechste))
    } catch (err) {
      setFehler(err instanceof ApiError ? err.message : 'Checkliste konnte nicht gespeichert werden.')
    }
  }

  const ausBewertung = async () => {
    try {
      setPunkte(await checklisteAusBewertung(tenderId))
    } catch (err) {
      setFehler(err instanceof ApiError ? err.message : 'Checkliste konnte nicht erzeugt werden.')
    }
  }

  const erledigt = punkte.filter((p) => p.status === 'vorhanden' || p.status === 'erledigt').length
  const fehlt = punkte.filter((p) => p.status === 'fehlt').length

  return (
    <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Abgabe-Checkliste</h2>
        {hatBewertung ? (
          <button type="button" onClick={ausBewertung} className="focus-ring text-xs font-medium text-brand hover:underline">
            Aus Bewertung ergänzen
          </button>
        ) : null}
      </div>
      {fehler ? <p className="mb-2 text-xs text-urgent-red">{fehler}</p> : null}
      {punkte.length === 0 ? (
        <p className="mb-3 text-sm text-ink-muted">
          Noch leer. Lass die Ausschreibung oben von Kevin bewerten – dann entsteht die Checkliste automatisch aus den
          geforderten Nachweisen und Ausschlusskriterien. Eigene Punkte kannst du unten ergänzen.
        </p>
      ) : (
        <>
          <div className="mb-3 flex items-center gap-3 text-xs text-ink-muted">
            <div className="h-2 w-40 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
              <div className="h-full bg-ki-strong" style={{ width: `${(erledigt / punkte.length) * 100}%` }} />
            </div>
            {erledigt}/{punkte.length} erledigt{fehlt ? ` · ${fehlt} fehlen noch` : ''}
          </div>
          <ul className="mb-3 flex flex-col gap-1.5">
            {punkte.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-3 rounded-md border border-line px-3 py-2">
                <span
                  className={`text-sm ${p.status === 'vorhanden' || p.status === 'erledigt' ? 'text-ink-faint line-through' : 'text-ink'}`}
                >
                  {p.text}
                </span>
                <div className="flex shrink-0 items-center gap-2">
                  <select
                    value={p.status}
                    onChange={(e) =>
                      speichern(punkte.map((x) => (x.id === p.id ? { ...x, status: e.target.value as ChecklistenPunkt['status'] } : x)))
                    }
                    className={`focus-ring rounded-md border border-line bg-surface px-1.5 py-0.5 text-xs ${STATUS.find((s) => s.wert === p.status)?.klasse ?? ''}`}
                  >
                    {STATUS.map((s) => (
                      <option key={s.wert} value={s.wert}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => speichern(punkte.filter((x) => x.id !== p.id))}
                    className="focus-ring text-xs text-ink-faint hover:text-urgent-red"
                    aria-label="Punkt entfernen"
                  >
                    ✕
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (!neu.trim()) return
          speichern([...punkte, { id: crypto.randomUUID().slice(0, 10), text: neu.trim(), art: 'eigen', status: 'offen' }])
          setNeu('')
        }}
        className="flex gap-2"
      >
        <input
          value={neu}
          onChange={(e) => setNeu(e.target.value)}
          placeholder="Eigenen Punkt hinzufügen, z. B. „Angebot unterschreiben lassen“"
          className="focus-ring flex-1 rounded-md border border-line bg-surface px-3 py-1.5 text-sm placeholder:text-ink-faint"
        />
        <button type="submit" className="focus-ring rounded-md border border-line px-3 py-1.5 text-sm text-ink-muted hover:bg-surface-sunken">
          Hinzufügen
        </button>
      </form>
    </section>
  )
}
