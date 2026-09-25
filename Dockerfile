# Ein-Container-Deployment für den Aktualisieren-Button (Nutzeranfrage 01.09.2026: kein
# Dauerbetrieb/permanentes Hintergrund-Update nötig, nur ein manueller Refresh-Button).
# Baut Frontend + Backend in ein Image; das Backend liefert das gebaute Frontend selbst aus
# (siehe backend/app/main.py "spa"-Fallback), damit nur ein einziger Dienst/Link nötig ist.
#
# Build-Kontext ist dieses Verzeichnis (ausschreibungscrawler/), NICHT das Repository-Root -
# das Repo enthält im Root auch ein unabhängiges Brettspiel-Projekt, das hier nichts verloren
# hat (siehe README). Also z. B. `docker build -f Dockerfile .` aus diesem Ordner heraus, oder
# bei Render/Fly "Root Directory" auf `ausschreibungscrawler` setzen (siehe render.yaml/fly.toml).

# ---------- Stage 1: Frontend bauen ----------
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# Gleicher Ursprung wie die API (kein CORS/keine feste Domain nötig) - siehe main.py "spa"-Route.
ENV VITE_API_BASE_URL=/api
# Optional (Nutzeranfrage 25.09.2026, API-Absicherung): beim Build mitgeben, z. B.
# `docker build --build-arg VITE_API_KEY=... .`, muss zum Backend-seitigen CRAWLER_API_KEY
# passen (siehe app/security.py). Leer lassen = API bleibt offen (Entwicklungs-Default).
ARG VITE_API_KEY=""
ENV VITE_API_KEY=${VITE_API_KEY}
RUN npm run build

# ---------- Stage 2: Backend + ausgeliefertes Frontend ----------
FROM python:3.11-slim AS backend
WORKDIR /app

# Playwright/Chromium-Systemabhängigkeiten (Kapitel 3: DB Bieterportal braucht Headless-Browser).
RUN apt-get update && apt-get install -y --no-install-recommends \
      wget gnupg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./static

ENV PYTHONUNBUFFERED=1
# Nutzerwunsch: kein Dauerbetrieb - der periodische Scheduler bleibt aus, nur der manuelle
# Aktualisieren-Button (POST /api/run-all) löst Portal-Läufe aus.
ENV CRAWLER_SCHEDULER_ENABLED=false

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
