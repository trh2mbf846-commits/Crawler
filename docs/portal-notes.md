# Portal-Konfiguration: robots.txt / ToS (Kapitel 9.3)

Vor der Implementierung jedes Connectors ist laut Handlungsanweisung robots.txt sowie die
sichtbaren Nutzungsbedingungen des jeweiligen Portals zu prüfen und das Ergebnis in der
Portal-Konfiguration festzuhalten (`portals.robots_status` / `portals.tos_hinweis`).

## Aktueller Stand (31.08.2026)

**Diese Prüfung konnte in dieser Entwicklungsumgebung noch nicht durchgeführt werden.** Die
Session läuft in einer Cloud-Umgebung, deren Netzwerk-Policy jeglichen allgemeinen
Internetzugriff blockiert (Egress-Proxy lässt nur wenige Infrastruktur-Domains wie
`pypi.org`/`npmjs.org`/`api.anthropic.com` zu, siehe Rückfrage im Chat vom 31.08.2026). Ein
Zugriff auf `vergabekooperation.berlin`, `bieterportal.noncd.db.de` oder `www.itdz-berlin.de`
war daher nicht möglich - weder für robots.txt noch für die Analyse der HTML-Struktur.

Alle 3 Pflicht-Portale stehen deshalb aktuell auf `robots_status = "ungeprueft"`
(siehe `app/seed.py`).

| Portal | robots.txt geprüft? | ToS geprüft? | Rechtliche Einschätzung (Kapitel 9.3, 13) |
|---|---|---|---|
| Vergabeplattform Berlin | ❌ nein | ❌ nein | Öffentliche Vergabebekanntmachung, nach GWB/VgV grundsätzlich zur Einsichtnahme bestimmt - konkrete robots.txt/ToS-Prüfung steht aber noch aus. |
| DB Bieterportal | ❌ nein | ❌ nein | s.o. - zusätzlich zu prüfen, ob Dokumente hinter einem Bieter-Login liegen (Kapitel 10.3-Beispiel). |
| ITDZ Berlin | ❌ nein | ❌ nein | s.o. - öffentliche Übersichtsseite laut Handlungsanweisung. |

## Vor dem ersten echten Testlauf nachzuholen (sobald Netzzugriff verfügbar ist)

1. `curl https://<portal>/robots.txt` je Portal abrufen und auswerten (`Disallow`-Regeln für
   die relevanten Pfade prüfen).
2. Sichtbare Nutzungsbedingungen/Impressum auf ausdrückliche Verbote automatisierten Abrufs
   sichten.
3. `portals.robots_status` auf `geprueft_ok` oder `geprueft_einschraenkung` setzen,
   `portals.tos_hinweis` mit dem konkreten Befund aktualisieren (`app/seed.py` anpassen oder
   direkt in der DB/via Admin-Funktion).
4. Erst danach `app/run_all_connectors.py` gegen die echten Portale laufen lassen und die
   TODO-Selektoren in `app/agents/connector/*.py` anhand der echten Seitenstruktur verifizieren
   bzw. korrigieren.

## Zusatzportale (Kapitel 3, 16.3)

Die 5 von Claude Code vorgeschlagenen Ergänzungsportale (e-Vergabe des Bundes, DTVP, Vergabe24,
TED, service.bund.de) sind bewusst noch nicht in `app/seed.py` angelegt. Laut Handlungsanweisung
sind sie vor Phase 3 kurz mit Vincent abzustimmen - das ist bislang nicht erfolgt.
