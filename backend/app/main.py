from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import nachlauf
from app.api import (
    assistant,
    bewerbung,
    categories,
    escalations,
    portals,
    run,
    search_profiles,
    tenders,
    themen,
    wuensche,
)
from app.bereinigung import bereinige_unbrauchbare_ausschreibungen
from app.config import settings
from app.db import SessionLocal, init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.security import require_api_key
from app.seed import run_seed
from app.tagesaktualisierung import start_tagesaktualisierung, stop_tagesaktualisierung

# Vom Docker-Build erzeugtes Frontend-Bundle (siehe Dockerfile) - lokal (npm run dev) existiert
# dieses Verzeichnis nicht, dann bleibt die API-only-Auslieferung unten einfach inaktiv.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
        bereinige_unbrauchbare_ausschreibungen(db)
    finally:
        db.close()
    if settings.scheduler_enabled:
        start_scheduler()
    start_tagesaktualisierung()
    # Offene KI-Nachprüfungen und Benachrichtigungen (z. B. aus früheren Läufen) nachholen.
    nachlauf.starte_im_hintergrund()
    yield
    stop_tagesaktualisierung()
    if settings.scheduler_enabled:
        stop_scheduler()


app = FastAPI(title="Ausschreibungs-Crawler API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_geschuetzt = [Depends(require_api_key)]
app.include_router(tenders.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(portals.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(search_profiles.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(escalations.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(categories.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(run.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(assistant.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(wuensche.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(bewerbung.router, prefix="/api", dependencies=_geschuetzt)
app.include_router(themen.router, prefix="/api", dependencies=_geschuetzt)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


if FRONTEND_DIST.is_dir():
    # Einfaches Ein-Container-Deployment (Kapitel: Aktualisieren-Button statt Dauerbetrieb,
    # Nutzeranfrage 01.09.2026): Backend liefert zusätzlich das gebaute Frontend aus, damit
    # Person X einen einzigen Dienst/Link braucht statt zweier getrennter Hosts. Erst NACH den
    # /api-Routern registriert, damit diese immer Vorrang haben.
    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        kandidat = FRONTEND_DIST / full_path
        if full_path and kandidat.is_file():
            return FileResponse(kandidat)
        return FileResponse(FRONTEND_DIST / "index.html")
