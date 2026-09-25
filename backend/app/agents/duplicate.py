"""Duplicate-Agent (Kapitel 18): entscheidet neu / aktualisiert / Duplikat und schreibt

Änderungen nachvollziehbar in tender_history (Kapitel 5.3, 24).
"""
from __future__ import annotations

import difflib
import hashlib
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import queue
from app.models import Job, Tender, TenderDocument, TenderHistory

# Felder, deren Änderung als History-Eintrag erfasst wird (Kapitel 6: aenderungshistorie).
TRACKED_FIELDS = (
    "titel", "kurzbeschreibung", "angebotsfrist", "fragenfrist", "verfahrensart",
    "geschaetzter_wert", "status", "vergabestelle",
)

# Portalübergreifende Duplikaterkennung (Nutzeranfrage 25.09.2026): reine Heuristik, da der
# dedupe_hash oben bewusst je Portal isoliert ist (Kapitel 5.3) und die bekannte Überschneidung
# Bekanntmachungsservice/TED/DTVP (docs/portal-notes.md) sonst unsichtbar bliebe. Grenzt die
# Kandidaten zunächst günstig ein (Veröffentlichungsdatum-Fenster ODER übereinstimmendes erstes
# Vergabestelle-Stichwort), bewertet dann Titel-Ähnlichkeit (teuer, daher erst auf der kleinen
# Kandidatenmenge). Live verifiziert 25.09.2026: DTVP zeigt auf Listen- UND Detailseite KEIN
# Veröffentlichungsdatum (nur Abgabefrist) - ohne den Vergabestelle-Stichwort-Pfad würde DTVP nie
# als Kandidat gefunden UND nie selbst einen Kandidaten finden, obwohl es genau der Fall war, der
# diese Funktion motiviert hat.
_DUPLIKAT_DATUM_FENSTER_TAGE = 5
_DUPLIKAT_KANDIDATEN_LIMIT = 300
_VERGABESTELLE_STICHWORT_ANZAHL = 2
_VERGABESTELLE_KANDIDATEN_LIMIT = 100
_TITEL_SCHWELLE_MIT_VERGABESTELLE = 0.75
_TITEL_SCHWELLE_OHNE_VERGABESTELLE = 0.90
_WORT_MUSTER = re.compile(r"[a-z0-9äöüß]+")


def _normalisiere_titel(titel: str) -> str:
    return " ".join(_WORT_MUSTER.findall(titel.lower()))


def _vergabestellen_ueberschneiden_sich(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    a, b = a.lower().strip(), b.lower().strip()
    return a in b or b in a


def _vergabestelle_stichwort(vergabestelle: str, anzahl: int = _VERGABESTELLE_STICHWORT_ANZAHL) -> str:
    return " ".join(_WORT_MUSTER.findall(vergabestelle.lower())[:anzahl])


def _sammle_kandidaten(db: Session, tender: Tender) -> list[Tender]:
    kandidaten: dict[str, Tender] = {}

    if tender.veroeffentlichungsdatum is not None:
        fenster_start = tender.veroeffentlichungsdatum - timedelta(days=_DUPLIKAT_DATUM_FENSTER_TAGE)
        fenster_ende = tender.veroeffentlichungsdatum + timedelta(days=_DUPLIKAT_DATUM_FENSTER_TAGE)
        for kandidat in db.scalars(
            select(Tender)
            .where(
                Tender.portal_id != tender.portal_id,
                Tender.id != tender.id,
                Tender.veroeffentlichungsdatum.between(fenster_start, fenster_ende),
            )
            .limit(_DUPLIKAT_KANDIDATEN_LIMIT)
        ):
            kandidaten[kandidat.id] = kandidat

    if tender.vergabestelle:
        stichwort = _vergabestelle_stichwort(tender.vergabestelle)
        if stichwort:
            for kandidat in db.scalars(
                select(Tender)
                .where(
                    Tender.portal_id != tender.portal_id,
                    Tender.id != tender.id,
                    Tender.vergabestelle.isnot(None),
                    func.lower(Tender.vergabestelle).like(f"%{stichwort}%"),
                )
                .limit(_VERGABESTELLE_KANDIDATEN_LIMIT)
            ):
                kandidaten[kandidat.id] = kandidat

    return list(kandidaten.values())


def _erkenne_cross_portal_duplikat(db: Session, tender: Tender) -> None:
    kandidaten = _sammle_kandidaten(db, tender)
    if not kandidaten:
        tender.moeglicherweise_duplikat_von = None
        tender.moeglicherweise_duplikat_hinweis = None
        return

    eigener_titel = _normalisiere_titel(tender.titel)
    bester_treffer: Tender | None = None
    beste_aehnlichkeit = 0.0
    for kandidat in kandidaten:
        aehnlichkeit = difflib.SequenceMatcher(None, eigener_titel, _normalisiere_titel(kandidat.titel)).ratio()
        schwelle = (
            _TITEL_SCHWELLE_MIT_VERGABESTELLE
            if _vergabestellen_ueberschneiden_sich(tender.vergabestelle, kandidat.vergabestelle)
            else _TITEL_SCHWELLE_OHNE_VERGABESTELLE
        )
        if aehnlichkeit >= schwelle and aehnlichkeit > beste_aehnlichkeit:
            bester_treffer, beste_aehnlichkeit = kandidat, aehnlichkeit

    if bester_treffer is None:
        tender.moeglicherweise_duplikat_von = None
        tender.moeglicherweise_duplikat_hinweis = None
        return

    tender.moeglicherweise_duplikat_von = bester_treffer.id
    tender.moeglicherweise_duplikat_hinweis = (
        f"Vermutlich auch bei {bester_treffer.portal.name} "
        f"(Titel-Ähnlichkeit {beste_aehnlichkeit * 100:.0f}%) - automatisch erkannt, nicht "
        "zusammengeführt, da nicht sicher genug für ein automatisches Merge."
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

    if ergebnis in ("neu", "aktualisiert"):
        _erkenne_cross_portal_duplikat(db, tender)
        db.commit()
        db.refresh(tender)

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
