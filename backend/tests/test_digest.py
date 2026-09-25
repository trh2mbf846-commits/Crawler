from datetime import datetime, timedelta

import httpx

from app import queue
from app.agents import digest as digest_module
from app.agents import source_health
from app.agents.digest import DigestResult, build_daily_digest, send_digest_webhook
from app.agents.duplicate import run_duplicate
from app.config import settings
from app.models import AssistantPreferences, Portal, Tender


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


_BEISPIEL_DIGEST = DigestResult(text="Testbericht", neue_relevante_anzahl=1, bald_ablaufend_anzahl=0, portale_mit_problem=[])


def test_send_digest_webhook_ohne_url_liefert_false(monkeypatch):
    monkeypatch.setattr(settings, "digest_webhook_url", None)

    assert send_digest_webhook(_BEISPIEL_DIGEST) is False


def test_send_digest_webhook_schickt_post_mit_text_und_content(monkeypatch):
    monkeypatch.setattr(settings, "digest_webhook_url", "https://example.invalid/webhook")
    aufrufe = []

    def fake_post(url, json, timeout):
        aufrufe.append((url, json))
        return httpx.Response(200)

    monkeypatch.setattr(digest_module.httpx, "post", fake_post)

    ergebnis = send_digest_webhook(_BEISPIEL_DIGEST)

    assert ergebnis is True
    assert len(aufrufe) == 1
    url, payload = aufrufe[0]
    assert url == "https://example.invalid/webhook"
    assert payload["text"] == "Testbericht"
    assert payload["content"] == "Testbericht"
    assert payload["neue_relevante_anzahl"] == 1


def test_send_digest_webhook_liefert_false_bei_fehlerstatus(monkeypatch):
    monkeypatch.setattr(settings, "digest_webhook_url", "https://example.invalid/webhook")
    monkeypatch.setattr(digest_module.httpx, "post", lambda *a, **k: httpx.Response(500))

    assert send_digest_webhook(_BEISPIEL_DIGEST) is False


def test_send_digest_webhook_liefert_false_bei_verbindungsfehler(monkeypatch):
    monkeypatch.setattr(settings, "digest_webhook_url", "https://example.invalid/webhook")

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("nicht erreichbar")

    monkeypatch.setattr(digest_module.httpx, "post", _raise)

    assert send_digest_webhook(_BEISPIEL_DIGEST) is False
