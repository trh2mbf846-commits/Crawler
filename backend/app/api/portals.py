from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Portal
from app.pipeline import run_portal_cycle
from app.schemas import PortalHealthOut, RunTriggerOut
from app.serializers import portal_to_health_out

router = APIRouter(tags=["portals"])


@router.get("/portals", response_model=list[PortalHealthOut])
def list_portals(db: Session = Depends(get_db)) -> list[PortalHealthOut]:
    portals = db.scalars(select(Portal).order_by(Portal.vorgegeben.desc(), Portal.name))
    return [portal_to_health_out(db, p) for p in portals]


@router.post("/portals/{portal_id}/run", response_model=RunTriggerOut)
def run_portal(portal_id: str, db: Session = Depends(get_db)) -> RunTriggerOut:
    """Manuell auslösbarer Testlauf eines Connectors (Kapitel 8.1, Phase-1-Abnahmekriterium).

    Läuft synchron in dieser Anfrage (MVP-Vereinfachung, siehe README) - bei Zugriffsschranken
    (Kapitel 9.2) landet der Lauf als Eskalation im Entscheidungs-Posteingang statt eines Fehlers.
    """
    portal = db.get(Portal, portal_id)
    if portal is None:
        raise HTTPException(404, "Portal nicht gefunden.")
    ergebnis = run_portal_cycle(db, portal)
    return RunTriggerOut(started=True, ergebnis=ergebnis)
