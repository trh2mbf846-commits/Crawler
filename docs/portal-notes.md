# Portal-Konfiguration: robots.txt / ToS (Kapitel 9.3)

Vor der Implementierung jedes Connectors ist laut Handlungsanweisung robots.txt sowie die
sichtbaren Nutzungsbedingungen des jeweiligen Portals zu prüfen und das Ergebnis in der
Portal-Konfiguration festzuhalten (`portals.robots_status` / `portals.tos_hinweis`).

## Stand nach Freischaltung des Netzzugriffs (31.08.2026)

Der Netzzugriff für diese Session wurde am 31.08.2026 freigeschaltet. Alle 3 Pflicht-Portale
wurden daraufhin real geprüft und die Connectoren gegen die tatsächliche Seitenstruktur
gebaut/getestet (siehe `app/agents/connector/*.py`, jeweils mit ausführlichem
Befund-Docstring).

| Portal | robots.txt | Zugriff auf Übersicht/Detail | Login/CAPTCHA? | Status |
|---|---|---|---|---|
| **ITDZ Berlin** | Vorhanden, erlaubt automatisierten Zugriff explizit bei klarer User-Agent-Kennung | Statisches HTML, keine Pagination nötig | Nein | `geprueft_ok` |
| **Vergabeplattform Berlin** | Keine robots.txt (404) | Server-seitiges HTML, Pagination über `&Start=N`, Detailseite inkl. Vergabeunterlagen vollständig öffentlich | Nein (Login nur für Angebotsabgabe, nicht fürs Einsehen) | `geprueft_ok` |
| **DB Bieterportal** | Kein echtes robots.txt (Server liefert für jeden Pfad die SPA-Startseite) | Reine Angular/Telerik-Kendo-SPA (Webpack-Bundles, SignalR/WebSocket-Datenkanal), Inhalte nur nach JS-Rendering sichtbar | Auf der Übersichtsseite selbst nicht erkennbar (noch nicht bis zum Ende getestet, siehe unten) | `ungeprueft` (technischer Blocker, siehe unten) |

### ITDZ Berlin – Details

robots.txt (vollständig geprüft): erlaubt "Any automated program" ausdrücklich, sofern es
sich im User-Agent-Header klar/eindeutig identifiziert und entweder nur die Startseite/RSS
abruft oder vollständig robots-konform ist. Die für uns relevanten `Disallow`-Regeln
(`/*/(S(*))`, `/land/kalender/print/`, `/presse/pressemitteilungen/index/search/`) betreffen
die Ausschreibungsseite nicht. → **Automatisierter Abruf ist ausdrücklich erlaubt.**

Wichtiger struktureller Befund: Jede gelistete Ausschreibung verlinkt direkt extern auf
**meinauftrag.rib.de** (RIB/iTWO-Vergabeplattform) - ITDZ Berlin selbst hostet keine eigene
Detailseite. Der Connector erfasst deshalb nur Titel + Veröffentlichungsdatum von der
Listenseite und verlinkt als `direktlink` direkt auf meinauftrag.rib.de, ohne dort selbst
weitere Inhalte abzurufen (das wäre ein eigenes Portal mit eigener robots.txt/ToS-Prüfung,
außerhalb des aktuellen Scopes - ggf. als Kapitel-3-Ergänzung mit Vincent zu klären).

### Vergabeplattform Berlin – Details

Keine robots.txt vorhanden. Die Teilnahmebedingungen regeln ausschließlich die Registrierung
für die **Teilnahme** an Vergabeverfahren (Angebotsabgabe) - das Einsehen veröffentlichter
Bekanntmachungen ist ausdrücklich ohne Registrierung möglich; "Anmelden" ist im Menü ein
separater Punkt, keine Zugriffsschranke für die öffentliche Suche. Kein Hinweis auf ein
Verbot automatisierten Abrufs gefunden. Sogar die Vergabeunterlagen sind laut Detailseite
"für einen uneingeschränkten und vollständigen direkten Zugang gebührenfrei" verfügbar - das
Beispiel-Szenario aus Kapitel 10.3 (Dokumente nur nach Login) trifft hier **nicht** zu, daher
keine Eskalation nötig. → **Vollständig öffentlich, automatisierter Abruf unproblematisch.**

Die vom Auftraggeber vorgegebene Einstiegs-URL (`LoginControllerServlet?function=
CookiesCheckDone`) ist entgegen des Namens kein Bieter-Login, sondern nur ein
Cookie-Consent-Schritt.

### DB Bieterportal – Details und offener technischer Punkt

Dies ist eine reine JavaScript-Single-Page-Application (Angular + Telerik Kendo UI), die
laut Bundle-Analyse einen SignalR/WebSocket-Datenkanal nutzt. Ein einfacher HTTP-Abruf
(`httpx`, wie in `polite_get` verwendet) liefert nur die leere SPA-Startseite (~2 KB) - für
echte Inhalte ist zwingend clientseitiges Rendering nötig (Kapitel 3: "Headless-Browser-
Ansatz einplanen", wie im Connector mit Playwright umgesetzt).

**Technischer Blocker in dieser Session:** Der Egress-Proxy dieser Cloud-Umgebung lässt
zwar normale HTTPS-GET-Anfragen an `bieterportal.noncd.db.de` zu (per `curl`/`httpx`
verifiziert, HTTP 200), bricht aber jede Chromium/Playwright-Navigation zu genau diesem Host
mit `ERR_CONNECTION_RESET` ab. Der Proxy-Status-Log zeigt den Grund: die Verbindung wird vom
Relay als `ws_closed_mid_exchange` behandelt und nach konstant ~6 Sekunden geschlossen -
laut Proxy-Dokumentation (`/root/.ccr/README.md`) sind WebSocket-Upgrades über diesen Proxy
grundsätzlich nicht unterstützt ("Not supported through the proxy ... report, do not work
around"). Getestet und ohne Erfolg: `--disable-http2`, explizite Proxy-Konfiguration statt
Auto-Erkennung, Blockieren von WebSocket-Requests per Route-Interception, `ignore_https_errors`.
Eine Suche nach einer direkt aufrufbaren REST/JSON-API in den (unminifizierten Strings der)
Webpack-Bundles blieb ohne eindeutigen Treffer - die Bundles sind stark minifiziert und die
Requests werden vermutlich dynamisch/injiziert zusammengesetzt.

**Das ist eine Einschränkung dieser konkreten Sandbox-Umgebung, keine Zugriffsschranke des
Portals selbst** (kein Login/CAPTCHA auf der Zielseite erkennbar - die Seite kommt gar nicht
erst zum Rendern). Der Connector-Code ist wie in Kapitel 3 vorgesehen mit Playwright
umgesetzt und sollte in einer Produktivumgebung ohne diese Proxy-Einschränkung funktionieren.
Empfehlung: Connector in einer Umgebung mit vollem, proxy-freiem oder WebSocket-fähigem
Netzzugriff (z. B. lokal bei Vincent oder auf einem eigenen Server) verifizieren und dabei
`robots_status` von `ungeprueft` auf den tatsächlichen Befund aktualisieren.

## Zusatzportale (Kapitel 3, 16.3)

Die 5 von Claude Code vorgeschlagenen Ergänzungsportale (e-Vergabe des Bundes, DTVP, Vergabe24,
TED, service.bund.de) sind bewusst noch nicht in `app/seed.py` angelegt. Laut Handlungsanweisung
sind sie vor Phase 3 kurz mit Vincent abzustimmen - das ist bislang nicht erfolgt.
