# Ausschreibungs-Crawler auf dem eigenen Rechner einrichten (Mac & Windows)

Diese Anleitung ist für Kolleg:innen. Der Crawler läuft komplett **auf deinem eigenen Rechner** –
kein Server, keine Kosten, keine Anmeldung. Du öffnest ihn im Browser unter `http://localhost:8000`.

**Zeitbedarf:** einmalig ca. 20–30 Minuten (größtenteils Warten auf Downloads), danach startest du
ihn mit einem Doppelklick.

> **Gut zu wissen:** Jeder Crawler ist eigenständig. Deine Merkliste, dein Firmenprofil, deine
> Referenzen und Themen liegen nur auf **deinem** Rechner. Was andere ändern, siehst du nicht –
> außer du bekommst eine neue „Startdatei“ (siehe Schritt 3).

---

## Schritt 1 – Programme installieren (einmalig)

| Programm | Wofür | Mac | Windows |
|---|---|---|---|
| **Python 3.11 oder neuer** | Crawler | python.org/downloads | python.org/downloads – **beim Installieren den Haken „Add python.exe to PATH“ setzen!** |
| **Node.js (LTS)** | Oberfläche | nodejs.org | nodejs.org |
| **Git** | Download + automatische Updates | wird beim ersten `git`-Befehl im Terminal angeboten („Entwicklertools installieren“) | git-scm.com/download/win (alle Voreinstellungen lassen) |
| **Ollama** *(optional)* | Crawler Kevin (Chat) kostenlos | ollama.com | ollama.com |
| **Google Chrome** *(optional, Mac)* | nur für das Portal „DB Bieterportal“ | google.com/chrome | nicht nötig (Edge reicht) |

Nach dem Installieren **Terminal bzw. PowerShell einmal schließen und neu öffnen**.

Zu **Kevin**: Er braucht ca. **5 GB Speicher** und läuft flüssig ab etwa **16 GB Arbeitsspeicher**
(bei 8 GB nutzt das Skript automatisch ein kleineres Modell). Ohne Ollama funktioniert alles andere
(Suche, Filter, Fristen, Checklisten, Themen) – nur Kevins Antworten, die KI-Nachprüfung und die
„Bewerben oder nicht?“-Bewertung entfallen.

## Schritt 2 – Crawler herunterladen (einmalig)

Das Repository ist öffentlich, du brauchst **kein** GitHub-Konto.

**Mac** – Programm „Terminal“ öffnen und eingeben:
```bash
git clone https://github.com/trh2mbf846-commits/Crawler.git ~/Crawler
```

**Windows** – „PowerShell“ öffnen (Startmenü) und eingeben:
```powershell
git clone https://github.com/trh2mbf846-commits/Crawler.git $HOME\Crawler
```

Der Crawler liegt jetzt im Ordner `Crawler` in deinem Benutzerordner.

## Schritt 3 – Startdatei einspielen (optional, aber empfohlen)

Wenn du von Vincent eine Datei `crawler-sicherung-….db` bekommen hast, enthält sie die gemeinsamen
Themen, das Firmenprofil und die Referenzen – dann startest du nicht bei null.

1. Im Ordner `Crawler\backend` einen Ordner **`data`** anlegen (falls er noch nicht existiert).
2. Die Datei dort hineinkopieren und **umbenennen in `ausschreibungscrawler.db`**.

Das muss **vor dem ersten Start** passieren. Später eine neue Startdatei einspielen: Crawler
beenden, Datei ersetzen, eventuell vorhandene Dateien `ausschreibungscrawler.db-wal` und
`ausschreibungscrawler.db-shm` löschen. ⚠️ Das überschreibt deine bisherigen eigenen Eingaben.

## Schritt 4 – Starten

- **Mac:** im Finder den Ordner `Crawler` öffnen und **`Crawler starten.command`** doppelklicken.
  Beim ersten Mal ggf. Rechtsklick → **Öffnen** → nochmal **Öffnen** bestätigen.
- **Windows:** im Explorer den Ordner `Crawler` öffnen und **`Crawler starten.bat`** doppelklicken.
  Meldet Windows „Der Computer wurde durch Windows geschützt“: **Weitere Informationen → Trotzdem
  ausführen**.

Beim **ersten Start** richtet sich alles selbst ein (ca. 5–10 Minuten, mit Kevin-Modell länger).
Danach öffnet sich der Browser mit dem Crawler. Fenster **offen lassen**, solange du den Crawler
nutzt; zum Beenden das Fenster schließen.

## Schritt 5 – Erste Schritte

1. In der **Übersicht** auf **„Aktualisieren“** klicken – der Crawler holt jetzt Ausschreibungen von
   allen Portalen (ca. 25–30 Minuten beim ersten Mal; Rechner dafür anlassen). Danach geht es viel
   schneller, weil nur Neues abgerufen wird.
2. Auf der Seite **„Mein Profil & Themen“** dein eigenes **Firmenprofil** und deine **Referenzen**
   eintragen (falls nicht per Startdatei da). Je genauer, desto besser Kevins Bewertung
   „Bewerben oder nicht?“.
3. Ausschreibungen mit **★ merken**, Fristen im Tab **„Fristen“** ansehen.

## Im Alltag

- **Starten:** Doppelklick wie in Schritt 4. Bei jedem Start holt sich der Crawler automatisch die
  neueste Version (braucht Internet; ohne Internet läuft die vorhandene).
- **Täglicher Lauf:** Der Crawler aktualisiert sich jeden Tag um 07:00 Uhr von selbst – aber nur,
  wenn er dann läuft. Wurde 07:00 verpasst, holt er es beim nächsten Start nach.
- **Benachrichtigung:** Auf dem Mac kommt bei neuen passenden Treffern eine Mitteilung.
- **Sicherung:** Auf „Mein Profil & Themen“ unten **„Datenbank-Sicherung herunterladen“** – das ist
  deine ganze persönliche Datenbank in einer Datei.

## Wenn etwas nicht klappt

| Problem | Lösung |
|---|---|
| „Python fehlt“ / „Node.js fehlt“ | Programm installieren (Schritt 1), **Terminal/PowerShell neu öffnen**, Skript erneut starten. Windows: bei Python den Haken „Add to PATH“ nachträglich durch erneutes Installieren (Modify) setzen. |
| Kevin antwortet „Ollama läuft nicht“ / „Modell fehlt“ | Ollama installieren und den Crawler neu starten – das Skript lädt das Modell beim Start selbst. |
| Beim Start steht ein gelber Hinweis zum Browser-Download | Nur das Portal „DB Bieterportal“ ist betroffen. Mac: Google Chrome installieren. Windows: Edge reicht, Hinweis ignorieren. |
| „Port 8000 ist belegt“ | Ein anderes Programm nutzt den Port. Es beenden oder den Rechner neu starten. |
| Keine Ausschreibungen sichtbar | Auf **„Aktualisieren“** klicken (Schritt 5). |
| Portale stehen auf „Nicht angebunden“ | Normal: sechs Portale verlangen Login oder haben Bot-Schutz und werden bewusst nicht abgefragt. |
| Fehlermeldung beim Start | Den Text aus dem Fenster kopieren und an Vincent schicken. |

⚠️ **Windows-Hinweis:** Das Windows-Startskript ist neu. In der Entwicklung konnte es nur geprüft
werden, nicht auf einem echten Windows-Rechner. Falls es dort hakt, bitte die Fehlermeldung
weitergeben – das lässt sich in der Regel schnell beheben.

---

## Für Vincent: Startdatei für Kolleg:innen erzeugen

1. Im eigenen Crawler: **Mein Profil & Themen → „Datenbank-Sicherung herunterladen“**.
2. Die Datei weitergeben (E-Mail, Cloud-Ordner, USB-Stick).
3. ⚠️ **Prüfen, was drinsteckt:** Die Datei enthält **alles** aus deinem Crawler – auch deine
   Merkliste samt Notizen, Suchprofile, Checklisten, Firmenprofil und Referenzen. Wenn Kolleg:innen
   davon nur Teile haben sollen, vorher bei dir aufräumen oder mit einer frischen Installation
   (nur Themen und Profil eintragen) eine eigene Startdatei erzeugen.
4. Neue Themen oder geändertes Profil später nachziehen? Neue Startdatei erzeugen und verteilen
   (jeweils mit dem Hinweis oben: das überschreibt die Eingaben der anderen) – oder die Themen
   einfach von Hand im Tab „Mein Profil & Themen“ ergänzen.
