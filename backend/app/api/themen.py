"""Themen pflegen (app/themen.py) - ersetzt Code-Änderungen für neue Kategorien/Suchbegriffe."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.classification import CATEGORY_ORDER
from app.db import get_db
from app.models import Thema
from app.schemas import ThemaIn, ThemaOut
from app.themen import ordne_im_hintergrund_neu_ein

router = APIRouter(tags=["themen"])


def _bereinigt(payload: ThemaIn) -> dict:
    name = " ".join(payload.name.split())
    if not name:
        raise HTTPException(422, "Name fehlt.")
    if name in CATEGORY_ORDER:
        raise HTTPException(422, f"„{name}“ ist bereits eine feste Grundkategorie.")
    stichworte = list(dict.fromkeys(" ".join(s.lower().split()) for s in payload.stichworte if s.strip()))
    if not stichworte:
        raise HTTPException(422, "Mindestens ein Stichwort angeben - daran erkennt der Crawler das Thema.")
    return {"name": name, "stichworte": stichworte, "ki_bezogen": payload.ki_bezogen, "aktiv": payload.aktiv}


def _out(thema: Thema) -> ThemaOut:
    return ThemaOut(id=thema.id, name=thema.name, stichworte=thema.stichworte, ki_bezogen=thema.ki_bezogen, aktiv=thema.aktiv)


@router.get("/themen", response_model=list[ThemaOut])
def liste(db: Session = Depends(get_db)) -> list[ThemaOut]:
    return [_out(t) for t in db.scalars(select(Thema).where(Thema.geloescht.is_(False)).order_by(Thema.name))]


def speichere_thema(db: Session, payload: ThemaIn, thema_id: str | None = None) -> Thema:
    daten = _bereinigt(payload)
    gleichnamig = db.scalars(select(Thema).where(Thema.name == daten["name"])).first()
    if thema_id is None and gleichnamig is not None and not gleichnamig.geloescht:
        raise HTTPException(409, f"Thema „{daten['name']}“ gibt es schon.")
    thema = db.get(Thema, thema_id) if thema_id else gleichnamig  # gelöschtes gleichnamiges wiederbeleben
    if thema_id and thema is None:
        raise HTTPException(404, "Thema nicht gefunden.")
    if thema is None:
        thema = Thema(**daten)
        db.add(thema)
    else:
        for feld, wert in daten.items():
            setattr(thema, feld, wert)
        thema.geloescht = False
    db.commit()
    ordne_im_hintergrund_neu_ein()
    return thema


@router.post("/themen", response_model=ThemaOut, status_code=201)
def anlegen(payload: ThemaIn, db: Session = Depends(get_db)) -> ThemaOut:
    return _out(speichere_thema(db, payload))


@router.put("/themen/{thema_id}", response_model=ThemaOut)
def aendern(thema_id: str, payload: ThemaIn, db: Session = Depends(get_db)) -> ThemaOut:
    return _out(speichere_thema(db, payload, thema_id))


@router.delete("/themen/{thema_id}", status_code=204)
def loeschen(thema_id: str, db: Session = Depends(get_db)) -> None:
    thema = db.get(Thema, thema_id)
    if thema is None or thema.geloescht:
        raise HTTPException(404, "Thema nicht gefunden.")
    thema.geloescht = True
    thema.aktiv = False
    db.commit()
    ordne_im_hintergrund_neu_ein()
