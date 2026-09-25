"""Search-Agent (Kapitel 8, 18): kombiniert Bestand und gespeicherte Suchprofile zu

personalisierten, gerankten Treffermengen. Läuft nicht als eigener Job je Ausschreibung,
sondern wird direkt im Anschluss an die Klassifikation aufgerufen (Kapitel 19.3, letzter
Schritt: "Datensatz wird ... für Search-Agent und Ranking Engine verfügbar").
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SearchProfile, SearchProfileHit, Tender


def profile_matches(profile: SearchProfile, tender: Tender) -> bool:
    if profile.portale and tender.portal_id not in profile.portale:
        return False

    if profile.keywords:
        text = f"{tender.titel} {tender.kurzbeschreibung or ''} {tender.vergabestelle or ''}".lower()
        if not any(kw.lower() in text for kw in profile.keywords):
            return False

    filt = profile.filter_json or {}
    if filt.get("ki_relevanz_min"):
        rang = {"nicht": 0, "moeglich": 1, "stark": 2}
        if rang.get(tender.ki_relevanz_score or "nicht", 0) < rang.get(filt["ki_relevanz_min"], 0):
            return False
    if filt.get("kategorien"):
        tender_kategorien = {tc.category.name for tc in tender.kategorien}
        if not tender_kategorien.intersection(filt["kategorien"]):
            return False
    if filt.get("region") and (tender.ort_region or "").lower() != str(filt["region"]).lower():
        return False
    if filt.get("mindestwert") and (tender.geschaetzter_wert or 0) < float(filt["mindestwert"]):
        return False

    return True


def match_tender_to_profiles(db: Session, tender: Tender) -> int:
    treffer = 0
    for profile in db.scalars(select(SearchProfile).where(SearchProfile.aktiv.is_(True))):
        if not profile_matches(profile, tender):
            continue
        hit = db.get(SearchProfileHit, (profile.id, tender.id))
        if hit is None:
            db.add(SearchProfileHit(profile_id=profile.id, tender_id=tender.id, gesehen=False))
            treffer += 1
    db.commit()
    return treffer


def recompute_profile_hits(db: Session, profile: SearchProfile) -> int:
    """Vollständiger Neuabgleich, z. B. nach dem Anlegen/Ändern eines Suchprofils (Kapitel 11.5)."""
    treffer = 0
    for tender in db.scalars(select(Tender).where(Tender.status != "abgelaufen")):
        if profile_matches(profile, tender):
            hit = db.get(SearchProfileHit, (profile.id, tender.id))
            if hit is None:
                db.add(SearchProfileHit(profile_id=profile.id, tender_id=tender.id, gesehen=False))
                treffer += 1
    db.commit()
    return treffer
