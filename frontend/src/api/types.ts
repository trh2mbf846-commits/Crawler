export type KiRelevanzScore = 'stark' | 'moeglich' | 'nicht' | null

export type TenderStatus = 'neu' | 'aktualisiert' | 'frist_bald' | 'abgelaufen' | 'vergeben'

export type Zugangsart = 'oeffentlich' | 'registrierung_erforderlich'

// inaktiv = bewusst nicht angebunden, neu = aktiv, aber noch nie gelaufen (beides kein Problemzustand)
export type StatusAmpel = 'gruen' | 'gelb' | 'rot' | 'inaktiv' | 'neu'

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
  frist_quelle?: 'seite' | 'ki' | null
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
  moeglicherweise_duplikat_hinweis: string | null
  gemerkt: boolean
  merk_notiz: string | null
  erfasst_am: string
  zuletzt_geprueft_am: string
}

export interface Bewertung {
  empfehlung: 'bewerben' | 'pruefen' | 'nicht_bewerben'
  passwert: number
  zusammenfassung: string
  begruendung: string
  ausschlusskriterien: string[]
  pflichtnachweise: string[]
  zuschlagskriterien: string[]
  fristen: string[]
  fehlende_nachweise: string[]
  risiken: string[]
  naechste_schritte: string[]
  passende_referenzen: string[]
  entfernt_ohne_beleg: number
  quellen: string[]
  modell: string
  firmenprofil_fehlte: boolean
  bewertet_am: string | null
}

export interface ChecklistenPunkt {
  id: string
  text: string
  art: 'nachweis' | 'ausschluss' | 'frist' | 'eigen'
  status: 'offen' | 'vorhanden' | 'fehlt' | 'erledigt'
}

export interface Frist {
  tender_id: string
  titel: string
  vergabestelle: string | null
  art: 'Angebotsfrist' | 'Fragenfrist'
  datum: string
  grund: string
  direktlink: string
}

export interface Referenz {
  id: string
  titel: string
  auftraggeber: string | null
  jahr: number | null
  volumen: number | null
  beschreibung: string | null
  erstellt_am: string
}

export type ReferenzInput = Omit<Referenz, 'id' | 'erstellt_am'>

export interface Thema {
  id: string
  name: string
  stichworte: string[]
  ki_bezogen: boolean
  aktiv: boolean
}

export type ThemaInput = Omit<Thema, 'id'>

export interface Wunsch {
  id: string
  titel: string
  beschreibung: string
  status: 'offen' | 'erledigt'
  erstellt_am: string
}

export interface TenderDetail extends Tender {
  bewertung?: Bewertung | null
  checkliste: ChecklistenPunkt[]
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
  qualitaet?: { anzahl: number; quoten: Record<string, number> } | null
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
  automatisch_um?: string | null
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

export interface AssistantMessage {
  rolle: 'user' | 'assistant'
  text: string
}

export interface AssistantActionProposal {
  name: string
  input: Record<string, unknown>
  beschreibung: string
}

export interface AssistantChatResult {
  antwort: string
  verfuegbar: boolean
  tenders: Tender[]
  vorschlag: AssistantActionProposal | null
}

export interface AssistantActionResult {
  erfolg: boolean
  meldung: string
}

export interface AssistantPreferences {
  prioritaeten_text: string | null
  firmenprofil?: string | null
  bevorzugte_kategorien: string[]
  bevorzugte_regionen: string[]
  mindestwert: number | null
}

export interface AssistantDigest {
  text: string
  neue_relevante_anzahl: number
  bald_ablaufend_anzahl: number
  portale_mit_problem: string[]
  tenders: Tender[]
}

export interface TenderQuery {
  q?: string
  portal?: string[]
  kategorie?: string[]
  ki_relevanz_min?: 'stark' | 'moeglich'
  frist_bis?: string
  status?: TenderStatus | 'alle'
  bedeutung?: boolean
  sort?: TenderSort
  page?: number
  page_size?: number
}
