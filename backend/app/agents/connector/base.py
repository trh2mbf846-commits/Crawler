"""Connector-Basisklasse (Kapitel 18, Connector-Agent).

Ein Connector kennt ausschliesslich die Technik eines einzelnen Portals (HTTP-Abruf bzw.
Headless-Browser, Pagination, Cookie-/Session-Handling) - keine Fachlogik. Die fachliche
Frage "was ist neu/veraendert" beantwortet bewusst getrennt der Discovery-Agent (Kapitel 18,
"Wichtig"-Hinweis am Ende der Tabelle).

WICHTIG (Stand dieser Implementierung): Diese Session-Umgebung hat keinen ausgehenden
Internetzugriff (Egress-Proxy blockiert alle externen Domains, siehe Chat-Rueckfrage vom
31.08.2026). Die konkreten CSS-Selektoren/URLs unten sind daher NICHT gegen die echten Seiten
verifiziert und mit "# TODO(portal-analyse)" markiert. robots_status bleibt bewusst auf
"ungeprueft" (Kapitel 9.3), bis eine echte Pruefung stattgefunden hat. Sobald Netzzugriff
verfuegbar ist: robots.txt/ToS pruefen, echte Struktur analysieren, TODOs abarbeiten, dann
robots_status aktualisieren.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.config import settings
from app.exceptions import AccessBlocked, TechnicalFailure

# Heuristische Erkennung echter Zugriffsschranken (Kapitel 9.2) in abgerufenem HTML/Text.
# Bewusst konservativ: lieber einmal zu viel eskalieren als eine Schranke technisch umgehen.
_LOGIN_MARKERS = [
    "bitte melden sie sich an", "bitte loggen sie sich ein", "login erforderlich",
    "bieteranmeldung", "bieterkonto erforderlich", "zugang nur für registrierte",
    "sign in to continue", "please log in",
]
_CAPTCHA_MARKERS = ["captcha", "recaptcha", "hcaptcha", "bot-schutz", "bitte bestätigen sie, dass sie kein roboter"]
_BLOCK_MARKERS = ["access denied", "zugriff verweigert", "429 too many requests", "temporarily blocked", "ihre anfragen wurden vorübergehend blockiert"]


def detect_access_block(html_or_text: str, http_status: int | None = None) -> AccessBlocked | None:
    text = (html_or_text or "").lower()
    if any(m in text for m in _CAPTCHA_MARKERS):
        return AccessBlocked(
            "captcha", "CAPTCHA/Bot-Schutz erkannt.",
            ["Automatisierten Abruf für dieses Portal pausieren", "Alternative Quelle prüfen (RSS/Newsletter/API)"],
            empfehlung=None,
        )
    if any(m in text for m in _LOGIN_MARKERS):
        return AccessBlocked(
            "login_erforderlich", "Inhalt scheint ein echtes Bieterkonto/Login vorauszusetzen.",
            ["Nur öffentlich sichtbare Metadaten erfassen, für Details auf Originallink verweisen",
             "Eigenes Bieterkonto bereitstellen lassen"],
            empfehlung="Nur öffentliche Metadaten erfassen, Originallink verlinken",
        )
    if http_status in (401, 403) or any(m in text for m in _BLOCK_MARKERS):
        return AccessBlocked(
            "ip_sperre", f"Zugriff blockiert (HTTP {http_status}) oder Sperr-Hinweis im Inhalt gefunden.",
            ["Abrufrate weiter reduzieren und später erneut versuchen", "Portal vorübergehend pausieren"],
            empfehlung="Abrufrate reduzieren und erneut versuchen; bei Wiederholung pausieren",
        )
    return None


@dataclass
class RawCandidate:
    externe_id: str
    detail_url: str
    titel_hint: str | None = None
    listen_metadaten: dict = field(default_factory=dict)


@dataclass
class RawDetail:
    externe_id: str
    detail_url: str
    felder: dict  # portalspezifische Rohfelder, vom Normalization-Agent abzubilden
    abgerufen_am: datetime = field(default_factory=datetime.utcnow)


class BaseConnector(ABC):
    slug: str
    name: str
    base_url: str
    vorgegeben: bool = True
    robots_status: str = "ungeprueft"
    tos_hinweis: str = "Noch nicht geprüft - kein Netzzugriff in dieser Entwicklungsumgebung (Stand siehe Docstring)."
    # Deckelt die Anzahl der Listenseiten pro Zyklus (Kapitel 9.1: höflicher, begrenzter Abruf
    # statt vollständiger Historie bei sehr großen Portalen) - einzelne Connectoren mit hohem
    # Trefferaufkommen überschreiben diesen Wert.
    max_pages: int = 50

    def __init__(self) -> None:
        self._client: httpx.Client | None = None
        self._last_request_at: float = 0.0

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                headers={"User-Agent": settings.http_user_agent},
                follow_redirects=True,
                timeout=30.0,
            )
        return self._client

    def _respect_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = settings.http_request_delay_seconds - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_at = time.monotonic()

    def polite_get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        """GET mit Rate-Limiting (Kapitel 9.1) und Zugriffsschranken-Erkennung (Kapitel 9.2)."""
        self._respect_rate_limit()
        try:
            response = self.client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise TechnicalFailure(f"HTTP-Fehler beim Abruf von {url}: {exc}") from exc

        block = detect_access_block(response.text, response.status_code)
        if block is not None:
            raise block
        if response.status_code >= 500:
            raise TechnicalFailure(f"Serverfehler {response.status_code} bei {url}")
        if response.status_code >= 400:
            raise TechnicalFailure(f"HTTP {response.status_code} bei {url}")
        return response

    @abstractmethod
    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        """Liefert Kandidaten einer Ergebnisseite + ob eine weitere Seite existiert (Pagination, Kapitel 9.1)."""

    @abstractmethod
    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        """Ruft die Detailseite ab und extrahiert die portalspezifischen Rohfelder (reines Parsing)."""

    def iter_all_candidates(self, max_pages: int | None = None) -> list[RawCandidate]:
        limit = max_pages if max_pages is not None else self.max_pages
        candidates: list[RawCandidate] = []
        page = 1
        while page <= limit:
            page_candidates, has_more = self.fetch_list_page(page)
            candidates.extend(page_candidates)
            if not has_more:
                break
            page += 1
        return candidates

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
