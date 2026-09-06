"""Manueller "Aktualisieren"-Button für alle aktiven Portale (Nutzeranfrage 01.09.2026:

kein dauerhaftes Hintergrund-Update, sondern ein Button, der einmal alles durchsucht).

Läuft in einem Hintergrund-Thread statt in der HTTP-Anfrage selbst (Kapitel 9.1: mehrere
ratenlimitierte Portal-Läufe hintereinander dauern je nach Portalanzahl mehrere Minuten - das
würde jeden vernünftigen HTTP-Timeout sprengen). Bewusst ein einfacher In-Memory-Zustand statt
einer eigenen Job-Warteschlange dafür (Kapitel 5.2: kein überdimensionierter Mechanismus) - das
reicht für einen Einzelprozess-Dienst mit einem "einen Lauf zur Zeit"-Button.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Portal
from app.pipeline import run_portal_cycle
from app.schemas import RunAllPortalResultOut, RunAllStatusOut

logger = logging.getLogger("ausschreibungscrawler.run_all")
router = APIRouter(tags=["run"])

_lock = threading.Lock()
_state: dict = {
    "laeuft": False,
    "gestartet_am": None,
    "beendet_am": None,
    "aktuelles_portal": None,
    "ergebnisse": [],
}


def _run_all_worker() -> None:
    db = SessionLocal()
    try:
        portale = list(db.scalars(select(Portal).where(Portal.aktiv.is_(True)).order_by(Portal.name)))
        for portal in portale:
            with _lock:
                _state["aktuelles_portal"] = portal.name
            try:
                ergebnis = run_portal_cycle(db, portal)
                eintrag = {
                    "portal_id": portal.id,
                    "portal_name": portal.name,
                    "status_ampel": ergebnis["quellstatus"]["status_ampel"],
                    "treffer_anzahl": ergebnis["quellstatus"].get("letzte_trefferzahl"),
                    "fehler": None,
                }
            except Exception as exc:  # ein fehlschlagendes Portal darf die anderen nicht verhindern (Kapitel 9.4)
                logger.exception("Aktualisieren-Lauf: unerwarteter Fehler bei %s", portal.slug)
                eintrag = {
                    "portal_id": portal.id,
                    "portal_name": portal.name,
                    "status_ampel": "rot",
                    "treffer_anzahl": None,
                    "fehler": str(exc),
                }
            with _lock:
                _state["ergebnisse"].append(eintrag)
    finally:
        db.close()
        with _lock:
            _state["laeuft"] = False
            _state["aktuelles_portal"] = None
            _state["beendet_am"] = datetime.utcnow()


@router.post("/run-all", response_model=RunAllStatusOut)
def run_all() -> RunAllStatusOut:
    """Stößt einen Aktualisieren-Lauf für alle aktiven Portale an (Aktualisieren-Button)."""
    with _lock:
        if _state["laeuft"]:
            raise HTTPException(409, "Es läuft bereits eine Aktualisierung.")
        _state["laeuft"] = True
        _state["gestartet_am"] = datetime.utcnow()
        _state["beendet_am"] = None
        _state["aktuelles_portal"] = None
        _state["ergebnisse"] = []

    thread = threading.Thread(target=_run_all_worker, daemon=True)
    thread.start()

    return _status_out()


@router.get("/run-all/status", response_model=RunAllStatusOut)
def run_all_status() -> RunAllStatusOut:
    return _status_out()


def _status_out() -> RunAllStatusOut:
    with _lock:
        return RunAllStatusOut(
            laeuft=_state["laeuft"],
            gestartet_am=_state["gestartet_am"],
            beendet_am=_state["beendet_am"],
            aktuelles_portal=_state["aktuelles_portal"],
            ergebnisse=[RunAllPortalResultOut(**e) for e in _state["ergebnisse"]],
        )
