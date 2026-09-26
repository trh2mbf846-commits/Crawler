"""Gemeinsame Such-/Filterlogik für Ausschreibungen (Kapitel 11.2-11.4).

Ursprünglich Teil von api/tenders.py; hier herausgelöst, damit sowohl die REST-Route als auch
der KI-Assistent (app/agents/assistant.py, Nutzeranfrage 25.09.2026 "Richtung KI-Agent") dieselbe,
einmal geprüfte Filterlogik verwenden statt sie zu duplizieren.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import case, func, or_, select
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
    bedeutung: bool = False,
) -> tuple[list[Tender], int]:
    """bedeutung=True (mit q): zusätzlich zur Stichwortsuche auch Ausschreibungen mit ähnlicher
    Bedeutung finden (app/semantik.py), sortiert nach Ähnlichkeit. Ist die Bedeutungssuche nicht
    verfügbar (kein Ollama/Modell), bleibt es bei der normalen Stichwortsuche."""
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

    # Standard (kein Status oder "offen", Nutzerwunsch 25.09.2026): nur Ausschreibungen, auf die
    # man sich noch bewerben kann - nicht vergeben/abgelaufen und Frist nicht verstrichen
    # (Ausschreibungen ohne bekannte Frist bleiben drin). "alle" zeigt wirklich alles.
    if not status or status == "offen":
        query = query.where(
            Tender.status.not_in(("abgelaufen", "vergeben")),
            or_(Tender.angebotsfrist.is_(None), Tender.angebotsfrist >= datetime.now()),
        )
    elif status != "alle":
        query = query.where(Tender.status == status)

    aehnlich: dict[str, float] | None = None
    if q and bedeutung:
        from app.semantik import aehnlichkeiten

        aehnlich = aehnlichkeiten(db, q)

    if q:
        like = f"%{q.lower()}%"
        stichwort = or_(
            func.lower(Tender.titel).like(like),
            func.lower(Tender.kurzbeschreibung).like(like),
            func.lower(Tender.vergabestelle).like(like),
        )
        query = query.where(or_(stichwort, Tender.id.in_(list(aehnlich))) if aehnlich else stichwort)

    query = query.distinct()

    if aehnlich is not None:
        # Stichwort-Treffer zuerst (sie enthalten den Suchbegriff wirklich), danach die ähnlichen
        # Ergänzungen, jeweils nach Bedeutungs-Ähnlichkeit.
        alle = list(db.scalars(query).unique().all())
        begriff = q.lower()

        def enthaelt(t: Tender) -> bool:
            return any(begriff in (feld or "").lower() for feld in (t.titel, t.kurzbeschreibung, t.vergabestelle))

        alle.sort(key=lambda t: (enthaelt(t), aehnlich.get(t.id, 0.0)), reverse=True)
        start = (page - 1) * page_size
        return alle[start:start + page_size], len(alle)

    total = len(db.scalars(query).unique().all())

    if sort == "frist":
        query = query.order_by(Tender.angebotsfrist.is_(None), Tender.angebotsfrist.asc())
    elif sort == "veroeffentlichung":
        query = query.order_by(Tender.veroeffentlichungsdatum.desc())
    elif sort == "ki_relevanz":
        # Die Oberfläche bot diese Sortierung an, das Backend kannte sie nicht (HTTP 422) - behoben 25.09.2026.
        rang = case({"stark": 2, "moeglich": 1}, value=Tender.ki_relevanz_score, else_=0)
        query = query.outerjoin(RankingScore, RankingScore.tender_id == Tender.id).order_by(
            rang.desc(), RankingScore.gesamtscore.desc().nulls_last()
        )
    else:
        query = query.outerjoin(RankingScore, RankingScore.tender_id == Tender.id).order_by(
            RankingScore.gesamtscore.desc().nulls_last()
        )

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(query).unique().all())

    return items, total
