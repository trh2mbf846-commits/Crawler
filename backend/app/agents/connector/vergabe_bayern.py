"""Connector: Vergabeplattform Bayern (vergabe.bayern.de) - Nutzeranfrage 25.09.2026 ("können wir

mehr Portale dazu fügen?").

Verifiziert am 25.09.2026 gegen die echte Seite. Befund:

- `vergabe.bayern.de` (Bayerisches Staatsministerium für Wohnen, Bau und Verkehr) bettet seine
  Auftragsbekanntmachungen-Seite per `<iframe>` direkt aus der zugrunde liegenden Vergabesoftware
  **RIB/iTWO** ein (`meinauftrag.rib.de/public/publicationsFrame?filter=604283`, `604283` ist die
  landesweite Bayern-Kundenkennung) - dieselbe Software-Familie, auf die auch ITDZ Berlin extern
  verlinkt (`app/agents/connector/itdz_berlin.py`), dort aber bewusst nicht selbst abgerufen wurde.
  Hier wird die RIB-Plattform diesmal direkt als Listenquelle genutzt, da sie für Bayern die
  vollständige, offizielle, öffentliche Trefferliste liefert (Stichprobe 25.09.2026: 402
  Bekanntmachungen).
- robots.txt von `meinauftrag.rib.de`: `User-agent: * / Allow: /` - **vollständig offen**, keine
  Sperre. `vergabe.bayern.de` selbst hat kein robots.txt (HTTP 404 = keine Einschränkung).
- Technischer Ablauf (kein Login, aber Session-/CSRF-Handling nötig): Die erste Seite
  (`GET .../publicationsFrame?filter=604283`) liefert serverseitig gerendert die ersten ~20
  Treffer als `<li id="tender-<ID>">`-Elemente, setzt ein `PHPSESSID`-Cookie und enthält ein
  CSRF-Token (`YII_CSRF_TOKEN`) sowie die Gesamttrefferzahl (`totalEntries`) als eingebettete
  JS-Variablen. Weitere Seiten werden per `POST .../public/nextPublications` (Offset-Pagination,
  20 pro Aufruf) nachgeladen - dafür müssen dasselbe Session-Cookie (übernimmt `httpx.Client`
  automatisch, da dieselbe Client-Instanz über den ganzen Discovery-Lauf wiederverwendet wird)
  und das zur Session passende CSRF-Token mitgeschickt werden - und zwar **zusätzlich als
  eigenes Formularfeld** (`YII_CSRF_TOKEN`), nicht nur als `X-CSRF-Token`-Header (live
  verifiziert 25.09.2026: mit Header allein liefert der Server HTTP 200, aber eine
  HTML-Fehlerseite statt JSON; mit beidem HTTP 200 + `{"success": true, "items": "<li ...>"}`).
  Fehlt Cookie oder Token ganz, liefert der Server HTTP 302 auf `/error/index`.
- Detailseite `https://www.meinauftrag.rib.de/public/publications/<ID>` ist vollständig ohne
  Login abrufbar (Titel, Kurzbeschreibung, Vergabestelle mit Adresse/Kontakt, Fristen,
  Ausführungsort, Vergabeunterlagen-Downloadlinks). Der "Apply"-Link (Angebotsabgabe) verlangt
  ein Bieterkonto - das betrifft nur die Angebotsabgabe selbst, nicht das Einsehen der
  Bekanntmachung (Kapitel 10.3 trifft hier nicht zu).
"""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail, detect_access_block
from app.exceptions import TechnicalFailure

BASE_URL = "https://www.meinauftrag.rib.de/public/publicationsFrame?filter=604283&config=exante/false"
NEXT_URL = "https://www.meinauftrag.rib.de/public/nextPublications"
DETAIL_URL_TMPL = "https://www.meinauftrag.rib.de/public/publications/{externe_id}"
_FILTER_ID = "604283"
# RIB liefert pro Nachlade-Aufruf 20 Treffer (live verifiziert 25.09.2026); dient hier nur als
# Sicherheitsnetz, falls `totalEntries` sich nicht aus der Startseite auslesen lässt.
_SEITENGROESSE = 20
_CSRF_MUSTER = re.compile(r"YII_CSRF_TOKEN\s*=\s*'([^']+)'")
_GESAMT_MUSTER = re.compile(r"totalEntries\s*=\s*(\d+)")


class VergabeBayernConnector(BaseConnector):
    slug = "vergabe-bayern"
    name = "Vergabeplattform Bayern (vergabe.bayern.de)"
    base_url = BASE_URL
    vorgegeben = False
    robots_status = "geprueft_ok"
    # ~402 Treffer / 20 pro Seite (Stichprobe 25.09.2026) + Puffer für Wachstum.
    max_pages = 30
    tos_hinweis = (
        "robots.txt der zugrunde liegenden RIB-Plattform meinauftrag.rib.de erlaubt automatisierten "
        "Zugriff vollständig (\"Allow: /\"); vergabe.bayern.de selbst hat kein robots.txt. Liste und "
        "Detailseiten sind ohne Login öffentlich abrufbar, nur die Angebotsabgabe selbst verlangt "
        "ein Bieterkonto."
    )

    def __init__(self) -> None:
        super().__init__()
        # Pagination läuft über Offset + Session-Cookie + CSRF-Token statt über eigenständige
        # URLs je Seite - dieser Zustand wird beim ersten Seitenabruf gefüllt und danach über
        # die Lebensdauer dieser Connector-Instanz (ein Discovery-Lauf) weitergereicht.
        self._csrf_token: str | None = None
        self._offset: int = 0
        self._gesamt_anzahl: int | None = None

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        if page == 1:
            response = self.polite_get(BASE_URL)
            token_match = _CSRF_MUSTER.search(response.text)
            if token_match is None:
                raise TechnicalFailure(
                    "Vergabe Bayern: CSRF-Token auf der Startseite nicht gefunden - "
                    "Seitenstruktur hat sich vermutlich geändert."
                )
            self._csrf_token = token_match.group(1)
            gesamt_match = _GESAMT_MUSTER.search(response.text)
            self._gesamt_anzahl = int(gesamt_match.group(1)) if gesamt_match else None

            soup = BeautifulSoup(response.text, "lxml")
            items = soup.select("li[id^='tender-']")
            if not items:
                raise TechnicalFailure(
                    "Vergabe Bayern: keine Ausschreibungen auf der Startseite gefunden - "
                    "Seitenstruktur hat sich vermutlich geändert."
                )
            candidates = _parse_items(items)
            self._offset = len(candidates)
        else:
            if self._csrf_token is None:
                raise TechnicalFailure("Vergabe Bayern: Pagination ohne vorherige Startseite aufgerufen.")
            self._respect_rate_limit()
            try:
                response = self.client.post(
                    NEXT_URL,
                    data={
                        "offset": self._offset,
                        "filter": _FILTER_ID,
                        "search": "",
                        "collapse": "true",
                        # Yii prüft das CSRF-Token nicht nur im Header, sondern erwartet es
                        # zusätzlich als eigenes Formularfeld - live verifiziert 25.09.2026: ohne
                        # dieses Feld liefert der Server HTTP 200 mit einer Fehlerseite statt JSON.
                        "YII_CSRF_TOKEN": self._csrf_token,
                    },
                    headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": self._csrf_token},
                )
            except httpx.HTTPError as exc:
                raise TechnicalFailure(f"Vergabe Bayern: HTTP-Fehler bei Pagination: {exc}") from exc

            block = detect_access_block(response.text, response.status_code)
            if block is not None:
                raise block
            if response.status_code >= 400:
                raise TechnicalFailure(
                    f"Vergabe Bayern: HTTP {response.status_code} bei Pagination (offset={self._offset})"
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise TechnicalFailure(f"Vergabe Bayern: Antwort auf Pagination war kein JSON: {exc}") from exc
            if not payload.get("success"):
                raise TechnicalFailure(f"Vergabe Bayern: Pagination meldete success=false (offset={self._offset})")

            soup = BeautifulSoup(payload.get("items") or "", "lxml")
            items = soup.select("li[id^='tender-']")
            candidates = _parse_items(items)
            self._offset += len(candidates)

        if self._gesamt_anzahl is not None:
            has_more = self._offset < self._gesamt_anzahl
        else:
            has_more = len(candidates) >= _SEITENGROESSE
        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        response = self.polite_get(candidate.detail_url)
        soup = BeautifulSoup(response.text, "lxml")

        details = soup.select_one("div.tender-details")
        titel_el = details.select_one("h4") if details else None
        vergabestelle = _abschnitt_erste_zeile(details, "Contracting Authority") if details else None
        kurzbeschreibung = _abschnitt_text(details, "Brief Description") if details else None

        meta = candidate.listen_metadaten
        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": titel_el.get_text(strip=True) if titel_el else candidate.titel_hint,
                "volltext": kurzbeschreibung or meta.get("kurzbeschreibung"),
                "kurzbeschreibung": kurzbeschreibung or meta.get("kurzbeschreibung"),
                "vergabestelle": vergabestelle or meta.get("vergabestelle"),
                "ort_region": meta.get("ort_region"),
                "verfahrensart": None,
                "angebotsfrist": meta.get("angebotsfrist"),
                "cpv_codes": [],
                "dokumente_links": _vergabeunterlagen_links(response.text),
            },
        )


def _parse_items(items: list) -> list[RawCandidate]:
    candidates: list[RawCandidate] = []
    for li in items:
        externe_id = (li.get("id") or "").removeprefix("tender-")
        if not externe_id:
            continue
        titel_el = li.select_one("div.item-left strong")
        vergabestelle_el = li.select_one("div.item-left div.text-muted[title]")
        candidates.append(
            RawCandidate(
                externe_id=externe_id,
                detail_url=DETAIL_URL_TMPL.format(externe_id=externe_id),
                titel_hint=titel_el.get_text(strip=True) if titel_el else None,
                listen_metadaten={
                    "vergabestelle": vergabestelle_el.get("title") if vergabestelle_el else None,
                    "angebotsfrist": _info_wert(li, "Application deadline"),
                    "ort_region": _info_wert(li, "Execution place"),
                    "kurzbeschreibung": _info_wert(li, "Brief Description"),
                },
            )
        )
    return candidates


def _info_wert(li, label: str) -> str | None:
    for label_div in li.select("div.info-label"):
        if label_div.get_text(strip=True) == label:
            wert_div = label_div.find_next_sibling("div")
            if wert_div is not None:
                text = wert_div.get_text(" ", strip=True)
                return text or None
    return None


def _abschnitt_text(container, ueberschrift: str) -> str | None:
    if container is None:
        return None
    for h6 in container.select("h6"):
        if h6.get_text(strip=True) == ueberschrift:
            eltern = h6.parent
            heading_text = h6.get_text(strip=True)
            text = eltern.get_text(" ", strip=True)
            if text.startswith(heading_text):
                text = text[len(heading_text):].strip()
            return text or None
    return None


def _abschnitt_erste_zeile(container, ueberschrift: str) -> str | None:
    if container is None:
        return None
    for h6 in container.select("h6"):
        if h6.get_text(strip=True) == ueberschrift:
            heading_text = h6.get_text(strip=True)
            for text in h6.parent.stripped_strings:
                if text != heading_text:
                    return text
    return None


# Regex statt DOM-Selektor: die Vergabeunterlagen-Downloadlinks liegen nicht als normale
# <a href>-Tags im HTML, sondern in einer JS-Variable (documentsAttachments/documentsApplicationForm)
# als verschachteltes JSON-artiges Literal mit escapten Slashes ("\/") - ein Regex direkt auf
# response.text ist hier robuster als ein DOM-Parser. Live verifiziert 25.09.2026: die
# resultierenden download.php-Links sind vollständig öffentlich (kein Login, kein Cookie/Session
# nötig - funktioniert auch mit einem komplett frischen HTTP-Client) und liefern echte PDFs.
_DOKUMENT_HASH_MUSTER = re.compile(r"download\.php\?k=([a-f0-9]{20,64})")


def _vergabeunterlagen_links(html: str) -> list[str]:
    hashes = dict.fromkeys(_DOKUMENT_HASH_MUSTER.findall(html))  # dedupliziert, behält Reihenfolge
    return [f"https://my.vergabe.bayern.de/remote/download.php?k={h}" for h in hashes]
