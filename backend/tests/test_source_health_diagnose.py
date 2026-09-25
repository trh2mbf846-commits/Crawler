"""Tests für die automatische Erstdiagnose bei Eskalationen (app/agents/source_health.py,

Nutzerrecherche 25.09.2026: "LLM als Reparaturtechniker, nur im Fehlerfall"). Bewusste
Sicherheitsgrenze: die Diagnose liefert nur eine Empfehlung für die Eskalation, sie greift nie
in Connector-Code ein.
"""
from __future__ import annotations

from app.agents import source_health
from app.config import settings
from app.models import Escalation


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text


def _drei_null_treffer_laeufe(db, portal) -> None:
    for _ in range(3):
        source_health.record_run(db, portal, erfolgreich=True, treffer_anzahl=0)


def test_eskalation_ohne_api_key_hat_keine_automatische_diagnose(db, portal):
    assert settings.anthropic_api_key is None  # Testumgebung setzt bewusst keinen Schlüssel

    _drei_null_treffer_laeufe(db, portal)
    source_health.evaluate(db, portal)

    eskalation = db.query(Escalation).filter(Escalation.portal_id == portal.id).first()
    assert eskalation is not None
    assert eskalation.empfehlung is None


def test_diagnose_portal_problem_ohne_api_key_liefert_none(db, portal):
    assert source_health._diagnose_portal_problem(portal, "Testkontext") is None


def test_diagnose_portal_problem_mit_api_key_ruft_llm_auf(db, portal, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(source_health.httpx, "get", lambda *a, **k: _FakeResponse("<html>Bitte melden Sie sich an</html>"))
    monkeypatch.setattr(
        source_health, "call_llm_json",
        lambda system, user: {"vermutete_ursache": "login_erforderlich", "rueckfrage_noetig": True, "kurzbegruendung": "Seite verlangt Login."},
    )

    diagnose = source_health._diagnose_portal_problem(portal, "Testkontext")

    assert diagnose["vermutete_ursache"] == "login_erforderlich"


def test_diagnose_portal_problem_bei_verbindungsfehler_liefert_none(db, portal, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def _raise(*args, **kwargs):
        import httpx

        raise httpx.ConnectError("nicht erreichbar")

    monkeypatch.setattr(source_health.httpx, "get", _raise)

    assert source_health._diagnose_portal_problem(portal, "Testkontext") is None


def test_eskalation_mit_diagnose_setzt_empfehlung(db, portal, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(source_health.httpx, "get", lambda *a, **k: _FakeResponse("<html>captcha</html>"))
    monkeypatch.setattr(
        source_health, "call_llm_json",
        lambda system, user: {"vermutete_ursache": "CAPTCHA erkannt", "rueckfrage_noetig": True, "kurzbegruendung": "Bot-Schutz aktiv."},
    )

    _drei_null_treffer_laeufe(db, portal)
    source_health.evaluate(db, portal)

    eskalation = db.query(Escalation).filter(Escalation.portal_id == portal.id).first()
    assert eskalation is not None
    assert eskalation.empfehlung is not None
    assert "CAPTCHA erkannt" in eskalation.empfehlung
    assert "Bot-Schutz aktiv." in eskalation.empfehlung
    assert eskalation.empfehlung.startswith("[Automatische Ersteinschätzung")
