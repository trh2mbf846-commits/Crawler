"""Tests für den manuellen Aktualisieren-Button (app/api/run.py, Nutzeranfrage 01.09.2026)."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import app


def test_run_all_verarbeitet_aktive_portale_im_hintergrund(portal, db):
    portal.aktiv = True
    db.commit()

    client = TestClient(app)

    response = client.post("/api/run-all")
    assert response.status_code == 200
    assert response.json()["laeuft"] is True

    for _ in range(50):
        status = client.get("/api/run-all/status").json()
        if not status["laeuft"]:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Aktualisieren-Lauf wurde nicht rechtzeitig abgeschlossen")

    assert status["beendet_am"] is not None
    assert len(status["ergebnisse"]) == 1
    assert status["ergebnisse"][0]["portal_name"] == portal.name
    # Kein Connector für das Test-Portal registriert -> erwarteter, sauber behandelter Fehlschlag.
    assert status["ergebnisse"][0]["status_ampel"] == "rot"


def test_run_all_lehnt_parallelen_zweiten_lauf_ab(portal, db):
    portal.aktiv = True
    db.commit()

    client = TestClient(app)
    client.post("/api/run-all")
    response = client.post("/api/run-all")
    assert response.status_code == 409

    for _ in range(50):
        if not client.get("/api/run-all/status").json()["laeuft"]:
            break
        time.sleep(0.1)
