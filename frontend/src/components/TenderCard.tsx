import { Link } from 'react-router-dom'
import type { Tender } from '../api/types'
import { formatDate, truncate } from '../utils/format'
import { getUrgencyLevel } from '../utils/tender'
import { CategoryTags, KiBadge, PortalBadge, UrgencyBadge } from './Badges'
import { Highlight } from './Highlight'

interface TenderCardProps {
  tender: Tender
  query?: string
}

const urgencyBorder: Record<string, string> = {
  critical: 'border-l-urgent-red',
  warning: 'border-l-urgent-yellow',
  expired: 'border-l-line',
  normal: 'border-l-transparent',
  unknown: 'border-l-transparent',
}

export function TenderCard({ tender, query = '' }: TenderCardProps) {
  const urgency = getUrgencyLevel(tender.angebotsfrist, tender.status)
  const isExpired = urgency === 'expired'

  return (
    <article
      className={`rounded-lg border border-l-4 border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-md ${urgencyBorder[urgency]} ${isExpired ? 'opacity-60' : ''}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <PortalBadge name={tender.portal.name} />
            <KiBadge score={tender.ki_relevanz_score} />
            {tender.gemerkt ? (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-brand-light px-2 py-0.5 text-xs font-medium text-brand"
                title={tender.merk_notiz ?? 'Gemerkt'}
              >
                ★ Gemerkt
              </span>
            ) : null}
          </div>
          <h3 className="text-base font-semibold leading-snug text-ink">
            <Link to={`/tenders/${tender.id}`} className="focus-ring rounded hover:text-brand">
              <Highlight text={tender.titel} query={query} />
            </Link>
          </h3>
          <p className="mt-0.5 text-sm text-ink-muted">
            {tender.vergabestelle ? <Highlight text={tender.vergabestelle} query={query} /> : 'Vergabestelle unbekannt'}
            {tender.ort_region ? ` · ${tender.ort_region}` : ''}
          </p>
        </div>
        <UrgencyBadge angebotsfrist={tender.angebotsfrist} status={tender.status} />
      </div>

      {tender.kurzbeschreibung ? (
        <p className="mt-2 text-sm text-ink-muted">
          <Highlight text={truncate(tender.kurzbeschreibung, 220)} query={query} />
        </p>
      ) : null}

      {tender.moeglicherweise_duplikat_hinweis ? (
        <p className="mt-2 text-xs italic text-ink-faint" title={tender.moeglicherweise_duplikat_hinweis}>
          ⓘ {tender.moeglicherweise_duplikat_hinweis}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <CategoryTags categories={tender.kategorien} />
        <div className="flex items-center gap-3 text-xs text-ink-faint">
          <span>Veröffentlicht {formatDate(tender.veroeffentlichungsdatum)}</span>
          <span>Score {(tender.gesamtscore * 100).toFixed(0)}%</span>
          <a
            href={tender.direktlink}
            target="_blank"
            rel="noopener noreferrer"
            className="focus-ring rounded font-medium text-brand hover:underline"
          >
            Original ansehen ↗
          </a>
        </div>
      </div>
    </article>
  )
}
