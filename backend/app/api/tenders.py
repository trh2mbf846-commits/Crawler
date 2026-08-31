"""Endpunkte rund um Ausschreibungen (Kapitel 11, 23: /tenders, /tenders/{id}, /tenders/{id}/history)."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Portal, RankingScore, Tender, TenderCategory, TenderHistory
from app.schemas import HistoryEntryOut, TenderDetailOut, TenderListOut
from app.serializers import tender_to_detail_out, tender_to_out

router = APIRouter(tags=["tenders"])

_KI_RANG = {"nicht": 0, "moeglich": 1, "stark": 2}


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
    query = select(Tender)

    if portal:
        portal_ids = set(portal)
        slug_ids = [p.id for p in db.scalars(select(Portal).where(Portal.slug.in_(portal)))]
        portal_ids.update(slug_ids)
        query = query.where(Tender.portal_id.in_(portal_ids))

    if kategorie:
        query = query.join(TenderCategory, TenderCategory.tender_id == Tender.id).join(
            Category, Category.id == TenderCategory.category_id
        ).where(Category.name.in_(kategorie))

    if ki_relevanz_min:
        min_rang = _KI_RANG.get(ki_relevanz_min, 0)
        erlaubt = [k for k, v in _KI_RANG.items() if v >= min_rang]
        query = query.where(Tender.ki_relevanz_score.in_(erlaubt))

    if frist_bis:
        query = query.where(Tender.angebotsfrist <= datetime.combine(frist_bis, datetime.max.time()))

    if status:
        query = query.where(Tender.status == status)

    if q:
        like = f"%{q.lower()}%"
        from sqlalchemy import func, or_

        query = query.where(
            or_(
                func.lower(Tender.titel).like(like),
                func.lower(Tender.kurzbeschreibung).like(like),
                func.lower(Tender.vergabestelle).like(like),
            )
        )

    query = query.distinct()

    total = len(db.scalars(query).unique().all())

    if sort == "frist":
        query = query.order_by(Tender.angebotsfrist.is_(None), Tender.angebotsfrist.asc())
    elif sort == "veroeffentlichung":
        query = query.order_by(Tender.veroeffentlichungsdatum.desc())
    else:
        query = query.outerjoin(RankingScore, RankingScore.tender_id == Tender.id).order_by(
            RankingScore.gesamtscore.desc().nulls_last()
        )

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).unique().all())

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
