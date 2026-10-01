# Den Crawler auf mehreren Geräten nutzen

Diese Anleitung beschreibt, wie das komplette Setup (Crawler, Oberfläche, Crawler Kevin) auf
anderen Geräten läuft – und wie du es dabei weiter ausbauen kannst.

## 1. Erst verstehen: Was liegt wo?

Das ist der wichtigste Abschnitt, denn davon hängt ab, welcher Weg für dich passt.

| Was | Wo gespeichert | Auf anderen Geräten? |
|---|---|---|
| **Programmcode** (Crawler, Oberfläche, Kevin) | GitHub: `trh2mbf846-commits/Crawler` | ✅ überall gleich, per Update |
| **Gesammelte Ausschreibungen, ★ Gemerktes, Suchprofile** | Datei `backend/data/ausschreibungscrawler.db` | ❌ **pro Installation eigen** (nicht in GitHub) |
| **Firmenprofil, Referenzen, Themen, Wunschliste, Checklisten** | dieselbe Datei | ❌ **pro Installation eigen** |
| **Schlüssel & Einstellungen** (API-Key, Uhrzeit …) | Datei `backend/.env` | ❌ pro Installation, bewusst nicht in GitHub |
| **Kevins Chatverlauf** | im **Browser** (localStorage) | ❌ pro Browser |
| **Sprachmodell für Kevin** (Ollama, ca. 5 GB) | auf dem Gerät | ❌ pro Gerät |

**Folge:** Installierst du den Crawler auf einem zweiten Gerät, startet er dort mit **leerer
Datenbank** – ohne dein Profil, deine Referenzen, Themen und Merkliste. Willst du auf allen
Geräten **dieselben Daten sehen**, nimm Weg B oder C (ein gemeinsamer Crawler, mehrere Browser).

## 2. Welcher Weg passt?

| | **A – Eigene Installation je Gerät** | **B – Ein Hauptgerät, andere per Browser** | **C – Online (Render)** |
|---|---|---|---|
| Gleiche Daten überall | ❌ | ✅ | ✅ |
| Handy/Tablet nutzbar | ❌ | ✅ (Browser) | ✅ (Browser) |
| Läuft ohne Internet | ✅ | ✅ (im selben WLAN) | ❌ |
| Hauptgerät muss laufen | – | ✅ (Mac wach, Crawler gestartet) | ❌ |
| Kevin kostenlos (Ollama) | ✅ | ✅ | ❌ (nur mit Anthropic-Key, kostet) |
| Zugriff von unterwegs | ❌ | ❌ | ✅ |
| Kosten | 0 € | 0 € | ca. 7 $/Monat |
| Passwortschutz nötig | nein | empfohlen | **ja, unbedingt** |

**Meine Empfehlung:** Für dich allein und mehrere eigene Geräte zu Hause/im Büro → **Weg B**.
Für Kolleg:innen oder Zugriff von überall → **Weg C**, aber erst mit Passwortschutz (siehe 5.).

---

## 3. Weg A – Eigene Installation auf jedem Gerät

### Mac
Genau wie bisher (siehe README „Lokal auf dem Mac“): Python 3.11+, Node.js LTS, Repository
klonen, `Crawler starten.command` doppelklicken. Für Kevin zusätzlich **Ollama** (ollama.com)
installieren – das Skript lädt das Modell selbst.

### Windows oder Linux (mit Docker)
Das Doppelklick-Skript gibt es nur für den Mac. Auf Windows/Linux läuft der Crawler am
einfachsten in **Docker**.

> ⚠️ Der Docker-Weg ist im Repository vorbereitet (`Dockerfile`), konnte aber in der
> Entwicklungsumgebung nicht ausprobiert werden. Falls etwas hakt, schick die Fehlermeldung an
> Claude Code.

1. **Docker Desktop** installieren (docker.com) und starten. **Git** installieren (git-scm.com).
2. Optional für Kevin: **Ollama** (ollama.com) installieren, dann im Terminal:
   `ollama pull qwen3:8b` (bei nur 8 GB Arbeitsspeicher: `ollama pull qwen3:4b`).
3. Im Terminal (Windows: PowerShell):
   ```bash
   git clone https://github.com/trh2mbf846-commits/Crawler.git
   cd Crawler
   docker build -t crawler .
   docker run -d --name crawler -p 8000:8000 -v crawler-daten:/app/data \
     --restart unless-stopped \
     -e CRAWLER_OLLAMA_URL=http://host.docker.internal:11434 \
     -e CRAWLER_OLLAMA_MODEL=qwen3:8b \
     crawler
   ```
   (In PowerShell die Befehlszeile in **eine** Zeile schreiben, `\` weglassen.
   Unter **Linux** zusätzlich `--add-host=host.docker.internal:host-gateway` angeben.)
4. Browser: **http://localhost:8000**
5. **Update** (neue Version aus GitHub):
   ```bash
   git pull
   docker build -t crawler .
   docker rm -f crawler
   # dann den docker run-Befehl von oben erneut ausführen
   ```
   Die Daten bleiben erhalten, weil sie im Docker-Volume `crawler-daten` liegen.

Beim ersten `docker build` dauert es einige Minuten (Browser für das DB Bieterportal inklusive).

### Daten von einem Gerät auf ein anderes übernehmen (optional)
Crawler auf beiden Geräten **beenden**, dann die Datei `backend/data/ausschreibungscrawler.db`
kopieren (Mac → Mac) bzw. per `docker cp` in den Container legen. Danach ist alles übernommen,
auch Profil, Themen und Referenzen. Danach **nicht beide Geräte parallel weiterpflegen** – sie
laufen sonst auseinander. Wer dasselbe Datenstand auf mehreren Geräten will: Weg B.

---

## 4. Weg B – Ein Hauptgerät, die anderen nutzen den Browser (gleiches WLAN)

Der Crawler läuft **nur auf einem Gerät** (z. B. deinem Mac); alle anderen Geräte – Laptop,
Tablet, Handy – öffnen ihn einfach im Browser. Es gibt nur **eine** Datenbank.

**Einrichtung auf dem Hauptgerät (Mac):**
1. In `~/Crawler/backend/.env` (Finder: `Cmd + Shift + .` zeigt versteckte Dateien) eine Zeile
   ergänzen:
   ```
   CRAWLER_HOST=0.0.0.0
   ```
2. `Crawler starten.command` neu starten. Im Fenster erscheint dann
   **„Andere Geräte im selben Netz: http://192.168.x.x:8000“**.
3. Beim ersten Mal fragt macOS, ob „Python eingehende Verbindungen annehmen“ darf → **Erlauben**.
4. Auf den anderen Geräten (im **selben WLAN**) diese Adresse im Browser öffnen. Tipp: als
   Lesezeichen speichern bzw. auf dem Handy „Zum Home-Bildschirm“.

**Worauf du achten musst:**
- **Der Mac muss wach bleiben und der Crawler laufen**, sonst sind die anderen Geräte „offline“.
  Ruhezustand verhindern: Systemeinstellungen → Batterie/Energie, oder im Terminal
  `caffeinate -d` laufen lassen. Der tägliche 07:00-Lauf klappt auch nur, wenn der Mac dann an ist.
- ⚠️ **Es gibt noch keinen Passwortschutz.** Jeder im selben Netz kann alles bedienen (auch
  Kevins Aktionen bestätigen). Nur im **eigenen, vertrauenswürdigen** Netz nutzen – **nicht** im
  Gäste-WLAN, Café oder Firmennetz mit fremden Geräten.
- Die Adresse ändert sich eventuell (Router vergibt neue IP). Stabiler: Router-Einstellung „feste
  IP für diesen Mac“ oder die Adresse `http://<Mac-Name>.local:8000` (Mac-Name unter
  Systemeinstellungen → Allgemein → Info).
- **Kevin** läuft über das Ollama des Hauptgeräts – er beantwortet Fragen nacheinander, mehrere
  Geräte gleichzeitig verlangsamen ihn. Der **Chatverlauf** liegt je Browser separat.
- Die Oberfläche ist für den Computer-Bildschirm gebaut; auf dem Handy **funktioniert** sie im
  Browser, ist dort aber **nicht gesondert getestet/optimiert**.

---

## 5. Weg C – Online (für Zugriff von überall und für andere Personen)

Die Schritt-für-Schritt-Einrichtung bei Render.com steht in der README (Abschnitt „Deployment“)
und gilt weiterhin: **New → Blueprint → Repository `Crawler`**, dann die Variablen eintragen.
Zusätzlich zu beachten:

1. **Erst Passwortschutz, dann Link teilen.** Ein öffentlicher Link ohne Schutz erlaubt jedem,
   Läufe zu starten und Kevins Aktionen auszuführen. Der vorhandene `CRAWLER_API_KEY` ist **kein**
   echter Schutz (der Schlüssel steckt im ausgelieferten Frontend). Ein richtiger
   Passwortschutz (Browser-Anmeldung mit Benutzername + Passwort) ist **fertig gebaut und getestet,
   aber noch nicht ins Repository übernommen** – bei Claude Code „Passwortschutz einbauen“ sagen,
   bevor du den Link weitergibst.
2. **Kevin kostenlos geht online nicht** (Ollama läuft nicht auf Render). Entweder
   `CRAWLER_ANTHROPIC_API_KEY` setzen (kostet pro Frage) oder Kevin online weglassen.
3. **Daten gehen bei jedem Neustart verloren**, solange kein „Persistent Disk“ (Zusatzoption bei
   Render, `/app/data`) gebucht ist. Danach ist auch Profil/Referenzen/Themen weg – ein Klick auf
   „Aktualisieren“ holt zwar die Ausschreibungen zurück, **deine eigenen Eingaben nicht**.
   Mit Disk dauerhaft sicher.
4. **Alle sehen dieselben Daten** – auch dein Firmenprofil und die Referenzen. Gedacht ist das
   System als Ein-Personen-Werkzeug; mehrere Nutzer teilen sich Merkliste, Profil und Themen.
5. Der 07:00-Lauf funktioniert nur, solange der Dienst „wach“ ist; Render-Tarife ohne Dauerbetrieb
   schlafen ein.

---

## 6. Kann ich es dann noch weiter bearbeiten? – Ja

Der **Code liegt in GitHub** und ist von allen Geräten und von Claude Code aus erreichbar. So läuft
Weiterentwicklung:

```
Wunsch an Claude Code (Repository „Crawler“)  →  Änderung + Tests  →  Push nach GitHub
        →  jedes Gerät holt sich die neue Version  →  fertig
```

- **Mac (Weg A/B):** Beim nächsten Start von `Crawler starten.command` automatisch (`git pull`).
- **Docker:** `git pull`, `docker build`, Container neu starten (siehe 3.).
- **Render (Weg C):** baut nach einem Push normalerweise automatisch neu; sonst im Dashboard
  „Manual Deploy → Deploy latest commit“.

**Ohne Claude Code änderbar** (direkt in der Oberfläche, gilt sofort): Themen/Kategorien,
Firmenprofil, Referenzen, Suchprofile, Fristen, Checklisten, Kevins Wunschliste.
**Mit Claude Code:** neue Portale, neue Funktionen, Fehlerbehebungen.

**Beachten bei mehreren Geräten:**
- Änderungen, die Claude Code auf `main` pusht, landen **bei allen Geräten** beim nächsten Update.
  Bei großen Umbauten daher sagen: „auf einem eigenen Branch arbeiten, ich prüfe und übernehme
  dann“.
- Zum Weiterentwickeln brauchst du **kein Entwicklungsgerät**: Claude Code arbeitet im Browser
  (claude.ai/code) auf dem Repository, nicht auf deinem Mac.
- Datenbankänderungen (neue Felder) macht der Crawler beim Start **selbst** (additiv, nichts geht
  verloren) – du musst nach Updates nichts Manuelles tun.

---

## 7. Checkliste für jedes neue Gerät

- [ ] Weg gewählt (A / B / C), Datenfrage geklärt (gleiche Daten nötig → B oder C)
- [ ] **A:** Voraussetzungen installiert (Mac: Python 3.11+, Node.js; Windows/Linux: Docker + Git)
- [ ] Platz & Leistung für Kevin: ca. **5 GB** Speicher, **16 GB RAM** empfohlen (bei 8 GB das
      kleinere Modell `qwen3:4b`); ohne Ollama funktioniert alles außer Kevins Antworten
- [ ] **Chrome** installiert (nur für das DB Bieterportal nötig, sonst entfällt dieses Portal)
- [ ] `.env` selbst anlegen/pflegen – **Schlüssel (API-Keys) nie in GitHub, Chat oder E-Mail posten**
- [ ] **B/C:** Netz-Sicherheit bedacht (kein Passwortschutz ohne Zusatz, siehe 4. und 5.)
- [ ] **B:** Hauptgerät bleibt wach; Firewall-Abfrage bestätigt
- [ ] Sicherung: gelegentlich `backend/data/ausschreibungscrawler.db` kopieren (enthält alle
      deine eigenen Eingaben)
- [ ] Zeitzone/Uhrzeit des Geräts stimmt (der tägliche Lauf nutzt die lokale Uhrzeit)

## 8. Häufige Probleme

| Problem | Lösung |
|---|---|
| Anderes Gerät erreicht den Crawler nicht (Weg B) | Beide im **selben WLAN**? `CRAWLER_HOST=0.0.0.0` gesetzt und Crawler neu gestartet? macOS-Firewall-Abfrage mit „Erlauben“ bestätigt? Gäste-WLAN trennt Geräte oft voneinander. |
| Seite lädt, aber „Kevin nicht erreichbar“ | Ollama läuft auf dem Gerät, auf dem der Crawler läuft? (Docker: `CRAWLER_OLLAMA_URL=http://host.docker.internal:11434`) |
| Neues Gerät zeigt keine Ausschreibungen | Normal – leere Datenbank. Einmal **„Aktualisieren“** klicken (ca. 25–30 Minuten, alle Portale). |
| Profil/Referenzen/Themen fehlen auf dem neuen Gerät | Siehe Abschnitt 1: Daten sind pro Installation. Datenbank-Datei kopieren (3.) oder Weg B/C. |
| Nach Update startet etwas nicht | Fehlertext aus dem Terminal an Claude Code schicken. |
