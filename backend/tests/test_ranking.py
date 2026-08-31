from datetime import datetime, timedelta

import pytest

from app.agents import ranking
from app.models import Tender


def _tender(**overrides) -> Tender:
    base = dict(
        titel="Test", direktlink="https://example.invalid", dedupe_hash="x", status="neu",
    )
    base.update(overrides)
    return Tender(**base)


def test_dringlichkeit_hoch_bei_kurzer_frist():
    t = _tender(angebotsfrist=datetime.utcnow() + timedelta(days=3))
    assert ranking.dringlichkeit_score(t) > 0.9


def test_dringlichkeit_niedrig_bei_langer_frist():
    t = _tender(angebotsfrist=datetime.utcnow() + timedelta(days=90))
    assert ranking.dringlichkeit_score(t) == 0.0


def test_dringlichkeit_abgelaufen_ist_null():
    t = _tender(angebotsfrist=datetime.utcnow() - timedelta(days=1))
    assert ranking.dringlichkeit_score(t) == 0.0


def test_ki_relevanz_basiswerte():
    assert ranking.ki_relevanz_score(_tender(ki_relevanz_score="stark")) == 1.0
    assert ranking.ki_relevanz_score(_tender(ki_relevanz_score="moeglich")) == 0.5
    assert ranking.ki_relevanz_score(_tender(ki_relevanz_score="nicht")) == 0.0


def test_gesamtscore_ohne_profil_skaliert_verbleibende_gewichte_hoch():
    score_ohne_profil = ranking.gesamtscore(1.0, 1.0, 0.0, 1.0, profil_aktiv=False)
    assert score_ohne_profil == pytest.approx(1.0)  # alle Teil-Scores maximal -> Gesamtscore trotz Reskalierung maximal


def test_compute_and_store_persistiert_score(db, portal):
    tender = _tender(portal_id=portal.id, ki_relevanz_score="stark", angebotsfrist=datetime.utcnow() + timedelta(days=5))
    db.add(tender)
    db.commit()
    db.refresh(tender)

    row = ranking.compute_and_store(db, tender)
    assert row.gesamtscore > 0
    assert tender.ranking is not None
