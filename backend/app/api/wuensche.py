"""Kevins Wunschliste (Verbesserungswünsche an den Crawler), siehe models.Verbesserungswunsch."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Verbesserungswunsch
from app.schemas import WunschOut, WunschStatusIn

router = APIRouter(tags=["wuensche"])


@router.get("/wuensche", response_model=list[WunschOut])
def liste(db: Session = Depends(get_db)) -> list[WunschOut]:
    wuensche = db.scalars(select(Verbesserungswunsch).order_by(Verbesserungswunsch.erstellt_am.desc()))
    return [WunschOut.model_validate(w, from_attributes=True) for w in wuensche]


@router.patch("/wuensche/{wunsch_id}", response_model=WunschOut)
def status_setzen(wunsch_id: str, payload: WunschStatusIn, db: Session = Depends(get_db)) -> WunschOut:
    if payload.status not in ("offen", "erledigt"):
        raise HTTPException(422, "Status muss 'offen' oder 'erledigt' sein.")
    wunsch = db.get(Verbesserungswunsch, wunsch_id)
    if wunsch is None:
        raise HTTPException(404, "Wunsch nicht gefunden.")
    wunsch.status = payload.status
    db.commit()
    return WunschOut.model_validate(wunsch, from_attributes=True)


@router.delete("/wuensche/{wunsch_id}", status_code=204)
def loeschen(wunsch_id: str, db: Session = Depends(get_db)) -> None:
    wunsch = db.get(Verbesserungswunsch, wunsch_id)
    if wunsch is None:
        raise HTTPException(404, "Wunsch nicht gefunden.")
    db.delete(wunsch)
    db.commit()
