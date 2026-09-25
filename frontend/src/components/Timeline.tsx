import type { HistoryEntry } from '../api/types'
import { formatDateTime } from '../utils/format'

const fieldLabels: Record<string, string> = {
  status: 'Status',
  angebotsfrist: 'Angebotsfrist',
  fragenfrist: 'Fragenfrist',
  geschaetzter_wert: 'Geschätzter Wert',
  titel: 'Titel',
  kurzbeschreibung: 'Kurzbeschreibung',
  ki_relevanz_score: 'KI-Relevanz',
}

function fieldLabel(feld: string): string {
  return fieldLabels[feld] ?? feld
}

export function Timeline({ entries }: { entries: HistoryEntry[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-ink-faint">Noch keine Änderungen erfasst.</p>
  }

  return (
    <ol className="relative flex flex-col gap-4 border-l border-line pl-5">
      {entries.map((entry, index) => (
        <li key={`${entry.feld}-${entry.erkannt_am}-${index}`} className="relative">
          <span className="absolute -left-[1.42rem] top-1 h-2.5 w-2.5 rounded-full border-2 border-surface bg-brand" aria-hidden />
          <p className="text-xs text-ink-faint">{formatDateTime(entry.erkannt_am)}</p>
          <p className="text-sm text-ink">
            <span className="font-medium">{fieldLabel(entry.feld)}</span> geändert
            {entry.alter_wert !== null || entry.neuer_wert !== null ? (
              <>
                {': '}
                <span className="text-ink-muted line-through">{entry.alter_wert ?? '–'}</span>
                {' → '}
                <span className="font-medium">{entry.neuer_wert ?? '–'}</span>
              </>
            ) : null}
          </p>
        </li>
      ))}
    </ol>
  )
}
