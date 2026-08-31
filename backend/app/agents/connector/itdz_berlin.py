"""Connector: ITDZ Berlin - Aktuelle Ausschreibungen (Kapitel 3, vom Auftraggeber vorgegeben).

Laut Handlungsanweisung: "Öffentlich zugängliche Übersichtsseite; besonders KI-nahe
Vergabestelle". Erwartung: klassische, serverseitig gerenderte HTML-Liste (kein SPA) - daher
hier mit httpx + BeautifulSoup statt Playwright umgesetzt. Diese Annahme ist bis zur echten
Analyse (siehe base.py-Docstring) nicht verifiziert.
"""
from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure

# TODO(portal-analyse): Selektoren gegen die echte Seite verifizieren, sobald Netzzugriff
# verfügbar ist (siehe Rückfrage im Chat vom 31.08.2026). Platzhalter beruhen auf einer
# plausiblen, typischen Struktur öffentlicher Ausschreibungslisten und MÜSSEN vor dem
# produktiven Einsatz bestätigt/angepasst werden.
LIST_ITEM_SELECTOR = "article.ausschreibung, li.ausschreibung, .teaser-liste .teaser"
LIST_TITLE_SELECTOR = "h2 a, h3 a, a.teaser-link"
LIST_NEXT_PAGE_SELECTOR = "a.pager__next, a[rel='next']"
DETAIL_TITLE_SELECTOR = "h1"
DETAIL_MAIN_SELECTOR = "main, .content, article"


class ItdzBerlinConnector(BaseConnector):
    slug = "itdz-berlin"
    name = "ITDZ Berlin – Aktuelle Ausschreibungen"
    base_url = "https://www.itdz-berlin.de/unternehmen/ausschreibungen/aktuelle-ausschreibungen/"
    vorgegeben = True

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        url = self.base_url if page == 1 else f"{self.base_url}?page={page}"
        response = self.polite_get(url)
        soup = BeautifulSoup(response.text, "lxml")

        items = soup.select(LIST_ITEM_SELECTOR)
        candidates: list[RawCandidate] = []
        for item in items:
            link = item.select_one(LIST_TITLE_SELECTOR)
            if link is None or not link.get("href"):
                continue
            detail_url = urljoin(url, link["href"])
            externe_id = detail_url.rstrip("/").rsplit("/", 1)[-1]
            candidates.append(
                RawCandidate(externe_id=externe_id, detail_url=detail_url, titel_hint=link.get_text(strip=True))
            )

        if not items and page == 1:
            raise TechnicalFailure(
                "ITDZ Berlin: keine Listeneinträge über LIST_ITEM_SELECTOR gefunden - "
                "Selektor vermutlich veraltet oder Seite erfordert JavaScript; Analyse nötig."
            )

        has_more = soup.select_one(LIST_NEXT_PAGE_SELECTOR) is not None
        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        response = self.polite_get(candidate.detail_url)
        soup = BeautifulSoup(response.text, "lxml")

        title_el = soup.select_one(DETAIL_TITLE_SELECTOR)
        main_el = soup.select_one(DETAIL_MAIN_SELECTOR)
        dokument_links = [
            urljoin(candidate.detail_url, a["href"])
            for a in soup.select("a[href$='.pdf'], a[href*='dokument']")
            if a.get("href")
        ]

        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": title_el.get_text(strip=True) if title_el else candidate.titel_hint,
                "volltext": main_el.get_text(" ", strip=True) if main_el else None,
                "vergabestelle": "IT-Dienstleistungszentrum Berlin (ITDZ Berlin)",
                "dokumente_links": dokument_links,
                "quelle_raw_html": str(soup)[:20000],
            },
        )
