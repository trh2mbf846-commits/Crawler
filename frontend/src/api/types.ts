export type KiRelevanzScore = 'stark' | 'moeglich' | 'nicht' | null

export type TenderStatus = 'neu' | 'aktualisiert' | 'frist_bald' | 'abgelaufen' | 'vergeben'

export type Zugangsart = 'oeffentlich' | 'registrierung_erforderlich'

export type StatusAmpel = 'gruen' | 'gelb' | 'rot'

export type EscalationKategorie =
  | 'login_erforderlich'
  | 'captcha'
  | 'tos_verbot'
  | 'ip_sperre'
  | 'kategorisierung_unklar'
  | 'sonstiges'

export type EscalationStatus = 'offen' | 'beantwortet' | 'geparkt'

export type RobotsStatus = 'geprueft_ok' | 'geprueft_einschraenkung' | 'ungeprueft'

export type TenderSort = 'ranking' | 'frist' | 'veroeffentlichung' | 'ki_relevanz'

export const CATEGORIES = [
  'KI & Machine Learning',
  'Softwareentwicklung & IT-Dienstleistungen',
  'Cloud & Infrastruktur',
  'Daten & Analytics',
  'Beratung & Strategie',
  'Prozessautomatisierung',
  'Cybersecurity',
  'Sonstige IT',
  'Nicht-IT',
] as const

export interface Tender {
  id: string
  titel: string
  kurzbeschreibung: string | null
  vergabestelle: string | null
  ort_region: string | null
  portal: { id: string; name: string }
  veroeffentlichungsdatum: string | null
  angebotsfrist: string | null
  fragenfrist: string | null
  verfahrensart: string | null
  cpv_codes: string[]
  geschaetzter_wert: number | null
  direktlink: string
  status: TenderStatus
  zugangsart: Zugangsart
  ki_relevanz_score: KiRelevanzScore
  ki_relevanz_begruendung: string | null
  kategorien: string[]
  gesamtscore: number
  erfasst_am: string
  zuletzt_geprueft_am: string
}

export interface TenderDetail extends Tender {
  volltext: string | null
  dokumente: { titel: string | null; url: string }[]
  ranking_aufschluesselung: {
    ki_relevanz: number
    dringlichkeit: number
    profil_uebereinstimmung: number
    aktualitaet: number
  }
}

export interface HistoryEntry {
  feld: string
  alter_wert: string | null
  neuer_wert: string | null
  erkannt_am: string
}

export interface PortalHealth {
  id: string
  name: string
  betreiber: string | null
  base_url: string
  aktiv: boolean
  robots_status: RobotsStatus
  tos_hinweis: string | null
  status_ampel: StatusAmpel
  letzter_erfolgreicher_lauf: string | null
  letzte_trefferzahl: number | null
  fehlerrate_gleitend: number | null
  meldung: string | null
}

export interface RunAllPortalResult {
  portal_id: string
  portal_name: string
  status_ampel: StatusAmpel | null
  treffer_anzahl: number | null
  fehler: string | null
}

export interface RunAllStatus {
  laeuft: boolean
  gestartet_am: string | null
  beendet_am: string | null
  aktuelle_portale: string[]
  ergebnisse: RunAllPortalResult[]
}

export interface SearchProfile {
  id: string
  name: string
  portale: string[]
  keywords: string[]
  filter_json: Record<string, unknown>
  aktiv: boolean
  erstellt_am: string
  neue_treffer_anzahl?: number
}

export type SearchProfileInput = Omit<SearchProfile, 'id' | 'erstellt_am' | 'neue_treffer_anzahl'>

export interface Escalation {
  id: string
  job_id: string | null
  kategorie: EscalationKategorie
  kontext: string
  optionen: string[]
  empfehlung: string | null
  status: EscalationStatus
  entscheidung: string | null
  erstellt_am: string
  beantwortet_am: string | null
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface TenderQuery {
  q?: string
  portal?: string[]
  kategorie?: string[]
  ki_relevanz_min?: 'stark' | 'moeglich'
  frist_bis?: string
  status?: TenderStatus
  sort?: TenderSort
  page?: number
  page_size?: number
}
