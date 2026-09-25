"""Crawler Kevin mit lokalem Sprachmodell über Ollama (Nutzerwunsch 25.09.2026: kostenlos).

Ollama wird nie echt angesprochen, sondern per httpx.MockTransport simuliert - geprüft wird,
dass Werkzeuge, Bestätigungspflicht und Fehlerhinweise genauso funktionieren wie mit Claude.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.agents.assistant import (
    _OLLAMA_MODELL_FEHLT_HINWEIS,
    _OLLAMA_NICHT_GESTARTET_HINWEIS,
    _ZU_KOMPLEX_HINWEIS,
    kevin_anbieter,
    run_assistant_chat,
)
from app.config import settings
from tests.test_assistant import _angelegte_ausschreibung


@pytest.fixture(autouse=True)
def _ollama_modus():
    vorher = (settings.kevin_anbieter, settings.anthropic_api_key)
    settings.kevin_anbieter = "ollama"
    yield
    settings.kevin_anbieter, settings.anthropic_api_key = vorher


def _mock_ollama(antworten: list[dict], anfragen: list[dict] | None = None, status: int = 200):
    """Liefert der Reihe nach die übergebenen assistant-Nachrichten, protokolliert die Anfragen."""
    rest = list(antworten)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if anfragen is not None:
            anfragen.append(body)
        if status != 200:
            return httpx.Response(status, json={"error": f"model '{body['model']}' not found"})
        return httpx.Response(200, json={"message": rest.pop(0)})

    return httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))


def _tool_call(name: str, arguments) -> dict:
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def test_auto_waehlt_ollama_ohne_und_claude_mit_api_key():
    settings.kevin_anbieter = "auto"
    settings.anthropic_api_key = None
    assert kevin_anbieter() == "ollama"
    settings.anthropic_api_key = "sk-ant-test"
    assert kevin_anbieter() == "anthropic"


def test_ollama_nutzt_werkzeug_und_antwortet(db, portal):
    tender_id = _angelegte_ausschreibung(db, portal, titel="KI-Plattform für Verwaltung")
    anfragen: list[dict] = []
    http = _mock_ollama(
        [
            _tool_call("suche_ausschreibungen", {"q": "KI"}),
            {"role": "assistant", "content": "<think>kurz überlegen</think>Es gibt eine passende Ausschreibung."},
        ],
        anfragen,
    )

    ergebnis = run_assistant_chat(db, "Gibt es KI-Ausschreibungen?", ollama_http=http)

    assert ergebnis.antwort == "Es gibt eine passende Ausschreibung."  # Denk-Block entfernt
    assert [t.id for t in ergebnis.tenders] == [tender_id]
    assert ergebnis.verfuegbar is True
    erste, zweite = anfragen
    assert erste["model"] == settings.ollama_model
    assert erste["messages"][0]["role"] == "system"
    assert {t["function"]["name"] for t in erste["tools"]} >= {"suche_ausschreibungen", "ausschreibung_merken"}
    werkzeug_ergebnis = zweite["messages"][-1]
    assert werkzeug_ergebnis["role"] == "tool"
    assert werkzeug_ergebnis["tool_name"] == "suche_ausschreibungen"
    assert "KI-Plattform für Verwaltung" in werkzeug_ergebnis["content"]


def test_ollama_argumente_als_json_string_werden_verstanden(db, portal):
    http = _mock_ollama([
        _tool_call("quellstatus", "{}"),
        {"role": "assistant", "content": "Alle Portale laufen."},
    ])
    assert run_assistant_chat(db, "Status?", ollama_http=http).antwort == "Alle Portale laufen."


def test_ollama_schreibendes_werkzeug_wird_nur_vorgeschlagen(db, portal):
    http = _mock_ollama([_tool_call("aktualisieren_starten", {"portal_slug": portal.slug})])

    ergebnis = run_assistant_chat(db, "Aktualisiere bitte", ollama_http=http)

    assert ergebnis.vorschlag is not None
    assert ergebnis.vorschlag.name == "aktualisieren_starten"
    assert ergebnis.vorschlag.input == {"portal_slug": portal.slug}
    assert portal.name in ergebnis.vorschlag.beschreibung


def test_ollama_endlosschleife_wird_abgebrochen(db):
    http = _mock_ollama([_tool_call("quellstatus", {})] * 10)
    assert run_assistant_chat(db, "Frage", ollama_http=http).antwort == _ZU_KOMPLEX_HINWEIS


def test_ollama_nicht_gestartet_liefert_hinweis(db):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    http = httpx.Client(base_url="http://ollama.test", transport=httpx.MockTransport(handler))
    ergebnis = run_assistant_chat(db, "Frage", ollama_http=http)
    assert ergebnis.antwort == _OLLAMA_NICHT_GESTARTET_HINWEIS
    assert ergebnis.verfuegbar is True  # konfiguriert, nur gerade nicht erreichbar


def test_ollama_modell_fehlt_liefert_hinweis_mit_befehl(db):
    http = _mock_ollama([], status=404)
    ergebnis = run_assistant_chat(db, "Frage", ollama_http=http)
    assert ergebnis.antwort == _OLLAMA_MODELL_FEHLT_HINWEIS.format(modell=settings.ollama_model)
    assert f"ollama pull {settings.ollama_model}" in ergebnis.antwort


def test_systemprompt_enthaelt_heutiges_datum(db):
    from datetime import date

    from app.agents.assistant import _build_system_prompt

    assert date.today().isoformat() in _build_system_prompt(db)


def test_ollama_erfundene_tender_id_wird_nicht_vorgeschlagen_sondern_zurueckgemeldet(db, portal):
    anfragen: list[dict] = []
    http = _mock_ollama(
        [
            _tool_call("ausschreibung_merken", {"tender_id": "erfunden-1"}),
            {"role": "assistant", "content": "Ich habe dazu keine passende Ausschreibung gefunden."},
        ],
        anfragen,
    )

    ergebnis = run_assistant_chat(db, "Merk dir die erste KI-Ausschreibung", ollama_http=http)

    assert ergebnis.vorschlag is None
    rueckmeldung = anfragen[1]["messages"][-1]
    assert rueckmeldung["role"] == "tool"
    assert "Unbekannte tender_id" in rueckmeldung["content"]


def test_ungefaehrer_kategoriename_wird_zugeordnet(db, portal):
    from app.agents.assistant import _ordne_kategorien_zu
    from app.models import Category

    db.add_all([Category(name="KI & Machine Learning"), Category(name="Cybersecurity")])
    db.commit()

    assert _ordne_kategorien_zu(db, ["KI"]) == (["KI & Machine Learning"], [])
    assert _ordne_kategorien_zu(db, ["cybersecurity"]) == (["Cybersecurity"], [])
    assert _ordne_kategorien_zu(db, ["Quantencomputing"]) == (None, ["Quantencomputing"])
    assert _ordne_kategorien_zu(db, None) == (None, [])


def test_ollama_antwort_ohne_werkzeug_wird_einmal_hinterfragt(db):
    anfragen: list[dict] = []
    http = _mock_ollama(
        [
            {"role": "assistant", "content": "Die wichtigste Ausschreibung ist frei erfunden."},
            _tool_call("suche_ausschreibungen", {"q": "KI"}),
            {"role": "assistant", "content": "Ich habe keine passenden Ausschreibungen gefunden."},
        ],
        anfragen,
    )

    ergebnis = run_assistant_chat(db, "Was ist die wichtigste KI-Ausschreibung?", ollama_http=http)

    assert ergebnis.antwort == "Ich habe keine passenden Ausschreibungen gefunden."
    assert "noch kein Werkzeug benutzt" in anfragen[1]["messages"][-1]["content"]


def test_ollama_begruessung_kommt_nach_einmaligem_nachhaken_durch(db):
    http = _mock_ollama([
        {"role": "assistant", "content": "Hallo!"},
        {"role": "assistant", "content": "Hallo! Wie kann ich helfen?"},
    ])
    assert run_assistant_chat(db, "Hallo", ollama_http=http).antwort == "Hallo! Wie kann ich helfen?"
