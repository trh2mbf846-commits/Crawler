"""Connector: ITDZ Berlin - Aktuelle Ausschreibungen (Kapitel 3, vom Auftraggeber vorgegeben).

Verifiziert am 31.08.2026 gegen die echte Seite (Netzzugriff wurde in dieser Session
freigeschaltet). Befund:

- robots.txt erlaubt automatisierten Abruf ausdrücklich, sofern der Client sich im
  User-Agent-Header klar identifiziert (siehe docs/portal-notes.md) - unser
  `settings.http_user_agent` erfüllt das. Keiner der in robots.txt gesperrten Pfade
  (`/*/(S(*))`, `/land/kalender/print/`, `/presse/pressemitteilungen/index/search/`)
  überschneidet sich mit dieser Seite.
- Die Liste ist server-seitig gerendertes, statisches HTML (kein JS nötig):
  `<div class="modul-rss_list"><ul class="list"><li><span class="date">TT.MM.JJJJ</span>
  <a href="...">ITDZ Berlin: Titel</a></li>...`. Keine Pagination - es werden nur die
  aktuell laufenden Ausschreibungen gezeigt (Stand 31.08.2026: 3 Einträge).
- WICHTIG: Jeder Eintrag verlinkt NICHT auf eine Detailseite bei itdz-berlin.de, sondern
  direkt extern auf die tatsächliche Vergabeplattform meinauftrag.rib.de (RIB/iTWO), wo
  die Ausschreibung geführt wird. Das ist zugleich der korrekte `direktlink` im Sinne von
  Kapitel 6 ("verweist immer auf die tatsächliche Originalseite"). Es gibt bewusst KEINEN
  zusätzlichen HTTP-Request auf meinauftrag.rib.de (eigenes Portal mit eigener
  robots.txt/ToS-Prüfung außerhalb des aktuellen Scopes, Kapitel 9.3) - Titel und
  Veröffentlichungsdatum aus der Liste reichen für Discovery/Normalization/Klassifikation.
- Der "Geplante Ausschreibungen"-Abschnitt (unverbindliche Themen ohne Link/ID) wird
  bewusst NICHT erfasst, da ihm die Pflichtfelder aus Kapitel 6 (insb. direktlink) fehlen.
- Ein RSS-Feed existiert (`index.php/rss`), war beim Test aber leer (0 Items), obwohl die
  HTML-Liste 3 Einträge zeigte - daher HTML als primäre Quelle, RSS nicht verwendet.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure


class ItdzBerlinConnector(BaseConnector):
    slug = "itdz-berlin"
    name = "ITDZ Berlin – Aktuelle Ausschreibungen"
    base_url = "https://www.itdz-berlin.de/unternehmen/ausschreibungen/aktuelle-ausschreibungen/"
    vorgegeben = True
    robots_status = "geprueft_ok"
    tos_hinweis = (
        "robots.txt (geprüft 31.08.2026) erlaubt automatisierten Abruf explizit bei klarer "
        "User-Agent-Kennung; keine der gesperrten Pfadmuster betrifft diese Seite. Kein "
        "Login/CAPTCHA auf der Übersichtsseite."
    )

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        if page > 1:
            return [], False  # keine Pagination vorhanden (Stand 31.08.2026)

        response = self.polite_get(self.base_url)
        soup = BeautifulSoup(response.text, "lxml")

        items = soup.select("div.modul-rss_list ul.list li")
        candidates: list[RawCandidate] = []
        for li in items:
            link = li.select_one("a")
            date_el = li.select_one("span.date")
            if link is None or not link.get("href"):
                continue
            detail_url = link["href"]
            externe_id = detail_url.rstrip("/").rsplit("/", 1)[-1]
            candidates.append(
                RawCandidate(
                    externe_id=externe_id,
                    detail_url=detail_url,
                    titel_hint=link.get_text(strip=True),
                    listen_metadaten={"veroeffentlichungsdatum": date_el.get_text(strip=True) if date_el else None},
                )
            )

        if not candidates and page == 1:
            # 0 Treffer ist am ITDZ-Portal ein plausibler Normalzustand (kleine, schwankende
            # Anzahl laufender Ausschreibungen) - kein automatischer TechnicalFailure hier,
            # das Source-Health-Monitoring (Kapitel 21.3) erkennt eine echte Auffälligkeit
            # erst bei mehreren aufeinanderfolgenden 0-Treffer-Läufen.
            if soup.select_one("div.modul-rss_list") is None:
                raise TechnicalFailure(
                    "ITDZ Berlin: Container 'div.modul-rss_list' nicht gefunden - "
                    "Seitenstruktur hat sich vermutlich geändert."
                )

        return candidates, False

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        # Bewusst kein weiterer HTTP-Request (siehe Modul-Docstring) - alle verfügbaren
        # Felder stammen aus der Listenseite.
        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": candidate.titel_hint,
                "vergabestelle": "IT-Dienstleistungszentrum Berlin (ITDZ Berlin)",
                "ort_region": "Berlin",
                "veroeffentlichungsdatum": candidate.listen_metadaten.get("veroeffentlichungsdatum"),
                "volltext": None,
                "dokumente_links": [],
                "_hinweis": (
                    "Detailseite liegt extern bei meinauftrag.rib.de (eigenes Portal, "
                    "nicht Teil des aktuellen Scopes) - nur Listen-Metadaten erfasst."
                ),
            },
        )
