"""Bewerbungsalltag: Abgabe-Checkliste, Fristen-Kalender (.ics), Referenzen (siehe app/bewerbung.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bewerbung import checkliste_aus_bewertung, fristen, fristen_ics
from app.db import get_db
from app.models import Referenz, Tender
from app.schemas import ChecklistenPunkt, FristOut, ReferenzIn, ReferenzOut

router = APIRouter(tags=["bewerbung"])

_STATUS = {"offen", "vorhanden", "fehlt", "erledigt"}


def _tender(db: Session, tender_id: str) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    return tender


@router.put("/tenders/{tender_id}/checkliste", response_model=list[ChecklistenPunkt])
def checkliste_speichern(
    tender_id: str, punkte: list[ChecklistenPunkt], db: Session = Depends(get_db)
) -> list[ChecklistenPunkt]:
    tender = _tender(db, tender_id)
    if any(p.status not in _STATUS for p in punkte):
        raise HTTPException(422, f"Status muss einer von {sorted(_STATUS)} sein.")
    tender.checkliste_json = [p.model_dump() for p in punkte if p.text.strip()] or None
    db.commit()
    return [ChecklistenPunkt(**p) for p in tender.checkliste_json or []]


@router.post("/tenders/{tender_id}/checkliste/aus-bewertung", response_model=list[ChecklistenPunkt])
def checkliste_aus_bewertung_erzeugen(tender_id: str, db: Session = Depends(get_db)) -> list[ChecklistenPunkt]:
    tender = _tender(db, tender_id)
    if not tender.bewertung_json:
        raise HTTPException(409, "Erst „Bewerben oder nicht?“ ausführen - die Checkliste entsteht aus der Bewertung.")
    punkte = checkliste_aus_bewertung(tender)
    db.commit()
    return [ChecklistenPunkt(**p) for p in punkte]


@router.get("/fristen", response_model=list[FristOut])
def fristen_liste(tage: int = Query(90, ge=1, le=365), db: Session = Depends(get_db)) -> list[FristOut]:
    return [FristOut(**e) for e in fristen(db, tage)]


@router.get("/fristen.ics")
def fristen_kalender(tage: int = Query(180, ge=1, le=365), db: Session = Depends(get_db)) -> Response:
    return Response(
        fristen_ics(fristen(db, tage)),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ausschreibungs-fristen.ics"'},
    )


@router.get("/referenzen", response_model=list[ReferenzOut])
def referenzen(db: Session = Depends(get_db)) -> list[ReferenzOut]:
    return [ReferenzOut.model_validate(r, from_attributes=True)
            for r in db.scalars(select(Referenz).order_by(Referenz.jahr.desc().nulls_last(), Referenz.titel))]


@router.post("/referenzen", response_model=ReferenzOut, status_code=201)
def referenz_anlegen(payload: ReferenzIn, db: Session = Depends(get_db)) -> ReferenzOut:
    if not payload.titel.strip():
        raise HTTPException(422, "Titel fehlt.")
    referenz = Referenz(**payload.model_dump())
    db.add(referenz)
    db.commit()
    return ReferenzOut.model_validate(referenz, from_attributes=True)


@router.put("/referenzen/{referenz_id}", response_model=ReferenzOut)
def referenz_aendern(referenz_id: str, payload: ReferenzIn, db: Session = Depends(get_db)) -> ReferenzOut:
    referenz = db.get(Referenz, referenz_id)
    if referenz is None:
        raise HTTPException(404, "Referenz nicht gefunden.")
    for feld, wert in payload.model_dump().items():
        setattr(referenz, feld, wert)
    db.commit()
    return ReferenzOut.model_validate(referenz, from_attributes=True)


@router.delete("/referenzen/{referenz_id}", status_code=204)
def referenz_loeschen(referenz_id: str, db: Session = Depends(get_db)) -> None:
    referenz = db.get(Referenz, referenz_id)
    if referenz is None:
        raise HTTPException(404, "Referenz nicht gefunden.")
    db.delete(referenz)
    db.commit()
