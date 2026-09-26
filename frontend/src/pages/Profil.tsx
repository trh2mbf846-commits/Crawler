import { useEffect, useState } from 'react'
import {
  ApiError,
  fetchAssistantPreferences,
  fetchReferenzen,
  loescheReferenz,
  speichereReferenz,
  updateAssistantPreferences,
} from '../api/client'
import type { AssistantPreferences, Referenz, ReferenzInput } from '../api/types'
import { formatCurrency } from '../utils/format'

// Mein Profil (26.09.2026): Firmenprofil + Referenzprojekte - Grundlage für Kevins
// "Bewerben oder nicht?"-Bewertung und die Auswahl passender Referenzen je Ausschreibung.

const LEER: ReferenzInput = { titel: '', auftraggeber: null, jahr: null, volumen: null, beschreibung: null }

const feldKlasse = 'focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm placeholder:text-ink-faint'

export function Profil() {
  const [praeferenzen, setPraeferenzen] = useState<AssistantPreferences | null>(null)
  const [referenzen, setReferenzen] = useState<Referenz[]>([])
  const [entwurf, setEntwurf] = useState<ReferenzInput>(LEER)
  const [bearbeitet, setBearbeitet] = useState<string | null>(null)
  const [meldung, setMeldung] = useState<string | null>(null)

  const laden = () => {
    fetchAssistantPreferences().then(setPraeferenzen).catch(() => setMeldung('Profil konnte nicht geladen werden.'))
    fetchReferenzen().then(setReferenzen).catch(() => setMeldung('Referenzen konnten nicht geladen werden.'))
  }
  useEffect(laden, [])

  const profilSpeichern = async () => {
    if (!praeferenzen) return
    try {
      setPraeferenzen(await updateAssistantPreferences(praeferenzen))
      setMeldung('Firmenprofil gespeichert.')
    } catch (err) {
      setMeldung(err instanceof ApiError ? err.message : 'Speichern fehlgeschlagen.')
    }
  }

  const referenzSpeichern = async () => {
    if (!entwurf.titel.trim()) return
    try {
      await speichereReferenz(entwurf, bearbeitet ?? undefined)
      setEntwurf(LEER)
      setBearbeitet(null)
      setMeldung('Referenz gespeichert.')
      laden()
    } catch (err) {
      setMeldung(err instanceof ApiError ? err.message : 'Speichern fehlgeschlagen.')
    }
  }

  const zahl = (wert: string) => (wert.trim() === '' ? null : Number(wert))

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Mein Profil</h1>
        <p className="mt-0.5 text-sm text-ink-muted">
          Je genauer Firmenprofil und Referenzen, desto aussagekräftiger Kevins „Bewerben oder nicht?“ – er vergleicht jede
          Ausschreibung damit und schlägt passende Referenzen vor.
        </p>
      </div>
      {meldung ? <p className="text-sm text-ink-muted">{meldung}</p> : null}

      <section className="rounded-lg border border-line bg-surface p-5 shadow-card">
        <h2 className="mb-2 text-sm font-semibold text-ink">Firmenprofil</h2>
        <textarea
          value={praeferenzen?.firmenprofil ?? ''}
          onChange={(e) => praeferenzen && setPraeferenzen({ ...praeferenzen, firmenprofil: e.target.value })}
          rows={5}
          disabled={!praeferenzen}
          placeholder="Leistungen, Schwerpunkte, Mitarbeitende, Umsatz, Zertifikate (z. B. ISO 27001), Regionen, was ihr NICHT anbietet …"
          className={`${feldKlasse} w-full resize-y`}
        />
        <button type="button" onClick={profilSpeichern} className="focus-ring mt-2 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90">
          Speichern
        </button>
      </section>

      <section className="rounded-lg border border-line bg-surface p-5 shadow-card">
        <h2 className="mb-3 text-sm font-semibold text-ink">Referenzprojekte ({referenzen.length})</h2>
        <div className="mb-4 grid gap-2 sm:grid-cols-2">
          <input value={entwurf.titel} onChange={(e) => setEntwurf({ ...entwurf, titel: e.target.value })} placeholder="Titel des Projekts *" className={feldKlasse} />
          <input value={entwurf.auftraggeber ?? ''} onChange={(e) => setEntwurf({ ...entwurf, auftraggeber: e.target.value || null })} placeholder="Auftraggeber" className={feldKlasse} />
          <input value={entwurf.jahr ?? ''} onChange={(e) => setEntwurf({ ...entwurf, jahr: zahl(e.target.value) })} placeholder="Jahr" inputMode="numeric" className={feldKlasse} />
          <input value={entwurf.volumen ?? ''} onChange={(e) => setEntwurf({ ...entwurf, volumen: zahl(e.target.value) })} placeholder="Auftragswert in €" inputMode="numeric" className={feldKlasse} />
          <textarea
            value={entwurf.beschreibung ?? ''}
            onChange={(e) => setEntwurf({ ...entwurf, beschreibung: e.target.value || null })}
            placeholder="Kurzbeschreibung: Was wurde geliefert, welche Technologien, welches Ergebnis?"
            rows={2}
            className={`${feldKlasse} resize-y sm:col-span-2`}
          />
          <div className="flex gap-2 sm:col-span-2">
            <button type="button" onClick={referenzSpeichern} disabled={!entwurf.titel.trim()} className="focus-ring rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              {bearbeitet ? 'Änderung speichern' : 'Referenz hinzufügen'}
            </button>
            {bearbeitet ? (
              <button type="button" onClick={() => { setEntwurf(LEER); setBearbeitet(null) }} className="focus-ring rounded-md px-3 py-1.5 text-sm text-ink-muted hover:text-ink">
                Abbrechen
              </button>
            ) : null}
          </div>
        </div>
        <ul className="flex flex-col gap-2">
          {referenzen.map((r) => (
            <li key={r.id} className="rounded-md border border-line px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-ink">{r.titel}</span>
                <div className="flex gap-3 text-xs">
                  <button type="button" onClick={() => { setEntwurf({ titel: r.titel, auftraggeber: r.auftraggeber, jahr: r.jahr, volumen: r.volumen, beschreibung: r.beschreibung }); setBearbeitet(r.id) }} className="focus-ring text-brand hover:underline">
                    Bearbeiten
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      if (!window.confirm(`Referenz „${r.titel}“ löschen?`)) return
                      await loescheReferenz(r.id).catch(() => setMeldung('Löschen fehlgeschlagen.'))
                      laden()
                    }}
                    className="focus-ring text-ink-muted hover:text-urgent-red"
                  >
                    Löschen
                  </button>
                </div>
              </div>
              <p className="text-xs text-ink-muted">
                {[r.auftraggeber, r.jahr, r.volumen ? formatCurrency(r.volumen) : null].filter(Boolean).join(' · ')}
              </p>
              {r.beschreibung ? <p className="mt-1 text-xs text-ink-muted">{r.beschreibung}</p> : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
