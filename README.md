# Ausschreibungs-Crawler & Suchportal

Webanwendung zur automatisierten Suche nach öffentlichen Ausschreibungen mit Schwerpunkt
Künstliche Intelligenz / KI-Entwicklung, gemäß der Handlungsanweisung vom 31.08.2026 (Vincent
Mews, Version 1.1 inkl. Kapitel 17–25 "Search Agent Operating System").

Dieses Verzeichnis ist ein eigenständiges Projekt innerhalb dieses Repositories und hat
**nichts mit dem Brettspiel-Begleit-Projekt im Repository-Root zu tun** (siehe README dort) -
beide Projekte teilen sich lediglich den Git-Verlauf.

## Wichtiger Hinweis zum aktuellen Stand

Diese Cloud-Entwicklungsumgebung hatte während der Implementierung **keinen ausgehenden
Internetzugriff** (Egress-Proxy blockiert alle externen Domains außer wenigen
Infrastruktur-Diensten). Dadurch konnten die 3 vom Auftraggeber vorgegebenen Portale
(Vergabeplattform Berlin, DB Bieterportal, ITDZ Berlin) **nicht live analysiert oder getestet
werden** - siehe die Rückfrage dazu im Chat vom 31.08.2026 sowie `docs/portal-notes.md`.

**Was trotzdem vollständig steht und mit Test-/Demo-Daten nachweislich funktioniert:**
Datenmodell, komplette 8-Agenten-Kette (Connector → Discovery → Analysis → Normalization →
Duplicate → AI Classification → Search → Source Health), Job-/Eskalations-System,
Ranking-Engine, Scheduler, REST-API und Frontend (Übersicht, Filter, Suche, Detailansicht,
Suchprofile, Quellstatus-Dashboard, Entscheidungs-Posteingang). Ein End-to-End-Test
(`backend/tests/test_pipeline_end_to_end.py`) belegt das mit einem Fake-Connector.

**Was noch fehlt, sobald Netzzugriff verfügbar ist:** die 3 Connectoren sind lauffähige
Gerüste mit klar markierten `# TODO(portal-analyse)`-Selektoren (plausible Annahmen, nicht
verifiziert) - siehe `backend/app/agents/connector/`. Sobald echter Zugriff besteht: robots.txt/
ToS prüfen (`docs/portal-notes.md`), Struktur analysieren, Selektoren anpassen,
`python -m app.run_all_connectors` laufen lassen.

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
