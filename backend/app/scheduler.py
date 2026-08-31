"""Scheduler (Kapitel 8.1, 17): stößt wiederkehrende, portalabhängige Connector-Läufe an.

Bewusst einfach gehalten (APScheduler, ein Prozess) statt überdimensionierter
Job-Queue-Infrastruktur, wie in Kapitel 5.2 als Vorgabe formuliert ("kein überdimensionierter
Scheduling-Mechanismus im MVP"). Für den Produktivbetrieb über Monate hinweg (Kapitel 17) reicht
das, solange der Prozess dauerhaft läuft; ein Neustart verliert keine Daten (Jobs/Tenders sind
in der DB persistiert, Kapitel 17.3 "zustandsbehaftet"), lediglich der In-Memory-Scheduler-Takt
setzt neu auf.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Portal
from app.pipeline import run_portal_cycle

logger = logging.getLogger("ausschreibungscrawler.scheduler")

_scheduler: BackgroundScheduler | None = None


def _run_portal_job(portal_id: str) -> None:
    db = SessionLocal()
    try:
        portal = db.get(Portal, portal_id)
        if portal is None or not portal.aktiv:
            return
        try:
            ergebnis = run_portal_cycle(db, portal)
            logger.info("Portal-Lauf %s abgeschlossen: %s", portal.slug, ergebnis)
        except Exception:
            logger.exception("Portal-Lauf %s mit unerwartetem Fehler", portal.slug)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler()
    db = SessionLocal()
    try:
        for portal in db.scalars(select(Portal).where(Portal.aktiv.is_(True))):
            scheduler.add_job(
                _run_portal_job,
                "interval",
                minutes=portal.intervall_minuten,
                args=[portal.id],
                id=f"portal-{portal.slug}",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
    finally:
        db.close()

    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
