"""Gemeinsame Such-/Filterlogik für Ausschreibungen (Kapitel 11.2-11.4).

Ursprünglich Teil von api/tenders.py; hier herausgelöst, damit sowohl die REST-Route als auch
der KI-Assistent (app/agents/assistant.py, Nutzeranfrage 25.09.2026 "Richtung KI-Agent") dieselbe,
einmal geprüfte Filterlogik verwenden statt sie zu duplizieren.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Category, Portal, RankingScore, Tender, TenderCategory

_KI_RANG = {"nicht": 0, "moeglich": 1, "stark": 2}


def search_tenders(
    db: Session,
    q: str | None = None,
    portal: list[str] | None = None,
    kategorie: list[str] | None = None,
    ki_relevanz_min: str | None = None,
    frist_bis: date | None = None,
    status: str | None = None,
    sort: str = "ranking",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Tender], int]:
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

    return items, total
