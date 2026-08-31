# Ausschreibungs-Crawler & Suchportal

Webanwendung zur automatisierten Suche nach öffentlichen Ausschreibungen mit Schwerpunkt
Künstliche Intelligenz / KI-Entwicklung, gemäß der Handlungsanweisung vom 31.08.2026 (Vincent
Mews, Version 1.1 inkl. Kapitel 17–25 "Search Agent Operating System").

Dieses Verzeichnis ist ein eigenständiges Projekt innerhalb dieses Repositories und hat
**nichts mit dem Brettspiel-Begleit-Projekt im Repository-Root zu tun** (siehe README dort) -
beide Projekte teilen sich lediglich den Git-Verlauf.

## Aktueller Stand (Update 31.08.2026, nach Freischaltung des Netzzugriffs)

Netzzugriff für diese Session wurde am 31.08.2026 freigeschaltet (zuvor blockierte der
Egress-Proxy jeglichen allgemeinen Internetzugriff, siehe Rückfrage im Chat). Daraufhin
wurden alle 3 Pflicht-Portale real analysiert und die Connectoren gegen die tatsächliche
Seitenstruktur gebaut und per `python -m app.run_all_connectors` getestet:

- **ITDZ Berlin** ✅ läuft produktiv gegen die echte Seite (robots.txt erlaubt automatisierten
  Zugriff ausdrücklich). Letzter Testlauf: 3 echte, aktuelle Ausschreibungen gefunden,
  Quellstatus grün.
- **Vergabeplattform Berlin** ✅ läuft produktiv gegen die echte Seite (keine robots.txt,
  öffentliche Bekanntmachungssuche ohne Login, sogar Vergabeunterlagen frei zugänglich).
  Letzter Testlauf: 137 echte, aktuelle Ausschreibungen über 3 Seiten gefunden, Quellstatus
  grün.
- **DB Bieterportal** ⚠️ Connector ist vollständig implementiert (Playwright, wie in Kapitel 3
  vorgesehen), scheitert in dieser konkreten Sandbox-Umgebung aber an einer
  Egress-Proxy-Einschränkung (WebSocket-Upgrades werden nicht unterstützt, die reine
  JavaScript-SPA nutzt SignalR/WebSocket) - **kein Login/CAPTCHA auf dem Portal selbst**,
  sondern eine Einschränkung dieser Session. Details, Diagnose und Empfehlung in
  `docs/portal-notes.md`.

Details zu robots.txt/ToS je Portal: `docs/portal-notes.md`.

**Vollständig funktionierend (Tests + Live-Läufe):** Datenmodell, komplette 8-Agenten-Kette
(Connector → Discovery → Analysis → Normalization → Duplicate → AI Classification → Search →
Source Health), Job-/Eskalations-System, Ranking-Engine, Scheduler, REST-API und Frontend
(Übersicht, Filter, Suche, Detailansicht, Suchprofile, Quellstatus-Dashboard,
Entscheidungs-Posteingang). 22 automatisierte Tests plus ein realer Testlauf gegen 2 von 3
Live-Portalen mit insgesamt 140 echten Ausschreibungen.

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

## Weiterführende Dokumente

- `docs/API_CONTRACT.md` – vollständiger REST-API-Vertrag zwischen Backend und Frontend
- `docs/schema_postgresql.sql` – PostgreSQL-DDL für den Produktivbetrieb (Kapitel 22)
- `docs/portal-notes.md` – robots.txt/ToS-Status je Portal (Kapitel 9.3) und offene Punkte
