import type { KiRelevanzScore, StatusAmpel, TenderStatus } from '../api/types'
import { formatDate } from '../utils/format'
import { getUrgencyLevel, kiRelevanzLabel, statusAmpelLabel, statusLabel, urgencyLabel } from '../utils/tender'

export function UrgencyBadge({ angebotsfrist, status }: { angebotsfrist: string | null; status: TenderStatus }) {
  const level = getUrgencyLevel(angebotsfrist, status)
  const styles: Record<typeof level, string> = {
    expired: 'bg-surface-sunken text-ink-faint',
    critical: 'bg-urgent-redBg text-urgent-red',
    warning: 'bg-urgent-yellowBg text-urgent-yellow',
    normal: 'bg-surface-sunken text-ink-muted',
    unknown: 'bg-surface-sunken text-ink-faint',
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${styles[level]}`}>
      {level === 'critical' || level === 'warning' ? (
        <span className={`h-1.5 w-1.5 rounded-full ${level === 'critical' ? 'bg-urgent-red' : 'bg-urgent-yellow'}`} aria-hidden />
      ) : null}
      {angebotsfrist ? formatDate(angebotsfrist) : urgencyLabel[level]}
      {level !== 'unknown' && angebotsfrist ? <span className="opacity-70">· {urgencyLabel[level]}</span> : null}
    </span>
  )
}

export function KiBadge({ score }: { score: KiRelevanzScore }) {
  if (!score) {
    return (
      <span className="inline-flex items-center rounded-full bg-surface-sunken px-2.5 py-1 text-xs font-medium text-ink-faint">
        Noch nicht bewertet
      </span>
    )
  }
  const styles: Record<NonNullable<KiRelevanzScore>, string> = {
    stark: 'bg-ki-strongBg text-ki-strong',
    moeglich: 'bg-ki-possibleBg text-ki-possible',
    nicht: 'bg-ki-noneBg text-ki-none',
  }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${styles[score]}`}>
      {kiRelevanzLabel[score]}
    </span>
  )
}

export function StatusBadge({ status }: { status: TenderStatus }) {
  return (
    <span className="inline-flex items-center rounded-full border border-line px-2.5 py-1 text-xs font-medium text-ink-muted">
      {statusLabel[status]}
    </span>
  )
}

export function PortalBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-brand-light px-2.5 py-1 text-xs font-medium text-brand">
      {name}
    </span>
  )
}

export function AmpelDot({ status }: { status: StatusAmpel }) {
  const colors: Record<StatusAmpel, string> = {
    gruen: 'bg-ki-strong',
    gelb: 'bg-urgent-yellow',
    rot: 'bg-urgent-red',
    inaktiv: 'bg-line',
    neu: 'bg-ink-faint',
  }
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${colors[status]}`} aria-hidden />
      <span className="text-sm font-medium text-ink">{statusAmpelLabel[status]}</span>
    </span>
  )
}

export function CategoryTags({ categories }: { categories: string[] }) {
  if (categories.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {categories.map((category) => (
        <span key={category} className="rounded-md bg-surface-sunken px-2 py-0.5 text-xs text-ink-muted">
          {category}
        </span>
      ))}
    </div>
  )
}
