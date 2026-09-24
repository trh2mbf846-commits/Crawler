"""Connector: e-Vergabe des Bundes (Kapitel 3, Nutzeranfrage 01.09.2026).

Verifiziert am 04./05.09.2026 gegen die echte Seite. Befund:

- robots.txt erlaubt `/search.html` und `/tenderdetails.html` explizit; die wenigen
  gesperrten Pfade (u. a. `/ws-suche/`) werden von diesem Connector nicht angefragt.
- Vor der eigentlichen Anwendung steht ein reiner Cookie-Consent-Redirect
  (`/search.html` -> `/search.html?cookieCheck` -> `/search.html`, setzt nur
  `COOKIES_SUPPORTED=yes` + Session-Cookie `APPSESSIONID`) - kein Login, kein CAPTCHA.
- Die Anwendung ist ein Apache-Wicket-Formular: jede Antwort enthält eine session-gebundene
  Seiteninstanz-Kennung in der URL (z. B. `search.html?161`). Eine eigene Such-Query per
  GET/POST-Parameter zu konstruieren ist bei Wicket fragil (siehe Kapitel 9.1) - stattdessen
  zeigt `#datatable` schon ohne jede Sucheingabe serverseitig ALLE aktuell offenen Verfahren
  (Stand 04.09.2026: 1072, sortiert nach Veröffentlichungsdatum absteigend) - das entspricht
  genau der Nutzeranfrage ("erstmal alle Ausschreibungen durchsuchen, dann lokal filtern").
  Die "Nächste Seite"-Verlinkung (`a.next`, ebenfalls eine Wicket-Seiteninstanz-URL) wird direkt
  aus der jeweiligen Antwort übernommen statt selbst konstruiert (Kapitel 9.1).
- Detailseite (`tenderdetails.html?id=<id>`) ist vollständig öffentlich (kein Login nötig, nur
  ein "Teilnahme aktivieren"-Link für die spätere Angebotsabgabe) und enthält die amtliche
  Bekanntmachung als gegliederte Kapitel (a-f: Vergabestelle, Verfahrensart, ..., Art des
  Auftrags, Ort der Ausführung, Art und Umfang der Leistung). CPV-Codes fehlen bei nationalen
  (nicht EU-weiten) Verfahren oft komplett - hier bewusst kein Pflichtfeld.
- WICHTIG: Ein direkter GET auf eine Wicket-Seiteninstanz-URL (z. B. die "nächste Seite"-Adresse
  aus der vorigen Antwort) ohne `Referer`-Header liefert HTTP 403 - das ist kein Bot-Schutz im
  Sinne von Kapitel 9.2 (kein CAPTCHA/Login-Hinweis, reproduzierbar auch mit browserähnlichem
  User-Agent), sondern eine einfache Referer-Prüfung der Wicket-Anwendung selbst, wie sie auch
  ein normaler Browser bei jeder Navigation automatisch mitschickt. Dieser Connector sendet
  daher bei jedem Folgeaufruf den `Referer` der zuvor abgerufenen Seite mit (entspricht exakt
  dem, was ein Browser beim Klick auf "Nächste Seite" täte - kein Umgehen einer Schranke).
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure

BASE_URL = "https://www.evergabe-online.de/"
SEARCH_URL = BASE_URL + "search.html"


class EvergabeBundConnector(BaseConnector):
    slug = "evergabe-bund"
    name = "e-Vergabe des Bundes"
    base_url = SEARCH_URL
    vorgegeben = False
    robots_status = "geprueft_ok"
    # Nutzeranfrage 05.09.2026: möglichst viele Ausschreibungen abbilden - 30 Seiten x 10 = bis
    # zu 300 Kandidaten der neuesten (Sortierung: veröffentlicht absteigend) von insgesamt
    # >1000 offenen Verfahren.
    max_pages = 30
    tos_hinweis = (
        "robots.txt erlaubt /search.html und /tenderdetails.html; nur wenige Pfade gesperrt "
        "(u. a. /ws-suche/), werden nicht angefragt. Suche funktioniert ohne Login (nur "
        "Cookie-Consent)."
    )

    def __init__(self) -> None:
        super().__init__()
        self._naechste_seite_url: str | None = None
        self._letzte_url: str | None = None

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        if page == 1:
            url = SEARCH_URL
        else:
            if self._naechste_seite_url is None:
                return [], False
            url = self._naechste_seite_url

        headers = {"Referer": self._letzte_url} if self._letzte_url else None
        response = self.polite_get(url, headers=headers)
        self._letzte_url = str(response.url)
        soup = BeautifulSoup(response.text, "lxml")

        table = soup.select_one("table#datatable")
        if table is None:
            raise TechnicalFailure(
                "e-Vergabe Bund: Ergebnistabelle 'table#datatable' nicht gefunden - "
                "Seitenstruktur hat sich vermutlich geändert (Cookie-Consent-Schritt prüfen)."
            )

        candidates: list[RawCandidate] = []
        for row in table.select("tbody tr"):
            tds = row.find_all("td")
            if len(tds) < 7:
                continue
            link = tds[0].select_one("a")
            if link is None or not link.get("href"):
                continue
            detail_url = str(response.url.join(link["href"]))
            externe_id = _id_aus_url(link["href"])
            candidates.append(
                RawCandidate(
                    externe_id=externe_id,
                    detail_url=detail_url,
                    titel_hint=link.get_text(strip=True),
                    listen_metadaten={
                        "geschaeftszeichen": tds[1].get_text(" ", strip=True),
                        "vergabestelle": tds[2].get_text(" ", strip=True),
                        "ort_region": tds[3].get_text(" ", strip=True),
                        "verfahrensart": tds[4].get_text(" ", strip=True),
                        "angebotsfrist": tds[5].get_text(" ", strip=True),
                        "veroeffentlichungsdatum": tds[6].get_text(" ", strip=True),
                    },
                )
            )

        next_link = soup.select_one("a.next")
        if next_link is not None and next_link.get("href") and "disabled" not in (next_link.get("class") or []):
            self._naechste_seite_url = str(response.url.join(next_link["href"]))
            has_more = True
        else:
            self._naechste_seite_url = None
            has_more = False

        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        headers = {"Referer": self._letzte_url} if self._letzte_url else None
        response = self.polite_get(candidate.detail_url, headers=headers)
        soup = BeautifulSoup(response.text, "lxml")

        meta = candidate.listen_metadaten
        beschreibung = _chapter_wert(soup, "Art und Umfang der Leistung")

        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": candidate.titel_hint,
                "volltext": beschreibung,
                "kurzbeschreibung": beschreibung,
                "vergabestelle": _form_gruppe_wert(soup, "Vergabestelle") or meta.get("vergabestelle"),
                "ort_region": _chapter_wert(soup, "Ort der Ausführung") or meta.get("ort_region"),
                "veroeffentlichungsdatum": _form_gruppe_wert(soup, "Veröffentlichungsdatum")
                or meta.get("veroeffentlichungsdatum"),
                "angebotsfrist": _form_gruppe_wert(soup, "Abgabefrist Angebot") or meta.get("angebotsfrist"),
                # "Verfahrensart" (Öffentliche Ausschreibung, Verhandlungsvergabe, ...) steht
                # zuverlässig schon in der Listen-Spalte; die Detailseite hat unter demselben Wort
                # nur "Art des Auftrags" (Bau-/Liefer-/Dienstleistung), ein anderes Feld.
                "verfahrensart": meta.get("verfahrensart"),
                "cpv_codes": [],
            },
        )


def _id_aus_url(href: str) -> str:
    if "id=" in href:
        return href.split("id=", 1)[1].split("&", 1)[0]
    return href.rstrip("/").rsplit("/", 1)[-1]


def _form_gruppe_wert(soup: BeautifulSoup, label_praefix: str) -> str | None:
    for gruppe in soup.select("div.form-group"):
        label = gruppe.select_one("label")
        if label and label.get_text(strip=True).startswith(label_praefix):
            wert = gruppe.select_one("p.form-control-static")
            return wert.get_text(" ", strip=True) if wert else None
    return None


def _chapter_wert(soup: BeautifulSoup, label_praefix: str) -> str | None:
    for headline in soup.select("div.chapter-headline"):
        if headline.get_text(strip=True).startswith(label_praefix):
            h4 = headline.parent
            content = h4.find_next_sibling("div", class_="chapter-content") if h4 else None
            return content.get_text(" ", strip=True) if content else None
    return None
