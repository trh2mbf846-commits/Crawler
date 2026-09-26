"""Crawler robuster (26.09.2026): inkrementelles Abrufen, Datenqualität pro Lauf, Fristen-Ergänzung."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.agents import discovery, frist_ergaenzung
from app.agents.connector.base import RawCandidate
from app.agents.source_health import evaluate, record_run
from app.datenqualitaet import einbrueche, messe
from app.models import Escalation, Job, KandidatenStand, Tender

# --- Inkrementell ---------------------------------------------------------------------------


class _FakeConnector:
    kandidaten: list[RawCandidate] = []

    def iter_all_candidates(self):
        return list(self.kandidaten)

    def close(self):
        pass


def _kand(eid, frist="01.11.2026"):
    return RawCandidate(externe_id=eid, detail_url=f"https://x.invalid/CX{eid}XXXXXXX", titel_hint=f"T{eid}",
                        listen_metadaten={"angebotsfrist": frist})


def _discovery(db, portal, monkeypatch, kandidaten):
    _FakeConnector.kandidaten = kandidaten
    monkeypatch.setitem(discovery.CONNECTORS, portal.slug, _FakeConnector)
    job = Job(typ="discovery", portal_id=portal.id, payload={})
    db.add(job)
    db.commit()
    return discovery.run_discovery(db, job)


def _als_erfasst(db, portal, eid):
    db.add(Tender(portal_id=portal.id, externe_id=eid, titel=f"T{eid}", dedupe_hash=eid, direktlink="https://x.invalid/CXABCDEFGH",
                  zuletzt_geprueft_am=datetime.utcnow() - timedelta(days=1)))
    db.commit()


def test_unveraenderte_bekannte_werden_uebersprungen(db, portal, monkeypatch):
    erst = _discovery(db, portal, monkeypatch, [_kand("1"), _kand("2")])
    assert erst["neu_oder_zu_pruefen"] == 2
    _als_erfasst(db, portal, "1")
    _als_erfasst(db, portal, "2")

    zweit = _discovery(db, portal, monkeypatch, [_kand("1"), _kand("2", frist="15.11.2026"), _kand("3")])

    # 1 unverändert -> übersprungen; 2 Frist geändert -> neu abrufen; 3 neu
    assert zweit["unveraendert_uebersprungen"] == 1
    assert zweit["neu_oder_zu_pruefen"] == 2
    assert zweit["kandidaten_gesamt"] == 3
    t1 = db.query(Tender).filter_by(externe_id="1").one()
    assert t1.zuletzt_geprueft_am > datetime.utcnow() - timedelta(minutes=1)


def test_nach_neupruefungsfrist_wird_wieder_abgerufen(db, portal, monkeypatch):
    _discovery(db, portal, monkeypatch, [_kand("1")])
    _als_erfasst(db, portal, "1")
    stand = db.get(KandidatenStand, (portal.id, "1"))
    stand.zuletzt_abgerufen_am = datetime.utcnow() - timedelta(days=30)
    db.commit()
    assert _discovery(db, portal, monkeypatch, [_kand("1")])["neu_oder_zu_pruefen"] == 1


# --- Datenqualität --------------------------------------------------------------------------


def _q(frist, n=20):
    return {"anzahl": n, "quoten": {"angebotsfrist": frist, "vergabestelle": 1.0, "kurzbeschreibung": 1.0,
                                     "ort_region": 1.0, "direktlink": 1.0}}


def test_einbruch_wird_erkannt_kleine_schwankung_nicht():
    assert einbrueche(_q(0.2), [_q(0.9), _q(0.95)]) == ["Anteil mit Frist von 92% auf 20% gefallen"]
    assert einbrueche(_q(0.8), [_q(0.9)]) == []
    assert einbrueche(_q(0.0, n=3), [_q(0.9)]) == []  # zu wenige Ausschreibungen


def test_messe_und_warnung_im_quellstatus(db, portal):
    start = datetime.utcnow() - timedelta(minutes=1)
    for i in range(12):
        db.add(Tender(portal_id=portal.id, externe_id=str(i), titel="x", dedupe_hash=str(i),
                      direktlink="https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX", vergabestelle="Amt"))
    db.commit()
    q = messe(db, portal, start)
    assert q["anzahl"] == 12 and q["quoten"]["angebotsfrist"] == 0 and q["quoten"]["direktlink"] == 1.0

    record_run(db, portal, erfolgreich=True, treffer_anzahl=12, qualitaet=_q(0.9))
    record_run(db, portal, erfolgreich=True, treffer_anzahl=12, qualitaet=q)
    status = evaluate(db, portal)
    assert status["status_ampel"] == "gelb"
    assert "Datenqualität" in status["meldung"] and "Frist" in status["meldung"]
    assert db.query(Escalation).filter(Escalation.kontext.contains("Datenqualität")).count() == 1


# --- Fristen-Ergänzung ----------------------------------------------------------------------

_JETZT = datetime(2026, 9, 26)


def test_frist_per_suchmuster():
    text = "Fragen bis 01.10.2026. Ablauf der Angebotsfrist: 14.10.2026 um 10:00 Uhr. Bindefrist 30.12.2026"
    assert frist_ergaenzung.frist_per_muster(text, _JETZT) == datetime(2026, 10, 14, 10, 0)
    assert frist_ergaenzung.frist_per_muster("Schlusstermin für den Eingang der Angebote 03.11.2026", _JETZT) == datetime(2026, 11, 3)
    assert frist_ergaenzung.frist_per_muster("Angebotsfrist: 01.01.2020", _JETZT) is None  # vergangen
    assert frist_ergaenzung.frist_per_muster("Keine Frist genannt", _JETZT) is None


def test_ki_frist_nur_mit_echtem_beleg(monkeypatch):
    text = "Die Angebote sind bis zum 20.10.2026, 12:00 Uhr elektronisch einzureichen."
    monkeypatch.setattr(frist_ergaenzung.prompts, "call_llm_json", lambda *a, **k: {
        "angebotsfrist": "2026-10-20T12:00", "beleg": "bis zum 20.10.2026, 12:00 Uhr elektronisch einzureichen"})
    assert frist_ergaenzung.frist_per_ki(text) == datetime(2026, 10, 20, 12, 0)
    # erfundener Beleg -> abgelehnt
    monkeypatch.setattr(frist_ergaenzung.prompts, "call_llm_json", lambda *a, **k: {
        "angebotsfrist": "2026-10-20T12:00", "beleg": "Angebotsfrist 20.10.2026"})
    assert frist_ergaenzung.frist_per_ki(text) is None
    # Beleg echt, aber Datum passt nicht dazu -> abgelehnt
    monkeypatch.setattr(frist_ergaenzung.prompts, "call_llm_json", lambda *a, **k: {
        "angebotsfrist": "2026-11-05T12:00", "beleg": "bis zum 20.10.2026, 12:00 Uhr elektronisch einzureichen"})
    assert frist_ergaenzung.frist_per_ki(text) is None


def test_ergaenze_fristen_markiert_quelle_und_versucht_nur_einmal(db, portal, monkeypatch):
    t = Tender(portal_id=portal.id, titel="KI", dedupe_hash="a", direktlink="https://x.invalid/CXABCDEFGH", ki_relevanz_score="stark")
    db.add(t)
    db.commit()
    aufrufe = []
    monkeypatch.setattr(frist_ergaenzung, "_verfahrensseite_text",
                        lambda url: aufrufe.append(url) or "Angebotsfrist: 30.12.2099 11:00")
    assert frist_ergaenzung.ergaenze_fristen(db)["seite"] == 1
    db.refresh(t)
    assert t.angebotsfrist == datetime(2099, 12, 30, 11, 0) and t.frist_quelle == "seite"
    t.angebotsfrist = None
    db.commit()
    frist_ergaenzung.ergaenze_fristen(db)
    assert len(aufrufe) == 1  # nicht erneut versucht


# --- Bewerbungsalltag: Checkliste, Fristen, Referenzen --------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_checkliste_aus_bewertung_ergaenzt_ohne_haekchen_zu_verlieren(db, portal):
    t = Tender(portal_id=portal.id, titel="KI", dedupe_hash="c", direktlink="https://x.invalid/CXABCDEFGH",
               bewertung_json={"pflichtnachweise": ["Referenzen", "ISO 27001"], "fehlende_nachweise": ["ISO 27001"],
                               "ausschlusskriterien": ["Insolvenz"], "fristen": []})
    db.add(t)
    db.commit()
    punkte = client.post(f"/api/tenders/{t.id}/checkliste/aus-bewertung").json()
    assert [(p["text"], p["status"]) for p in punkte] == [
        ("Referenzen", "offen"), ("ISO 27001", "fehlt"), ("Ausschlusskriterium prüfen: Insolvenz", "offen")]
    punkte[0]["status"] = "vorhanden"
    punkte.append({"id": "eigen1", "text": "Angebot unterschreiben", "art": "eigen", "status": "offen"})
    assert client.put(f"/api/tenders/{t.id}/checkliste", json=punkte).status_code == 200
    erneut = client.post(f"/api/tenders/{t.id}/checkliste/aus-bewertung").json()
    assert len(erneut) == 4 and erneut[0]["status"] == "vorhanden"  # Häkchen bleiben, keine Doppelten
    assert client.put(f"/api/tenders/{t.id}/checkliste", json=[{"id": "x", "text": "a", "status": "quatsch"}]).status_code == 422


def test_fristen_kalender_und_ics(db, portal):
    bald = datetime.utcnow() + timedelta(days=5)
    db.add_all([
        Tender(portal_id=portal.id, titel="Gemerkt, Chatbot; Stadt", dedupe_hash="f1", gemerkt=True,
               direktlink="https://x.invalid/CX1ABCDEFG", angebotsfrist=bald.replace(hour=10, minute=0),
               fragenfrist=bald - timedelta(days=2)),
        Tender(portal_id=portal.id, titel="Lohnt nicht", dedupe_hash="f2", direktlink="https://x.invalid/CX2ABCDEFG",
               angebotsfrist=bald, bewertung_json={"empfehlung": "nicht_bewerben"}),
        Tender(portal_id=portal.id, titel="Unbeachtet", dedupe_hash="f3", direktlink="https://x.invalid/CX3ABCDEFG",
               angebotsfrist=bald),
    ])
    db.commit()
    fristen = client.get("/api/fristen").json()
    assert [(f["art"], f["titel"]) for f in fristen] == [
        ("Fragenfrist", "Gemerkt, Chatbot; Stadt"), ("Angebotsfrist", "Gemerkt, Chatbot; Stadt")]
    ics = client.get("/api/fristen.ics")
    assert ics.headers["content-type"].startswith("text/calendar")
    assert ics.text.count("BEGIN:VEVENT") == 2 and r"Gemerkt\, Chatbot\; Stadt" in ics.text and "TRIGGER:-P3D" in ics.text


def test_referenzen_crud():
    neu = client.post("/api/referenzen", json={"titel": "KI-Chatbot Landkreis", "jahr": 2025, "volumen": 80000}).json()
    assert client.get("/api/referenzen").json()[0]["titel"] == "KI-Chatbot Landkreis"
    geaendert = client.put(f"/api/referenzen/{neu['id']}", json={"titel": "KI-Chatbot Landkreis Y", "jahr": 2025}).json()
    assert geaendert["titel"] == "KI-Chatbot Landkreis Y"
    assert client.delete(f"/api/referenzen/{neu['id']}").status_code == 204
    assert client.get("/api/referenzen").json() == []


# --- Quellstatus ohne Fehlalarme (Nutzerfrage "warum steht nur eingeschränkt?") --------------

from app.config import settings  # noqa: E402
from app.models import Portal  # noqa: E402


def test_inaktive_und_neue_portale_sind_nicht_gelb(db, portal):
    inaktiv = Portal(name="Vergabe24", slug="vergabe24", base_url="https://x.invalid/", aktiv=False)
    db.add(inaktiv)
    db.commit()
    assert evaluate(db, inaktiv)["status_ampel"] == "inaktiv"
    assert evaluate(db, portal)["status_ampel"] == "neu"


def test_einzelner_null_treffer_lauf_bleibt_gruen(db, portal):
    record_run(db, portal, erfolgreich=True, treffer_anzahl=0)
    assert evaluate(db, portal)["status_ampel"] == "gruen"
    record_run(db, portal, erfolgreich=True, treffer_anzahl=0)
    assert evaluate(db, portal)["status_ampel"] == "gelb"


def test_einzelner_fehlschlag_bei_wenigen_schritten_kein_alarm(db, portal):
    record_run(db, portal, erfolgreich=True, treffer_anzahl=10, fehlerrate=0.5, fehler_anzahl=1)
    assert evaluate(db, portal)["status_ampel"] == "gruen"
    record_run(db, portal, erfolgreich=True, treffer_anzahl=10, fehlerrate=0.5, fehler_anzahl=5)
    assert "Fehlerrate" in evaluate(db, portal)["meldung"]


def test_ohne_dauerbetrieb_ist_ein_tag_ohne_lauf_normal(db, portal, monkeypatch):
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    m = record_run(db, portal, erfolgreich=True, treffer_anzahl=10)
    m.lauf_am = datetime.utcnow() - timedelta(days=2)
    db.commit()
    assert evaluate(db, portal)["status_ampel"] == "gruen"
    m.lauf_am = datetime.utcnow() - timedelta(days=4)
    db.commit()
    ergebnis = evaluate(db, portal)
    assert ergebnis["status_ampel"] == "rot" and "3 Tagen" in ergebnis["meldung"]
