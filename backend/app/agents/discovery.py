"""Discovery-Agent (Kapitel 18): findet neue/veränderte/entfernte Kandidaten über den

Connector eines Portals. Kennt bewusst keine Portal-Technik (das ist Aufgabe des Connectors)
und keine inhaltliche Detailauswertung (das ist Aufgabe von Analysis/Duplicate) - nur die
fachliche Frage "welche Kandidaten gibt es gerade und welche davon sind neu für uns".
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue
from app.agents.connector import CONNECTORS
from app.exceptions import AccessBlocked, TechnicalFailure
from app.models import Job, Portal, Tender


def run_discovery(db: Session, job: Job) -> dict:
    """Handler für Jobs vom Typ 'discovery'. Erzeugt 'analysis'-Jobs für neue/veränderte

    Kandidaten (Kapitel 19.3, Schritt 1) und markiert aus der aktuellen Liste verschwundene,
    fristabgelaufene Ausschreibungen als 'abgelaufen'.
    """
    portal = db.get(Portal, job.portal_id)
    if portal is None:
        raise TechnicalFailure(f"Unbekanntes Portal für Job {job.id}: {job.portal_id}")

    connector_cls = CONNECTORS.get(portal.slug)
    if connector_cls is None:
        raise TechnicalFailure(f"Kein Connector für Portal-Slug '{portal.slug}' registriert.")

    connector = connector_cls()
    try:
        candidates = connector.iter_all_candidates()
    finally:
        connector.close()

    known_ids = {
        t.externe_id
        for t in db.scalars(
            select(Tender).where(Tender.portal_id == portal.id, Tender.externe_id.is_not(None))
        )
    }
    current_ids = {c.externe_id for c in candidates}

    enqueued = 0
    for candidate in candidates:
        queue.enqueue(
            db,
            "analysis",
            portal_id=portal.id,
            ziel_id=candidate.externe_id,
            payload={
                "externe_id": candidate.externe_id,
                "detail_url": candidate.detail_url,
                "listen_metadaten": candidate.listen_metadaten,
                "titel_hint": candidate.titel_hint,
            },
        )
        enqueued += 1

    verschwunden = known_ids - current_ids
    abgelaufen_markiert = 0
    if verschwunden:
        for tender in db.scalars(
            select(Tender).where(Tender.portal_id == portal.id, Tender.externe_id.in_(verschwunden))
        ):
            if tender.status not in ("abgelaufen", "vergeben") and (
                tender.angebotsfrist is None or tender.angebotsfrist < datetime.utcnow()
            ):
                tender.status = "abgelaufen"
                abgelaufen_markiert += 1
        db.commit()

    return {
        "kandidaten_gesamt": len(candidates),
        "neu_oder_zu_pruefen": enqueued,
        "als_abgelaufen_markiert": abgelaufen_markiert,
    }
