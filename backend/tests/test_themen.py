"""Themen statt fest einprogrammierter Kategorien (26.09.2026, app/themen.py)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.agents.assistant import execute_assistant_action
from app.agents.classification import run_classification
from app.agents.connector import ted
from app.main import app
from app.models import Job, Tender, Thema
from app.themen import STANDARD_THEMEN, lege_standard_themen_an, ordne_neu_ein, ted_suchbegriffe

client = TestClient(app)


def _tender(db, portal, titel, **felder):
    t = Tender(portal_id=portal.id, titel=titel, dedupe_hash=titel, direktlink="https://x.invalid/CXABCDEFGH", **felder)
    db.add(t)
    db.commit()
    return t


def _klassifiziere(db, tender):
    job = Job(typ="classification", portal_id=tender.portal_id, payload={"tender_id": tender.id})
    db.add(job)
    db.commit()
    run_classification(db, job)
    db.refresh(tender)


def test_standardthemen_ki_avatare_und_training(db):
    lege_standard_themen_an(db)
    namen = [t["name"] for t in client.get("/api/themen").json()]
    assert namen == sorted(t["name"] for t in STANDARD_THEMEN)
    kategorien = client.get("/api/categories").json()
    assert "KI-Avatare & digitale Assistenten" in kategorien and "KI-Training & Schulung" in kategorien


def test_geloeschtes_standardthema_kommt_nicht_wieder(db):
    lege_standard_themen_an(db)
    thema = db.query(Thema).filter_by(name="KI-Training & Schulung").one()
    assert client.delete(f"/api/themen/{thema.id}").status_code == 204
    lege_standard_themen_an(db)
    assert "KI-Training & Schulung" not in [t["name"] for t in client.get("/api/themen").json()]


def test_klassifikation_nutzt_themen(db, portal):
    lege_standard_themen_an(db)
    t = _tender(db, portal, "Entwicklung eines Gebärdensprach-Avatars für das Bürgeramt")
    _klassifiziere(db, t)
    assert "KI-Avatare & digitale Assistenten" in {tk.category.name for tk in t.kategorien}
    assert t.ki_relevanz_score in ("moeglich", "stark")  # danach entscheidet die KI-Nachprüfung streng


def test_neues_thema_ueber_oberflaeche_und_neu_einordnung(db, portal):
    t = _tender(db, portal, "Beschaffung eines Serviceroboters für die Bibliothek", ki_relevanz_score="nicht")
    antwort = client.post("/api/themen", json={"name": "Robotik", "stichworte": ["Serviceroboter", "  robotik "]})
    assert antwort.status_code == 201 and antwort.json()["stichworte"] == ["serviceroboter", "robotik"]
    assert client.post("/api/themen", json={"name": "Robotik", "stichworte": ["x"]}).status_code == 409
    assert client.post("/api/themen", json={"name": "Leer", "stichworte": []}).status_code == 422
    assert client.post("/api/themen", json={"name": "Cybersecurity", "stichworte": ["x"]}).status_code == 422

    assert ordne_neu_ein(db) == 1
    db.refresh(t)
    assert "Robotik" in {tk.category.name for tk in t.kategorien}
    assert t.ki_relevanz_score == "moeglich"  # KI-bezogen -> zur Nachprüfung vormerken
    assert ordne_neu_ein(db) == 0  # idempotent


def test_ted_sucht_auch_nach_themen(db, monkeypatch):
    lege_standard_themen_an(db)
    begriffe = ted_suchbegriffe(db)
    assert "ki-avatar" in begriffe and "gebaerdensprach-avatar" in begriffe
    monkeypatch.setattr(ted, "_themen_begriffe", lambda: begriffe)
    assert 'FT ~ "ki-schulung"' in ted._ft_query()


def test_kevin_legt_thema_nach_bestaetigung_an(db):
    ergebnis = execute_assistant_action(db, "thema_anlegen", {"name": "Robotik", "stichworte": ["robotik", "roboter"]})
    assert ergebnis.erfolg and db.query(Thema).filter_by(name="Robotik").one().ki_bezogen is True
    assert not execute_assistant_action(db, "thema_anlegen", {"name": "Robotik", "stichworte": ["x"]}).erfolg


def test_kombi_stichworte_und_wortgrenzen():
    from app.themen import stichwort_trifft

    text = " schulungen für beschäftigte zum einsatz von ki in der verwaltung "
    assert stichwort_trifft("schulung + ki", text)
    assert not stichwort_trifft("schulung + ki", " schulungen für kita-personal in kiel ")  # "ki" nur als Wort
    assert stichwort_trifft("ki-avatar", " entwicklung eines ki-avatars ")
    assert not stichwort_trifft("avatar", " kavatarien ")  # nur am Wortanfang
