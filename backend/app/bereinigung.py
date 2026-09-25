"""Einmalige, idempotente Bereinigung alter Datensätze beim Start (Nutzerrückmeldung 25.09.2026:
"viele falsch oder direkt Dokumente zum Download").

Bis zur Umstellung der Connectoren auf eForms-Verfahrenslinks (siehe
agents/connector/verfahrenslink.py) wurden gespeichert:
- Zuschlagsmitteilungen, Vertragsänderungen und Vorinformationen (eForms-Typen can-*, pin-*,
  veat) von TED und dem Bekanntmachungsservice - darauf kann man sich nicht bewerben;
- Bekanntmachungsservice-Einträge, deren Link nur auf die Homepage der Vergabestelle bzw. die
  allgemeine Suchseite zeigt statt auf das Verfahren.

Diese werden hier entfernt; der nächste Klick auf "Aktualisieren" holt die weiterhin offenen
Ausschreibungen mit korrektem Verfahrenslink neu. Gemerkte Ausschreibungen (★) bleiben immer
erhalten. Neue Datensätze erfüllen die Kriterien nie, daher ist mehrfaches Ausführen harmlos.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agents.connector.verfahrenslink import ist_verfahrensspezifisch
from app.models import Portal, SearchProfileHit, Tender

logger = logging.getLogger("ausschreibungscrawler.bereinigung")

_NICHT_BEWERBBAR = re.compile(r"^(can-|pin-|veat)", re.IGNORECASE)
_EFORMS_PORTALE = ("ted", "oeffentlichevergabe")


def _unbrauchbar(tender: Tender, slug: str) -> bool:
    if _NICHT_BEWERBBAR.match(tender.verfahrensart or ""):
        return True
    return slug == "oeffentlichevergabe" and not ist_verfahrensspezifisch(tender.direktlink or "")


def bereinige_unbrauchbare_ausschreibungen(db: Session) -> int:
    kandidaten = db.execute(
        select(Tender, Portal.slug)
        .join(Portal, Portal.id == Tender.portal_id)
        .where(Portal.slug.in_(_EFORMS_PORTALE), Tender.gemerkt.is_not(True))
    ).all()
    zu_loeschen = [tender for tender, slug in kandidaten if _unbrauchbar(tender, slug)]
    if not zu_loeschen:
        return 0
    ids = [t.id for t in zu_loeschen]
    for start in range(0, len(ids), 500):
        db.execute(delete(SearchProfileHit).where(SearchProfileHit.tender_id.in_(ids[start:start + 500])))
    for tender in zu_loeschen:
        db.delete(tender)
    db.commit()
    logger.info("Bereinigung: %d nicht bewerbbare bzw. falsch verlinkte Ausschreibungen entfernt", len(ids))
    return len(ids)
