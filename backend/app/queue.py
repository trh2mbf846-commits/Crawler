"""Job-/Ereignis-Warteschlange (Kapitel 17.4, 19). Agenten kommunizieren ausschließlich

über diese Schicht, nie durch direkte Aufrufe untereinander (Kapitel 19.1). Für den lokalen
Betrieb ist die Warteschlange DB-gestützt (Tabellen jobs/job_events/escalations) statt einer
externen Message-Broker-Infrastruktur - passend zur MVP-Vorgabe "keine überdimensionierte
Job-Queue-Infrastruktur" aus Kapitel 5.2, aber mit identischer Semantik (Zustandsautomat,
Idempotenz über correlation_id, strukturierte Ereignisse) wie in Kapitel 17-19 gefordert.
"""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Escalation, Job, JobEvent

JOB_TYPES = (
    "discovery",
    "analysis",
    "normalization",
    "duplicate",
    "classification",
    "search",
    "source_health",
)


def enqueue(
    db: Session,
    typ: str,
    *,
    portal_id: str | None = None,
    ziel_id: str | None = None,
    payload: dict | None = None,
    correlation_id: str | None = None,
    max_versuche: int = 3,
) -> Job:
    job = Job(
        typ=typ,
        portal_id=portal_id,
        ziel_id=ziel_id,
        correlation_id=correlation_id or str(uuid.uuid4()),
        payload=payload or {},
        status="queued",
        max_versuche=max_versuche,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next(db: Session, typ: str) -> Job | None:
    job = db.scalars(
        select(Job).where(Job.typ == typ, Job.status == "queued").order_by(Job.erstellt_am).limit(1)
    ).first()
    return _claim(db, job)


def claim_next_any(db: Session) -> Job | None:
    """Claimt den ältesten wartenden Job unabhängig vom Typ (Kapitel 19.1: eine zentrale Warteschlange)."""
    job = db.scalars(select(Job).where(Job.status == "queued").order_by(Job.erstellt_am).limit(1)).first()
    return _claim(db, job)


def _claim(db: Session, job: Job | None) -> Job | None:
    if job is None:
        return None
    job.status = "running"
    job.gestartet_am = datetime.utcnow()
    job.versuch_nr += 1
    db.commit()
    db.refresh(job)
    return job


def log_event(
    db: Session,
    job: Job,
    agent: str,
    ereignis: str,
    *,
    details: dict | None = None,
    dauer_ms: int | None = None,
) -> JobEvent:
    event = JobEvent(job_id=job.id, agent=agent, ereignis=ereignis, details=details, dauer_ms=dauer_ms)
    db.add(event)
    db.commit()
    return event


def mark_succeeded(db: Session, job: Job, agent: str, *, details: dict | None = None, dauer_ms: int | None = None) -> None:
    job.status = "succeeded"
    job.beendet_am = datetime.utcnow()
    db.commit()
    log_event(db, job, agent, "succeeded", details=details, dauer_ms=dauer_ms)


def mark_failed(db: Session, job: Job, agent: str, fehler: str, *, dauer_ms: int | None = None) -> None:
    """Technischer Fehlschlag -> Auto-Retry mit Backoff bis max_versuche (Kapitel 17.4)."""
    job.fehler = fehler
    if job.versuch_nr >= job.max_versuche:
        job.status = "failed"
        job.beendet_am = datetime.utcnow()
    else:
        job.status = "queued"  # wird beim naechsten Scheduler-Tick erneut versucht (Backoff im Scheduler)
    db.commit()
    log_event(db, job, agent, "failed", details={"fehler": fehler, "versuch_nr": job.versuch_nr}, dauer_ms=dauer_ms)


def escalate(
    db: Session,
    job: Job,
    agent: str,
    *,
    kategorie: str,
    kontext: str,
    optionen: list[str],
    empfehlung: str | None = None,
    portal_id: str | None = None,
) -> Escalation:
    """Echte Zugriffsschranke gemaess Abschnitt 9.2 -> nicht-blockierende Eskalation (Kapitel 17.2).

    Der betroffene Job wechselt in waiting_for_decision, alle uebrigen Jobs/Portale laufen
    unbeeinflusst weiter (Kernprinzip aus Kapitel 17.2).
    """
    job.status = "waiting_for_decision"
    job.beendet_am = datetime.utcnow()
    db.add(
        Escalation(
            job_id=job.id,
            portal_id=portal_id or job.portal_id,
            kategorie=kategorie,
            kontext=kontext,
            optionen=optionen,
            empfehlung=empfehlung,
            status="offen",
        )
    )
    db.commit()
    log_event(db, job, agent, "escalated", details={"kategorie": kategorie, "kontext": kontext})
    return db.scalars(
        select(Escalation).where(Escalation.job_id == job.id).order_by(Escalation.erstellt_am.desc())
    ).first()


@dataclass
class Timer:
    start: float

    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)


@contextmanager
def timer():
    t = Timer(time.perf_counter())
    yield t
