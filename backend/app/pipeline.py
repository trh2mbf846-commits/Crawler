"""Pipeline-Runner: verarbeitet Jobs aus der zentralen Warteschlange (Kapitel 19) und stellt

den manuell auslösbaren Testlauf sowie den Scheduler-Einstiegspunkt bereit (Kapitel 8.1,
Phase-1-Abnahmekriterium "Manuell auslösbarer Testlauf aller drei Connectoren").
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app import queue
from app.agents import analysis, classification, discovery, duplicate, normalization, source_health
from app.exceptions import AccessBlocked, TechnicalFailure
from app.models import Job, Portal

logger = logging.getLogger("ausschreibungscrawler.pipeline")

AGENT_HANDLERS: dict[str, Callable[[Session, Job], dict]] = {
    "discovery": discovery.run_discovery,
    "analysis": analysis.run_analysis,
    "normalization": normalization.run_normalization,
    "duplicate": duplicate.run_duplicate,
    "classification": classification.run_classification,
}


def process_job(db: Session, job: Job) -> None:
    handler = AGENT_HANDLERS.get(job.typ)
    if handler is None:
        queue.mark_failed(db, job, job.typ, f"Kein Handler für Job-Typ '{job.typ}' registriert.")
        return

    with queue.timer() as t:
        try:
            details = handler(db, job)
        except AccessBlocked as exc:
            queue.escalate(
                db, job, job.typ,
                kategorie=exc.kategorie, kontext=exc.kontext, optionen=exc.optionen, empfehlung=exc.empfehlung,
            )
            logger.warning("Job %s (%s) eskaliert: %s", job.id, job.typ, exc.kontext)
            return
        except TechnicalFailure as exc:
            queue.mark_failed(db, job, job.typ, str(exc), dauer_ms=t.ms())
            logger.info("Job %s (%s) technisch fehlgeschlagen (Versuch %s/%s): %s", job.id, job.typ, job.versuch_nr, job.max_versuche, exc)
            return
        except Exception as exc:  # unerwarteter Fehler -> wie technischer Fehlschlag behandeln, nicht verschlucken
            queue.mark_failed(db, job, job.typ, f"Unerwarteter Fehler: {exc}", dauer_ms=t.ms())
            logger.exception("Job %s (%s) mit unerwartetem Fehler", job.id, job.typ)
            return

    queue.mark_succeeded(db, job, job.typ, details=details, dauer_ms=t.ms())


def drain_queue(db: Session, limit: int = 100000) -> int:
    processed = 0
    while processed < limit:
        job = queue.claim_next_any(db)
        if job is None:
            break
        process_job(db, job)
        processed += 1
    return processed


def drain_queue_for_portal(db: Session, portal_id: str, limit: int = 100000) -> int:
    """Wie drain_queue, aber nur Jobs eines Portals (Nutzeranfrage 05.09.2026: Portale beim

    Aktualisieren-Button parallel statt sequenziell abarbeiten) - verhindert, dass der Zyklus
    eines Portals versehentlich Jobs eines gleichzeitig laufenden anderen Portals übernimmt.
    """
    processed = 0
    while processed < limit:
        job = queue.claim_next_for_portal(db, portal_id)
        if job is None:
            break
        process_job(db, job)
        processed += 1
    return processed


def run_portal_cycle(db: Session, portal: Portal) -> dict:
    """Ein vollständiger Testlauf für genau ein Portal: Discovery anstoßen, die aus diesem

    Portal entstehenden Jobs bis zum Ende abarbeiten, Ergebnis für das Source-Health-Monitoring
    protokollieren.
    """
    start = datetime.utcnow()
    job = queue.enqueue(db, "discovery", portal_id=portal.id, payload={})

    processed = drain_queue_for_portal(db, portal.id)

    db.refresh(job)
    dauer_ms = int((datetime.utcnow() - start).total_seconds() * 1000)

    if job.status == "succeeded":
        details = job.events[-1].details or {}
        source_health.record_run(
            db, portal,
            erfolgreich=True,
            treffer_anzahl=details.get("kandidaten_gesamt", 0),
            neu_anzahl=details.get("neu_oder_zu_pruefen", 0),
            fehlerrate=_fehlerrate_dieser_lauf(db, portal.id, start),
            dauer_ms=dauer_ms,
        )
    elif job.status == "waiting_for_decision":
        source_health.record_run(db, portal, erfolgreich=False, fehlertyp="eskalation", dauer_ms=dauer_ms)
    else:
        source_health.record_run(db, portal, erfolgreich=False, fehlertyp=job.fehler or "unbekannt", dauer_ms=dauer_ms)

    gesundheit = source_health.evaluate(db, portal)
    return {"job_status": job.status, "jobs_verarbeitet": processed, "quellstatus": gesundheit}


def _fehlerrate_dieser_lauf(db: Session, portal_id: str, seit: datetime) -> float | None:
    from sqlalchemy import select

    from app.models import Job as JobModel

    lauf_jobs = list(
        db.scalars(select(JobModel).where(JobModel.portal_id == portal_id, JobModel.erstellt_am >= seit))
    )
    if not lauf_jobs:
        return None
    fehlgeschlagen = sum(1 for j in lauf_jobs if j.status == "failed")
    return fehlgeschlagen / len(lauf_jobs)
