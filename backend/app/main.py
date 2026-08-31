from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import categories, escalations, portals, search_profiles, tenders
from app.config import settings
from app.db import SessionLocal, init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import run_seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
    start_scheduler()
    yield
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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
