"""Themen statt fest einprogrammierter Kategorien (26.09.2026).

Bisher standen Kategorien und KI-Suchbegriffe fest im Code (classification.py, keywords.py,
TED-Suchanfrage) - jede Erweiterung brauchte eine Code-Änderung. Themen liegen jetzt in der
Datenbank und sind in der Oberfläche ("Mein Profil" -> Themen) oder über Kevin pflegbar:

- Ein Thema wird zur Kategorie, sobald eines seiner Stichworte in Titel/Beschreibung vorkommt.
- Ist es "KI-bezogen", zählen seine Stichworte zusätzlich als KI-Treffer (Relevanz-Einstufung,
  danach wie immer die strengere KI-Nachprüfung durch das Sprachmodell) und werden in die
  TED-Suche aufgenommen, damit die Quelle solche Ausschreibungen überhaupt liefert.
- Nach jeder Änderung werden die offenen Ausschreibungen im Hintergrund neu eingeordnet.

Die übrigen Quellen (Bekanntmachungsservice, RIB, DTVP, e-Vergabe, Berlin) liefern ohnehin alle
Ausschreibungen ohne Themenfilter - dort wirkt ein neues Thema sofort auf die Einordnung.
"""
from __future__ import annotations

import logging
import threading

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Tender, TenderCategory, Thema

logger = logging.getLogger("ausschreibungscrawler.themen")

STANDARD_THEMEN = [
    {
        "name": "KI-Avatare & digitale Assistenten",
        "stichworte": [
            "avatar", "ki-avatar", "digitaler mensch", "digital human", "virtueller mitarbeiter",
            "virtuelle mitarbeiterin", "virtuelle assistenz", "virtueller assistent", "sprachavatar",
            "gebärdensprach-avatar", "gebärdenavatar", "3d-avatar", "videoavatar",
            # Kombi-Stichworte: alle Teile müssen vorkommen (Behörden schreiben selten "KI-Avatar" am Stück)
            "digitale + assistenz + ki", "virtuelle + beratung + ki", "animierte + figur",
        ],
        "ki_bezogen": True,
    },
    {
        "name": "KI-Training & Schulung",
        "stichworte": [
            # Menschen im KI-Einsatz schulen ...
            "ki-schulung", "ki-training", "ki-weiterbildung", "ki-fortbildung", "ki-kompetenz",
            "ki-qualifizierung", "ki-workshop", "ki-lernangebot", "prompt-engineering", "prompting",
            "schulung künstliche intelligenz", "weiterbildung künstliche intelligenz",
            # ... und KI-Modelle trainieren
            "training von ki", "trainingsdaten", "datenannotation", "annotation von daten",
            "fine-tuning", "feinabstimmung",
            # Kombi-Stichworte ("Schulungen zum Einsatz von KI", "Weiterbildung künstliche Intelligenz")
            "schulung + ki", "schulung + künstliche intelligenz", "weiterbildung + ki",
            "fortbildung + ki", "qualifizierung + ki", "training + künstliche intelligenz",
            "workshop + künstliche intelligenz", "workshop + ki",
        ],
        "ki_bezogen": True,
    },
]


def lege_standard_themen_an(db: Session) -> None:
    vorhanden = {t.name for t in db.scalars(select(Thema))}  # inkl. gelöschter
    for daten in STANDARD_THEMEN:
        if daten["name"] not in vorhanden:
            db.add(Thema(**daten))
    db.commit()


def aktive_themen(db: Session) -> list[Thema]:
    return list(db.scalars(select(Thema).where(Thema.aktiv.is_(True), Thema.geloescht.is_(False)).order_by(Thema.name)))


def _normiert(text: str) -> str:
    return f" {' '.join(text.lower().split())} "


def _teil_trifft(teil: str, text: str) -> bool:
    teil = " ".join(teil.lower().split())
    if not teil:
        return False
    # Wortanfang muss passen ("schulung" trifft "Schulungen", aber "ki" nicht "Kiel"/"Kita"):
    # sehr kurze Teile (<= 3 Zeichen) müssen als ganzes Wort (oder mit Bindestrich) stehen.
    ende = r"(?![a-zäöüß])" if len(teil) <= 3 else ""
    return re.search(rf"(?<![a-zäöüß0-9]){re.escape(teil)}{ende}", text) is not None


def stichwort_trifft(stichwort: str, text: str) -> bool:
    """Einfaches Stichwort oder Kombi-Stichwort "a + b" (alle Teile müssen vorkommen)."""
    return all(_teil_trifft(teil, text) for teil in stichwort.split("+"))


def themen_treffer(db: Session, *texte: str | None) -> tuple[list[str], list[str]]:
    """(passende Themennamen, getroffene Stichworte KI-bezogener Themen)."""
    text = _normiert(" ".join(t for t in texte if t))
    namen, ki_stichworte = [], []
    for thema in aktive_themen(db):
        treffer = [s for s in thema.stichworte if s and stichwort_trifft(s, text)]
        if treffer:
            namen.append(thema.name)
            if thema.ki_bezogen:
                ki_stichworte.extend(treffer)
    return namen, ki_stichworte


def ted_suchbegriffe(db: Session) -> list[str]:
    """Zusätzliche TED-Volltextbegriffe aus KI-bezogenen Themen (Umlaute umschrieben)."""
    ersatz = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
    begriffe: list[str] = []
    for thema in aktive_themen(db):
        if thema.ki_bezogen:
            for s in thema.stichworte:
                if "+" in s:
                    continue  # Kombi-Stichworte lassen sich nicht als einzelner Volltextbegriff suchen
                b = s.lower().translate(ersatz).replace('"', "").strip()
                if len(b) >= 4 and b not in begriffe:
                    begriffe.append(b)
    return begriffe[:40]  # Anfrage kurz halten


def ordne_neu_ein(db: Session) -> int:
    """Offene Ausschreibungen nach geänderten Themen neu einordnen (ohne Sprachmodell).

    Themen-Kategorien werden ergänzt bzw. entfernt; ist eine bisher als "nicht" KI-relevant
    eingestufte Ausschreibung jetzt über ein KI-Thema getroffen, wird sie "moeglich" - die
    KI-Nachprüfung im nächsten Nachlauf entscheidet dann streng.
    """
    from app.agents import ranking

    themen_namen = {t.name for t in db.scalars(select(Thema))}
    geaendert = 0
    for tender in db.scalars(select(Tender).where(Tender.status.not_in(("abgelaufen", "vergeben")))):
        namen, ki_stichworte = themen_treffer(db, tender.titel, tender.kurzbeschreibung)
        bisher = {tk.category.name for tk in tender.kategorien}
        neu = (bisher - themen_namen) | set(namen)
        hochgestuft = bool(ki_stichworte) and tender.ki_relevanz_score in (None, "nicht") and tender.ki_relevanz_quelle != "llm"
        if neu == bisher and not hochgestuft:
            continue
        if neu != bisher:
            db.execute(TenderCategory.__table__.delete().where(TenderCategory.tender_id == tender.id))
            for name in neu:
                kategorie = db.scalars(select(Category).where(Category.name == name)).first()
                if kategorie is None:
                    kategorie = Category(name=name)
                    db.add(kategorie)
                    db.flush()
                db.add(TenderCategory(tender_id=tender.id, category_id=kategorie.id))
        if hochgestuft:
            tender.ki_relevanz_score = "moeglich"
            tender.ki_relevanz_quelle = "keyword"
            tender.ki_relevanz_begruendung = f"Treffer über Thema: {', '.join(dict.fromkeys(ki_stichworte))} (regelbasiert)."
        geaendert += 1
        db.commit()
        ranking.compute_and_store(db, tender)
    if geaendert:
        logger.info("Themen: %d Ausschreibungen neu eingeordnet.", geaendert)
    return geaendert


def ordne_im_hintergrund_neu_ein() -> None:
    from app.db import SessionLocal

    def lauf() -> None:
        db = SessionLocal()
        try:
            ordne_neu_ein(db)
        except Exception:
            logger.exception("Neu-Einordnung nach Themenänderung fehlgeschlagen.")
        finally:
            db.close()

    threading.Thread(target=lauf, name="themen-neu-einordnen", daemon=True).start()
