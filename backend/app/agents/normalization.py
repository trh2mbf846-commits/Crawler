"""Normalization-Agent (Kapitel 18): bildet portalspezifische Rohfelder auf das einheitliche

Datenmodell aus Kapitel 6 ab. Nicht abbildbare Felder werden protokolliert statt verworfen.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import queue
from app.models import Job
from app.normalize_utils import make_kurzbeschreibung, parse_currency_de, parse_date_de


def run_normalization(db: Session, job: Job) -> dict:
    raw = job.payload["raw_felder"]

    normalized = {
        "externe_id": job.payload.get("externe_id"),
        "direktlink": job.payload.get("detail_url"),
        "titel": raw.get("titel") or job.payload.get("titel_hint") or "(ohne Titel)",
        "volltext": raw.get("volltext"),
        "kurzbeschreibung": raw.get("kurzbeschreibung") or make_kurzbeschreibung(raw.get("volltext")),
        "vergabestelle": raw.get("vergabestelle"),
        "ort_region": raw.get("ort_region"),
        "veroeffentlichungsdatum": parse_date_de(raw.get("veroeffentlichungsdatum")),
        "angebotsfrist": parse_date_de(raw.get("angebotsfrist")),
        "fragenfrist": parse_date_de(raw.get("fragenfrist")),
        "verfahrensart": raw.get("verfahrensart"),
        "cpv_codes": raw.get("cpv_codes") or [],
        "geschaetzter_wert": parse_currency_de(raw.get("geschaetzter_wert")) if isinstance(raw.get("geschaetzter_wert"), str) else raw.get("geschaetzter_wert"),
        "dokumente_links": raw.get("dokumente_links") or [],
        "zugangsart": "registrierung_erforderlich" if raw.get("_registrierung_fuer_details") else "oeffentlich",
    }

    nicht_abbildbar = [k for k, v in raw.items() if k.startswith("_") and k != "_fehlende_pflichtfelder"]

    queue.enqueue(
        db,
        "duplicate",
        portal_id=job.portal_id,
        ziel_id=job.ziel_id,
        correlation_id=job.correlation_id,
        payload={"normalized": _jsonable(normalized)},
    )
    return {"nicht_abbildbare_rohfelder": nicht_abbildbar}


def _jsonable(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out
