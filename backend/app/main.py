from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api import assistant, categories, escalations, portals, run, search_profiles, tenders
from app.config import settings
from app.db import SessionLocal, init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import run_seed

# Vom Docker-Build erzeugtes Frontend-Bundle (siehe Dockerfile) - lokal (npm run dev) existiert
# dieses Verzeichnis nicht, dann bleibt die API-only-Auslieferung unten einfach inaktiv.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
    if settings.scheduler_enabled:
        start_scheduler()
    yield
    if settings.scheduler_enabled:
        stop_scheduler()


app = FastAPI(title="Ausschreibungs-Crawler API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders.router, prefix="/api")
app.include_router(portals.router, prefix="/api")
app.include_router(search_profiles.router, prefix="/api")
app.include_router(escalations.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(run.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")


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
