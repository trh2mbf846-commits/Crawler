from app import queue
from app.agents.classification import run_classification
from app.agents.duplicate import run_duplicate
from app.models import Tender


def _make_tender(db, portal, titel, kurzbeschreibung):
    job = queue.enqueue(
        db, "duplicate", portal_id=portal.id,
        payload={
            "normalized": {
                "externe_id": "X-1", "direktlink": "https://example.invalid/1", "titel": titel,
                "volltext": kurzbeschreibung, "kurzbeschreibung": kurzbeschreibung, "vergabestelle": "Amt",
                "ort_region": None, "veroeffentlichungsdatum": None, "angebotsfrist": None,
                "fragenfrist": None, "verfahrensart": None, "cpv_codes": [], "geschaetzter_wert": None,
                "dokumente_links": [], "zugangsart": "oeffentlich",
            }
        },
    )
    ergebnis = run_duplicate(db, job)
    return db.get(Tender, ergebnis["tender_id"])


def test_starke_ki_relevanz_bei_mehreren_treffern(db, portal):
    tender = _make_tender(db, portal, "Beschaffung eines Machine-Learning-Systems", "Künstliche Intelligenz und Deep Learning für die Verwaltung")
    job = queue.enqueue(db, "classification", portal_id=portal.id, payload={"tender_id": tender.id})
    ergebnis = run_classification(db, job)

    assert ergebnis["ki_relevanz_score"] == "stark"
    assert "KI & Machine Learning" in ergebnis["kategorien"]


def test_keine_ki_relevanz_ohne_treffer(db, portal):
    tender = _make_tender(db, portal, "Lieferung von Büromaterial", "Stifte und Papier für die Verwaltung")
    job = queue.enqueue(db, "classification", portal_id=portal.id, payload={"tender_id": tender.id})
    ergebnis = run_classification(db, job)

    assert ergebnis["ki_relevanz_score"] == "nicht"


def test_klassifikation_ist_nachvollziehbar(db, portal):
    tender = _make_tender(db, portal, "KI-Strategie-Beratung", "Beratung zur KI-Strategie der Behörde")
    job = queue.enqueue(db, "classification", portal_id=portal.id, payload={"tender_id": tender.id})
    run_classification(db, job)

    db.refresh(tender)
    assert tender.ki_relevanz_begruendung is not None
    assert tender.ki_relevanz_quelle in ("keyword", "cpv")
