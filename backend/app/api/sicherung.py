"""Sicherung der Datenbank zum Herunterladen: alle eigenen Eingaben (Profil, Referenzen, Themen,
Merkliste, Checklisten, Suchprofile) und die gesammelten Ausschreibungen liegen in einer Datei.
Dient als Backup und als "Startdatei" für weitere Geräte (docs/ANLEITUNG-kollegen.md). Konsistent auch
während der Crawler schreibt (SQLite-Backup-API statt Dateikopie - die Datenbank läuft im WAL-Modus)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.config import settings

router = APIRouter(tags=["sicherung"])


@router.get("/datenbank-sicherung")
def sicherung() -> FileResponse:
    if not settings.database_url.startswith("sqlite:///"):
        raise HTTPException(501, "Sicherung per Download ist nur für die SQLite-Datenbank vorgesehen.")
    quelle = settings.database_url.removeprefix("sqlite:///")
    handle, ziel = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    # Konsistente Kopie auch während der Crawler schreibt (SQLite-Backup-API statt Datei kopieren).
    with sqlite3.connect(quelle) as src, sqlite3.connect(ziel) as dst:
        src.backup(dst)
    return FileResponse(
        ziel,
        media_type="application/vnd.sqlite3",
        filename=f"crawler-sicherung-{datetime.now():%Y-%m-%d}.db",
        background=BackgroundTask(os.remove, ziel),
    )
