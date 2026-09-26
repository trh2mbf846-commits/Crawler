"""Tests für: RIB bundesweit, tägliche automatische Aktualisierung, KI-Nachprüfung (25.09.2026)."""
from __future__ import annotations

from datetime import datetime

import pytest

from app import prompts
from app.agents import ki_nachpruefung
from app.agents.connector import vergabe_bayern
from app.config import settings
from app.models import Category, Tender, TenderCategory
from app.tagesaktualisierung import lauf_heute_verpasst, uhrzeit

# --- RIB/iTWO bundesweit --------------------------------------------------------------------


def test_rib_connector_ohne_bayern_filter():
    assert "filter=" not in vergabe_bayern.BASE_URL
    assert vergabe_bayern._FILTER_ID == ""
    assert vergabe_bayern.VergabeBayernConnector.max_pages * 20 >= 1500


# --- Tägliche automatische Aktualisierung ---------------------------------------------------


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [("07:00", (7, 0)), ("6:30", (6, 30)), ("", None), ("25:00", None), ("sieben", None)],
)
def test_uhrzeit_einstellung(wert, erwartet):
    vorher = settings.auto_aktualisieren_uhrzeit
    settings.auto_aktualisieren_uhrzeit = wert
    try:
        assert uhrzeit() == erwartet
    finally:
        settings.auto_aktualisieren_uhrzeit = vorher


def test_verpasster_lauf_wird_erkannt():
    heute_9 = datetime(2026, 9, 25, 9, 0)
    assert lauf_heute_verpasst(heute_9, None, 7, 0) is True
    # vor 7 Uhr: noch nicht fällig
    assert lauf_heute_verpasst(datetime(2026, 9, 25, 6, 0), None, 7, 0) is False
    # gestern gelaufen -> heute verpasst
    assert lauf_heute_verpasst(heute_9, datetime(2026, 9, 24, 12, 0), 7, 0) is True
    # heute schon gelaufen (20:00 UTC liegt in jeder Zeitzone zwischen UTC-12 und UTC+3 heute nach
    # 07:00 lokal) -> nicht verpasst
    assert lauf_heute_verpasst(heute_9.replace(hour=23), datetime(2026, 9, 25, 20, 0), 7, 0) is False


# --- KI-Nachprüfung -------------------------------------------------------------------------


@pytest.fixture
def ollama_modus():
    vorher = settings.kevin_anbieter
    settings.kevin_anbieter = "ollama"
    yield
    settings.kevin_anbieter = vorher


def _kandidat(db, portal, titel, score, kategorien=("KI & Machine Learning",), cpv=("72000000",)):
    t = Tender(portal_id=portal.id, titel=titel, direktlink="https://x.invalid/CXP4YLPMVFX", dedupe_hash=titel,
               ki_relevanz_score=score, ki_relevanz_quelle="keyword", cpv_codes=list(cpv))
    db.add(t)
    db.flush()
    for name in kategorien:
        k = db.query(Category).filter_by(name=name).first() or Category(name=name)
        db.add(k)
        db.flush()
        db.add(TenderCategory(tender_id=t.id, category_id=k.id))
    db.commit()
    return t


def test_nachpruefung_stuft_nebenbei_erwaehnt_herab(db, portal, ollama_modus, monkeypatch):
    projekt = _kandidat(db, portal, "Digitales Testfeld AI-THENA - RoRo-Fahrspurüberbrückung", "moeglich")
    echt = _kandidat(db, portal, "Beschaffung eines KI-Serversystems", "stark")
    antworten = {
        projekt.titel: {"einstufung": "nicht_relevant", "begruendung": "AI-THENA ist ein Projektname.", "konfidenz": 0.9},
        echt.titel: {"einstufung": "stark_relevant", "begruendung": "KI-Hardware ist Kern.", "konfidenz": 0.9},
    }
    monkeypatch.setattr(prompts, "call_llm_json", lambda system, user, lokal_erlaubt=False: next(
        v for k, v in antworten.items() if k in user))
    monkeypatch.setattr(ki_nachpruefung, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    ergebnis = ki_nachpruefung.fuehre_nachpruefung_aus()

    assert ergebnis == {"kandidaten": 2, "geprueft": 2, "herabgestuft": 1}
    db.refresh(projekt)
    db.refresh(echt)
    assert projekt.ki_relevanz_score == "nicht"
    assert projekt.ki_relevanz_quelle == "llm"
    assert "KI-Nachprüfung" in projekt.ki_relevanz_begruendung and "Projektname" in projekt.ki_relevanz_begruendung
    assert {tk.category.name for tk in projekt.kategorien} == {"Softwareentwicklung & IT-Dienstleistungen"}
    assert echt.ki_relevanz_score == "stark"
    assert ki_nachpruefung.zu_pruefen(db) == []  # jede Ausschreibung nur einmal


def test_nachpruefung_ohne_modell_aendert_nichts(db, portal, ollama_modus, monkeypatch):
    t = _kandidat(db, portal, "Chatbot für Bürgerservice", "stark")
    monkeypatch.setattr(prompts, "call_llm_json", lambda *a, **k: None)
    monkeypatch.setattr(ki_nachpruefung, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    assert ki_nachpruefung.fuehre_nachpruefung_aus()["geprueft"] == 0
    db.refresh(t)
    assert (t.ki_relevanz_score, t.ki_relevanz_quelle) == ("stark", "keyword")


def test_ohne_eingerichtetes_modell_gar_kein_lauf():
    assert settings.kevin_anbieter == "anthropic" and not settings.anthropic_api_key  # Testumgebung
    assert ki_nachpruefung.fuehre_nachpruefung_aus() == {"uebersprungen": "kein Sprachmodell eingerichtet"}


def test_lokales_modell_nur_wenn_ausdruecklich_erlaubt(ollama_modus, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(prompts, "_ollama_json", lambda s, u: aufrufe.append(u) or {"ok": True})
    assert prompts.call_llm_json("sys", "massenhaft") is None  # z. B. Kategorisierung: nie lokal
    assert prompts.call_llm_json("sys", "gezielt", lokal_erlaubt=True) == {"ok": True}
    assert aufrufe == ["gezielt"]


# --- Benachrichtigung bei neuen Treffern ----------------------------------------------------

from app import benachrichtigung  # noqa: E402
from app.models import SearchProfile, SearchProfileHit  # noqa: E402


def test_profiltreffer_werden_einmal_gemeldet_und_herabgestufte_entfernt(db, portal, monkeypatch):
    profil = SearchProfile(name="KI Berlin", keywords=["ki"], filter_json={"ki_relevanz_min": "stark"})
    db.add(profil)
    db.commit()
    passt = _kandidat(db, portal, "KI-Plattform für Verwaltung", "stark")
    herabgestuft = _kandidat(db, portal, "KI-Beratung light", "nicht")
    db.add_all([SearchProfileHit(profile_id=profil.id, tender_id=passt.id),
                SearchProfileHit(profile_id=profil.id, tender_id=herabgestuft.id)])
    db.commit()
    gemeldet = []
    monkeypatch.setattr(benachrichtigung, "_mac_mitteilung", lambda m: gemeldet.append(m) or True)

    (meldung,) = benachrichtigung.benachrichtige(db)
    assert meldung.titel == "1 neue Treffer: KI Berlin"
    assert meldung.text == "KI-Plattform für Verwaltung"
    assert db.get(SearchProfileHit, (profil.id, herabgestuft.id)) is None
    assert benachrichtigung.benachrichtige(db) == []  # nur einmal
    assert len(gemeldet) == 1


def test_ohne_suchprofil_neue_starke_ki_ausschreibungen(db, portal, monkeypatch):
    _kandidat(db, portal, "Chatbot für Bürgerservice", "stark")
    _kandidat(db, portal, "CMS-Webseite", "moeglich")
    monkeypatch.setattr(benachrichtigung, "_mac_mitteilung", lambda m: True)
    (meldung,) = benachrichtigung.benachrichtige(db)
    assert meldung.titel == "1 neue KI-Ausschreibungen"
    assert benachrichtigung.benachrichtige(db) == []


def test_mac_mitteilung_nur_unter_macos(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(benachrichtigung.subprocess, "run", lambda *a, **k: aufrufe.append(a[0]))
    monkeypatch.setattr(benachrichtigung.shutil, "which", lambda n: "/usr/bin/osascript")
    m = benachrichtigung.Meldung(titel='2 neue "Treffer"', text="A\nB", anzahl=2)
    monkeypatch.setattr(benachrichtigung.sys, "platform", "linux")
    assert benachrichtigung._mac_mitteilung(m) is False
    monkeypatch.setattr(benachrichtigung.sys, "platform", "darwin")
    assert benachrichtigung._mac_mitteilung(m) is True
    skript = aufrufe[0][2]
    assert 'subtitle "2 neue \\"Treffer\\""' in skript and "A · B" in skript


# --- Go/No-Go-Bewertung ---------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.agents import bewertung  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AssistantPreferences, Verbesserungswunsch  # noqa: E402

client = TestClient(app)


def test_bewertung_wird_normalisiert_gespeichert_und_im_detail_geliefert(db, portal, ollama_modus, monkeypatch):
    t = _kandidat(db, portal, "Chatbot für Bürgerservice", "stark")
    db.add(AssistantPreferences(firmenprofil="KI-Agentur, 12 Leute, ISO 27001"))
    db.commit()
    gesehen = {}

    def llm(system, user, lokal_erlaubt=False):
        gesehen["user"] = user
        return {"empfehlung": "bewerben", "passwert": "140", "zusammenfassung": "Chatbot.",
                "begruendung": "Passt.", "pflichtnachweise": ["Zwei Referenzen vergleichbarer Projekte", "",
                                                              "Nachweis Tariftreue Bundesland"],
                "risiken": "knappe Frist", "passende_referenzen": ["Chatbot Stadt X", "Erfunden"]}

    monkeypatch.setattr(bewertung.prompts, "call_llm_json", llm)
    monkeypatch.setattr(bewertung, "_verfahrensseite_text",
                        lambda url: "Zuschlagskriterien: Preis 40 %. Geforderte Nachweise: zwei Referenzen vergleichbarer Projekte.")
    from app.models import Referenz

    db.add(Referenz(titel="Chatbot Stadt X", jahr=2025))
    db.commit()

    antwort = client.post(f"/api/tenders/{t.id}/bewertung")
    assert antwort.status_code == 200, antwort.text
    b = antwort.json()
    assert b["empfehlung"] == "bewerben" and b["passwert"] == 100  # auf 0-100 begrenzt
    # Prüfer: belegter Punkt bleibt, erfundener ("Tariftreue") fliegt raus
    assert b["pflichtnachweise"] == ["Zwei Referenzen vergleichbarer Projekte"] and b["entfernt_ohne_beleg"] == 1
    assert b["risiken"] == ["knappe Frist"]
    assert b["passende_referenzen"] == ["Chatbot Stadt X"]  # nur existierende Referenzen
    detail = client.get(f"/api/tenders/{t.id}").json()
    assert [p["text"] for p in detail["checkliste"]] == ["Zwei Referenzen vergleichbarer Projekte"]  # automatisch
    assert b["quellen"] == ["Bekanntmachung", "Verfahrensseite"]
    assert b["firmenprofil_fehlte"] is False
    assert "ISO 27001" in gesehen["user"] and "Preis 40 %" in gesehen["user"] and "Chatbot Stadt X" in gesehen["user"]
    assert client.get(f"/api/tenders/{t.id}").json()["bewertung"]["empfehlung"] == "bewerben"


def test_bewertung_ohne_modell_klare_fehlermeldung(db, portal):
    t = _kandidat(db, portal, "Chatbot", "stark")
    antwort = client.post(f"/api/tenders/{t.id}/bewertung")
    assert antwort.status_code == 503 and "Sprachmodell" in antwort.json()["detail"]


# --- Kevins Wunschliste ---------------------------------------------------------------------

from app.agents.assistant import execute_assistant_action  # noqa: E402


def test_wunsch_notieren_auflisten_erledigen_loeschen(db):
    ergebnis = execute_assistant_action(db, "verbesserungswunsch_notieren",
                                        {"titel": "Portal NRW ergänzen", "beschreibung": "evergabe.nrw.de anbinden."})
    assert ergebnis.erfolg
    (wunsch,) = client.get("/api/wuensche").json()
    assert wunsch["titel"] == "Portal NRW ergänzen" and wunsch["status"] == "offen"
    assert client.patch(f"/api/wuensche/{wunsch['id']}", json={"status": "erledigt"}).json()["status"] == "erledigt"
    assert client.delete(f"/api/wuensche/{wunsch['id']}").status_code == 204
    assert db.query(Verbesserungswunsch).count() == 0
    assert not execute_assistant_action(db, "verbesserungswunsch_notieren", {"titel": "x"}).erfolg


# --- Suche nach Bedeutung -------------------------------------------------------------------

from app import semantik  # noqa: E402
from app.tender_queries import search_tenders  # noqa: E402

_VEKTOREN = {
    "Wissensmanagement mittels Sprachmodell": [1.0, 0.0],
    "Streusalzsilos für den Winterdienst": [0.0, 1.0],
    "KI-Plattform": [0.9, 0.1],
    "künstliche intelligenz": [1.0, 0.05],
}


def _fake_einbetten(texte, timeout=300.0):
    return [_VEKTOREN[next(k for k in _VEKTOREN if k.lower() in t.lower())] for t in texte]


@pytest.fixture
def semantik_an(monkeypatch):
    monkeypatch.setattr(settings, "semantik_aktiv", True)


def test_bedeutungssuche_ist_standardmaessig_aus(db, portal, monkeypatch):
    monkeypatch.setattr(semantik, "einbetten", _fake_einbetten)
    _kandidat(db, portal, "KI-Plattform", "stark")
    assert settings.semantik_aktiv is False
    assert semantik.aktualisiere_embeddings(db) == 0
    assert semantik.aehnlichkeiten(db, "künstliche intelligenz") is None


def test_bedeutungssuche_findet_umschreibungen_und_sortiert(db, portal, monkeypatch, semantik_an):
    monkeypatch.setattr(semantik, "einbetten", _fake_einbetten)
    for titel in ("Wissensmanagement mittels Sprachmodell", "Streusalzsilos für den Winterdienst", "KI-Plattform"):
        _kandidat(db, portal, titel, "nicht")
    assert semantik.aktualisiere_embeddings(db) == 3
    assert semantik.aktualisiere_embeddings(db) == 0  # nur einmal je Ausschreibung

    stichwort, _ = search_tenders(db, q="künstliche intelligenz")
    bedeutung, anzahl = search_tenders(db, q="künstliche intelligenz", bedeutung=True)
    assert stichwort == []
    assert [t.titel for t in bedeutung] == ["Wissensmanagement mittels Sprachmodell", "KI-Plattform"]
    assert anzahl == 2


def test_bedeutungssuche_ohne_modell_faellt_auf_stichworte_zurueck(db, portal, monkeypatch, semantik_an):
    monkeypatch.setattr(semantik, "einbetten", lambda texte, timeout=300.0: None)
    _kandidat(db, portal, "KI-Plattform", "stark")
    treffer, _ = search_tenders(db, q="ki-plattform", bedeutung=True)
    assert [t.titel for t in treffer] == ["KI-Plattform"]


def test_sortierung_nach_ki_relevanz(db, portal):
    _kandidat(db, portal, "Allgemeine IT", "nicht")
    _kandidat(db, portal, "Chatbot", "stark")
    _kandidat(db, portal, "Datenplattform", "moeglich")
    antwort = client.get("/api/tenders", params={"sort": "ki_relevanz"})
    assert antwort.status_code == 200
    assert [t["titel"] for t in antwort.json()["items"]] == ["Chatbot", "Datenplattform", "Allgemeine IT"]
