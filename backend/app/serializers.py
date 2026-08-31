from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents import ranking, source_health
from app.models import Portal, Tender
from app.schemas import (
    DokumentOut,
    PortalHealthOut,
    PortalRef,
    RankingBreakdown,
    TenderDetailOut,
    TenderOut,
)


def tender_to_out(tender: Tender) -> TenderOut:
    r = tender.ranking
    return TenderOut(
        id=tender.id,
        titel=tender.titel,
        kurzbeschreibung=tender.kurzbeschreibung,
        vergabestelle=tender.vergabestelle,
        ort_region=tender.ort_region,
        portal=PortalRef(id=tender.portal_id, name=tender.portal.name),
        veroeffentlichungsdatum=tender.veroeffentlichungsdatum,
        angebotsfrist=tender.angebotsfrist,
        fragenfrist=tender.fragenfrist,
        verfahrensart=tender.verfahrensart,
        cpv_codes=tender.cpv_codes or [],
        geschaetzter_wert=tender.geschaetzter_wert,
        direktlink=tender.direktlink,
        status=tender.status,
        zugangsart=tender.zugangsart,
        ki_relevanz_score=tender.ki_relevanz_score,
        ki_relevanz_begruendung=tender.ki_relevanz_begruendung,
        kategorien=[tc.category.name for tc in tender.kategorien],
        gesamtscore=r.gesamtscore if r else 0.0,
        erfasst_am=tender.erfasst_am,
        zuletzt_geprueft_am=tender.zuletzt_geprueft_am,
    )


def tender_to_detail_out(tender: Tender) -> TenderDetailOut:
    base = tender_to_out(tender)
    r = tender.ranking
    breakdown = (
        RankingBreakdown(
            ki_relevanz=r.ki_relevanz_score, dringlichkeit=r.dringlichkeit_score,
            profil_uebereinstimmung=r.profil_score, aktualitaet=r.aktualitaet_score,
        )
        if r
        else RankingBreakdown(ki_relevanz=0, dringlichkeit=0, profil_uebereinstimmung=0, aktualitaet=0)
    )
    return TenderDetailOut(
        **base.model_dump(),
        volltext=tender.volltext,
        dokumente=[DokumentOut(titel=d.titel, url=d.url) for d in tender.dokumente],
        ranking_aufschluesselung=breakdown,
    )


def portal_to_health_out(db: Session, portal: Portal) -> PortalHealthOut:
    status = source_health.evaluate(db, portal)
    return PortalHealthOut(
        id=portal.id,
        name=portal.name,
        betreiber=portal.betreiber,
        base_url=portal.base_url,
        aktiv=portal.aktiv,
        robots_status=portal.robots_status,
        tos_hinweis=portal.tos_hinweis,
        **status,
    )
