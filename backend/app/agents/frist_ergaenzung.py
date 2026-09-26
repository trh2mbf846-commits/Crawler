"""Fehlende Angebotsfristen ergänzen (26.09.2026, "selbstheilende" Auswertung nach Profi-Empfehlung:
feste Regeln zuerst, Sprachmodell nur als Notlösung - und dann mit geprüfter Belegstelle).

Viele Bekanntmachungen liefern die Angebotsfrist nicht im strukturierten Datensatz (TED-Suchindex
bei ca. der Hälfte leer, einzelne eForms ohne BT-131), obwohl sie auf der verlinkten
Verfahrensseite steht. Ablauf je Ausschreibung ohne Frist (einmal, höchstens
settings.frist_ergaenzung_pro_lauf pro Nachlauf, KI-relevante und gemerkte zuerst):
1. Verfahrensseite abrufen (ein Request, wie bei der Go/No-Go-Bewertung);
2. Suchmuster ("Angebotsfrist: 12.10.2026 10:00", "Schlusstermin ... Angebote", ...);
3. nur wenn das nichts findet: Sprachmodell (lokal erlaubt) - übernommen wird die Frist nur, wenn
   das zitierte Belegstück wirklich im Seitentext vorkommt und das Datum darin steht (Prüfer-Schritt
   gegen erfundene Fristen).
Die Herkunft wird in Tender.frist_quelle vermerkt ("seite" bzw. "ki") und in der Oberfläche angezeigt.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app import prompts
from app.agents import ranking
from app.agents.bewertung import _verfahrensseite_text
from app.config import settings
from app.models import Tender

logger = logging.getLogger("ausschreibungscrawler.frist_ergaenzung")

_SCHLUESSEL = (
    r"(?:ablauf\s+der\s+)?angebotsfrist|schlusstermin[^.:]{0,60}angebot\w*|"
    r"frist\s+(?:für\s+den\s+)?eingang\s+der\s+angebote|angebotsabgabe\s+(?:bis|spätestens)|"
    r"einreichungsfrist|abgabefrist|abgabetermin|time\s+limit\s+for\s+receipt\s+of\s+tenders|deadline\s+for\s+receipt\s+of\s+tenders"
)
_DATUM = r"(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[^\d]{1,12}(\d{1,2})[:.](\d{2}))?"
_MUSTER = re.compile(rf"(?:{_SCHLUESSEL})[^0-9]{{0,80}}{_DATUM}", re.IGNORECASE)
_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?")


def frist_per_muster(text: str, jetzt: datetime | None = None) -> datetime | None:
    jetzt = jetzt or datetime.utcnow()
    for treffer in _MUSTER.finditer(text):
        tag, monat, jahr, stunde, minute = treffer.groups()
        try:
            frist = datetime(int(jahr), int(monat), int(tag), int(stunde or 0), int(minute or 0))
        except ValueError:
            continue
        if frist >= jetzt.replace(hour=0, minute=0, second=0, microsecond=0):
            return frist
    return None


def _normiert(text: str) -> str:
    return " ".join(text.lower().split())


def frist_per_ki(text: str) -> datetime | None:
    ergebnis = prompts.call_llm_json(prompts.FRIST_SYSTEM, text[:6000], lokal_erlaubt=True) or {}
    wert, beleg = ergebnis.get("angebotsfrist"), str(ergebnis.get("beleg") or "")
    if not wert or len(beleg) < 6 or _normiert(beleg) not in _normiert(text):
        return None  # Prüfer: ohne wörtlich vorhandenen Beleg keine Übernahme
    iso = _ISO.search(str(wert))
    if not iso:
        return None
    jahr, monat, tag, stunde, minute = iso.groups()
    try:
        frist = datetime(int(jahr), int(monat), int(tag), int(stunde or 0), int(minute or 0))
    except ValueError:
        return None
    # Das Datum muss auch im Beleg stehen (deutsch oder ISO geschrieben).
    im_beleg = f"{int(tag)}.{int(monat)}." in beleg.replace(" ", "") or f"{int(tag):02d}.{int(monat):02d}." in beleg or f"{jahr}-{monat}-{tag}" in beleg
    return frist if im_beleg else None


def kandidaten(db: Session, limit: int) -> list[Tender]:
    prioritaet = case(
        (Tender.gemerkt.is_(True), 0),
        (Tender.ki_relevanz_score == "stark", 1),
        (Tender.ki_relevanz_score == "moeglich", 2),
        else_=3,
    )
    return list(
        db.scalars(
            select(Tender)
            .where(
                Tender.angebotsfrist.is_(None),
                Tender.frist_ergaenzung_versucht.is_(False),
                Tender.status.not_in(("abgelaufen", "vergeben")),
                Tender.direktlink.is_not(None),
            )
            .order_by(prioritaet, Tender.erfasst_am.desc())
            .limit(limit)
        )
    )


def ergaenze_fristen(db: Session, limit: int | None = None) -> dict:
    ergaenzt = {"seite": 0, "ki": 0, "nicht_gefunden": 0}
    for tender in kandidaten(db, settings.frist_ergaenzung_pro_lauf if limit is None else limit):
        tender.frist_ergaenzung_versucht = True
        text = _verfahrensseite_text(tender.direktlink)
        frist, quelle = None, None
        if text:
            frist, quelle = frist_per_muster(text), "seite"
            if frist is None:
                frist, quelle = frist_per_ki(text), "ki"
        if frist is None:
            ergaenzt["nicht_gefunden"] += 1
        else:
            tender.angebotsfrist, tender.frist_quelle = frist, quelle
            ergaenzt[quelle] += 1
        db.commit()
        if frist is not None:
            ranking.compute_and_store(db, tender)
    if any(ergaenzt.values()):
        logger.info("Fristen-Ergänzung: %s", ergaenzt)
    return ergaenzt
