#!/bin/bash
# Startet den Ausschreibungs-Crawler lokal auf dem Mac - per Doppelklick im Finder.
#
# Beim ersten Start wird alles Nötige eingerichtet (Python-Umgebung, Headless-Browser,
# Frontend-Build), danach startet das nur noch den Server und öffnet http://localhost:8000.
# Voraussetzung: Python 3.11+ (python.org) und Node.js 22 (nodejs.org), optional Ollama
# (ollama.com) für Crawler Kevin, siehe README "Lokal auf dem Mac". Beenden: dieses Fenster schließen oder Ctrl+C.
#
# Bewusst kompatibel mit der macOS-Standard-Bash 3.2 (keine Bash-4-Features).

set -e
cd "$(dirname "$0")"
PROJEKT="$(pwd)"
SKRIPT="$PROJEKT/$(basename "$0")"
PORT=8000
URL="http://localhost:$PORT"

schritt() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
fehler() {
  printf '\n\033[31mFEHLER: %s\033[0m\n' "$1"
  printf '\nFenster mit Enter schließen.'
  read -r _
  exit 1
}

# --- Voraussetzungen ---------------------------------------------------------------------
PYTHON=""
for kandidat in python3.13 python3.12 python3.11 python3; do
  if command -v "$kandidat" >/dev/null 2>&1 \
     && "$kandidat" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PYTHON="$kandidat"
    break
  fi
done
[ -n "$PYTHON" ] || fehler "Python 3.11 oder neuer fehlt. Bitte von https://www.python.org/downloads/ installieren und dieses Skript erneut starten."
command -v npm >/dev/null 2>&1 || fehler "Node.js fehlt. Bitte die LTS-Version von https://nodejs.org installieren und dieses Skript erneut starten."

# Läuft noch ein alter Crawler (z. B. Fenster nicht richtig geschlossen), würde sonst weiter die
# alte Version antworten und Updates kämen nie an - daher den alten Crawler beenden und neu starten.
ALTE_PIDS="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$ALTE_PIDS" ]; then
  if curl -fs "$URL/api/health" >/dev/null 2>&1; then
    schritt "Beende den noch laufenden Crawler, damit die neueste Version startet"
    kill $ALTE_PIDS 2>/dev/null || true
    for _ in $(seq 1 20); do
      lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
      sleep 0.5
    done
  else
    fehler "Port $PORT ist von einem anderen Programm belegt. Bitte dieses Programm beenden und den Crawler erneut starten."
  fi
fi

# --- Updates holen (optional, Fehler z. B. ohne Internet werden ignoriert) ---------------
if [ -d .git ]; then
  schritt "Suche nach Updates"
  SKRIPT_VORHER="$(cksum < "$SKRIPT")"
  git pull --ff-only 2>/dev/null || echo "(kein Update geladen - es geht mit dem vorhandenen Stand weiter)"
  # Hat das Update dieses Skript selbst geändert, läuft die Bash sonst mit der alten Fassung
  # im Speicher weiter - daher einmal die neue Fassung neu starten.
  if [ -z "$CRAWLER_SKRIPT_NEU_GESTARTET" ] && [ "$(cksum < "$SKRIPT")" != "$SKRIPT_VORHER" ]; then
    export CRAWLER_SKRIPT_NEU_GESTARTET=1
    exec "$SKRIPT" "$@"
  fi
fi

# --- Backend einrichten ------------------------------------------------------------------
cd "$PROJEKT/backend"
mkdir -p data

if [ ! -x .venv/bin/python ]; then
  schritt "Erstmalige Einrichtung: Python-Umgebung anlegen"
  "$PYTHON" -m venv .venv
fi

REQ_STAND="$(cksum requirements.txt)"
if [ ! -f .venv/.installiert ] || [ "$(cat .venv/.installiert)" != "$REQ_STAND" ]; then
  schritt "Python-Pakete installieren (dauert beim ersten Mal ein paar Minuten)"
  .venv/bin/python -m pip install --upgrade pip -q
  .venv/bin/python -m pip install -r requirements.txt -q
  echo "$REQ_STAND" > .venv/.installiert
  rm -f .venv/.browser-ok .venv/.browser-uebersprungen
fi

# Headless-Browser nur für das DB Bieterportal - alle anderen Portale brauchen ihn nicht.
# Ist Google Chrome installiert, nutzt der Connector einfach diesen (kein Download nötig).
# Sonst genau EIN Download-Versuch: ein fehlgeschlagener Download (z. B. Timeout beim
# Playwright-CDN) darf weder den Start verhindern noch jeden weiteren Start minutenlang aufhalten.
if [ ! -f .venv/.browser-ok ] && [ ! -f .venv/.browser-uebersprungen ]; then
  if [ -d "/Applications/Google Chrome.app" ] || [ -d "$HOME/Applications/Google Chrome.app" ]; then
    echo "Google Chrome gefunden - wird für das DB Bieterportal genutzt, kein Download nötig."
    touch .venv/.browser-ok
  else
    schritt "Headless-Browser für das DB Bieterportal installieren"
    if PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=180000 .venv/bin/python -m playwright install chromium; then
      touch .venv/.browser-ok
    else
      touch .venv/.browser-uebersprungen
      printf '\n\033[33mHinweis: Browser-Download fehlgeschlagen - nur das DB Bieterportal ist betroffen,\n'
      printf 'alle anderen Portale funktionieren. Abhilfe: Google Chrome installieren, oder den Download\n'
      printf 'später manuell wiederholen mit:\n'
      printf '  ~/Crawler/backend/.venv/bin/python -m playwright install chromium\033[0m\n'
    fi
  fi
fi

if [ ! -f .env ]; then
  # Kein automatisches Hintergrund-Crawling (Nutzerwunsch 01.09.2026) - nur der
  # Aktualisieren-Button startet Läufe, genau wie im Render-/Docker-Deployment.
  cat > .env <<'EOF'
CRAWLER_SCHEDULER_ENABLED=false
# Crawler Kevin läuft kostenlos über Ollama (https://ollama.com). Optional stattdessen Claude
# (kostenpflichtig, bessere Antworten): Raute entfernen und eigenen Schlüssel eintragen:
# CRAWLER_ANTHROPIC_API_KEY=sk-ant-...
# Anderes lokales Modell erzwingen (Standard: qwen3:8b, auf Macs mit 8 GB qwen3:4b):
# CRAWLER_OLLAMA_MODEL=qwen3:8b
EOF
fi

# --- Crawler Kevin: kostenloses lokales Sprachmodell über Ollama ---------------------------
# Nutzerwunsch 25.09.2026. Ist in backend/.env ein Anthropic-Key eingetragen, nutzt Kevin Claude
# und Ollama wird übersprungen. Alles hier ist optional - ohne Ollama startet der Crawler
# trotzdem, nur Kevin meldet dann, dass er nicht erreichbar ist.
if ! grep -Eq '^[[:space:]]*CRAWLER_ANTHROPIC_API_KEY=.+' .env; then
  OLLAMA=""
  if command -v ollama >/dev/null 2>&1; then
    OLLAMA="ollama"
  elif [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
    OLLAMA="/Applications/Ollama.app/Contents/Resources/ollama"
  fi

  if [ -z "$OLLAMA" ]; then
    printf '\n\033[33mHinweis: Für Crawler Kevin (kostenlos) bitte Ollama von https://ollama.com installieren\n'
    printf 'und den Crawler danach neu starten. Alles andere funktioniert auch ohne.\033[0m\n'
  else
    # Modell nach Arbeitsspeicher: 8B braucht ca. 6 GB frei, auf 8-GB-Macs das kleinere 4B.
    # Eigene Wahl in backend/.env (CRAWLER_OLLAMA_MODEL=...) hat Vorrang.
    MODELL="$(sed -n 's/^[[:space:]]*CRAWLER_OLLAMA_MODEL=//p' .env | tail -1)"
    if [ -z "$MODELL" ]; then
      RAM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || awk '/MemTotal/ {print $2 * 1024}' /proc/meminfo 2>/dev/null || echo 0)"
      if [ "${RAM_BYTES:-0}" -ge 15000000000 ] 2>/dev/null; then MODELL="qwen3:8b"; else MODELL="qwen3:4b"; fi
      export CRAWLER_OLLAMA_MODEL="$MODELL"
    fi

    if ! curl -fs http://localhost:11434/api/version >/dev/null 2>&1; then
      schritt "Ollama starten"
      open -a Ollama 2>/dev/null || (nohup "$OLLAMA" serve >/dev/null 2>&1 &)
      for _ in $(seq 1 30); do
        curl -fs http://localhost:11434/api/version >/dev/null 2>&1 && break
        sleep 1
      done
    fi

    if curl -fs http://localhost:11434/api/version >/dev/null 2>&1; then
      if ! "$OLLAMA" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$MODELL"; then
        schritt "Sprachmodell $MODELL für Crawler Kevin herunterladen (einmalig, einige GB)"
        "$OLLAMA" pull "$MODELL" || printf '\033[33mHinweis: Download fehlgeschlagen - wird beim nächsten Start erneut versucht.\033[0m\n'
      fi
      # Zusatzmodell nur für die experimentelle Suche nach Bedeutung (CRAWLER_SEMANTIK_AKTIV=true).
      EMBEDDING="$(sed -n 's/^[[:space:]]*CRAWLER_OLLAMA_EMBEDDING_MODEL=//p' .env | tail -1)"
      EMBEDDING="${EMBEDDING:-qwen3-embedding:0.6b}"
      if grep -Eiq '^[[:space:]]*CRAWLER_SEMANTIK_AKTIV=(true|1)' .env \
         && ! "$OLLAMA" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$EMBEDDING"; then
        schritt "Zusatzmodell $EMBEDDING für die Suche nach Bedeutung herunterladen (einmalig)"
        "$OLLAMA" pull "$EMBEDDING" || printf '\033[33mHinweis: Download fehlgeschlagen - Suche nach Bedeutung bleibt bis zum nächsten Start aus.\033[0m\n'
      fi
      # Modell schon jetzt im Hintergrund in den Speicher laden (dauert beim ersten Mal etwas),
      # damit Kevins erste Antwort nicht zusätzlich darauf warten muss.
      (curl -fs http://localhost:11434/api/generate -d "{\"model\": \"$MODELL\", \"keep_alive\": \"60m\"}" >/dev/null 2>&1 &)
      echo "Crawler Kevin nutzt das lokale Modell $MODELL (kostenlos)."
    else
      printf '\033[33mHinweis: Ollama ließ sich nicht starten - bitte die Ollama-App einmal von Hand öffnen.\033[0m\n'
    fi
  fi
fi

# --- Frontend bauen (nur wenn sich der Frontend-Code geändert hat) -----------------------
cd "$PROJEKT/frontend"
FE_STAND="$(find src public index.html package.json package-lock.json vite.config.ts -type f 2>/dev/null \
  | LC_ALL=C sort | xargs cksum | cksum)"
if [ ! -f "$PROJEKT/backend/static/index.html" ] || [ ! -f .build-stand ] || [ "$(cat .build-stand)" != "$FE_STAND" ]; then
  schritt "Oberfläche bauen"
  npm ci --no-audit --no-fund --loglevel=error
  VITE_API_BASE_URL=/api npm run build
  rm -rf "$PROJEKT/backend/static"
  cp -R dist "$PROJEKT/backend/static"
  echo "$FE_STAND" > .build-stand
fi

# --- Starten -----------------------------------------------------------------------------
cd "$PROJEKT/backend"
schritt "Crawler läuft auf $URL"
echo "Zum Beenden dieses Fenster schließen oder Ctrl+C drücken."

(
  for _ in $(seq 1 60); do
    if curl -fs "$URL/api/health" >/dev/null 2>&1; then
      open "$URL" 2>/dev/null || true
      exit 0
    fi
    sleep 1
  done
) &

exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
