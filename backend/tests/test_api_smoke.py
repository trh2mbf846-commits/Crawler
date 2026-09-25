"""HTTP-Smoke-Tests für alle registrierten Router (app/main.py).

Grund: Der reine Refactor von api/tenders.py in app/tender_queries.py (Nutzeranfrage 25.09.2026,
KI-Assistent) hat versehentlich den Tender-Import aus api/tenders.py entfernt - die Agenten-Tests
(test_duplicate.py etc.) riefen die Agenten-Funktionen direkt auf und liefen alle grün, aber
GET /api/tenders/{id} war live tatsächlich kaputt (NameError, erst per Playwright-Browsertest
gegen die echte laufende Anwendung entdeckt). Diese Datei schließt genau diese Lücke: mindestens
ein durchgehender HTTP-Aufruf pro Endpunkt, damit ein kaputter Import/Wiring-Fehler künftig schon
im schnellen Testlauf auffällt statt erst im Browser.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import queue
from app.agents.duplicate import run_duplicate
from app.main import app

client = TestClient(app)


def _angelegte_ausschreibung(db, portal):
    normalized = {
        "externe_id": "SMOKE-1",
        "direktlink": "https://example.invalid/smoke-1",
        "titel": "Smoke-Test-Ausschreibung",
        "volltext": "Volltext", "kurzbeschreibung": "Kurz",
        "vergabestelle": "Testamt", "ort_region": "Berlin",
        "veroeffentlichungsdatum": "2026-08-01T00:00:00", "angebotsfrist": "2026-09-30T00:00:00",
        "fragenfrist": None, "verfahrensart": "Offenes Verfahren", "cpv_codes": [],
        "geschaetzter_wert": 100000.0, "dokumente_links": [], "zugangsart": "oeffentlich",
    }
    job = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": normalized})
    return run_duplicate(db, job)["tender_id"]


def test_tenders_liste_und_detail_und_verlauf(db, portal):
    tender_id = _angelegte_ausschreibung(db, portal)

    liste = client.get("/api/tenders")
    assert liste.status_code == 200
    assert liste.json()["total"] >= 1

    detail = client.get(f"/api/tenders/{tender_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == tender_id

    verlauf = client.get(f"/api/tenders/{tender_id}/history")
    assert verlauf.status_code == 200


def test_tenders_detail_404_bei_unbekannter_id(db):
    response = client.get("/api/tenders/existiert-nicht")
    assert response.status_code == 404


def test_portals_liste(db, portal):
    response = client.get("/api/portals")
    assert response.status_code == 200
    assert any(p["name"] == portal.name for p in response.json())


def test_categories_liste(db):
    response = client.get("/api/categories")
    assert response.status_code == 200


def test_search_profiles_liste(db):
    response = client.get("/api/search-profiles")
    assert response.status_code == 200


def test_escalations_liste(db):
    response = client.get("/api/escalations")
    assert response.status_code == 200


def test_assistant_chat_ohne_api_key(db):
    response = client.post("/api/assistant/chat", json={"nachricht": "Test"})
    assert response.status_code == 200
    assert response.json()["verfuegbar"] is False


def test_assistant_actions_execute_unbekannte_aktion(db):
    response = client.post("/api/assistant/actions/execute", json={"name": "unbekannt", "input": {}})
    assert response.status_code == 200
    assert response.json()["erfolg"] is False


def test_assistant_digest(db, portal):
    response = client.get("/api/assistant/digest")
    assert response.status_code == 200
    assert "text" in response.json()


def test_assistant_preferences_get_und_put(db):
    get_response = client.get("/api/assistant/preferences")
    assert get_response.status_code == 200
    assert get_response.json()["prioritaeten_text"] is None

    put_response = client.put(
        "/api/assistant/preferences",
        json={"prioritaeten_text": "Fokus auf KI", "bevorzugte_kategorien": [], "bevorzugte_regionen": [], "mindestwert": None},
    )
    assert put_response.status_code == 200
    assert put_response.json()["prioritaeten_text"] == "Fokus auf KI"

    erneut = client.get("/api/assistant/preferences")
    assert erneut.json()["prioritaeten_text"] == "Fokus auf KI"
