import type { PortalHealth, TenderSort, TenderStatus } from '../api/types'
import { statusLabel } from '../utils/tender'

export interface TenderFilters {
  q: string
  portal: string[]
  kategorie: string[]
  ki_relevanz_min: '' | 'moeglich' | 'stark'
  frist_bis: string
  status: '' | TenderStatus
  sort: TenderSort
}

interface FilterBarProps {
  filters: TenderFilters
  onChange: (filters: TenderFilters) => void
  portals: PortalHealth[]
  categories: string[]
}

const sortOptions: { value: TenderSort; label: string }[] = [
  { value: 'ranking', label: 'Ranking-Score' },
  { value: 'frist', label: 'Frist (dringlichste zuerst)' },
  { value: 'veroeffentlichung', label: 'Veröffentlichung (neueste zuerst)' },
  { value: 'ki_relevanz', label: 'KI-Relevanz' },
]

const statusOptions: TenderStatus[] = ['neu', 'aktualisiert', 'frist_bald', 'abgelaufen', 'vergeben']

function toggleValue(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((entry) => entry !== value) : [...list, value]
}

export function FilterBar({ filters, onChange, portals, categories }: FilterBarProps) {
  const set = <K extends keyof TenderFilters>(key: K, value: TenderFilters[K]) => {
    onChange({ ...filters, [key]: value })
  }

  const hasActiveFilters =
    filters.portal.length > 0 ||
    filters.kategorie.length > 0 ||
    filters.ki_relevanz_min !== '' ||
    filters.frist_bis !== '' ||
    filters.status !== ''

  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <input
            type="search"
            value={filters.q}
            onChange={(event) => set('q', event.target.value)}
            placeholder="Suche nach Titel, Vergabestelle, Beschreibung…"
            className="focus-ring w-full rounded-md border border-line bg-surface px-3 py-2 text-sm placeholder:text-ink-faint"
          />
        </div>
        <select
          value={filters.sort}
          onChange={(event) => set('sort', event.target.value as TenderSort)}
          className="focus-ring rounded-md border border-line bg-surface px-3 py-2 text-sm"
        >
          {sortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              Sortierung: {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <select
          value={filters.status}
          onChange={(event) => set('status', event.target.value as TenderFilters['status'])}
          className="focus-ring rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs text-ink-muted"
        >
          <option value="">Alle Status</option>
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              {statusLabel[status]}
            </option>
          ))}
        </select>

        <select
          value={filters.ki_relevanz_min}
          onChange={(event) => set('ki_relevanz_min', event.target.value as TenderFilters['ki_relevanz_min'])}
          className="focus-ring rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs text-ink-muted"
        >
          <option value="">Jede KI-Relevanz</option>
          <option value="moeglich">Mindestens möglich relevant</option>
          <option value="stark">Nur stark relevant</option>
        </select>

        <label className="flex items-center gap-1.5 text-xs text-ink-muted">
          Frist bis
          <input
            type="date"
            value={filters.frist_bis}
            onChange={(event) => set('frist_bis', event.target.value)}
            className="focus-ring rounded-md border border-line bg-surface px-2 py-1.5"
          />
        </label>

        {hasActiveFilters ? (
          <button
            type="button"
            onClick={() =>
              onChange({ ...filters, portal: [], kategorie: [], ki_relevanz_min: '', frist_bis: '', status: '' })
            }
            className="focus-ring ml-auto rounded-md px-2 py-1 text-xs font-medium text-brand hover:underline"
          >
            Filter zurücksetzen
          </button>
        ) : null}
      </div>

      {portals.length > 0 ? (
        <div className="mt-3 border-t border-line pt-3">
          <p className="mb-1.5 text-xs font-medium text-ink-faint">Portal</p>
          <div className="flex flex-wrap gap-1.5">
            {portals.map((portal) => (
              <button
                key={portal.id}
                type="button"
                onClick={() => set('portal', toggleValue(filters.portal, portal.id))}
                className={`focus-ring rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                  filters.portal.includes(portal.id)
                    ? 'border-brand bg-brand-light text-brand'
                    : 'border-line text-ink-muted hover:bg-surface-sunken'
                }`}
              >
                {portal.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {categories.length > 0 ? (
        <div className="mt-3 border-t border-line pt-3">
          <p className="mb-1.5 text-xs font-medium text-ink-faint">Kategorie</p>
          <div className="flex flex-wrap gap-1.5">
            {categories.map((category) => (
              <button
                key={category}
                type="button"
                onClick={() => set('kategorie', toggleValue(filters.kategorie, category))}
                className={`focus-ring rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                  filters.kategorie.includes(category)
                    ? 'border-brand bg-brand-light text-brand'
                    : 'border-line text-ink-muted hover:bg-surface-sunken'
                }`}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
