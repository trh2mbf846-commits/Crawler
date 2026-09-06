# Ausschreibungs-Crawler & Suchportal

Webanwendung zur automatisierten Suche nach öffentlichen Ausschreibungen mit Schwerpunkt
Künstliche Intelligenz / KI-Entwicklung, gemäß der Handlungsanweisung vom 31.08.2026 (Vincent
Mews, Version 1.1 inkl. Kapitel 17–25 "Search Agent Operating System").

Dieses Verzeichnis ist ein eigenständiges Projekt innerhalb dieses Repositories und hat
**nichts mit dem Brettspiel-Begleit-Projekt im Repository-Root zu tun** (siehe README dort) -
beide Projekte teilen sich lediglich den Git-Verlauf.

## Aktueller Stand (Update 06.09.2026)

13 Portale/Quellen sind konfiguriert (3 vom Auftraggeber vorgegeben + 10 auf Nutzerwunsch
recherchierte Zusatzquellen, Kapitel 3/16.3), davon **6 mit echtem, live verifiziertem
Connector**:

| Portal | Status | Letzter Testlauf |
|---|---|---|
| Vergabeplattform Berlin (Vergabekooperation Berlin) | ✅ grün | 164 Ausschreibungen |
| ITDZ Berlin | ✅ grün | 3 Ausschreibungen |
| TED – Tenders Electronic Daily | ✅ grün | 424 Ausschreibungen (offizielle REST-API) |
| DTVP – Deutsches Vergabeportal | ✅ grün | 286 Ausschreibungen |
| e-Vergabe des Bundes | ✅ grün | 35 Ausschreibungen |
| Bekanntmachungsservice (Bund/Länder/Kommunen) | ✅ grün | 4744 Ausschreibungen (offizielle OpenData-API, deckt teilw. auch Brandenburg/Deutsche-eVergabe-Vergabestellen ab) |
| DB Bieterportal | ⚠️ Connector fertig (Playwright), scheitert nur an einer Proxy-Einschränkung *dieser* Entwicklungsumgebung (kein Login/CAPTCHA auf dem Portal) |
| 5 weitere (Vergabe24, Vergabemarktplatz Brandenburg, Deutsche eVergabe, subreport ELViS, cosinex) | ⛔ bewusst nicht implementiert - Login-/Abo-Pflicht, robots.txt-Sperre oder Bot-Schutz, jeweils dokumentiert statt umgangen (Kapitel 9.2) |
| Förderdatenbank BMWK/BMBF | ⛔ Bot-Schutz, kein offizieller Datenexport gefunden |

Details je Portal (robots.txt/ToS, Selektoren, Randfälle, Recherche zu offiziellen
Datenquellen als Alternative zum Scraping): `docs/portal-notes.md` und die Docstrings der
jeweiligen Connector-Module (`backend/app/agents/connector/*.py`).

**Vollständig funktionierend (Tests + Live-Läufe):** Datenmodell, komplette 8-Agenten-Kette
(Connector → Discovery → Analysis → Normalization → Duplicate → AI Classification → Search →
Source Health), Job-/Eskalations-System, Ranking-Engine, Scheduler (per Konfiguration
abschaltbar, siehe Deployment unten), REST-API, manueller Aktualisieren-Button (`POST
/api/run-all`) und Frontend (Übersicht, Filter, Suche, Detailansicht, Suchprofile,
Quellstatus-Dashboard mit Quellen-Übersicht, Entscheidungs-Posteingang). 24 automatisierte
Tests plus reale Testläufe gegen 6 Live-Portale mit 5656 echten Ausschreibungen.

Bekannte Einschränkung der neuen Quelle "Bekanntmachungsservice": liefert kein
Angebotsfrist-Feld und überschneidet sich teilweise mit TED/DTVP (dieselbe EU-Ausschreibung
über zwei Quellen) - Details und Abwägung in `docs/portal-notes.md`.

## Projektstruktur

```
ausschreibungscrawler/
├── backend/        Python/FastAPI, SQLAlchemy, Playwright, APScheduler
├── frontend/        React + Vite + TypeScript + Tailwind
└── docs/            API-Vertrag, PostgreSQL-Schema, robots.txt/ToS-Dokumentation
```

## Schnellstart

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.demo_seed        # optional: Testdaten zur UI-Vorschau (klar als "[DEMO]" markiert)
uvicorn app.main:app --reload --port 8000
```

Läuft dann auf `http://localhost:8000`, API unter `/api/*`, interaktive Doku unter `/docs`.
Beim ersten Start werden automatisch die 3 Pflicht-Portale und die Kategorien-Taxonomie
angelegt (`app/seed.py`).

Manueller Testlauf aller drei Connectoren (Phase-1-Abnahmekriterium):

```bash
python -m app.run_all_connectors
```

Tests:

```bash
pytest
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL ggf. anpassen
npm run dev            # http://localhost:5174
```

## Konfiguration

Zentrale Einstellungen (Ranking-Gewichte, Source-Health-Schwellenwerte, optionaler
Claude-API-Key für die LLM-Nachbewertung von Grenzfällen) über Umgebungsvariablen mit Präfix
`CRAWLER_`, siehe `backend/app/config.py`. Ohne `CRAWLER_ANTHROPIC_API_KEY` läuft die
Keyword-/CPV-Klassifikation (Kapitel 4.1/4.2) unverändert weiter - die LLM-Stufe (Kapitel 4.3)
wird dann einfach übersprungen.

## Deployment (Aktualisieren-Button statt Dauerbetrieb)

Nutzerwunsch (01.09.2026): kein dauerhaftes Hintergrund-Update, sondern ein einziger Link, auf
dem ein "Aktualisieren"-Button einmal alle aktiven Portale durchsucht - lokal filtern passiert
danach direkt in der Weboberfläche.

Dafür liegt im Projektordner (`ausschreibungscrawler/`, **nicht** im Repository-Root - das
enthält zusätzlich ein unabhängiges Brettspiel-Projekt) ein `Dockerfile`, das Frontend und
Backend in einem einzigen Container ausliefert (das Backend liefert das gebaute Frontend
selbst mit aus, siehe `backend/app/main.py`). Der periodische Scheduler ist im Image per
`CRAWLER_SCHEDULER_ENABLED=false` fest abgeschaltet - einzige Aktualisierungsquelle ist der
Button (`POST /api/run-all`, mit Live-Fortschritt über `GET /api/run-all/status`).

**Render.com:** `render.yaml` liegt bereits vorbereitet vor (Pfade sind repo-root-relativ).
Entweder diese Datei vor dem Verbinden nach `<repo-root>/render.yaml` kopieren (Render-Blueprints
werden nur dort automatisch erkannt), oder einfacher: in Render "New → Web Service" (kein
Blueprint) wählen, dieses Repository verbinden und **Root Directory auf `ausschreibungscrawler`**
setzen - dann reicht das Dockerfile allein.

**Fly.io:** `fly.toml` liegt direkt in diesem Ordner. Von hier aus (`cd ausschreibungscrawler`)
`fly launch --no-deploy` (App-Name ggf. anpassen, muss global eindeutig sein), dann `fly deploy`.

**Persistenz:** Ohne bezahlten Disk-Zusatz verliert die SQLite-Datenbank ihren Inhalt bei jedem
Neustart/Redeploy - beim nächsten Klick auf "Aktualisieren" ist die Liste aber sofort wieder
gefüllt, was zum Nutzungsmuster "gelegentlich manuell aktualisieren" passt. Für dauerhafte
Historie: Persistent Disk unter `/app/data` hinzufügen, oder auf die in
`docs/schema_postgresql.sql` vorbereitete PostgreSQL-Variante wechseln
(`CRAWLER_DATABASE_URL` entsprechend setzen).

**Lokal testen** (ohne Docker-Daemon geht auch eine manuelle Simulation):

```bash
cd frontend && VITE_API_BASE_URL=/api npm run build
cp -r dist ../backend/static
cd ../backend && CRAWLER_SCHEDULER_ENABLED=false uvicorn app.main:app --port 8000
# http://localhost:8000 liefert dann Frontend + API aus einem Prozess
```

## Weiterführende Dokumente

- `docs/API_CONTRACT.md` – vollständiger REST-API-Vertrag zwischen Backend und Frontend
- `docs/schema_postgresql.sql` – PostgreSQL-DDL für den Produktivbetrieb (Kapitel 22)
- `docs/portal-notes.md` – robots.txt/ToS-Status je Portal (Kapitel 9.3) und offene Punkte
