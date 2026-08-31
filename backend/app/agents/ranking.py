"""Ranking Engine (Kapitel 20): kombiniert vier Teil-Scores zu einem transparenten Gesamtscore.

Die Gesamtübersicht (ohne aktives Suchprofil) hat keinen Profil-Kontext; gemäß Kapitel 20.3
("ohne aktives Profil entfällt dieser Anteil und die übrigen Gewichte werden proportional
hochskaliert") wird der Profil-Anteil dort auf 0 gesetzt und die übrigen drei Gewichte
proportional hochskaliert. Innerhalb eines Suchprofil-Feeds (search.py) fließt die tatsächliche
Profil-Übereinstimmung ein.
"""
from __future__ import annotations

from datetime import datetime

from app.config import settings
from app.models import RankingScore, Tender

DRINGLICHKEIT_FENSTER_TAGE = 60
AKTUALITAET_FENSTER_TAGE = 30

_KI_BASISWERTE = {"stark": 1.0, "moeglich": 0.5, "nicht": 0.0}


def ki_relevanz_score(tender: Tender) -> float:
    basis = _KI_BASISWERTE.get(tender.ki_relevanz_score or "", 0.0)
    if tender.ki_relevanz_quelle == "llm" and tender.ki_relevanz_konfidenz is not None:
        # Kontinuierliche Variante gemäß Kapitel 20.3 ("...oder kontinuierlich anhand der LLM-Konfidenz").
        abweichung = (tender.ki_relevanz_konfidenz - 0.5) * 0.2
        basis = min(1.0, max(0.0, basis + abweichung))
    return basis


def dringlichkeit_score(tender: Tender, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    if tender.angebotsfrist is None:
        return 0.3  # unbekannte Frist: neutral-niedrig statt 0, damit sie nicht ganz untergeht
    verbleibende_tage = (tender.angebotsfrist - now).total_seconds() / 86400
    if verbleibende_tage <= 0:
        return 0.0
    return max(0.0, min(1.0, 1 - verbleibende_tage / DRINGLICHKEIT_FENSTER_TAGE))


def aktualitaet_score(tender: Tender, now: datetime | None = None) -> float:
    now = now or datetime.utcnow()
    referenz = tender.veroeffentlichungsdatum or tender.erfasst_am
    if referenz is None:
        return 0.0
    alter_tage = (now - referenz).total_seconds() / 86400
    return max(0.0, min(1.0, 1 - alter_tage / AKTUALITAET_FENSTER_TAGE))


def gesamtscore(
    ki: float, dringlichkeit: float, profil: float, aktualitaet: float, *, profil_aktiv: bool
) -> float:
    w1, w2, w3, w4 = (
        settings.ranking_weight_ki_relevanz,
        settings.ranking_weight_dringlichkeit,
        settings.ranking_weight_profil,
        settings.ranking_weight_aktualitaet,
    )
    if not profil_aktiv:
        rest = w1 + w2 + w4
        if rest <= 0:
            return 0.0
        w1, w2, w4 = w1 / rest, w2 / rest, w4 / rest
        return w1 * ki + w2 * dringlichkeit + w4 * aktualitaet
    return w1 * ki + w2 * dringlichkeit + w3 * profil + w4 * aktualitaet


def compute_and_store(db, tender: Tender, profil_score: float = 0.0, profil_aktiv: bool = False) -> RankingScore:
    ki = ki_relevanz_score(tender)
    dr = dringlichkeit_score(tender)
    ak = aktualitaet_score(tender)
    gesamt = gesamtscore(ki, dr, profil_score, ak, profil_aktiv=profil_aktiv)

    row = tender.ranking
    if row is None:
        row = RankingScore(tender_id=tender.id)
        db.add(row)
    row.ki_relevanz_score = ki
    row.dringlichkeit_score = dr
    row.profil_score = profil_score
    row.aktualitaet_score = ak
    row.gesamtscore = gesamt
    row.berechnet_am = datetime.utcnow()
    db.commit()
    return row
