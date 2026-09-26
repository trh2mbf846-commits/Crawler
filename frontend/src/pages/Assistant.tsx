import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  executeAssistantAction,
  fetchAssistantDigest,
  fetchAssistantPreferences,
  fetchCategories,
  fetchWuensche,
  loescheWunsch,
  sendAssistantMessage,
  setzeWunschStatus,
  updateAssistantPreferences,
} from '../api/client'
import type { AssistantPreferences, Wunsch } from '../api/types'
import { CATEGORIES } from '../api/types'
import { TenderCard } from '../components/TenderCard'
import {
  type AktionStatus,
  type ChatEntry,
  haengeAn,
  ladeChat,
  laufendeKevinAnfrage,
  loescheChat,
  merkeLaufendeAnfrage,
  speichereChat,
} from '../utils/kevinChat'

const BEISPIELE = [
  'Welche KI-relevanten Ausschreibungen laufen in Bayern aus?',
  'Gibt es neue Ausschreibungen zu Cybersecurity?',
  'Wie ist der aktuelle Quellstatus?',
]

const LEERE_PRAEFERENZEN: AssistantPreferences = {
  prioritaeten_text: null,
  firmenprofil: null,
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
  // Feste Grundkategorien + eigene Themen (backend /api/categories) statt fester Liste.
  const [kategorien, setKategorien] = useState<string[]>([...CATEGORIES])

  useEffect(() => {
    fetchCategories().then(setKategorien).catch(() => undefined)
  }, [])

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

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-ink-muted">
              Firmenprofil (für „Bewerben oder nicht?“: Leistungen, Referenzen, Zertifikate, Größe)
            </span>
            <textarea
              value={praeferenzen.firmenprofil ?? ''}
              onChange={(e) => setPraeferenzen((prev) => ({ ...prev, firmenprofil: e.target.value }))}
              rows={4}
              placeholder="z. B. 8 Mitarbeitende, KI-Beratung und Entwicklung (LLM, Chatbots), 3 Referenzen öffentlicher Sektor, ISO 27001 in Vorbereitung, Jahresumsatz ca. 900.000 €"
              className="focus-ring resize-y rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
            />
          </label>

          <div>
            <span className="text-xs font-medium text-ink-muted">Bevorzugte Kategorien</span>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {kategorien.map((kategorie) => (
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

function WunschlistePanel({ onClose }: { onClose: () => void }) {
  const [wuensche, setWuensche] = useState<Wunsch[] | null>(null)
  const [fehler, setFehler] = useState<string | null>(null)
  const [kopiert, setKopiert] = useState(false)

  const laden = useCallback(() => {
    fetchWuensche()
      .then(setWuensche)
      .catch(() => setFehler('Wunschliste konnte nicht geladen werden.'))
  }, [])
  useEffect(laden, [laden])

  const offene = (wuensche ?? []).filter((w) => w.status === 'offen')

  const kopieren = async () => {
    const text =
      'Bitte setze im Repository trh2mbf846-commits/Crawler folgende Verbesserungswünsche um ' +
      '(jeweils mit Tests, danach auf main pushen):\n\n' +
      offene.map((w, i) => `${i + 1}. ${w.titel}\n${w.beschreibung}`).join('\n\n')
    try {
      await navigator.clipboard.writeText(text)
      setKopiert(true)
      setTimeout(() => setKopiert(false), 2500)
    } catch {
      setFehler('Kopieren nicht möglich – Text bitte manuell markieren.')
    }
  }

  const status = async (w: Wunsch, neu: Wunsch['status']) => {
    await setzeWunschStatus(w.id, neu).catch(() => setFehler('Status konnte nicht gespeichert werden.'))
    laden()
  }
  const loeschen = async (w: Wunsch) => {
    if (!window.confirm(`Wunsch „${w.titel}“ löschen?`)) return
    await loescheWunsch(w.id).catch(() => setFehler('Löschen fehlgeschlagen.'))
    laden()
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">Kevins Wunschliste</h2>
          <p className="mt-0.5 text-xs text-ink-muted">
            Kevin ändert selbst keinen Code. Sag ihm, was am Crawler besser werden soll – er notiert es hier als Aufgabe.
            Umsetzen: „Offene kopieren“ und in eine Claude-Code-Sitzung zum Repository „Crawler“ einfügen.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={kopieren}
            disabled={offene.length === 0}
            className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-50"
          >
            {kopiert ? '✓ Kopiert' : `Offene kopieren (${offene.length})`}
          </button>
          <button type="button" onClick={onClose} className="focus-ring rounded-md px-2 py-1.5 text-xs text-ink-muted hover:text-ink">
            Schließen
          </button>
        </div>
      </div>
      {fehler ? <p className="mb-2 text-xs text-urgent-red">{fehler}</p> : null}
      {wuensche === null ? (
        <p className="text-sm text-ink-muted">Lade…</p>
      ) : wuensche.length === 0 ? (
        <p className="text-sm text-ink-muted">
          Noch keine Wünsche. Beispiel an Kevin: „Merk dir als Wunsch: Die Übersicht soll auch nach Bundesland filtern können.“
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {wuensche.map((w) => (
            <li key={w.id} className="rounded-md border border-line px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className={`text-sm font-medium ${w.status === 'erledigt' ? 'text-ink-faint line-through' : 'text-ink'}`}>
                  {w.titel}
                </span>
                <div className="flex gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() => status(w, w.status === 'offen' ? 'erledigt' : 'offen')}
                    className="focus-ring text-brand hover:underline"
                  >
                    {w.status === 'offen' ? 'Erledigt' : 'Wieder öffnen'}
                  </button>
                  <button type="button" onClick={() => loeschen(w)} className="focus-ring text-ink-muted hover:text-urgent-red">
                    Löschen
                  </button>
                </div>
              </div>
              <p className="mt-1 whitespace-pre-line text-xs text-ink-muted">{w.beschreibung}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Assistant() {
  // Verlauf kommt aus dem Browser-Speicher (utils/kevinChat.ts) - bleibt beim Tab-Wechsel und
  // Neustart erhalten, bis er über "Chat löschen" bewusst geleert wird.
  const [verlauf, setVerlauf] = useState<ChatEntry[]>(() => ladeChat().verlauf)
  const [eingabe, setEingabe] = useState('')
  const [senden, setSenden] = useState(() => laufendeKevinAnfrage() !== null)
  const [fehler, setFehler] = useState<string | null>(null)
  const [nichtKonfiguriert, setNichtKonfiguriert] = useState(false)
  const [aktionStatus, setAktionStatus] = useState<Record<string, AktionStatus>>(() => ladeChat().aktionStatus)
  const [aktionLaeuft, setAktionLaeuft] = useState<string | null>(null)
  const [praeferenzenOffen, setPraeferenzenOffen] = useState(false)
  const [wunschlisteOffen, setWunschlisteOffen] = useState(false)
  const endeRef = useRef<HTMLDivElement>(null)
  const aktiv = useRef(true)

  useEffect(() => {
    aktiv.current = true
    return () => {
      aktiv.current = false
    }
  }, [])

  useEffect(() => {
    speichereChat({ verlauf, aktionStatus })
  }, [verlauf, aktionStatus])

  useEffect(() => {
    endeRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [verlauf, aktionStatus])

  // Hat Kevin noch geantwortet, während ein anderer Tab offen war? Dann nach Abschluss nachladen.
  useEffect(() => {
    const anfrage = laufendeKevinAnfrage()
    if (!anfrage) return
    anfrage.finally(() => {
      if (!aktiv.current) return
      setVerlauf(ladeChat().verlauf)
      setSenden(false)
    })
  }, [])

  const ladeKurzbericht = useCallback(() => {
    fetchAssistantDigest()
      .then((digest) => {
        if (!aktiv.current) return
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

  // Kurzbericht nur für einen leeren Chat - ein gespeicherter Verlauf wird nicht überschrieben.
  useEffect(() => {
    if (ladeChat().verlauf.length === 0 && laufendeKevinAnfrage() === null) ladeKurzbericht()
  }, [ladeKurzbericht])

  const chatLoeschen = useCallback(() => {
    if (!window.confirm('Den gesamten Chat mit Crawler Kevin löschen? Das lässt sich nicht rückgängig machen.')) return
    loescheChat()
    setVerlauf([])
    setAktionStatus({})
    setFehler(null)
    ladeKurzbericht()
  }, [ladeKurzbericht])

  const absenden = useCallback(
    async (text: string) => {
      const nachricht = text.trim()
      if (!nachricht || senden) return

      const userEintrag: ChatEntry = { id: crypto.randomUUID(), rolle: 'user', text: nachricht }
      const bisherigerVerlauf = verlauf.map(({ rolle, text }) => ({ rolle, text }))
      setVerlauf((prev) => [...prev, userEintrag])
      speichereChat({ verlauf: [...verlauf, userEintrag], aktionStatus })
      setEingabe('')
      setSenden(true)
      setFehler(null)

      // Die Antwort wird direkt in den Speicher geschrieben - so geht sie auch dann nicht verloren,
      // wenn inzwischen ein anderer Tab geöffnet wurde (Komponente nicht mehr sichtbar).
      const anfrage = (async () => {
        try {
          const ergebnis = await sendAssistantMessage(nachricht, bisherigerVerlauf)
          const chat = haengeAn({
            id: crypto.randomUUID(),
            rolle: 'assistant',
            text: ergebnis.antwort,
            tenders: ergebnis.tenders,
            vorschlag: ergebnis.vorschlag,
          })
          if (aktiv.current) {
            setNichtKonfiguriert(!ergebnis.verfuegbar)
            setVerlauf(chat.verlauf)
          }
        } catch (err) {
          if (aktiv.current) setFehler(err instanceof ApiError ? err.message : 'Crawler Kevin konnte nicht antworten.')
        } finally {
          if (aktiv.current) setSenden(false)
        }
      })()
      merkeLaufendeAnfrage(anfrage)
      await anfrage
    },
    [senden, verlauf, aktionStatus]
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
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={chatLoeschen}
            disabled={senden || verlauf.length === 0}
            className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            🗑 Chat löschen
          </button>
          <button
            type="button"
            onClick={() => setWunschlisteOffen((prev) => !prev)}
            className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            📝 Wunschliste
          </button>
          <button
            type="button"
            onClick={() => setPraeferenzenOffen((prev) => !prev)}
            className="focus-ring rounded-md border border-line bg-surface px-3 py-1.5 text-sm font-medium text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            ⚙ Präferenzen
          </button>
        </div>
      </div>

      {praeferenzenOffen ? <PraeferenzenPanel onClose={() => setPraeferenzenOffen(false)} /> : null}
      {wunschlisteOffen ? <WunschlistePanel onClose={() => setWunschlisteOffen(false)} /> : null}

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
