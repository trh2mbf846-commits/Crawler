"""Connector: Vergabeplattform Berlin / Vergabekooperation Berlin (u. a. für die BVG).

Kapitel 3: "Servlet-basiert, Cookie-/Session-Handling erforderlich." Die vom Auftraggeber
genannte URL enthält bereits einen Hinweis auf einen Cookie-Consent-Schritt
("LoginControllerServlet?function=CookiesCheckDone") - typisch für Vergabemanagement-Systeme,
bei denen die ÖFFENTLICHE Bekanntmachungsliste ohne Bieterkonto einsehbar ist, aber ein
Cookie-Consent-Redirect vorgeschaltet ist. Diese Annahme ist NICHT verifiziert (kein
Netzzugriff, siehe base.py-Docstring).

Falls sich beim ersten echten Testlauf zeigt, dass hinter diesem Schritt tatsächlich ein
Bieterkonto-Login liegt (nicht nur ein Cookie-Consent), ist das gemäß Abschnitt 9.2 eine echte
Zugriffsschranke -> AccessBlocked/Eskalation, kein Umgehungsversuch.
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import AccessBlocked, TechnicalFailure

BASE_URL = "https://vergabekooperation.berlin/"
# Cookie-Consent-Einstieg lt. Auftraggeber-Vorgabe (Kapitel 3). NetServer-Systeme (z. B.
# AI Vergabemanager / cosinex) bieten meist eine öffentliche Bekanntmachungssuche unter
# einem Pfad wie NetServer/PublicationSearchControllerServlet - TODO(portal-analyse): echten
# Pfad der öffentlichen Bekanntmachungsliste ermitteln.
ENTRY_URL = "https://vergabekooperation.berlin/NetServer/LoginControllerServlet?function=CookiesCheckDone"
LIST_URL_CANDIDATES = [
    "https://vergabekooperation.berlin/NetServer/PublicationSearchControllerServlet",
]

LIST_ITEM_SELECTOR = "table.ergebnisliste tr, .bekanntmachung-item"
LIST_TITLE_SELECTOR = "a"


class VergabekooperationBerlinConnector(BaseConnector):
    slug = "vergabekooperation-berlin"
    name = "Vergabeplattform Berlin (Vergabekooperation Berlin)"
    base_url = BASE_URL
    vorgegeben = True

    def _ensure_session(self) -> None:
        # Cookie-Consent-Schritt einmalig durchlaufen; danach hält httpx.Client die Session-Cookies.
        self.polite_get(ENTRY_URL)

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        if page == 1:
            self._ensure_session()

        list_url = None
        last_error: Exception | None = None
        for candidate_url in LIST_URL_CANDIDATES:
            try:
                url = candidate_url if page == 1 else f"{candidate_url}&page={page}"
                response = self.polite_get(url)
                list_url = url
                break
            except (TechnicalFailure, AccessBlocked) as exc:
                last_error = exc
                continue

        if list_url is None:
            raise TechnicalFailure(
                "Vergabeplattform Berlin: keine der bekannten Listen-URLs erreichbar - "
                f"echter Pfad der öffentlichen Bekanntmachungsliste muss noch ermittelt werden ({last_error})."
            )

        soup = BeautifulSoup(response.text, "lxml")
        items = soup.select(LIST_ITEM_SELECTOR)
        candidates: list[RawCandidate] = []
        for item in items:
            link = item.select_one(LIST_TITLE_SELECTOR)
            if link is None or not link.get("href"):
                continue
            detail_url = urljoin(list_url, link["href"])
            externe_id = detail_url.rsplit("=", 1)[-1] if "=" in detail_url else detail_url
            candidates.append(
                RawCandidate(externe_id=externe_id, detail_url=detail_url, titel_hint=link.get_text(strip=True))
            )

        if not items and page == 1:
            raise TechnicalFailure(
                "Vergabeplattform Berlin: keine Listeneinträge gefunden - Struktur unbekannt, "
                "Analyse mit echtem Netzzugriff nötig (LIST_ITEM_SELECTOR/LIST_URL_CANDIDATES prüfen)."
            )

        next_link = soup.select_one("a.naechste-seite, a[rel='next']")
        return candidates, next_link is not None

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        response = self.polite_get(candidate.detail_url)
        soup = BeautifulSoup(response.text, "lxml")
        title_el = soup.select_one("h1, .bekanntmachung-titel")
        main_el = soup.select_one("main, .content, .bekanntmachung-detail")

        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": title_el.get_text(strip=True) if title_el else candidate.titel_hint,
                "volltext": main_el.get_text(" ", strip=True) if main_el else None,
                "quelle_raw_html": str(soup)[:20000],
            },
        )
