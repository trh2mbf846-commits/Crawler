import { useState } from 'react'
import { ApiError, bewerteTender } from '../api/client'
import type { Bewertung } from '../api/types'
import { formatDateTime } from '../utils/format'

// Go/No-Go-Bewertung auf der Detailseite (Nutzeranfrage 25.09.2026, siehe backend agents/bewertung.py).

const EMPFEHLUNG: Record<Bewertung['empfehlung'], { label: string; klasse: string }> = {
  bewerben: { label: 'Bewerben', klasse: 'bg-ki-strongBg text-ki-strong' },
  pruefen: { label: 'Genauer prüfen', klasse: 'bg-urgent-yellowBg text-urgent-yellow' },
  nicht_bewerben: { label: 'Nicht bewerben', klasse: 'bg-urgent-redBg text-urgent-red' },
}

const LISTEN: { feld: keyof Bewertung; titel: string }[] = [
  { feld: 'ausschlusskriterien', titel: 'Ausschlusskriterien' },
  { feld: 'pflichtnachweise', titel: 'Pflichtnachweise' },
  { feld: 'fehlende_nachweise', titel: 'Fehlt dir evtl. noch' },
  { feld: 'zuschlagskriterien', titel: 'Zuschlagskriterien' },
  { feld: 'fristen', titel: 'Fristen' },
  { feld: 'risiken', titel: 'Risiken' },
  { feld: 'naechste_schritte', titel: 'Nächste Schritte' },
]

export function BewertungPanel({
  tenderId,
  anfangs,
  onBewertet,
}: {
  tenderId: string
  anfangs: Bewertung | null | undefined
  onBewertet?: () => void
}) {
  const [bewertung, setBewertung] = useState<Bewertung | null>(anfangs ?? null)
  const [laeuft, setLaeuft] = useState(false)
  const [fehler, setFehler] = useState<string | null>(null)

  const bewerten = async () => {
    setLaeuft(true)
    setFehler(null)
    try {
      setBewertung(await bewerteTender(tenderId))
      onBewertet?.() // Checkliste wurde serverseitig ergänzt - Detailseite neu laden
    } catch (err) {
      setFehler(err instanceof ApiError ? err.message : 'Bewertung fehlgeschlagen.')
    } finally {
      setLaeuft(false)
    }
  }

  return (
    <section className="rounded-lg border border-line bg-surface p-6 shadow-card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Bewerben oder nicht?</h2>
        <button
          type="button"
          onClick={bewerten}
          disabled={laeuft}
          className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:cursor-wait disabled:opacity-60"
        >
          {laeuft ? 'Kevin bewertet… (kann etwas dauern)' : bewertung ? 'Neu bewerten' : 'Von Kevin bewerten lassen'}
        </button>
      </div>

      {fehler ? <p className="mb-3 text-sm text-urgent-red">{fehler}</p> : null}

      {!bewertung ? (
        <p className="text-sm text-ink-muted">
          Kevin vergleicht die Ausschreibung – inklusive Vergabeunterlagen bzw. Verfahrensseite – mit deinem Firmenprofil und
          deinen Referenzen (Seite „Mein Profil“) und zieht Ausschlusskriterien, Pflichtnachweise und Fristen heraus. Daraus
          entsteht automatisch die Abgabe-Checkliste.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${EMPFEHLUNG[bewertung.empfehlung].klasse}`}>
              {EMPFEHLUNG[bewertung.empfehlung].label}
            </span>
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <div className="h-2 w-28 overflow-hidden rounded-full bg-surface-sunken" aria-hidden>
                <div className="h-full bg-brand" style={{ width: `${bewertung.passwert}%` }} />
              </div>
              Passwert {bewertung.passwert}/100
            </div>
          </div>
          {bewertung.zusammenfassung ? <p className="text-sm text-ink">{bewertung.zusammenfassung}</p> : null}
          {bewertung.begruendung ? <p className="text-sm text-ink-muted">{bewertung.begruendung}</p> : null}
          {bewertung.firmenprofil_fehlte ? (
            <p className="rounded-md bg-surface-sunken px-3 py-2 text-xs text-ink-muted">
              Tipp: Trag unter „Mein Profil“ ein Firmenprofil und deine Referenzprojekte ein, dann wird der Passwert
              deutlich aussagekräftiger.
            </p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            {LISTEN.map(({ feld, titel }) => {
              const eintraege = bewertung[feld] as string[]
              if (!eintraege.length) return null
              return (
                <div key={feld}>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-faint">{titel}</p>
                  <ul className="list-disc space-y-0.5 pl-4 text-sm text-ink">
                    {eintraege.map((eintrag) => (
                      <li key={eintrag}>{eintrag}</li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
          {bewertung.passende_referenzen?.length ? (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-faint">Passende Referenzen von dir</p>
              <ul className="list-disc space-y-0.5 pl-4 text-sm text-ink">
                {bewertung.passende_referenzen.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p className="text-xs text-ink-faint">
            {bewertung.entfernt_ohne_beleg
              ? `Prüfer: ${bewertung.entfernt_ohne_beleg} Punkt(e) verworfen, die nicht im Quelltext standen. `
              : ''}
            KI-Einschätzung ({bewertung.modell}), keine Rechtsberatung · Grundlage: {bewertung.quellen.join(', ')}
            {bewertung.bewertet_am ? ` · ${formatDateTime(bewertung.bewertet_am)}` : ''}
          </p>
        </div>
      )}
    </section>
  )
}
