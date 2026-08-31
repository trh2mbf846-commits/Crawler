const dateFormatter = new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
const dateTimeFormatter = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const currencyFormatter = new Intl.NumberFormat('de-DE', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

export function formatDate(value: string | null | undefined): string {
  if (!value) return '–'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '–'
  return dateFormatter.format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '–'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '–'
  return dateTimeFormatter.format(date)
}

export function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined) return '–'
  return currencyFormatter.format(value)
}

export function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null
  const target = new Date(value)
  if (Number.isNaN(target.getTime())) return null
  const now = new Date()
  const diffMs = target.getTime() - now.getTime()
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

export function truncate(text: string | null | undefined, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength).trimEnd()}…`
}
