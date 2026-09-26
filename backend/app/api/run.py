"""Manueller "Aktualisieren"-Button für alle aktiven Portale (Nutzeranfrage 01.09.2026:

kein dauerhaftes Hintergrund-Update, sondern ein Button, der einmal alles durchsucht;
Nutzeranfrage 05.09.2026: "möglichst viele Ausschreibungen abbilden" + der Button soll
"nochmal alles durchsucht" - Portale laufen daher parallel statt nacheinander, damit ein
Aktualisieren-Lauf trotz wachsender Quellenzahl in vertretbarer Zeit fertig wird).

Läuft in Hintergrund-Threads statt in der HTTP-Anfrage selbst (Kapitel 9.1: mehrere
ratenlimitierte Portal-Läufe dauern je nach Portalanzahl mehrere Minuten - das würde jeden
vernünftigen HTTP-Timeout sprengen). Bewusst ein einfacher In-Memory-Zustand statt einer eigenen
Job-Warteschlange dafür (Kapitel 5.2: kein überdimensionierter Mechanismus) - das reicht für
einen Einzelprozess-Dienst mit einem "einen Lauf zur Zeit"-Button.

Die parallelen Portal-Läufe schreiben gleichzeitig in dieselbe SQLite-Datenbank - dafür wurde
in app/db.py der WAL-Modus aktiviert und in app/queue.py das Job-Claiming race-sicher gemacht
(atomare UPDATE...WHERE status='queued' statt SELECT+UPDATE), sonst könnten zwei Portal-Läufe
denselben Job doppelt verarbeiten.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app import nachlauf
from app.db import SessionLocal
from app.models import Portal
from app.pipeline import run_portal_cycle
from app.schemas import RunAllPortalResultOut, RunAllStatusOut
from app.tagesaktualisierung import anzeige_uhrzeit

logger = logging.getLogger("ausschreibungscrawler.run_all")
router = APIRouter(tags=["run"])

# Deckelt, wie viele Portale gleichzeitig laufen - unabhängig von Rate-Limiting je Portal (das
# bleibt in jedem Connector selbst bestehen), nur um die SQLite-Schreiblast nicht unbegrenzt
# ansteigen zu lassen.
_MAX_GLEICHZEITIG = 6

_lock = threading.Lock()
_state: dict = {
    "laeuft": False,
    "gestartet_am": None,
    "beendet_am": None,
    "aktuelle_portale": [],
    "ergebnisse": [],
}


def _run_ein_portal(portal_id: str, portal_name: str, portal_slug: str) -> dict:
    with _lock:
        _state["aktuelle_portale"].append(portal_name)
    db = SessionLocal()
    try:
        portal = db.get(Portal, portal_id)
        ergebnis = run_portal_cycle(db, portal)
        return {
            "portal_id": portal_id,
            "portal_name": portal_name,
            "status_ampel": ergebnis["quellstatus"]["status_ampel"],
            "treffer_anzahl": ergebnis["quellstatus"].get("letzte_trefferzahl"),
            "fehler": None,
        }
    except Exception as exc:  # ein fehlschlagendes Portal darf die anderen nicht verhindern (Kapitel 9.4)
        logger.exception("Aktualisieren-Lauf: unerwarteter Fehler bei %s", portal_slug)
        return {
            "portal_id": portal_id,
            "portal_name": portal_name,
            "status_ampel": "rot",
            "treffer_anzahl": None,
            "fehler": str(exc),
        }
    finally:
        db.close()
        with _lock:
            if portal_name in _state["aktuelle_portale"]:
                _state["aktuelle_portale"].remove(portal_name)


def _run_all_worker(portal_ids: list[str] | None = None) -> None:
    db = SessionLocal()
    try:
        query = select(Portal).where(Portal.aktiv.is_(True)).order_by(Portal.name)
        if portal_ids:
            query = query.where(Portal.id.in_(portal_ids))
        portale = list(db.scalars(query))
    finally:
        db.close()

    try:
        with ThreadPoolExecutor(max_workers=min(_MAX_GLEICHZEITIG, max(len(portale), 1))) as pool:
            futures = [pool.submit(_run_ein_portal, p.id, p.name, p.slug) for p in portale]
            for future in as_completed(futures):
                eintrag = future.result()
                with _lock:
                    _state["ergebnisse"].append(eintrag)
    finally:
        with _lock:
            _state["laeuft"] = False
            _state["aktuelle_portale"] = []
            _state["beendet_am"] = datetime.utcnow()
        # KI-Nachprüfung + Benachrichtigung über neue Treffer im Hintergrund (app/nachlauf.py).
        nachlauf.starte_im_hintergrund()


def start_run(portal_ids: list[str] | None = None) -> RunAllStatusOut:
    """Stößt einen Aktualisieren-Lauf an - für alle aktiven Portale (portal_ids=None) oder nur

    für die übergebenen. Gemeinsame Grundlage für den Aktualisieren-Button (POST /run-all) UND
    für Crawler Kevins "aktualisieren_starten"-Werkzeug (Nutzeranfrage 25.09.2026) - ein einziger
    In-Memory-Laufzustand, egal wer den Lauf angestoßen hat, damit der Button in der Übersicht
    auch einen von Kevin gestarteten Lauf korrekt als laufend anzeigt.
    """
    with _lock:
        if _state["laeuft"]:
            raise HTTPException(409, "Es läuft bereits eine Aktualisierung.")
        _state["laeuft"] = True
        _state["gestartet_am"] = datetime.utcnow()
        _state["beendet_am"] = None
        _state["aktuelle_portale"] = []
        _state["ergebnisse"] = []

    thread = threading.Thread(target=_run_all_worker, args=(portal_ids,), daemon=True)
    thread.start()

    return _status_out()


@router.post("/run-all", response_model=RunAllStatusOut)
def run_all() -> RunAllStatusOut:
    """Stößt einen Aktualisieren-Lauf für alle aktiven Portale an (Aktualisieren-Button) - alle

    Portale laufen parallel, damit der Lauf trotz wachsender Quellenzahl zügig fertig wird.
    """
    return start_run()


@router.get("/run-all/status", response_model=RunAllStatusOut)
def run_all_status() -> RunAllStatusOut:
    return _status_out()


def _status_out() -> RunAllStatusOut:
    with _lock:
        return RunAllStatusOut(
            laeuft=_state["laeuft"],
            gestartet_am=_state["gestartet_am"],
            beendet_am=_state["beendet_am"],
            aktuelle_portale=list(_state["aktuelle_portale"]),
            ergebnisse=[RunAllPortalResultOut(**e) for e in _state["ergebnisse"]],
            automatisch_um=anzeige_uhrzeit(),
        )
