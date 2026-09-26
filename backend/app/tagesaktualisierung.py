"""Tägliche automatische Aktualisierung (Nutzeranfrage 25.09.2026: "jeden Morgen um 7 Uhr ein Lauf,
statt selbst auf Aktualisieren zu klicken").

Unabhängig vom periodischen Portal-Scheduler (scheduler.py, im Deployment/Mac-Start bewusst aus):
genau ein Lauf pro Tag zur eingestellten Uhrzeit (CRAWLER_AUTO_AKTUALISIEREN_UHRZEIT, Default
"07:00", lokale Zeit des Rechners; leer = aus). Nutzt denselben Lauf wie der Aktualisieren-Button
(api/run.py:start_run), der Fortschritt ist also ganz normal in der Übersicht sichtbar.

Läuft nur, solange der Crawler läuft. War er um 7 Uhr aus, wird der verpasste Lauf beim nächsten
Start nachgeholt (kurz nach dem Start, sofern heute seit der eingestellten Uhrzeit noch kein Lauf
stattgefunden hat).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import HTTPException
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import SourceHealthMetric

logger = logging.getLogger("ausschreibungscrawler.tagesaktualisierung")

_scheduler: BackgroundScheduler | None = None
NACHHOL_VERZOEGERUNG_SEKUNDEN = 60


def uhrzeit() -> tuple[int, int] | None:
    """Eingestellte Uhrzeit als (Stunde, Minute), None = automatische Aktualisierung aus."""
    wert = (settings.auto_aktualisieren_uhrzeit or "").strip()
    if not wert:
        return None
    try:
        stunde, minute = (int(teil) for teil in wert.split(":", 1))
    except ValueError:
        logger.warning("Ungültige CRAWLER_AUTO_AKTUALISIEREN_UHRZEIT %r - automatische Aktualisierung aus", wert)
        return None
    if not (0 <= stunde <= 23 and 0 <= minute <= 59):
        logger.warning("Ungültige CRAWLER_AUTO_AKTUALISIEREN_UHRZEIT %r - automatische Aktualisierung aus", wert)
        return None
    return stunde, minute


def anzeige_uhrzeit() -> str | None:
    zeit = uhrzeit()
    return f"{zeit[0]:02d}:{zeit[1]:02d}" if zeit else None


def _starte_lauf() -> None:
    from app.api.run import start_run  # spät importiert: api.run importiert FastAPI-Router

    try:
        start_run()
        logger.info("Automatische Tagesaktualisierung gestartet.")
    except HTTPException:
        logger.info("Automatische Tagesaktualisierung übersprungen - es läuft bereits eine Aktualisierung.")
    except Exception:
        logger.exception("Automatische Tagesaktualisierung konnte nicht gestartet werden.")


def lauf_heute_verpasst(jetzt_lokal: datetime, letzter_lauf_utc: datetime | None, stunde: int, minute: int) -> bool:
    """Ist die heutige Startzeit schon vorbei, ohne dass seitdem ein Lauf stattgefunden hat?"""
    faellig_lokal = jetzt_lokal.replace(hour=stunde, minute=minute, second=0, microsecond=0)
    if jetzt_lokal < faellig_lokal:
        return False
    if letzter_lauf_utc is None:
        return True
    # lauf_am wird als naive UTC-Zeit gespeichert (datetime.utcnow) - in lokale Zeit umrechnen.
    letzter_lauf_lokal = letzter_lauf_utc.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    return letzter_lauf_lokal < faellig_lokal


def _letzter_lauf() -> datetime | None:
    db = SessionLocal()
    try:
        return db.scalar(select(func.max(SourceHealthMetric.lauf_am)))
    finally:
        db.close()


def start_tagesaktualisierung() -> BackgroundScheduler | None:
    global _scheduler
    zeit = uhrzeit()
    if zeit is None or _scheduler is not None:
        return _scheduler
    stunde, minute = zeit

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _starte_lauf,
        CronTrigger(hour=stunde, minute=minute),
        id="tagesaktualisierung",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    if lauf_heute_verpasst(datetime.now(), _letzter_lauf(), stunde, minute):
        logger.info("Heutige automatische Aktualisierung (%02d:%02d) wurde verpasst - wird gleich nachgeholt.", stunde, minute)
        scheduler.add_job(
            _starte_lauf,
            "date",
            run_date=datetime.now() + timedelta(seconds=NACHHOL_VERZOEGERUNG_SEKUNDEN),
            id="tagesaktualisierung-nachholen",
        )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Automatische Aktualisierung aktiv: täglich um %02d:%02d.", stunde, minute)
    return scheduler


def stop_tagesaktualisierung() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
