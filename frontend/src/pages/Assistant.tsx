import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, sendAssistantMessage } from '../api/client'
import type { AssistantMessage, Tender } from '../api/types'
import { TenderCard } from '../components/TenderCard'

interface ChatEntry extends AssistantMessage {
  id: string
  tenders?: Tender[]
}

const BEISPIELE = [
  'Welche KI-relevanten Ausschreibungen laufen in Bayern aus?',
  'Gibt es neue Ausschreibungen zu Cybersecurity?',
  'Wie ist der aktuelle Quellstatus?',
]

export function Assistant() {
  const [verlauf, setVerlauf] = useState<ChatEntry[]>([])
  const [eingabe, setEingabe] = useState('')
  const [senden, setSenden] = useState(false)
  const [fehler, setFehler] = useState<string | null>(null)
  const [nichtKonfiguriert, setNichtKonfiguriert] = useState(false)
  const endeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endeRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [verlauf])

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
          { id: crypto.randomUUID(), rolle: 'assistant', text: ergebnis.antwort, tenders: ergebnis.tenders },
        ])
      } catch (err) {
        setFehler(err instanceof ApiError ? err.message : 'Der KI-Assistent konnte nicht antworten.')
      } finally {
        setSenden(false)
      }
    },
    [senden, verlauf]
  )

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">KI-Assistent</h1>
        <p className="mt-0.5 text-sm text-ink-muted">
          Fragen in natürlicher Sprache zu erfassten Ausschreibungen und zum Quellstatus – ergänzt die
          Übersicht, ersetzt sie nicht. Der Assistent liest nur, er löst keine Läufe aus und ändert keine Daten.
        </p>
      </div>

      {nichtKonfiguriert ? (
        <div className="rounded-md border border-line bg-surface-sunken px-4 py-3 text-sm text-ink-muted">
          Der KI-Assistent ist auf diesem Server nicht konfiguriert (kein <code>ANTHROPIC_API_KEY</code> hinterlegt).
          Nutze in der Zwischenzeit die normale Suche/Filter in der Übersicht.
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

          {verlauf.map((eintrag) => (
            <div key={eintrag.id} className={`flex ${eintrag.rolle === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] ${eintrag.rolle === 'user' ? '' : 'w-full'}`}>
                <div
                  className={`whitespace-pre-line rounded-lg px-3.5 py-2.5 text-sm leading-relaxed ${
                    eintrag.rolle === 'user' ? 'bg-brand text-white' : 'bg-surface-sunken text-ink'
                  }`}
                >
                  {eintrag.text}
                </div>
                {eintrag.tenders && eintrag.tenders.length > 0 ? (
                  <div className="mt-2 flex flex-col gap-2">
                    {eintrag.tenders.map((tender) => (
                      <TenderCard key={tender.id} tender={tender} />
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ))}

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
            placeholder="Frage an den KI-Assistenten…"
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
