# API-Vertrag Ausschreibungs-Crawler (Backend ↔ Frontend)

Grundlage: Kapitel 6, 7, 11, 17, 20, 21, 23 der Handlungsanweisung. Backend: FastAPI unter
`http://localhost:8000`, Präfix `/api`. Alle Zeitstempel als ISO-8601-Strings (UTC).

## Enums

- `ki_relevanz_score`: `"stark" | "moeglich" | "nicht" | null` (null = noch nicht bewertet)
- `status` (Tender): `"neu" | "aktualisiert" | "frist_bald" | "abgelaufen" | "vergeben"`
- `zugangsart`: `"oeffentlich" | "registrierung_erforderlich"`
- `status_ampel` (Portal): `"gruen" | "gelb" | "rot"`
- `escalation.kategorie`: `"login_erforderlich" | "captcha" | "tos_verbot" | "ip_sperre" | "kategorisierung_unklar" | "sonstiges"`
- `escalation.status`: `"offen" | "beantwortet" | "geparkt"`
- Kategorien (Taxonomie, Kapitel 7 — feste Liste, auch über `/api/categories` abrufbar):
  `"KI & Machine Learning"`, `"Softwareentwicklung & IT-Dienstleistungen"`, `"Cloud & Infrastruktur"`,
  `"Daten & Analytics"`, `"Beratung & Strategie"`, `"Prozessautomatisierung"`, `"Cybersecurity"`,
  `"Sonstige IT"`, `"Nicht-IT"`

## Typen

```ts
interface Tender {
  id: string;
  titel: string;
  kurzbeschreibung: string | null;
  vergabestelle: string | null;
  ort_region: string | null;
  portal: { id: string; name: string };           // Portal-Badge
  veroeffentlichungsdatum: string | null;          // date
  angebotsfrist: string | null;                    // date-time
  fragenfrist: string | null;
  verfahrensart: string | null;
  cpv_codes: string[];
  geschaetzter_wert: number | null;
  direktlink: string;                              // Original-URL, target=_blank
  status: TenderStatus;
  zugangsart: "oeffentlich" | "registrierung_erforderlich";
  ki_relevanz_score: "stark" | "moeglich" | "nicht" | null;
  ki_relevanz_begruendung: string | null;           // falls LLM-gestützt, klar als Einschätzung markiert
  kategorien: string[];
  gesamtscore: number;                              // Ranking Engine, 0..1
  erfasst_am: string;
  zuletzt_geprueft_am: string;
}

interface TenderDetail extends Tender {
  volltext: string | null;
  dokumente: { titel: string | null; url: string }[];
  ranking_aufschluesselung: {
    ki_relevanz: number; dringlichkeit: number;
    profil_uebereinstimmung: number; aktualitaet: number;
  };
}

interface HistoryEntry {
  feld: string; alter_wert: string | null; neuer_wert: string | null; erkannt_am: string;
}

interface PortalHealth {
  id: string; name: string; betreiber: string | null; base_url: string; aktiv: boolean;
  robots_status: "geprueft_ok" | "geprueft_einschraenkung" | "ungeprueft";
  tos_hinweis: string | null;
  status_ampel: "gruen" | "gelb" | "rot";
  letzter_erfolgreicher_lauf: string | null;
  letzte_trefferzahl: number | null;
  fehlerrate_gleitend: number | null;               // 0..1, letzte Läufe
  meldung: string | null;                            // Klartext-Grund für gelb/rot
}

interface SearchProfile {
  id: string; name: string; portale: string[] /* portal ids */; keywords: string[];
  filter_json: Record<string, unknown>; aktiv: boolean; erstellt_am: string;
  neue_treffer_anzahl?: number;                       // ungesehene Treffer, für Badge
}

interface Escalation {
  id: string; job_id: string | null; kategorie: string; kontext: string;
  optionen: string[]; empfehlung: string | null;
  status: "offen" | "beantwortet" | "geparkt"; entscheidung: string | null;
  erstellt_am: string; beantwortet_am: string | null;
}
```

## Endpunkte

- `GET /api/tenders?q=&portal=&kategorie=&ki_relevanz_min=&frist_bis=&status=&sort=ranking|frist|veroeffentlichung&page=&page_size=`
  → `{ items: Tender[]; total: number; page: number; page_size: number }`
  Filter sind kombinierbar (UND-Verknüpfung), `portal`/`kategorie` als Mehrfachwerte
  (`?portal=itdz-berlin&portal=db-bieterportal`). `sort` Default `ranking`.
- `GET /api/tenders/{id}` → `TenderDetail`
- `GET /api/tenders/{id}/history` → `HistoryEntry[]`
- `GET /api/portals` → `PortalHealth[]`
- `GET /api/search-profiles` → `SearchProfile[]`
- `POST /api/search-profiles` (Body ohne id/erstellt_am) → `SearchProfile` (201)
- `PUT /api/search-profiles/{id}` → `SearchProfile`
- `DELETE /api/search-profiles/{id}` → 204
- `GET /api/search-profiles/{id}/hits?page=` → `{ items: Tender[]; total: number }`
- `GET /api/escalations?status=offen|beantwortet|geparkt` → `Escalation[]`
- `POST /api/escalations/{id}/resolve` Body `{ entscheidung: string }` → `Escalation`
- `GET /api/categories` → `string[]`
- `POST /api/portals/{id}/run` → `{ started: true }` (manueller Testlauf eines Connectors)

## Oberflächen-Anforderungen (Kapitel 11) — Kurzfassung für das Frontend

1. **Gesamtübersicht** (Startseite, zentrales Element): Karten-/Listenansicht aller Tenders.
   Je Eintrag: Titel, Vergabestelle, Portal-Badge, Frist mit Dringlichkeits-Ampel (rot <7 Tage,
   gelb <30 Tage, sonst neutral; abgelaufen ausgegraut), KI-Relevanz-Badge (stark/möglich/nicht,
   farblich abgesetzt), Kategorie-Tags, Kurzbeschreibung (gekürzt), Direktlink „Original ansehen“
   öffnet `direktlink` in neuem Tab (`target="_blank" rel="noopener noreferrer"`).
2. **Filterleiste**: alle Filterdimensionen aus Kapitel 7 kombinierbar, Änderungen wirken sofort
   (kein Seiten-Reload) — Debounce für Freitext ok.
3. **Volltextsuche**: über Titel/Kurzbeschreibung/Vergabestelle, Treffer im Text hervorheben
   (`<mark>`).
4. **Sortierung**: Frist (Standard: dringlichste zuerst — nach Ranking-Score als Default gemäß
   Kapitel 20, umschaltbar auf Frist/Veröffentlichungsdatum/KI-Relevanz).
5. **Suchprofile**: eigener Bereich zum Anlegen/Bearbeiten/Löschen, Treffer je Profil als eigener
   gefilterter Feed, Badge mit Anzahl neuer/ungesehener Treffer.
6. **Detailansicht**: alle Felder, Änderungshistorie als Zeitleiste, Ranking-Aufschlüsselung
   (Kapitel 20.4 — 4 Teil-Scores sichtbar, z. B. kleine Balken), gut sichtbarer „Original ansehen“-
   Link.
7. **Quellstatus-Dashboard** (Kapitel 21.6): eigener Bereich, Ampel je Portal, Zeitpunkt letzter
   erfolgreicher Lauf, Trend (Trefferzahl/Fehlerrate), robots.txt/ToS-Status sichtbar, Button für
   manuellen Testlauf.
8. **Entscheidungs-Posteingang** (Kapitel 17.2, 21.4): Liste offener Eskalationen mit Kontext,
   Optionen, Empfehlung; Auswahl/Freitext zum Auflösen (`POST .../resolve`).
9. **Gestaltung** (Kapitel 11.7): aufgeräumt, ruhige Farbgebung, gezielte Akzentfarben nur für
   Dringlichkeit/KI-Relevanz, Desktop-first, aber auf mobilen Geräten nutzbar. Keine unnötige
   visuelle Ablenkung.

## Betrieb / Konfiguration Frontend

- Vite + React + TypeScript, eigenständiges Projekt unter `ausschreibungscrawler/frontend`
  (unabhängig vom Haupt-Repo-Spiel, aber gleiche Tooling-Konventionen).
- API-Basis-URL über `VITE_API_BASE_URL`, Default `http://localhost:8000/api`.
- Dev-Server-Port `5174` (damit parallel zum Haupt-Repo-Vite-Server auf 5173 lauffähig), siehe
  `vite.config.ts`.
- Kein Backend beim Frontend-Build zwingend erreichbar — für die UI-Entwicklung reicht Arbeiten
  gegen die obigen Typen; ein `npm run dev` muss auch ohne laufendes Backend starten (Fehler beim
  Datenladen freundlich anzeigen, nicht crashen).
