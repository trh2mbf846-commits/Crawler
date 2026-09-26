"""Discovery-Agent (Kapitel 18): findet neue/veränderte/entfernte Kandidaten über den

Connector eines Portals. Kennt bewusst keine Portal-Technik (das ist Aufgabe des Connectors)
und keine inhaltliche Detailauswertung (das ist Aufgabe von Analysis/Duplicate) - nur die
fachliche Frage "welche Kandidaten gibt es gerade und welche davon sind neu für uns".
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import queue
from app.agents.connector import CONNECTORS
from app.agents.connector.base import RawCandidate
from app.config import settings
from app.exceptions import AccessBlocked, TechnicalFailure
from app.models import Job, KandidatenStand, Portal, Tender


def fingerabdruck(candidate: RawCandidate) -> str:
    """Stabiler Hash der Listendaten (Frist, Vergabestelle, Titel, Link …) eines Kandidaten."""
    daten = json.dumps(
        [candidate.detail_url, candidate.titel_hint, candidate.listen_metadaten],
        sort_keys=True, default=str, ensure_ascii=False,
    )
    return hashlib.sha1(daten.encode("utf-8")).hexdigest()


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

    # Inkrementell (26.09.2026): bekannte Ausschreibungen mit unveränderten Listendaten, die vor
    # kurzem schon im Detail abgerufen wurden, überspringen.
    staende = {
        s.externe_id: s
        for s in db.scalars(select(KandidatenStand).where(KandidatenStand.portal_id == portal.id))
    }
    jetzt = datetime.utcnow()
    frisch_ab = jetzt - timedelta(days=settings.detail_neupruefung_tage)

    enqueued = 0
    unveraendert: list[str] = []
    for candidate in candidates:
        fp = fingerabdruck(candidate)
        stand = staende.get(candidate.externe_id)
        if (
            candidate.externe_id in known_ids
            and stand is not None
            and stand.fingerabdruck == fp
            and stand.zuletzt_abgerufen_am >= frisch_ab
        ):
            unveraendert.append(candidate.externe_id)
            continue
        if stand is None:
            stand = KandidatenStand(portal_id=portal.id, externe_id=candidate.externe_id, fingerabdruck=fp)
            db.add(stand)
            staende[candidate.externe_id] = stand
        stand.fingerabdruck = fp
        stand.zuletzt_abgerufen_am = jetzt
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

    # Weiterhin in der Liste des Portals - also noch aktuell, nur nicht erneut abgerufen. In Blöcken,
    # damit ältere SQLite-Versionen (Grenze 999 Parameter je Anweisung) nicht scheitern.
    for start in range(0, len(unveraendert), 500):
        db.execute(
            update(Tender)
            .where(Tender.portal_id == portal.id, Tender.externe_id.in_(unveraendert[start:start + 500]))
            .values(zuletzt_geprueft_am=jetzt)
        )
    db.commit()

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
        "unveraendert_uebersprungen": len(unveraendert),
        "als_abgelaufen_markiert": abgelaufen_markiert,
    }
