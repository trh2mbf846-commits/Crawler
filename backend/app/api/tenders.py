"""Endpunkte rund um Ausschreibungen (Kapitel 11, 23: /tenders, /tenders/{id}, /tenders/{id}/history)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tender, TenderHistory
from app.schemas import HistoryEntryOut, TenderDetailOut, TenderListOut
from app.serializers import tender_to_detail_out, tender_to_out
from app.tender_queries import search_tenders

router = APIRouter(tags=["tenders"])


@router.get("/tenders", response_model=TenderListOut)
def list_tenders(
    q: str | None = Query(None),
    portal: list[str] | None = Query(None),
    kategorie: list[str] | None = Query(None),
    ki_relevanz_min: str | None = Query(None),
    frist_bis: date | None = Query(None),
    status: str | None = Query(None),
    sort: str = Query("ranking", pattern="^(ranking|frist|veroeffentlichung)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> TenderListOut:
    items, total = search_tenders(
        db, q=q, portal=portal, kategorie=kategorie, ki_relevanz_min=ki_relevanz_min,
        frist_bis=frist_bis, status=status, sort=sort, page=page, page_size=page_size,
    )
    return TenderListOut(items=[tender_to_out(t) for t in items], total=total, page=page, page_size=page_size)


@router.get("/tenders/{tender_id}", response_model=TenderDetailOut)
def get_tender(tender_id: str, db: Session = Depends(get_db)) -> TenderDetailOut:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    return tender_to_detail_out(tender)


@router.get("/tenders/{tender_id}/history", response_model=list[HistoryEntryOut])
def get_tender_history(tender_id: str, db: Session = Depends(get_db)) -> list[HistoryEntryOut]:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(404, "Ausschreibung nicht gefunden.")
    rows = db.scalars(
        select(TenderHistory).where(TenderHistory.tender_id == tender_id).order_by(TenderHistory.erkannt_am)
    )
    return [HistoryEntryOut(feld=r.feld, alter_wert=r.alter_wert, neuer_wert=r.neuer_wert, erkannt_am=r.erkannt_am) for r in rows]
