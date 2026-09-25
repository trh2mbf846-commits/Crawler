from app import queue
from app.agents.duplicate import run_duplicate
from app.models import Portal, Tender, TenderHistory


def _normalized(**overrides):
    base = {
        "externe_id": "AUSS-1",
        "direktlink": "https://example.invalid/1",
        "titel": "KI-Beratung für die Verwaltung",
        "volltext": "Volltext",
        "kurzbeschreibung": "Kurz",
        "vergabestelle": "Testamt",
        "ort_region": "Berlin",
        "veroeffentlichungsdatum": "2026-08-01T00:00:00",
        "angebotsfrist": "2026-09-30T00:00:00",
        "fragenfrist": None,
        "verfahrensart": "Offenes Verfahren",
        "cpv_codes": [],
        "geschaetzter_wert": 100000.0,
        "dokumente_links": [],
        "zugangsart": "oeffentlich",
    }
    base.update(overrides)
    return base


def test_neue_ausschreibung_wird_angelegt(db, portal):
    job = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": _normalized()})
    ergebnis = run_duplicate(db, job)

    assert ergebnis["ergebnis"] == "neu"
    tender = db.get(Tender, ergebnis["tender_id"])
    assert tender.titel == "KI-Beratung für die Verwaltung"
    assert tender.status == "neu"


def test_wiederholter_lauf_erzeugt_kein_duplikat(db, portal):
    job1 = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": _normalized()})
    run_duplicate(db, job1)

    job2 = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": _normalized()})
    ergebnis2 = run_duplicate(db, job2)

    assert ergebnis2["ergebnis"] == "unveraendert"
    alle = db.query(Tender).filter(Tender.portal_id == portal.id).all()
    assert len(alle) == 1


def test_veraenderte_frist_wird_als_aktualisierung_erkannt(db, portal):
    job1 = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": _normalized()})
    run_duplicate(db, job1)

    job2 = queue.enqueue(
        db, "duplicate", portal_id=portal.id,
        payload={"normalized": _normalized(angebotsfrist="2026-10-15T00:00:00")},
    )
    ergebnis2 = run_duplicate(db, job2)

    assert ergebnis2["ergebnis"] == "aktualisiert"
    tender = db.get(Tender, ergebnis2["tender_id"])
    assert tender.status == "aktualisiert"
    assert tender.angebotsfrist.day == 15

    historie = db.query(TenderHistory).filter(TenderHistory.tender_id == tender.id).all()
    assert any(h.feld == "angebotsfrist" for h in historie)


def test_aehnliche_ausschreibung_auf_anderem_portal_wird_als_moegliches_duplikat_markiert(db, portal):
    anderes_portal = Portal(name="Zweites Test-Portal", slug="zweites-test-portal", base_url="https://example.invalid/2")
    db.add(anderes_portal)
    db.commit()
    db.refresh(anderes_portal)

    job1 = queue.enqueue(
        db, "duplicate", portal_id=portal.id,
        payload={"normalized": _normalized(externe_id="A-1", direktlink="https://example.invalid/a-1")},
    )
    run_duplicate(db, job1)

    job2 = queue.enqueue(
        db, "duplicate", portal_id=anderes_portal.id,
        payload={"normalized": _normalized(
            externe_id="B-1", direktlink="https://example.invalid/b-1",
            titel="KI-Beratung für die Verwaltung ",  # minimale Abweichung (Leerzeichen)
            veroeffentlichungsdatum="2026-08-02T00:00:00",  # 1 Tag später, im Fenster
        )},
    )
    ergebnis2 = run_duplicate(db, job2)

    tender2 = db.get(Tender, ergebnis2["tender_id"])
    assert tender2.moeglicherweise_duplikat_hinweis is not None
    assert "Test-Portal" in tender2.moeglicherweise_duplikat_hinweis


def test_unaehnliche_ausschreibung_auf_anderem_portal_bleibt_unmarkiert(db, portal):
    anderes_portal = Portal(name="Zweites Test-Portal", slug="zweites-test-portal", base_url="https://example.invalid/2")
    db.add(anderes_portal)
    db.commit()
    db.refresh(anderes_portal)

    job1 = queue.enqueue(
        db, "duplicate", portal_id=portal.id,
        payload={"normalized": _normalized(externe_id="A-1", direktlink="https://example.invalid/a-1")},
    )
    run_duplicate(db, job1)

    job2 = queue.enqueue(
        db, "duplicate", portal_id=anderes_portal.id,
        payload={"normalized": _normalized(
            externe_id="B-1", direktlink="https://example.invalid/b-1",
            titel="Neubau einer Sporthalle in Musterstadt",
            vergabestelle="Ganz anderes Amt",
            veroeffentlichungsdatum="2026-08-02T00:00:00",
        )},
    )
    ergebnis2 = run_duplicate(db, job2)

    tender2 = db.get(Tender, ergebnis2["tender_id"])
    assert tender2.moeglicherweise_duplikat_hinweis is None
