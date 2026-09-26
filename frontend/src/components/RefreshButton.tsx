import { useEffect, useRef, useState } from 'react'
import { fetchRunAllStatus, runAllPortals } from '../api/client'
import type { RunAllStatus } from '../api/types'

const POLL_INTERVAL_MS = 2000

export function RefreshButton({ onDone }: { onDone: () => void }) {
  const [status, setStatus] = useState<RunAllStatus | null>(null)
  const [starting, setStarting] = useState(false)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const poll = () => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const next = await fetchRunAllStatus()
        setStatus(next)
        if (!next.laeuft) {
          stopPolling()
          onDone()
        }
      } catch {
        stopPolling()
      }
    }, POLL_INTERVAL_MS)
  }

  useEffect(() => stopPolling, [])

  // Auch Läufe anzeigen, die nicht per Klick gestartet wurden (tägliche automatische
  // Aktualisierung, Crawler Kevin): beim Öffnen und danach jede Minute kurz nachsehen.
  useEffect(() => {
    let abgebrochen = false
    const pruefen = async () => {
      try {
        const next = await fetchRunAllStatus()
        if (abgebrochen) return
        setStatus(next)
        if (next.laeuft && pollRef.current === null) poll()
      } catch {
        // Backend kurz nicht erreichbar - beim nächsten Intervall erneut versuchen.
      }
    }
    void pruefen()
    const intervall = setInterval(pruefen, 60_000)
    return () => {
      abgebrochen = true
      clearInterval(intervall)
    }
    // poll ist stabil genug (setzt nur Intervalle), bewusst nur beim Einhängen registriert.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleClick = async () => {
    setStarting(true)
    try {
      const next = await runAllPortals()
      setStatus(next)
      poll()
    } catch {
      // Läuft evtl. schon (409) - trotzdem den bestehenden Lauf beobachten.
      try {
        const next = await fetchRunAllStatus()
        setStatus(next)
        if (next.laeuft) poll()
      } catch {
        // Backend nicht erreichbar - Button bleibt nutzbar, nächster Klick versucht erneut.
      }
    } finally {
      setStarting(false)
    }
  }

  const laeuft = status?.laeuft ?? false
  const fertigCount = status?.ergebnisse.length ?? 0

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={laeuft || starting}
        className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-1.5 text-xs font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-70 hover:border-brand"
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          className={laeuft ? 'animate-spin' : ''}
          aria-hidden
        >
          <path d="M21 12a9 9 0 1 1-2.64-6.36" />
          <path d="M21 3v6h-6" />
        </svg>
        {laeuft ? 'Aktualisiere…' : 'Aktualisieren'}
      </button>
      {laeuft ? (
        <span className="max-w-[280px] text-right text-xs text-ink-faint">
          {status?.aktuelle_portale.length ? `Durchsuche parallel: ${status.aktuelle_portale.join(', ')}` : 'Startet…'}
          {fertigCount > 0 ? ` (${fertigCount} fertig)` : ''}
        </span>
      ) : null}
      {!laeuft && status?.beendet_am ? (
        <span className="text-xs text-ink-faint">
          Fertig · {status.ergebnisse.filter((e) => e.status_ampel === 'gruen').length}/{status.ergebnisse.length}{' '}
          Quellen erfolgreich
        </span>
      ) : null}
      {!laeuft && status?.automatisch_um ? (
        <span className="text-xs text-ink-faint">Automatisch täglich um {status.automatisch_um} Uhr</span>
      ) : null}
    </div>
  )
}
