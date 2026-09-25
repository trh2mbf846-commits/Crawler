# Ausschreibungs-Crawler & Suchportal

Webanwendung zur automatisierten Suche nach öffentlichen Ausschreibungen mit Schwerpunkt
Künstliche Intelligenz / KI-Entwicklung, gemäß der Handlungsanweisung vom 31.08.2026 (Vincent
Mews, Version 1.1 inkl. Kapitel 17–25 "Search Agent Operating System").

Das Projekt lag ursprünglich im Unterordner `ausschreibungscrawler/` des Repositories
`Schatten-ber-Biesdorf` und wurde am 25.09.2026 samt Git-Historie in dieses eigenständige
Repository verschoben (Projektordner = Repository-Root).

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
/api/run-all`), KI-Assistent "Crawler Kevin" (siehe unten) und Frontend (Übersicht, Filter,
Suche, Detailansicht, Suchprofile, Quellstatus-Dashboard mit Quellen-Übersicht,
Entscheidungs-Posteingang, Crawler-Kevin-Tab). 82 automatisierte Tests plus reale Testläufe
gegen 7 Live-Portale mit 7306 echten Ausschreibungen.

### KI-Assistent "Crawler Kevin" (Update 25.09.2026)

Nutzeranfrage: "Richtung KI-Agent, aber die Übersicht soll bleiben", dann "Nennen wir ihn Crawler
Kevin", dann "Kevin darf alle drei Sachen [mitarbeiten statt nur lesen]". Ergänzt - nicht ersetzt
- die bestehende Übersicht um einen zusätzlichen Tab (`/assistant`, `frontend/src/pages/
Assistant.tsx`): eine Chat-Oberfläche, in der Fragen in natürlicher Sprache zu erfassten
Ausschreibungen und zum Quellstatus gestellt werden können (z. B. "welche KI-relevanten
Ausschreibungen in Bayern laufen in den nächsten 14 Tagen aus?").

Technisch ein Tool-Use-Agent auf Basis der Anthropic API (`backend/app/agents/assistant.py`,
`POST /api/assistant/chat`), mit zwei Werkzeug-Arten:

- **Lesend** (`suche_ausschreibungen`, `quellstatus`): werden sofort ausgeführt, über dieselbe,
  bereits geprüfte Such-/Health-Logik wie die REST-API (aus `api/tenders.py` in
  `app/tender_queries.py` herausgelöst, damit Chat und normale Suche nicht auseinanderlaufen).
- **Schreibend** (`aktualisieren_starten`, `suchprofil_anlegen`, `ausschreibung_merken`): werden
  **nie automatisch ausgeführt**. Ruft Kevin eines davon auf, bricht die Tool-Schleife ab und der
  Vorschlag geht als Klartext-Beschreibung ans Frontend - erst ein expliziter
  "Bestätigen"-Klick führt ihn über `POST /assistant/actions/execute` wirklich aus ("Ablehnen"
  verwirft ihn folgenlos). `aktualisieren_starten` nutzt dieselbe Hintergrund-Lauf-Infrastruktur
  wie der Aktualisieren-Button (`app/api/run.py:start_run`, jetzt auch für ein einzelnes Portal
  aufrufbar), `suchprofil_anlegen` legt ein echtes Suchprofil an (`app/api/search_profiles.py`-
  Logik), `ausschreibung_merken` setzt ein neues `gemerkt`/`merk_notiz`-Feld am Tender-Datensatz
  (in der Übersicht als ★-Badge sichtbar).

Ohne konfigurierten `CRAWLER_ANTHROPIC_API_KEY` (wie in dieser Entwicklungsumgebung) liefert der
Chat-Endpunkt einen klaren Hinweis statt eines Fehlers. Live end-to-end verifiziert (Playwright,
Chat-Antwort per Route-Interception simuliert, da kein API-Key verfügbar ist, aber Bestätigung
und Ausführung real gegen den echten Server): alle drei Aktionen bestätigt und geprüft, dass sie
tatsächlich etwas verändert haben (Tender wirklich `gemerkt`, Suchprofil wirklich in der DB,
ITDZ-Berlin-Lauf wirklich und erfolgreich durchgelaufen). Dabei einen echten Regressions-Bug
gefunden und behoben: der `tender_queries`-Refactor hatte versehentlich den `Tender`-Import aus
`api/tenders.py` entfernt - `GET /api/tenders/{id}` war dadurch kaputt (500), aber kein
bestehender Test hatte die HTTP-Schicht dieses Endpunkts abgedeckt. Als Konsequenz neue
`tests/test_api_smoke.py`: mindestens ein durchgehender HTTP-Aufruf pro Router, damit ein
kaputter Import künftig schon im schnellen Testlauf auffällt statt erst im Browser.

### API-Absicherung, proaktiver Kurzbericht, Kevins Kontext (Update 25.09.2026)

Nutzeranfrage nach "was würdest du empfehlen noch auszubauen?": "alle drei Sachen" - API-
Absicherung, proaktives Kevin, Kevin kennt meinen Kontext. Umgesetzt:

- **API-Absicherung** (`backend/app/security.py`): seit Kevin echte Aktionen auslösen kann, wiegt
  eine komplett offene API schwerer. Optionaler gemeinsamer Schlüssel statt vollem Login-System
  (Kapitel 5.2, nur ein Nutzer) - `CRAWLER_API_KEY` auf dem Server, `VITE_API_KEY` im Frontend,
  Header `X-API-Key`, zeitkonstanter Vergleich (`hmac.compare_digest`). Ohne gesetzten Schlüssel
  bleibt die API wie bisher offen (Entwicklungs-Default); `/api/health` bleibt für
  Load-Balancer-Checks immer ungeschützt. Live end-to-end verifiziert: 401 ohne/mit falschem
  Header, 200 mit richtigem, Frontend hängt den Header nachweislich an echte Requests.
- **Kevins Kontext** (`AssistantPreferences`, Singleton-Tabelle): Vincents Prioritäten
  (Freitext, bevorzugte Kategorien/Regionen, Mindestwert), einstellbar über ein neues
  "⚙ Präferenzen"-Panel auf Kevins Seite. Fließen in Kevins Systemprompt ein (`_build_system_prompt`
  in `app/agents/assistant.py`) - "Kevin soll sich in meine Position versetzen", ohne dass
  Vincent das in jeder Frage wiederholen muss.
- **Proaktiver Kurzbericht** (`app/agents/digest.py`, `GET /assistant/digest`): rein
  deterministisch aus der Datenbank berechnet (kein LLM nötig, funktioniert also auch ohne
  API-Key) - neue KI-relevante Ausschreibungen der letzten 24h, Fristen der nächsten 7 Tage bei
  gemerkten/relevanten Ausschreibungen, Portale mit Problemen, unter Berücksichtigung der
  Prioritäten. Kevins Chat-Seite lädt das beim Öffnen automatisch als erste Nachricht, statt dass
  Vincent erst fragen muss.

Live per Playwright verifiziert: Kurzbericht lädt automatisch und zeigt eine real erfasste,
bald ablaufende Ausschreibung korrekt an; Präferenzen speichern und wirken sofort im nächsten
Kurzbericht (auf derselben Datenbank neu geladen bestätigt). Dabei einen kleinen Darstellungsfehler
gefunden und behoben: der Kurzbericht-Text nutzte `**Markdown**`-Sternchen, die im Chat nirgends
gerendert wurden - jetzt reiner Text.

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

### PDF-Volltextsuche, Selbstdiagnose, Push-Benachrichtigung (Update 25.09.2026)

Nutzeranfrage nach Recherche zu "was können gute Agenten fürs Crawling/Durchsuchen noch": "alles
auf einmal, damit es direkt perfekt ist". Drei Ausbaustufen:

- **Vergabeunterlagen-Volltext** (`backend/app/agents/document_extraction.py`): lädt verlinkte
  PDF-Anhänge herunter und extrahiert ihren Text (`pypdf`, begrenzt auf max. 3 Dokumente/
  Ausschreibung, 40 Seiten, 20.000 Zeichen, 15 MB Downloadgröße - rein additiv, ein
  Fehlschlag bricht nie den Duplicate-Agenten ab). Neues Kevin-Werkzeug `dokumente_lesen`
  liest die gespeicherten Auszüge auf Nachfrage. Live verifiziert an einer echten
  Vergabeplattform-Bayern-Ausschreibung: 21 reale Dokumentlinks gefunden (dafür musste der
  Bayern-Connector zuerst um eine `dokumente_links`-Extraktion aus dem eingebetteten
  JS-Objekt ergänzt werden, `vergabe_bayern.py`), erstes Dokument vollständig heruntergeladen
  und zu ~20.000 Zeichen echtem PDF-Text verarbeitet. Dabei eine bestehende
  Dokumentations-Ungenauigkeit gefunden und korrigiert (`docs/portal-notes.md`): die
  Vergabeplattform-Berlin-Detailseite wirbt zwar mit gebührenfreiem Zugang, die eigentlichen
  Dokument-Downloads verlangen aber tatsächlich eine Registrierung als Verfahrens-Teilnehmer -
  `extract_pdf_text()` erkennt das korrekt (HTML statt PDF) und liefert `None`, ohne die
  Zugriffsschranke zu umgehen.
- **Selbstdiagnose bei Quell-Eskalation** (`backend/app/agents/source_health.py`): löst eine
  Eskalation aus (z. B. weil ein Connector plötzlich 0 Treffer liefert), ruft **nur dann, nur
  falls `CRAWLER_ANTHROPIC_API_KEY` gesetzt ist**, die Live-Seite des Portals ab und lässt ein
  LLM eine erste Einschätzung der vermutlichen Ursache formulieren (wiederverwendet den
  bereits vorhandenen, bis dahin ungenutzten `QUELLSTATUS_SYSTEM`-Prompt). Die Einschätzung
  landet als Empfehlungstext an der Eskalation - **ausdrücklich keine automatische
  Code-Änderung oder gar ein automatisches Deployment**, das bleibt bewusst Vincents
  Entscheidung; ohne API-Key funktioniert die Eskalation unverändert wie bisher, nur ohne die
  zusätzliche Einschätzung.
- **Echte Push-Benachrichtigung für den Kurzbericht** (`backend/app/agents/digest.py`,
  `app/scheduler.py`): bislang wurde der proaktive Kurzbericht (siehe oben) nur beim Öffnen
  von Kevins Chat-Tab angezeigt (reines Pull-Modell). Optional (`CRAWLER_DIGEST_WEBHOOK_URL`)
  schickt ein täglicher Scheduler-Job (`CRAWLER_DIGEST_STUNDE`, Default 7 Uhr) denselben
  Kurzbericht zusätzlich per POST-Webhook - Payload enthält sowohl `text` (Slack/Mattermost-
  kompatibel) als auch `content` (Discord-kompatibel), passt sich also ohne weitere
  Konfiguration an gängige Chat-Webhook-Formate an (auch für n8n/Zapier nutzbar). Ohne
  gesetzte URL bleibt das Verhalten wie bisher rein Pull-basiert. Live verifiziert gegen einen
  lokalen Test-Webhook-Empfänger: Kurzbericht kommt vollständig und mit beiden Schlüsseln an.

Beim Testen mit dieser neuen Funktionalität gegen die echte, persistente Entwicklungs-
Datenbank (`data/ausschreibungscrawler.db`) zusätzlich eine echte, unabhängige Lücke
gefunden und behoben: `Base.metadata.create_all()` legt nur komplett neue Tabellen an, nie
fehlende Spalten in bereits existierenden Tabellen - eine Datenbank, die älter als eine der
Schema-Erweiterungen dieser Session ist, crashte dadurch beim Start mit `no such column`.
Neue `_sqlite_synchronisiere_fehlende_spalten()` in `backend/app/db.py` ergänzt beim Start
automatisch und rein additiv (nie ein DROP/RENAME) fehlende Spalten per `ALTER TABLE`. Live
verifiziert: gegen eine absichtlich veraltete Test-Datenbank ausgeführt, alle fehlenden
Spalten korrekt ergänzt; anschließend auf die echte Entwicklungs-Datenbank angewendet, die
tatsächlich betroffen war.

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
./
├── backend/        Python/FastAPI, SQLAlchemy, Playwright, APScheduler
├── frontend/        React + Vite + TypeScript + Tailwind
└── docs/            API-Vertrag, PostgreSQL-Schema, robots.txt/ToS-Dokumentation
```

## Lokal auf dem Mac (Doppelklick)

Einmalig installieren: **Python 3.11+** (https://www.python.org/downloads/) und **Node.js LTS**
(https://nodejs.org), dann im Terminal:

```bash
git clone https://github.com/trh2mbf846-commits/Crawler.git ~/Crawler
```

Danach im Finder den Ordner `Crawler` (im Benutzerordner) öffnen und **`Crawler starten.command`**
doppelklicken. Beim ersten Start richtet das Skript alles ein (ca. 5 Minuten), danach öffnet sich
`http://localhost:8000` automatisch im Browser. Beenden: Terminal-Fenster schließen.

- Holt bei jedem Start per `git pull` automatisch den neuesten Stand.
- Legt `backend/.env` mit `CRAWLER_SCHEDULER_ENABLED=false` an (nur der Aktualisieren-Button
  crawlt); für "Crawler Kevin" dort `CRAWLER_ANTHROPIC_API_KEY` eintragen und neu starten.
- Daten bleiben in `backend/data/` zwischen den Starts erhalten.

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
wird dann einfach übersprungen (ebenso die Selbstdiagnose bei Quell-Eskalationen, siehe oben).
Optional `CRAWLER_DIGEST_WEBHOOK_URL` (Slack/Discord/Mattermost/n8n/Zapier-kompatible
Incoming-Webhook-URL) für den täglichen Kurzbericht per Push, `CRAWLER_DIGEST_STUNDE` (Default
`7`, UTC) für die Uhrzeit des täglichen Jobs.

## Deployment (Aktualisieren-Button statt Dauerbetrieb)

Nutzerwunsch (01.09.2026): kein dauerhaftes Hintergrund-Update, sondern ein einziger Link, auf
dem ein "Aktualisieren"-Button einmal alle aktiven Portale durchsucht - lokal filtern passiert
danach direkt in der Weboberfläche.

Dafür liegt im Repository-Root ein `Dockerfile`, das Frontend und
Backend in einem einzigen Container ausliefert (das Backend liefert das gebaute Frontend
selbst mit aus, siehe `backend/app/main.py`). Der periodische Scheduler ist im Image per
`CRAWLER_SCHEDULER_ENABLED=false` fest abgeschaltet - einzige Aktualisierungsquelle ist der
Button (`POST /api/run-all`, mit Live-Fortschritt über `GET /api/run-all/status`).

**Render.com:** `render.yaml` liegt im Repository-Root und wird daher direkt als Blueprint
erkannt ("New → Blueprint", dieses Repository verbinden). Alternativ "New → Web Service" wählen
und das Repository verbinden - Render erkennt das `Dockerfile` im Root automatisch.

**Fly.io:** `fly.toml` liegt im Repository-Root. Von dort aus
`fly launch --no-deploy` (App-Name ggf. anpassen, muss global eindeutig sein), dann `fly deploy`.

**API-Absicherung (empfohlen für ein öffentlich erreichbares Deployment):** ohne gesetzten
Schlüssel ist die API vollständig offen (praktisch für lokale Entwicklung, aber seit Crawler
Kevin echte Aktionen auslösen kann - Läufe starten, Suchprofile anlegen, Datensätze ändern - ein
echtes Risiko bei einem öffentlichen Link). Vor dem Deployment einen zufälligen Wert für
`CRAWLER_API_KEY` als Umgebungsvariable des Backend-Dienstes setzen und denselben Wert beim
Docker-Build als `--build-arg VITE_API_KEY=...` mitgeben (backt ihn ins ausgelieferte Frontend
ein, siehe Dockerfile und `app/security.py`).

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
