import type { EscalationKategorie, KiRelevanzScore, RobotsStatus, StatusAmpel, TenderStatus, Zugangsart } from '../api/types'
import { daysUntil } from './format'

export type UrgencyLevel = 'expired' | 'critical' | 'warning' | 'normal' | 'unknown'

export function getUrgencyLevel(angebotsfrist: string | null, status: TenderStatus): UrgencyLevel {
  if (status === 'abgelaufen') return 'expired'
  const days = daysUntil(angebotsfrist)
  if (days === null) return 'unknown'
  if (days < 0) return 'expired'
  if (days < 7) return 'critical'
  if (days < 30) return 'warning'
  return 'normal'
}

export const urgencyLabel: Record<UrgencyLevel, string> = {
  expired: 'Abgelaufen',
  critical: 'Dringend',
  warning: 'Bald fällig',
  normal: 'Ausreichend Zeit',
  unknown: 'Frist unbekannt',
}

export const statusLabel: Record<TenderStatus, string> = {
  neu: 'Neu',
  aktualisiert: 'Aktualisiert',
  frist_bald: 'Frist bald',
  abgelaufen: 'Abgelaufen',
  vergeben: 'Vergeben',
}

export const kiRelevanzLabel: Record<NonNullable<KiRelevanzScore>, string> = {
  stark: 'Stark KI-relevant',
  moeglich: 'Möglich KI-relevant',
  nicht: 'Nicht KI-relevant',
}

export const zugangsartLabel: Record<Zugangsart, string> = {
  oeffentlich: 'Öffentlich zugänglich',
  registrierung_erforderlich: 'Registrierung erforderlich',
}

export const statusAmpelLabel: Record<StatusAmpel, string> = {
  gruen: 'Ordnungsgemäß',
  gelb: 'Eingeschränkt',
  rot: 'Gestört',
}

export const robotsStatusLabel: Record<RobotsStatus, string> = {
  geprueft_ok: 'robots.txt geprüft – ok',
  geprueft_einschraenkung: 'robots.txt geprüft – Einschränkung',
  ungeprueft: 'robots.txt ungeprüft',
}

export const escalationKategorieLabel: Record<EscalationKategorie, string> = {
  login_erforderlich: 'Login erforderlich',
  captcha: 'Captcha',
  tos_verbot: 'ToS-Verbot',
  ip_sperre: 'IP-Sperre',
  kategorisierung_unklar: 'Kategorisierung unklar',
  sonstiges: 'Sonstiges',
}
