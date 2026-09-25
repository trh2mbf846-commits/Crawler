# Ausschreibungs-Crawler & Suchportal

Webanwendung zur automatisierten Suche nach öffentlichen Ausschreibungen mit Schwerpunkt
Künstliche Intelligenz / KI-Entwicklung, gemäß der Handlungsanweisung vom 31.08.2026 (Vincent
Mews, Version 1.1 inkl. Kapitel 17–25 "Search Agent Operating System").

Dieses Verzeichnis ist ein eigenständiges Projekt innerhalb dieses Repositories und hat
**nichts mit dem Brettspiel-Begleit-Projekt im Repository-Root zu tun** (siehe README dort) -
beide Projekte teilen sich lediglich den Git-Verlauf.

## Aktueller Stand (Update 25.09.2026, neues Portal Bayern)

14 Portale/Quellen sind konfiguriert (3 vom Auftraggeber vorgegeben + 11 auf Nutzerwunsch
recherchierte Zusatzquellen, Kapitel 3/16.3), davon **7 mit echtem, live verifiziertem
Connector**. Letzter kompletter Aktualisieren-Lauf (alle Portale parallel, aus leerer
Datenbank): **7306 Ausschreibungen nach Duplikaterkennung in 27 Minuten** (Rohtreffer vor
Duplikaterkennung: 7739 - Differenz vor allem durch die erwartete Überschneidung
Bekanntmachungsservice/TED/DTVP, siehe unten):

| Portal | Status | Letzter Testlauf |
|---|---|---|
| Bekanntmachungsservice (Bund/Länder/Kommunen) | ✅ grün | 5376 Ausschreibungen (offizielle OpenData-API, deckt teilw. auch Brandenburg/Deutsche-eVergabe-Vergabestellen ab) |
| TED – Tenders Electronic Daily | ✅ grün | 1000 Ausschreibungen (offizielle REST-API) |
| DTVP – Deutsches Vergabeportal | ✅ grün | 539 Ausschreibungen |
| e-Vergabe des Bundes | ✅ grün | 300 Ausschreibungen |
| Vergabeplattform Berlin (Vergabekooperation Berlin) | ✅ grün | 118 Ausschreibungen |
| Vergabeplattform Bayern (vergabe.bayern.de) | ✅ grün | 402 Ausschreibungen (RIB/iTWO-Plattform, neu seit 25.09.2026) |
| ITDZ Berlin | ✅ grün | 4 Ausschreibungen |
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
/api/run-all`), KI-Assistent (siehe unten) und Frontend (Übersicht, Filter, Suche,
Detailansicht, Suchprofile, Quellstatus-Dashboard mit Quellen-Übersicht,
Entscheidungs-Posteingang, KI-Assistent-Tab). 33 automatisierte Tests plus reale Testläufe
gegen 7 Live-Portale mit 7306 echten Ausschreibungen.

### KI-Assistent (Update 25.09.2026)

Nutzeranfrage: "Richtung KI-Agent, aber die Übersicht soll bleiben". Ergänzt - nicht ersetzt -
die bestehende Übersicht um einen zusätzlichen Tab (`/assistant`, `frontend/src/pages/
Assistant.tsx`): eine Chat-Oberfläche, in der Fragen in natürlicher Sprache zu erfassten
Ausschreibungen und zum Quellstatus gestellt werden können (z. B. "welche KI-relevanten
Ausschreibungen in Bayern laufen in den nächsten 14 Tagen aus?").

Technisch ein Tool-Use-Agent auf Basis der Anthropic API (`backend/app/agents/assistant.py`,
`POST /api/assistant/chat`): Claude entscheidet selbst, ob und welches der beiden Werkzeuge
(`suche_ausschreibungen`, `quellstatus`) es für eine Antwort braucht, ruft es auf und fasst das
Ergebnis zusammen. Beide Werkzeuge nutzen dieselbe, bereits geprüfte Such-/Health-Logik wie die
REST-API (aus `api/tenders.py` in `app/tender_queries.py` herausgelöst, damit Chat und normale
Suche nicht auseinanderlaufen). Bewusst **keine schreibenden Werkzeuge** - der Assistent löst
keine Läufe aus und ändert keine Daten, er beantwortet nur Fragen zum vorhandenen Bestand.

Ohne konfigurierten `CRAWLER_ANTHROPIC_API_KEY` (wie in dieser Entwicklungsumgebung) liefert der
Endpunkt einen klaren Hinweis statt eines Fehlers - live per Browser-Test verifiziert (Screenshot-
Verifikation: Übersicht bleibt unverändert Startseite, neuer Tab funktioniert, Fallback-Hinweis
erscheint korrekt). Die eigentliche Tool-Use-Schleife ist mit einem eingeschleusten Fake-Client
automatisiert getestet (`tests/test_assistant.py`), da diese Umgebung selbst keinen API-Key hat.

### Neues Portal: Vergabeplattform Bayern (Update 25.09.2026)

Nutzeranfrage: "können wir mehr Portale dazu fügen?". Recherche ergab: `vergabe.bayern.de`
bettet seine Bekanntmachungen aus der RIB/iTWO-Plattform (`meinauftrag.rib.de`) ein - derselben
Software-Familie, auf die ITDZ Berlin bisher nur extern verlinkt hat (siehe
`app/agents/connector/itdz_berlin.py`), hier aber erstmals direkt als eigene Listenquelle
genutzt. robots.txt der RIB-Plattform erlaubt automatisierten Zugriff vollständig
("Allow: /"), Liste und Detailseiten sind ohne Login öffentlich. Live verifiziert: 402
Ausschreibungen vollständig und ohne Duplikate abgerufen (`app/agents/connector/vergabe_bayern.py`).

Dabei einen echten Bug gefunden und behoben: die serverseitige CSRF-Prüfung (Yii-Framework) der
Pagination verlangt das Token zusätzlich als Formularfeld (`YII_CSRF_TOKEN`), nicht nur als
`X-CSRF-Token`-Header - ohne das Formularfeld liefert der Server HTTP 200 mit einer
HTML-Fehlerseite statt der erwarteten JSON-Antwort, was ansonsten die Pagination nach Seite 1
stillschweigend hätte abbrechen lassen (aufgefangen durch die bestehende
`iter_all_candidates`-Absicherung, aber ohne den Fix eben nur 20 statt 402 Treffer).

RIB/iTWO wird laut Recherche als White-Label-Plattform von mehreren Bundesländern genutzt
(ähnlich wie cosinex für DTVP/Brandenburg) - weitere Bundesländer mit eigener `filter`-ID wären
ein nahliegender nächster Schritt für noch mehr Abdeckung (`docs/portal-notes.md`).

### Aktualisieren-Button: parallel + maximale Abdeckung (Update 05.09.2026)

Nutzeranfrage: "möglichst viele Ausschreibungen abbilden können und ausfiltern" + der
Aktualisieren-Button soll zuverlässig "nochmal alles durchsucht". Daraufhin überarbeitet:

- **Portale laufen jetzt parallel** statt nacheinander (`app/api/run.py`,
  `ThreadPoolExecutor`), damit ein Lauf trotz wachsender Quellenzahl und höherer
  Abdeckungs-Limits in vertretbarer Zeit fertig wird. Der Frontend-Button zeigt alle gerade
  laufenden Quellen gleichzeitig an.
- Dafür zwei Voraussetzungen geschaffen: SQLite läuft jetzt im **WAL-Modus** mit großzügigem
  `busy_timeout` (`app/db.py`), und das Job-Claiming in der Warteschlange ist jetzt
  **race-sicher** (atomares `UPDATE...WHERE status='queued'` statt SELECT+UPDATE,
  `app/queue.py`) - sonst hätten zwei parallel laufende Portale denselben Job doppelt verarbeiten
  oder sich gegenseitig die Ergebnisse "wegschnappen" können. Zusätzlich arbeitet jeder
  Portal-Zyklus jetzt nur noch seine **eigenen** Warteschlangen-Jobs ab
  (`drain_queue_for_portal`) statt der gesamten globalen Warteschlange - das behebt einen
  Seiteneffekt, bei dem ein Portal fälschlich als "rot" gemeldet wurde, weil ein paralleler
  anderer Portal-Lauf seinen Discovery-Job "weggeschnappt" hatte.
- **Abdeckungs-Limits deutlich angehoben** (Nutzerpriorität: Breite vor serverseitiger
  Vorfilterung, Filtern passiert client-seitig): TED 20 statt 8 Seiten, e-Vergabe des Bundes 30
  statt 10 Seiten, DTVP 20 statt 6 Seiten pro Kategorie, Bekanntmachungsservice 7 statt 2 Tage.
- Dabei einen echten Bug im DTVP-Connector gefunden und behoben: kleinere CPV-Kategorien (z. B.
  "Beratung", nur ~5 reale Seiten) lieferten bei Seite 6+ HTTP 404 statt einer leeren Liste -
  das ließ den kompletten Discovery-Lauf fehlschlagen und **alle** bereits gefundenen
  Kandidaten verwerfen, nicht nur die eine überzählige Seite. Der Connector erkennt erschöpfte
  Kategorien jetzt selbst und überspringt sie. Als zusätzliche Absicherung bricht
  `iter_all_candidates` (Basisklasse aller Connectoren) bei einem Fehler auf einer späteren
  Seite jetzt sauber ab und behält die bereits gefundenen Kandidaten, statt alles zu verlieren.

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
