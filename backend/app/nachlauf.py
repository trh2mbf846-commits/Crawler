"""Was nach jeder Aktualisierung (und beim Start) im Hintergrund passiert, in dieser Reihenfolge:
1. KI-Nachprüfung markierter Ausschreibungen (agents/ki_nachpruefung.py),
2. fehlende Angebotsfristen aus den Verfahrensseiten ergänzen (agents/frist_ergaenzung.py),
3. Bedeutungsvektoren für neue Ausschreibungen (semantik.py, Suche nach Bedeutung),
4. Benachrichtigung über neue Treffer (benachrichtigung.py) - bewusst zuletzt, damit nichts
   gemeldet wird, was die Nachprüfung gerade herabgestuft hat.
"""
from __future__ import annotations

import logging
import threading

from app.agents import ki_nachpruefung
from app.benachrichtigung import benachrichtige
from app.agents.frist_ergaenzung import ergaenze_fristen
from app.db import SessionLocal
from app.semantik import aktualisiere_embeddings

logger = logging.getLogger("ausschreibungscrawler.nachlauf")

_lock = threading.Lock()


def fuehre_aus() -> None:
    if not _lock.acquire(blocking=False):
        return
    try:
        ki_nachpruefung.fuehre_nachpruefung_aus()
        db = SessionLocal()
        try:
            ergaenze_fristen(db)
            aktualisiere_embeddings(db)
            benachrichtige(db)
        finally:
            db.close()
    except Exception:
        logger.exception("Nachlauf mit unerwartetem Fehler abgebrochen.")
    finally:
        _lock.release()


def starte_im_hintergrund() -> None:
    threading.Thread(target=fuehre_aus, name="nachlauf", daemon=True).start()
