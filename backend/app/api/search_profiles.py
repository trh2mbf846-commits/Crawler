from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.search import recompute_profile_hits
from app.db import get_db
from app.models import SearchProfile, SearchProfileHit
from app.schemas import SearchProfileIn, SearchProfileOut, TenderListOut
from app.serializers import tender_to_out

router = APIRouter(tags=["search-profiles"])


def _to_out(db: Session, profile: SearchProfile) -> SearchProfileOut:
    neue = db.scalars(
        select(SearchProfileHit).where(SearchProfileHit.profile_id == profile.id, SearchProfileHit.gesehen.is_(False))
    ).all()
    return SearchProfileOut(
        id=profile.id, name=profile.name, portale=profile.portale, keywords=profile.keywords,
        filter_json=profile.filter_json, aktiv=profile.aktiv, erstellt_am=profile.erstellt_am,
        neue_treffer_anzahl=len(neue),
    )


@router.get("/search-profiles", response_model=list[SearchProfileOut])
def list_profiles(db: Session = Depends(get_db)) -> list[SearchProfileOut]:
    profiles = db.scalars(select(SearchProfile).order_by(SearchProfile.erstellt_am.desc()))
    return [_to_out(db, p) for p in profiles]


@router.post("/search-profiles", response_model=SearchProfileOut, status_code=201)
def create_profile(body: SearchProfileIn, db: Session = Depends(get_db)) -> SearchProfileOut:
    profile = SearchProfile(**body.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    recompute_profile_hits(db, profile)
    return _to_out(db, profile)


@router.put("/search-profiles/{profile_id}", response_model=SearchProfileOut)
def update_profile(profile_id: str, body: SearchProfileIn, db: Session = Depends(get_db)) -> SearchProfileOut:
    profile = db.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "Suchprofil nicht gefunden.")
    for k, v in body.model_dump().items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    recompute_profile_hits(db, profile)
    return _to_out(db, profile)


@router.delete("/search-profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str, db: Session = Depends(get_db)) -> None:
    profile = db.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "Suchprofil nicht gefunden.")
    db.delete(profile)
    db.commit()


@router.get("/search-profiles/{profile_id}/hits", response_model=TenderListOut)
def profile_hits(
    profile_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
) -> TenderListOut:
    profile = db.get(SearchProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "Suchprofil nicht gefunden.")

    hits = list(
        db.scalars(
            select(SearchProfileHit)
            .where(SearchProfileHit.profile_id == profile_id)
            .order_by(SearchProfileHit.markiert_am.desc().nulls_last())
        )
    )
    total = len(hits)
    page_hits = hits[(page - 1) * page_size : (page - 1) * page_size + page_size]
    for h in page_hits:
        h.gesehen = True
    db.commit()

    return TenderListOut(
        items=[tender_to_out(h.tender) for h in page_hits], total=total, page=page, page_size=page_size
    )
