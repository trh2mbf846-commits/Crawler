from datetime import datetime, timedelta

from app import queue
from app.agents.digest import build_daily_digest
from app.agents.duplicate import run_duplicate
from app.models import AssistantPreferences, Portal, Tender
from app.agents import source_health


def _angelegte_ausschreibung(db, portal, **overrides):
    base = {
        "externe_id": "DIGEST-1",
        "direktlink": "https://example.invalid/digest-1",
        "titel": "KI-Beratung für die Verwaltung",
        "volltext": "Volltext", "kurzbeschreibung": "Kurz",
        "vergabestelle": "Testamt", "ort_region": "Berlin",
        "veroeffentlichungsdatum": "2026-08-01T00:00:00", "angebotsfrist": "2026-09-30T00:00:00",
        "fragenfrist": None, "verfahrensart": "Offenes Verfahren", "cpv_codes": [],
        "geschaetzter_wert": 100000.0, "dokumente_links": [], "zugangsart": "oeffentlich",
    }
    base.update(overrides)
    job = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": base})
    ergebnis = run_duplicate(db, job)
    tender_id = ergebnis["tender_id"]
    return db.get(Tender, tender_id)


def test_digest_ohne_daten_ist_neutral(db):
    ergebnis = build_daily_digest(db)

    assert ergebnis.neue_relevante_anzahl == 0
    assert ergebnis.bald_ablaufend_anzahl == 0
    assert "Keine neuen relevanten Ausschreibungen" in ergebnis.text


def test_digest_findet_neue_relevante_ausschreibung(db, portal):
    tender = _angelegte_ausschreibung(db, portal, externe_id="DIGEST-NEU")
    tender.ki_relevanz_score = "stark"
    tender.erfasst_am = datetime.utcnow()
    db.commit()

    ergebnis = build_daily_digest(db)

    assert ergebnis.neue_relevante_anzahl == 1
    assert tender.titel in ergebnis.text
    assert any(t.id == tender.id for t in ergebnis.tenders)


def test_digest_ignoriert_alte_ausschreibung(db, portal):
    tender = _angelegte_ausschreibung(db, portal, externe_id="DIGEST-ALT")
    tender.ki_relevanz_score = "stark"
    tender.erfasst_am = datetime.utcnow() - timedelta(days=5)
    db.commit()

    ergebnis = build_daily_digest(db)

    assert ergebnis.neue_relevante_anzahl == 0


def test_digest_findet_bald_ablaufende_gemerkte_ausschreibung(db, portal):
    tender = _angelegte_ausschreibung(db, portal, externe_id="DIGEST-FRIST")
    tender.angebotsfrist = datetime.utcnow() + timedelta(days=3)
    tender.gemerkt = True
    db.commit()

    ergebnis = build_daily_digest(db)

    assert ergebnis.bald_ablaufend_anzahl == 1
    assert "Frist(en) laufen" in ergebnis.text


def test_digest_zeigt_rote_portale(db, portal):
    source_health.record_run(db, portal, erfolgreich=False, fehlertyp="technisch", dauer_ms=100)
    source_health.record_run(db, portal, erfolgreich=False, fehlertyp="technisch", dauer_ms=100)
    source_health.record_run(db, portal, erfolgreich=False, fehlertyp="technisch", dauer_ms=100)

    ergebnis = build_daily_digest(db)

    assert portal.name in ergebnis.portale_mit_problem
    assert "Probleme bei" in ergebnis.text


def test_digest_erwaehnt_prioritaeten_wenn_gesetzt(db):
    db.add(AssistantPreferences(id="singleton", prioritaeten_text="Fokus auf KI-Projekte in Bayern"))
    db.commit()

    ergebnis = build_daily_digest(db)

    assert "Fokus auf KI-Projekte in Bayern" in ergebnis.text
