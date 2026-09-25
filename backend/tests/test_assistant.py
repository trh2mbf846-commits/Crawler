from app import queue
from app.agents.assistant import (
    MAX_TOOL_ITERATIONEN,
    _NICHT_ERREICHBAR_HINWEIS,
    _NICHT_KONFIGURIERT_HINWEIS,
    _ZU_KOMPLEX_HINWEIS,
    _tool_quellstatus,
    _tool_suche_ausschreibungen,
    execute_assistant_action,
    run_assistant_chat,
)
from app.agents.assistant import _build_system_prompt
from app.agents.duplicate import run_duplicate
from app.models import AssistantPreferences, SearchProfile, Tender


class FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeToolUseBlock:
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id = id
        self.name = name
        self.input = input


class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class FakeMessagesSequence:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, **kwargs):
        return self._responses.pop(0)


class FakeClientSequence:
    def __init__(self, responses):
        self.messages = FakeMessagesSequence(responses)


class FakeMessagesAlwaysToolUse:
    def create(self, **kwargs):
        return FakeResponse("tool_use", [FakeToolUseBlock("t1", "quellstatus", {})])


class FakeClientAlwaysToolUse:
    def __init__(self):
        self.messages = FakeMessagesAlwaysToolUse()


class FakeMessagesRaising:
    def create(self, **kwargs):
        raise RuntimeError("API nicht erreichbar (simuliert)")


class FakeClientRaising:
    def __init__(self):
        self.messages = FakeMessagesRaising()


def _angelegte_ausschreibung(db, portal, **overrides):
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
    job = queue.enqueue(db, "duplicate", portal_id=portal.id, payload={"normalized": base})
    ergebnis = run_duplicate(db, job)
    return ergebnis["tender_id"]


def test_ohne_api_key_liefert_hinweis_statt_fehler(db):
    ergebnis = run_assistant_chat(db, "Was gibt es Neues?")

    assert ergebnis.antwort == _NICHT_KONFIGURIERT_HINWEIS
    assert ergebnis.tenders == []


def test_tool_suche_ausschreibungen_findet_treffer(db, portal):
    _angelegte_ausschreibung(db, portal)

    ergebnis = _tool_suche_ausschreibungen(db, {"q": "KI-Beratung"}, {})

    assert ergebnis["gesamttreffer"] == 1
    assert ergebnis["treffer"][0]["titel"] == "KI-Beratung für die Verwaltung"
    assert ergebnis["treffer"][0]["portal"] == portal.name


def test_tool_quellstatus_listet_portale(db, portal):
    ergebnis = _tool_quellstatus(db)

    namen = [p["name"] for p in ergebnis["portale"]]
    assert portal.name in namen


def test_run_assistant_chat_nutzt_werkzeug_und_antwortet(db, portal):
    tender_id = _angelegte_ausschreibung(db, portal)

    fake_client = FakeClientSequence([
        FakeResponse("tool_use", [FakeToolUseBlock("t1", "suche_ausschreibungen", {"q": "KI-Beratung"})]),
        FakeResponse("end_turn", [FakeTextBlock("Es gibt eine passende Ausschreibung: KI-Beratung für die Verwaltung.")]),
    ])

    ergebnis = run_assistant_chat(db, "Gibt es KI-Ausschreibungen?", client=fake_client)

    assert "KI-Beratung" in ergebnis.antwort
    assert [t.id for t in ergebnis.tenders] == [tender_id]


def test_run_assistant_chat_bricht_bei_endlosschleife_ab(db):
    ergebnis = run_assistant_chat(db, "Frage", client=FakeClientAlwaysToolUse())

    assert ergebnis.antwort == _ZU_KOMPLEX_HINWEIS


def test_run_assistant_chat_faengt_api_fehler_ab(db):
    ergebnis = run_assistant_chat(db, "Frage", client=FakeClientRaising())

    assert ergebnis.antwort == _NICHT_ERREICHBAR_HINWEIS


def test_max_tool_iterationen_ist_begrenzt():
    assert 1 <= MAX_TOOL_ITERATIONEN <= 10


def test_schreibendes_werkzeug_wird_nur_vorgeschlagen_nicht_ausgefuehrt(db, portal):
    fake_client = FakeClientSequence([
        FakeResponse("tool_use", [FakeToolUseBlock("t1", "aktualisieren_starten", {"portal_slug": portal.slug})]),
    ])

    ergebnis = run_assistant_chat(db, "Aktualisiere bitte das Testportal", client=fake_client)

    assert ergebnis.vorschlag is not None
    assert ergebnis.vorschlag.name == "aktualisieren_starten"
    assert portal.name in ergebnis.vorschlag.beschreibung
    # Kein zweiter API-Aufruf nötig gewesen (FakeMessagesSequence hätte sonst IndexError geworfen) -
    # die Schleife ist also wirklich nach dem Vorschlag abgebrochen, nicht in eine zweite Runde gegangen.


def test_execute_aktualisieren_starten_lehnt_unbekanntes_portal_ab(db):
    ergebnis = execute_assistant_action(db, "aktualisieren_starten", {"portal_slug": "nicht-vorhanden"})

    assert ergebnis.erfolg is False
    assert "nicht gefunden" in ergebnis.meldung


def test_execute_suchprofil_anlegen_legt_profil_an(db, portal):
    ergebnis = execute_assistant_action(
        db, "suchprofil_anlegen",
        {"name": "KI in Bayern", "keywords": ["Künstliche Intelligenz"], "portal_slugs": [portal.slug]},
    )

    assert ergebnis.erfolg is True
    profile = db.query(SearchProfile).filter(SearchProfile.name == "KI in Bayern").first()
    assert profile is not None
    assert profile.portale == [portal.id]
    assert profile.keywords == ["Künstliche Intelligenz"]


def test_execute_suchprofil_anlegen_ohne_namen_schlaegt_fehl(db):
    ergebnis = execute_assistant_action(db, "suchprofil_anlegen", {"name": ""})

    assert ergebnis.erfolg is False
    assert db.query(SearchProfile).count() == 0


def test_execute_ausschreibung_merken_setzt_flag_und_notiz(db, portal):
    tender_id = _angelegte_ausschreibung(db, portal)

    ergebnis = execute_assistant_action(db, "ausschreibung_merken", {"tender_id": tender_id, "notiz": "Für Q4 vormerken"})

    assert ergebnis.erfolg is True
    tender = db.get(Tender, tender_id)
    assert tender.gemerkt is True
    assert tender.merk_notiz == "Für Q4 vormerken"


def test_execute_ausschreibung_merken_unbekannte_id_schlaegt_fehl(db):
    ergebnis = execute_assistant_action(db, "ausschreibung_merken", {"tender_id": "existiert-nicht"})

    assert ergebnis.erfolg is False


def test_execute_unbekannte_aktion_schlaegt_fehl(db):
    ergebnis = execute_assistant_action(db, "loesche_alles", {})

    assert ergebnis.erfolg is False


def test_systemprompt_ohne_praeferenzen_zeigt_hinweis(db):
    prompt = _build_system_prompt(db)

    assert "noch keine hinterlegt" in prompt


def test_systemprompt_enthaelt_gesetzte_praeferenzen(db):
    db.add(AssistantPreferences(
        id="singleton", prioritaeten_text="Fokus auf KI in Bayern",
        bevorzugte_kategorien=["KI & Machine Learning"], mindestwert=50000.0,
    ))
    db.commit()

    prompt = _build_system_prompt(db)

    assert "Fokus auf KI in Bayern" in prompt
    assert "KI & Machine Learning" in prompt
    assert "50.000" in prompt or "50,000" in prompt
