"""KI-Nachprüfung (Nutzeranfrage 25.09.2026: "Ausschreibungen, die nur nebenbei KI erwähnen,
werden zu oft als relevant markiert - eine zweite Prüfung durch Kevin, lokal und kostenlos").

Die regelbasierte Einstufung (classification.py) markiert schon bei einem allgemeinen IT-CPV-Code
oder einem Treffer wie "AI-" in einem Projektnamen als "moeglich"/"stark". Hier bewertet ein
Sprachmodell (lokal über Ollama oder Claude, siehe prompts.llm_anbieter) jede so markierte, noch
offene Ausschreibung ein zweites Mal mit strengeren Regeln (prompts.KI_RELEVANZ_SYSTEM).

Bewusst NICHT im Aktualisieren-Lauf selbst, sondern danach im Hintergrund: ein lokales Modell
braucht einige Sekunden pro Ausschreibung und soll den Lauf nicht ausbremsen. Jede Ausschreibung
wird nur einmal geprüft (ki_relevanz_quelle = "llm"). Ist kein Modell erreichbar, bleibt es
einfach bei der regelbasierten Einstufung und der nächste Lauf versucht es erneut.
"""
from __future__ import annotations

import logging
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import prompts
from app.agents import ranking
from app.config import settings
from app.db import SessionLocal
from app.keywords import find_cpv_hits
from app.models import Category, Tender, TenderCategory

logger = logging.getLogger("ausschreibungscrawler.ki_nachpruefung")

_KI_KATEGORIE = "KI & Machine Learning"
_RANG = {"nicht": 0, "moeglich": 1, "stark": 2}
_lock = threading.Lock()


def zu_pruefen(db: Session) -> list[Tender]:
    return list(
        db.scalars(
            select(Tender)
            .where(
                Tender.ki_relevanz_score.in_(("stark", "moeglich")),
                Tender.ki_relevanz_quelle != "llm",
                Tender.status.not_in(("abgelaufen", "vergeben")),
            )
            .order_by(Tender.erfasst_am.desc())
        )
    )


def _kategorien_angleichen(db: Session, tender: Tender, einstufung: str) -> None:
    namen = {tk.category.name for tk in tender.kategorien}
    if einstufung == "nicht" and _KI_KATEGORIE in namen:
        namen.discard(_KI_KATEGORIE)
        if not namen:
            namen.add("Softwareentwicklung & IT-Dienstleistungen" if find_cpv_hits(tender.cpv_codes or []) else "Nicht-IT")
    elif einstufung == "stark" and _KI_KATEGORIE not in namen:
        namen.add(_KI_KATEGORIE)
    else:
        return
    db.execute(TenderCategory.__table__.delete().where(TenderCategory.tender_id == tender.id))
    for name in namen:
        kategorie = db.scalars(select(Category).where(Category.name == name)).first()
        if kategorie is None:
            kategorie = Category(name=name)
            db.add(kategorie)
            db.flush()
        db.add(TenderCategory(tender_id=tender.id, category_id=kategorie.id))
    db.expire(tender, ["kategorien"])


def pruefe_ausschreibung(db: Session, tender: Tender) -> bool:
    """Eine Ausschreibung nachprüfen. False = kein Sprachmodell erreichbar (nichts geändert)."""
    ergebnis = prompts.call_llm_json(
        prompts.KI_RELEVANZ_SYSTEM,
        prompts.ki_relevanz_user(tender.titel, tender.kurzbeschreibung, tender.vergabestelle, tender.volltext),
        lokal_erlaubt=True,
    )
    einstufung = (ergebnis or {}).get("einstufung")
    if einstufung not in ("stark_relevant", "moeglich_relevant", "nicht_relevant"):
        return False
    vorher = tender.ki_relevanz_score
    tender.ki_relevanz_score = einstufung.replace("_relevant", "")
    try:
        tender.ki_relevanz_konfidenz = float(ergebnis.get("konfidenz", 0.6))
    except (TypeError, ValueError):
        tender.ki_relevanz_konfidenz = 0.6
    tender.ki_relevanz_begruendung = (
        f"[KI-Nachprüfung durch {prompts.llm_bezeichnung()}, keine gesicherte Tatsache; vorher "
        f"regelbasiert: {vorher}] {ergebnis.get('begruendung', '')}".strip()
    )
    tender.ki_relevanz_quelle = "llm"
    _kategorien_angleichen(db, tender, tender.ki_relevanz_score)
    db.commit()
    ranking.compute_and_store(db, tender)
    return True


def fuehre_nachpruefung_aus() -> dict:
    """Alle offenen Kandidaten nacheinander prüfen; bricht ab, sobald kein Modell antwortet."""
    if prompts.llm_anbieter() == "anthropic" and not settings.anthropic_api_key:
        return {"uebersprungen": "kein Sprachmodell eingerichtet"}
    if not _lock.acquire(blocking=False):
        return {"uebersprungen": "Nachprüfung läuft bereits"}
    db = SessionLocal()
    try:
        kandidaten = zu_pruefen(db)
        geprueft = herabgestuft = 0
        for tender in kandidaten:
            vorher = tender.ki_relevanz_score
            if not pruefe_ausschreibung(db, tender):
                logger.info("KI-Nachprüfung pausiert: kein Sprachmodell erreichbar (%d offen).", len(kandidaten) - geprueft)
                break
            geprueft += 1
            herabgestuft += _RANG[tender.ki_relevanz_score] < _RANG[vorher]
        if geprueft:
            logger.info("KI-Nachprüfung: %d geprüft, %d herabgestuft.", geprueft, herabgestuft)
        return {"kandidaten": len(kandidaten), "geprueft": geprueft, "herabgestuft": herabgestuft}
    except Exception:
        logger.exception("KI-Nachprüfung mit unerwartetem Fehler abgebrochen.")
        return {"fehler": True}
    finally:
        db.close()
        _lock.release()


def starte_im_hintergrund() -> None:
    threading.Thread(target=fuehre_nachpruefung_aus, name="ki-nachpruefung", daemon=True).start()
