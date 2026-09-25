from app import queue
from app.agents.assistant import (
    MAX_TOOL_ITERATIONEN,
    _NICHT_ERREICHBAR_HINWEIS,
    _NICHT_KONFIGURIERT_HINWEIS,
    _ZU_KOMPLEX_HINWEIS,
    _tool_quellstatus,
    _tool_suche_ausschreibungen,
    run_assistant_chat,
)
from app.agents.duplicate import run_duplicate


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
