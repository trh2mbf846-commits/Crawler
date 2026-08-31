"""Fehlerklassen der Agentenkette (Kapitel 9, 18)."""
from __future__ import annotations


class TechnicalFailure(Exception):
    """Rein technischer Fehlschlag (HTTP-Fehler, Timeout, Parsing-Fehler) -> Auto-Retry (Kapitel 9.1, 17.4)."""


class AccessBlocked(Exception):
    """Echte Zugriffsschranke im Sinne von Abschnitt 9.2 - wird NICHT umgangen, sondern eskaliert.

    kategorie: login_erforderlich | captcha | tos_verbot | ip_sperre | kategorisierung_unklar | sonstiges
    """

    def __init__(self, kategorie: str, kontext: str, optionen: list[str], empfehlung: str | None = None):
        super().__init__(kontext)
        self.kategorie = kategorie
        self.kontext = kontext
        self.optionen = optionen
        self.empfehlung = empfehlung
