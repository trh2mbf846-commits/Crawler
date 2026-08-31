"""Duplicate-Agent (Kapitel 18): entscheidet neu / aktualisiert / Duplikat und schreibt

Änderungen nachvollziehbar in tender_history (Kapitel 5.3, 24).
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import queue
from app.models import Job, Tender, TenderDocument, TenderHistory

# Felder, deren Änderung als History-Eintrag erfasst wird (Kapitel 6: aenderungshistorie).
TRACKED_FIELDS = (
    "titel", "kurzbeschreibung", "angebotsfrist", "fragenfrist", "verfahrensart",
    "geschaetzter_wert", "status", "vergabestelle",
)


def _parse_dt(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _dedupe_hash(portal_id: str, externe_id: str | None, titel: str, vergabestelle: str | None, veroeffentlichungsdatum) -> str:
    # Kapitel 5.3: "Hash aus Portal, externer ID bzw. Titel, Vergabestelle und Veröffentlichungsdatum".
    basis = f"{portal_id}|{externe_id}" if externe_id else f"{portal_id}|{titel}|{vergabestelle}|{veroeffentlichungsdatum}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def run_duplicate(db: Session, job: Job) -> dict:
    n = job.payload["normalized"]
    dedupe_hash = _dedupe_hash(
        job.portal_id, n.get("externe_id"), n["titel"], n.get("vergabestelle"), n.get("veroeffentlichungsdatum")
    )

    existing = db.scalars(
        select(Tender).where(Tender.portal_id == job.portal_id, Tender.dedupe_hash == dedupe_hash)
    ).first()

    now = datetime.utcnow()
    veraendert = False

    if existing is None:
        tender = Tender(
            portal_id=job.portal_id,
            externe_id=n.get("externe_id"),
            titel=n["titel"],
            kurzbeschreibung=n.get("kurzbeschreibung"),
            volltext=n.get("volltext"),
            vergabestelle=n.get("vergabestelle"),
            ort_region=n.get("ort_region"),
            veroeffentlichungsdatum=_parse_dt(n.get("veroeffentlichungsdatum")),
            angebotsfrist=_parse_dt(n.get("angebotsfrist")),
            fragenfrist=_parse_dt(n.get("fragenfrist")),
            verfahrensart=n.get("verfahrensart"),
            cpv_codes=n.get("cpv_codes") or [],
            geschaetzter_wert=n.get("geschaetzter_wert"),
            direktlink=n["direktlink"],
            status="neu",
            zugangsart=n.get("zugangsart", "oeffentlich"),
            dedupe_hash=dedupe_hash,
            erfasst_am=now,
            zuletzt_geprueft_am=now,
        )
        db.add(tender)
        db.flush()
        for doc_url in n.get("dokumente_links") or []:
            db.add(TenderDocument(tender_id=tender.id, url=doc_url, titel=None))
        db.commit()
        db.refresh(tender)
        ergebnis = "neu"
    else:
        existing.zuletzt_geprueft_am = now
        neue_werte = {
            "titel": n["titel"],
            "kurzbeschreibung": n.get("kurzbeschreibung"),
            "volltext": n.get("volltext") or existing.volltext,
            "vergabestelle": n.get("vergabestelle"),
            "angebotsfrist": _parse_dt(n.get("angebotsfrist")),
            "fragenfrist": _parse_dt(n.get("fragenfrist")),
            "verfahrensart": n.get("verfahrensart"),
            "geschaetzter_wert": n.get("geschaetzter_wert"),
        }
        for feld, neuer_wert in neue_werte.items():
            alter_wert = getattr(existing, feld)
            if _differs(alter_wert, neuer_wert):
                db.add(
                    TenderHistory(
                        tender_id=existing.id,
                        feld=feld,
                        alter_wert=str(alter_wert) if alter_wert is not None else None,
                        neuer_wert=str(neuer_wert) if neuer_wert is not None else None,
                        erkannt_am=now,
                    )
                )
                setattr(existing, feld, neuer_wert)
                veraendert = True

        if veraendert and existing.status not in ("vergeben", "abgelaufen"):
            existing.status = "aktualisiert"

        db.commit()
        db.refresh(existing)
        tender = existing
        ergebnis = "aktualisiert" if veraendert else "unveraendert"

    if ergebnis in ("neu", "aktualisiert") or tender.ki_relevanz_score is None:
        queue.enqueue(
            db,
            "classification",
            portal_id=job.portal_id,
            correlation_id=job.correlation_id,
            payload={"tender_id": tender.id},
        )

    return {"ergebnis": ergebnis, "tender_id": tender.id}


def _differs(a, b) -> bool:
    if a is None and b is None:
        return False
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) > 1e-6
    return a != b
