"""Analysis-Agent (Kapitel 18): ruft die Detailseite eines Kandidaten ab und extrahiert die

portalspezifischen Rohfelder. Reines Parsing, keine fachliche Bewertung.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import queue
from app.agents.connector import CONNECTORS
from app.agents.connector.base import RawCandidate
from app.exceptions import TechnicalFailure
from app.models import Job, Portal

REQUIRED_FIELDS = ("titel",)  # Kapitel 6 Pflichtfelder-Minimum fürs Parsing; weitere in normalization.py geprüft


def run_analysis(db: Session, job: Job) -> dict:
    portal = db.get(Portal, job.portal_id)
    if portal is None:
        raise TechnicalFailure(f"Unbekanntes Portal für Job {job.id}: {job.portal_id}")

    connector_cls = CONNECTORS.get(portal.slug)
    if connector_cls is None:
        raise TechnicalFailure(f"Kein Connector für Portal-Slug '{portal.slug}' registriert.")

    candidate = RawCandidate(
        externe_id=job.payload["externe_id"],
        detail_url=job.payload["detail_url"],
        titel_hint=job.payload.get("titel_hint"),
        listen_metadaten=job.payload.get("listen_metadaten") or {},
    )

    connector = connector_cls()
    try:
        raw = connector.fetch_detail(candidate)
    finally:
        connector.close()

    fehlende_pflichtfelder = [f for f in REQUIRED_FIELDS if not raw.felder.get(f)]
    if fehlende_pflichtfelder:
        # Kapitel 24 (Analysis-Agent DoD): fehlende Pflichtfelder aktiv melden statt still leer lassen.
        raw.felder["_fehlende_pflichtfelder"] = fehlende_pflichtfelder

    queue.enqueue(
        db,
        "normalization",
        portal_id=portal.id,
        ziel_id=job.ziel_id,
        correlation_id=job.correlation_id,
        payload={
            "externe_id": raw.externe_id,
            "detail_url": raw.detail_url,
            "raw_felder": raw.felder,
        },
    )
    return {"fehlende_pflichtfelder": fehlende_pflichtfelder}
