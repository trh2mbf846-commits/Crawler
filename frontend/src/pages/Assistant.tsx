import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  executeAssistantAction,
  fetchAssistantDigest,
  fetchAssistantPreferences,
  sendAssistantMessage,
  updateAssistantPreferences,
} from '../api/client'
import type { AssistantActionProposal, AssistantMessage, AssistantPreferences, Tender } from '../api/types'
import { CATEGORIES } from '../api/types'
import { TenderCard } from '../components/TenderCard'

interface ChatEntry extends AssistantMessage {
  id: string
  tenders?: Tender[]
  vorschlag?: AssistantActionProposal | null
}

type AktionStatus = { status: 'ausgefuehrt' | 'abgelehnt' | 'fehler'; meldung?: string }

const BEISPIELE = [
  'Welche KI-relevanten Ausschreibungen laufen in Bayern aus?',
  'Gibt es neue Ausschreibungen zu Cybersecurity?',
  'Wie ist der aktuelle Quellstatus?',
]

const LEERE_PRAEFERENZEN: AssistantPreferences = {
  prioritaeten_text: null,
  bevorzugte_kategorien: [],
  bevorzugte_regionen: [],
  mindestwert: null,
}

function PraeferenzenPanel({ onClose }: { onClose: () => void }) {
  const [praeferenzen, setPraeferenzen] = useState<AssistantPreferences>(LEERE_PRAEFERENZEN)
  const [regionenText, setRegionenText] = useState('')
  const [ladend, setLadend] = useState(true)
  const [speichernd, setSpeichernd] = useState(false)
  const [fehler, setFehler] = useState<string | null>(null)
  const [gespeichert, setGespeichert] = useState(false)

  useEffect(() => {
    fetchAssistantPreferences()
      .then((p) => {
        setPraeferenzen(p)
        setRegionenText(p.bevorzugte_regionen.join(', '))
      })
      .catch(() => setFehler('Präferenzen konnten nicht geladen werden.'))
      .finally(() => setLadend(false))
  }, [])

  const toggleKategorie = (kategorie: string) => {
    setPraeferenzen((prev) => ({
      ...prev,
      bevorzugte_kategorien: prev.bevorzugte_kategorien.includes(kategorie)
        ? prev.bevorzugte_kategorien.filter((k) => k !== kategorie)
        : [...prev.bevorzugte_kategorien, kategorie],
    }))
  }

  const speichern = async () => {
    setSpeichernd(true)
    setFehler(null)
    setGespeichert(false)
    try {
      const payload: AssistantPreferences = {
        ...praeferenzen,
        bevorzugte_regionen: regionenText
          .split(',')
          .map((r) => r.trim())
          .filter(Boolean),
      }
      const aktualisiert = await updateAssistantPreferences(payload)
      setPraeferenzen(aktualisiert)
      setGespeichert(true)
    } catch (err) {
      setFehler(err instanceof ApiError ? err.message : 'Präferenzen konnten nicht gespeichert werden.')
    } finally {
      setSpeichernd(false)
    }
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink">Deine Prioritäten für Kevin</h2>
        <button type="button" onClick={onClose} className="focus-ring rounded text-xs text-ink-muted hover:text-ink">
          Schließen
        </button>
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        Kevin berücksichtigt das in Antworten, Vorschlägen und im täglichen Kurzbericht.
      </p>

      {ladend ? (
        <p className="mt-3 text-xs text-ink-muted">Lädt…</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-muted">Freitext (z. B. Fokus, Ausschlusskriterien)</span>
            <textarea
              value={praeferenzen.prioritaeten_text ?? ''}
              onChange={(e) => setPraeferenzen((prev) => ({ ...prev, prioritaeten_text: e.target.value }))}
              rows={2}
              placeholder="z. B. Fokus auf KI/Cloud-Projekte, Fristen unter 2 Wochen sind besonders dringend"
              className="focus-ring resize-none rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
            />
          </label>

          <div>
            <span className="text-xs font-medium text-ink-muted">Bevorzugte Kategorien</span>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {CATEGORIES.map((kategorie) => (
                <button
                  key={kategorie}
                  type="button"
                  onClick={() => toggleKategorie(kategorie)}
                  className={`focus-ring rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                    praeferenzen.bevorzugte_kategorien.includes(kategorie)
                      ? 'border-brand bg-brand-light text-brand'
                      : 'border-line text-ink-muted hover:bg-surface-sunken'
                  }`}
                >
                  {kategorie}
                </button>
              ))}
            </div>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-muted">Bevorzugte Regionen (kommagetrennt)</span>
            <input
              type="text"
              value={regionenText}
              onChange={(e) => setRegionenText(e.target.value)}
              placeholder="z. B. Berlin, Bayern"
              className="focus-ring rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-muted">Mindestwert (€)</span>
            <input
              type="number"
              value={praeferenzen.mindestwert ?? ''}
              onChange={(e) =>
                setPraeferenzen((prev) => ({
                  ...prev,
                  mindestwert: e.target.value === '' ? null : Number(e.target.value),
                }))
              }
              placeholder="z. B. 50000"
              className="focus-ring rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
            />
          </label>

          {fehler ? <p className="text-xs text-urgent-red">{fehler}</p> : null}
          {gespeichert ? <p className="text-xs text-ink-muted">Gespeichert.</p> : null}

          <div>
            <button
              type="button"
              disabled={speichernd}
              onClick={() => void speichern()}
              className="focus-ring rounded-md bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {speichernd ? 'Speichert…' : 'Speichern'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function Assistant() {
  const [verlauf, setVerlauf] = useState<ChatEntry[]>([])
  const [eingabe, setEingabe] = useState('')
  const [senden, setSenden] = useState(false)
  const [fehler, setFehler] = useState<string | null>(null)
  const [nichtKonfiguriert, setNichtKonfiguriert] = useState(false)
  const [aktionStatus, setAktionStatus] = useState<Record<string, AktionStatus>>({})
  const [aktionLaeuft, setAktionLaeuft] = useState<string | null>(null)
  const [praeferenzenOffen, setPraeferenzenOffen] = useState(false)
  const endeRef = useRef<HTMLDivElement>(null)
  const digestGeladen = useRef(false)

  useEffect(() => {
    endeRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [verlauf, aktionStatus])

  useEffect(() => {
    if (digestGeladen.current) return
    digestGeladen.current = true
    fetchAssistantDigest()
      .then((digest) => {
        setVerlauf((prev) =>
          prev.length > 0
            ? prev
            : [{ id: crypto.randomUUID(), rolle: 'assistant', text: `Guten Tag! Dein Kurzbericht:\n\n${digest.text}`, tenders: digest.tenders }]
        )
      })
      .catch(() => {
        // Kurzbericht ist ein Bonus, kein kritischer Pfad - bei Fehler bleibt einfach die
        // normale Begrüßung mit den Beispiel-Fragen stehen.
      })
  }, [])

  const absenden = useCallback(
    async (text: string) => {
      const nachricht = text.trim()
      if (!nachricht || senden) return

      const userEintrag: ChatEntry = { id: crypto.randomUUID(), rolle: 'user', text: nachricht }
      const bisherigerVerlauf = verlauf.map(({ rolle, text }) => ({ rolle, text }))
      setVerlauf((prev) => [...prev, userEintrag])
      setEingabe('')
      setSenden(true)
      setFehler(null)

      try {
        const ergebnis = await sendAssistantMessage(nachricht, bisherigerVerlauf)
        setNichtKonfiguriert(!ergebnis.verfuegbar)
        setVerlauf((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            rolle: 'assistant',
            text: ergebnis.antwort,
            tenders: ergebnis.tenders,
            vorschlag: ergebnis.vorschlag,
          },
        ])
      } catch (err) {
        setFehler(err instanceof ApiError ? err.message : 'Crawler Kevin konnte nicht antworten.')
      } finally {
        setSenden(false)
      }
    },
    [senden, verlauf]
  )

  const bestaetigen = useCallback(async (eintrag: ChatEntry) => {
    if (!eintrag.vorschlag) return
    setAktionLaeuft(eintrag.id)
    try {
      const ergebnis = await executeAssistantAction(eintrag.vorschlag.name, eintrag.vorschlag.input)
      setAktionStatus((prev) => ({
        ...prev,
        [eintrag.id]: { status: ergebnis.erfolg ? 'ausgefuehrt' : 'fehler', meldung: ergebnis.meldung },
      }))
    } catch (err) {
      setAktionStatus((prev) => ({
        ...prev,
        [eintrag.id]: {
          status: 'fehler',
          meldung: err instanceof ApiError ? err.message : 'Aktion konnte nicht ausgeführt werden.',
        },
      }))
    } finally {
      setAktionLaeuft(null)
    }
  }, [])

  const ablehnen = useCallback((eintrag: ChatEntry) => {
    setAktionStatus((prev) => ({ ...prev, [eintrag.id]: { status: 'abgelehnt' } }))
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Crawler Kevin</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Dein KI-Kollege für die Ausschreibungssuche – frag ihn in natürlicher Sprache zu erfassten
            Ausschreibungen und zum Quellstatus. Ergänzt die Übersicht, ersetzt sie nicht: Kevin kann einen
            Aktualisieren-Lauf anstoßen, ein Suchprofil anlegen oder eine Ausschreibung merken – schlägt das
            aber nur vor, ausgeführt wird erst nach deiner Bestätigung.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setPraeferenzenOffen((prev) => !prev)}
          className="focus-ring shrink-0 rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink"
        >
          ⚙ Präferenzen
        </button>
      </div>

      {praeferenzenOffen ? <PraeferenzenPanel onClose={() => setPraeferenzenOffen(false)} /> : null}

      {nichtKonfiguriert ? (
        <div className="rounded-md border border-line bg-surface-sunken px-4 py-3 text-sm text-ink-muted">
          Crawler Kevin ist auf diesem Server nicht konfiguriert: Es ist Claude als Anbieter gewählt, aber kein{' '}
          <code>CRAWLER_ANTHROPIC_API_KEY</code> hinterlegt. Kostenlose Alternative: <code>CRAWLER_KEVIN_ANBIETER=ollama</code>{' '}
          mit Ollama (ollama.com). Nutze in der Zwischenzeit die normale Suche/Filter in der Übersicht.
        </div>
      ) : null}

      <div className="flex min-h-[50vh] flex-col rounded-lg border border-line bg-surface shadow-card">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {verlauf.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 py-10 text-center">
              <p className="text-sm text-ink-muted">Stell eine Frage, z. B.:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {BEISPIELE.map((beispiel) => (
                  <button
                    key={beispiel}
                    type="button"
                    onClick={() => void absenden(beispiel)}
                    className="focus-ring rounded-full border border-line px-3 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink"
                  >
                    {beispiel}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {verlauf.map((eintrag) => {
            const status = aktionStatus[eintrag.id]
            return (
              <div key={eintrag.id} className={`flex ${eintrag.rolle === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] ${eintrag.rolle === 'user' ? '' : 'w-full'}`}>
                  <div
                    className={`whitespace-pre-line rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
                      eintrag.rolle === 'user' ? 'bg-brand text-white' : 'bg-surface-sunken text-ink'
                    }`}
                  >
                    {eintrag.text}
                  </div>

                  {eintrag.vorschlag ? (
                    <div className="mt-2 rounded-md border border-brand/30 bg-brand-light px-3.5 py-2.5 text-sm text-ink">
                      <p className="font-medium text-brand">Vorschlag: {eintrag.vorschlag.beschreibung}</p>
                      {status === undefined ? (
                        <div className="mt-2 flex gap-2">
                          <button
                            type="button"
                            disabled={aktionLaeuft === eintrag.id}
                            onClick={() => void bestaetigen(eintrag)}
                            className="focus-ring rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {aktionLaeuft === eintrag.id ? 'Wird ausgeführt…' : 'Bestätigen'}
                          </button>
                          <button
                            type="button"
                            disabled={aktionLaeuft === eintrag.id}
                            onClick={() => ablehnen(eintrag)}
                            className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken"
                          >
                            Ablehnen
                          </button>
                        </div>
                      ) : (
                        <p
                          className={`mt-2 text-xs ${
                            status.status === 'fehler' ? 'text-urgent-red' : 'text-ink-muted'
                          }`}
                        >
                          {status.status === 'abgelehnt' ? 'Abgelehnt.' : status.meldung}
                        </p>
                      )}
                    </div>
                  ) : null}

                  {eintrag.tenders && eintrag.tenders.length > 0 ? (
                    <div className="mt-2 flex flex-col gap-2">
                      {eintrag.tenders.map((tender) => (
                        <TenderCard key={tender.id} tender={tender} />
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            )
          })}

          {senden ? (
            <div className="flex justify-start">
              <div className="rounded-lg bg-surface-sunken px-3.5 py-2.5 text-sm text-ink-muted">Antwortet…</div>
            </div>
          ) : null}

          <div ref={endeRef} />
        </div>

        {fehler ? <p className="border-t border-line px-4 py-2 text-xs text-urgent-red">{fehler}</p> : null}

        <form
          onSubmit={(event) => {
            event.preventDefault()
            void absenden(eingabe)
          }}
          className="flex items-center gap-2 border-t border-line p-3"
        >
          <input
            type="text"
            value={eingabe}
            onChange={(event) => setEingabe(event.target.value)}
            placeholder="Frage an Crawler Kevin…"
            className="focus-ring flex-1 rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
          />
          <button
            type="submit"
            disabled={senden || !eingabe.trim()}
            className="focus-ring rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Senden
          </button>
        </form>
      </div>
    </div>
  )
}
