import { useCallback, useMemo, useState } from 'react'
import { fetchCategories, fetchPortals, fetchTenders } from '../api/client'
import { FilterBar, type TenderFilters } from '../components/FilterBar'
import { Pagination } from '../components/Pagination'
import { RefreshButton } from '../components/RefreshButton'
import { SourcesSummary } from '../components/SourcesSummary'
import { EmptyView, ErrorView, LoadingView } from '../components/StateViews'
import { TenderCard } from '../components/TenderCard'
import { useAsync } from '../hooks/useAsync'
import { useDebouncedValue } from '../hooks/useDebouncedValue'

const PAGE_SIZE = 20

const defaultFilters: TenderFilters = {
  q: '',
  portal: [],
  kategorie: [],
  ki_relevanz_min: '',
  frist_bis: '',
  status: '',
  sort: 'ranking',
  bedeutung: false,
}

function isDefaultFilters(filters: TenderFilters): boolean {
  return (
    filters.q === '' &&
    filters.portal.length === 0 &&
    filters.kategorie.length === 0 &&
    filters.ki_relevanz_min === '' &&
    filters.frist_bis === '' &&
    filters.status === '' &&
    filters.sort === 'ranking'
  )
}

export function Overview() {
  const [filters, setFilters] = useState<TenderFilters>(defaultFilters)
  const [page, setPage] = useState(1)
  const debouncedQuery = useDebouncedValue(filters.q, 300)

  const { data: portals, reload: reloadPortals } = useAsync(fetchPortals, [])
  const { data: categories } = useAsync(fetchCategories, [])

  const handleFiltersChange = useCallback((next: TenderFilters) => {
    setFilters(next)
    setPage(1)
  }, [])

  const tendersFetcher = useCallback(
    () =>
      fetchTenders({
        q: debouncedQuery || undefined,
        portal: filters.portal.length ? filters.portal : undefined,
        kategorie: filters.kategorie.length ? filters.kategorie : undefined,
        ki_relevanz_min: filters.ki_relevanz_min || undefined,
        frist_bis: filters.frist_bis || undefined,
        status: filters.status || undefined,
        sort: filters.sort,
        bedeutung: filters.bedeutung,
        page,
        page_size: PAGE_SIZE,
      }),
    [debouncedQuery, filters.portal, filters.kategorie, filters.ki_relevanz_min, filters.frist_bis, filters.status, filters.sort, filters.bedeutung, page],
  )

  const { data, loading, error, reload } = useAsync(tendersFetcher, [tendersFetcher])

  const resultCountLabel = useMemo(() => {
    if (!data) return null
    if (data.total === 0) return 'Keine Treffer'
    if (data.total === 1) return '1 Ausschreibung'
    return `${data.total} Ausschreibungen`
  }, [data])

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink">Gesamtübersicht</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Alle erfassten Ausschreibungen, sortiert und gefiltert nach KI-Relevanz, Dringlichkeit und Kategorie.
          </p>
        </div>
        <div className="flex items-start gap-3">
          <SourcesSummary portals={portals ?? []} />
          <RefreshButton
            onDone={() => {
              reload()
              reloadPortals()
            }}
          />
        </div>
      </div>

      <FilterBar filters={filters} onChange={handleFiltersChange} portals={portals ?? []} categories={categories ?? []} />

      {resultCountLabel ? <p className="text-sm text-ink-faint">{resultCountLabel}</p> : null}

      {loading ? <LoadingView label="Lade Ausschreibungen…" /> : null}

      {!loading && error ? (
        <ErrorView title="Ausschreibungen konnten nicht geladen werden" description={error} action={{ label: 'Erneut versuchen', onClick: reload }} />
      ) : null}

      {!loading && !error && data && data.items.length === 0 ? (
        <EmptyView
          title="Keine Ausschreibungen gefunden"
          description="Passe die Filter oder den Suchbegriff an, um mehr Treffer zu sehen."
          action={!isDefaultFilters(filters) ? { label: 'Filter zurücksetzen', onClick: () => handleFiltersChange(defaultFilters) } : undefined}
        />
      ) : null}

      {!loading && !error && data && data.items.length > 0 ? (
        <>
          <div className="flex flex-col gap-3">
            {data.items.map((tender) => (
              <TenderCard key={tender.id} tender={tender} query={debouncedQuery} />
            ))}
          </div>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={setPage} />
        </>
      ) : null}
    </div>
  )
}
