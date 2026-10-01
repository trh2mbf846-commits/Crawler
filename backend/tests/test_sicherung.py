"""Datenbank-Sicherung / Startdatei (api/sicherung.py)."""
from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app.main import app
from app.models import Thema

client = TestClient(app)


def test_sicherung_ist_gueltige_sqlite_datei_mit_den_eigenen_daten(db, portal, tmp_path):
    db.add(Thema(name="Robotik", stichworte=["robotik"]))
    db.commit()
    antwort = client.get("/api/datenbank-sicherung")
    assert antwort.status_code == 200
    assert "crawler-sicherung-" in antwort.headers["content-disposition"]
    assert antwort.content[:15] == b"SQLite format 3"

    datei = tmp_path / "sicherung.db"
    datei.write_bytes(antwort.content)
    verbindung = sqlite3.connect(datei)
    assert ("Robotik",) in verbindung.execute("select name from themen").fetchall()
    assert verbindung.execute("select count(*) from portals").fetchone()[0] >= 1
    verbindung.close()
