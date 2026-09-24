"""Connector: DTVP – Deutsches Vergabeportal (Kapitel 3, Nutzeranfrage 01.09.2026).

Verifiziert am 04./05.09.2026 gegen die echte Seite. Befund:

- robots.txt (Standard-WordPress + Yoast-Block) erlaubt automatisierten Zugriff auf die
  öffentliche Sektion vollständig, keine relevante Disallow-Regel.
- Die schlichte Landingpage `/ausschreibungen/` zeigt nur 9 CPV-Themenkacheln plus einen
  angerissenen, teils absichtlich unscharf dargestellten Teaser (Klasse `is-blurred` ab dem
  5. Eintrag) - keine geeignete Listenquelle.
- Die vollständige, NICHT verschleierte Trefferliste liegt auf den CPV-Kategorieseiten unter
  `/ausschreibungen/cpv/<slug>-<cpv-code>/` (WordPress-Taxonomie-Archiv, `<article
  role="article" id="post_...">` je Ausschreibung, Pagination über `<link rel="next">` /
  `.../page/N/`). Diese Seiten sind vollständig öffentlich (kein Login, kein Blur).
- Die alte Such-Anwendung `www.dtvp.de/Center/common/project/search.do` (JWT-CSRF-Token) und
  die WordPress-Volltextsuche (`dtvp.de/?s=...`) wurden geprüft, liefern aber keine
  verlässliche/vollständige Trefferabdeckung für den Ausschreibungen-Posttyp (siehe eigene
  Recherche 04.09.2026) - deshalb werden stattdessen 3 gezielt identifizierte, thematisch
  passende CPV-Kategorien direkt gecrawlt (Kapitel 4.1 + Nutzeranfrage: KI/IT, Planung/
  Bauüberwachung, Beratung). Das deckt die relevanten Themenfelder ab, ohne die komplette
  Alt-Suche zu benötigen.
- Detailseite (gleiche URL wie der Artikel-Link aus der Liste) zeigt Titel, CPV-Code,
  Abgabefrist, Vergabeart/-ordnung, Mandant (=Vergabestelle), Ort der Ausführung und die
  volle Leistungsbeschreibung - alles öffentlich, kein zusätzlicher Login-Schritt.
"""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail, detect_access_block
from app.exceptions import TechnicalFailure

BASE_URL = "https://dtvp.de/ausschreibungen/"

# Thematisch passende CPV-Top-Kategorien (Kapitel 4.1 + Nutzeranfrage: KI/IT,
# Planung/Bauüberwachung, Beratung), verifiziert per Breadcrumb-Navigation am 04.09.2026.
_KATEGORIEN: list[str] = [
    "https://dtvp.de/ausschreibungen/cpv/it-dienste-beratung-software-entwicklung-internet-und-hilfestellung-72000000-5/",
    "https://dtvp.de/ausschreibungen/cpv/dienstleistungen-von-ingenieurbueros-71300000-1/",
    "https://dtvp.de/ausschreibungen/cpv/unternehmens-und-managementberatung-und-zugehoerige-dienste-79400000-8/",
]
# Pro Kategorie max. so viele Seiten (16 Treffer/Seite). Nutzeranfrage 05.09.2026: möglichst
# viele Ausschreibungen abbilden, lokal filtern statt serverseitig stark einzuschränken.
_MAX_SEITEN_PRO_KATEGORIE = 20


class DtvpConnector(BaseConnector):
    slug = "dtvp"
    name = "DTVP – Deutsches Vergabeportal"
    base_url = BASE_URL
    vorgegeben = False
    robots_status = "geprueft_ok"
    # Selbstbegrenzend: 3 Kategorien x _MAX_SEITEN_PRO_KATEGORIE virtuelle Seiten, danach liefert
    # fetch_list_page von sich aus has_more=False - dieser Wert ist nur eine zusätzliche
    # Absicherung, keine funktionale Grenze.
    max_pages = 3 * _MAX_SEITEN_PRO_KATEGORIE
    tos_hinweis = (
        "robots.txt (Standard-WordPress) erlaubt automatisierten Zugriff auf die öffentliche "
        "Sektion /ausschreibungen/; die genutzten CPV-Kategorieseiten sind vollständig "
        "öffentlich (kein Login, kein Blur-Teaser)."
    )

    def __init__(self) -> None:
        super().__init__()
        # Wir kennen die reale Seitenzahl je Kategorie nicht im Voraus (kleine Kategorien wie
        # "Beratung" haben z. B. nur ~5 Seiten, andere deutlich mehr) - einmal als erschöpft
        # erkannte Kategorien (HTTP 404 auf einer Folgeseite) werden hier vermerkt, damit nicht
        # bis zu _MAX_SEITEN_PRO_KATEGORIE weitere, garantiert leere Anfragen an dieselbe
        # Kategorie geschickt werden.
        self._erschoepfte_kategorien: set[int] = set()

    def _seite_fuer(self, virtuelle_seite: int) -> tuple[int, str, int] | None:
        """Bildet eine fortlaufende virtuelle Seitenzahl auf (Kategorie-Index, -URL, reale Seite) ab."""
        index = virtuelle_seite - 1
        kategorie_index, reale_seite = divmod(index, _MAX_SEITEN_PRO_KATEGORIE)
        if kategorie_index >= len(_KATEGORIEN):
            return None
        return kategorie_index, _KATEGORIEN[kategorie_index], reale_seite + 1

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        ziel = self._seite_fuer(page)
        if ziel is None:
            return [], False
        kategorie_index, kategorie_url, reale_seite = ziel

        if kategorie_index in self._erschoepfte_kategorien:
            return [], self._seite_fuer(page + 1) is not None

        url = kategorie_url if reale_seite == 1 else f"{kategorie_url}page/{reale_seite}/"
        self._respect_rate_limit()
        try:
            response = self.client.get(url)
        except httpx.HTTPError as exc:
            raise TechnicalFailure(f"DTVP: HTTP-Fehler bei {url}: {exc}") from exc

        if reale_seite > 1 and response.status_code == 404:
            # Reale Kategorie ist kürzer als unser Seitenbudget (_MAX_SEITEN_PRO_KATEGORIE) -
            # WordPress liefert für eine nicht existierende Seitenzahl 404 statt einer leeren
            # Trefferliste. Kein Zugriffsproblem, sondern schlicht "diese Kategorie ist zu Ende".
            self._erschoepfte_kategorien.add(kategorie_index)
            return [], self._seite_fuer(page + 1) is not None

        block = detect_access_block(response.text, response.status_code)
        if block is not None:
            raise block
        if response.status_code >= 400:
            raise TechnicalFailure(f"DTVP: HTTP {response.status_code} bei {url}")

        soup = BeautifulSoup(response.text, "lxml")

        articles = soup.select('article[role="article"]')
        if not articles and reale_seite == 1:
            raise TechnicalFailure(
                f"DTVP: keine Ausschreibungen auf CPV-Kategorieseite gefunden ({kategorie_url}) - "
                "Seitenstruktur hat sich vermutlich geändert."
            )

        candidates: list[RawCandidate] = []
        for article in articles:
            link = article.select_one("h5.title a")
            if link is None or not link.get("href"):
                continue
            detail_url = link["href"]
            if not detail_url.startswith("http"):
                # Ab einer gewissen Seitentiefe blendet DTVP zusätzlich zu echten, nur optisch
                # unscharf dargestellten Einträgen (Klasse "is-blurred", haben trotzdem eine
                # echte, nutzbare URL) eine wiederholte Registrierungs-Karte als Pseudo-Artikel
                # ein - deren Link ist ein bloßes "#" statt einer echten Detailseite. Kein Titel/
                # keine ID, also kein verwertbarer Kandidat - übersprungen statt als kaputte
                # Ausschreibung mit "#"-Link weiterzureichen.
                continue
            externe_id = article.get("id", "").removeprefix("post_") or detail_url.rstrip("/").rsplit("/", 1)[-1]
            candidates.append(
                RawCandidate(
                    externe_id=externe_id,
                    detail_url=detail_url,
                    titel_hint=link.get_text(strip=True),
                    listen_metadaten={
                        "ort_region": _by_icon(article, "bi-geo-alt"),
                        "vergabestelle": _by_icon(article, "bi-house"),
                        "verfahrensart": _by_icon(article, "bi-book"),
                        "angebotsfrist": _by_icon(article, "bi-calendar-check"),
                    },
                )
            )

        # Es gibt entweder eine weitere Seite innerhalb derselben Kategorie (echtes
        # <link rel="next">, gedeckelt durch _MAX_SEITEN_PRO_KATEGORIE) oder die nächste
        # Kategorie in der virtuellen Sequenz ist noch nicht erreicht.
        naechste_seite_existiert = (
            reale_seite < _MAX_SEITEN_PRO_KATEGORIE and soup.select_one('link[rel="next"]') is not None
        )
        has_more = naechste_seite_existiert or self._seite_fuer(page + 1) is not None
        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        response = self.polite_get(candidate.detail_url)
        soup = BeautifulSoup(response.text, "lxml")

        titel_el = soup.select_one("h1")
        beschreibung_el = soup.select_one("div.dtvp21-cc-oc-desc-content")
        beschreibung = beschreibung_el.get_text(" ", strip=True) if beschreibung_el else None

        sidebar = soup.select_one("div.col-4")
        main = soup.select_one("div.col-md-8")
        cpv_text = _h6_wert(sidebar, "CPV-Code") if sidebar else None
        angebotsfrist = _h6_wert(sidebar, "Abgabefrist") if sidebar else None
        vergabeart = _h6_wert(main, "Vergabeart") if main else None
        mandant = _h6_wert(main, "Mandant") if main else None
        ort = _h6_wert(main, "Ort der Ausführung") if main else None

        cpv_code = cpv_text.split()[0] if cpv_text else None

        meta = candidate.listen_metadaten
        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": titel_el.get_text(strip=True) if titel_el else candidate.titel_hint,
                "volltext": beschreibung,
                "kurzbeschreibung": beschreibung,
                "vergabestelle": mandant or meta.get("vergabestelle"),
                "ort_region": ort or meta.get("ort_region"),
                "verfahrensart": vergabeart or meta.get("verfahrensart"),
                "angebotsfrist": angebotsfrist or meta.get("angebotsfrist"),
                "cpv_codes": [cpv_code] if cpv_code else [],
            },
        )


def _by_icon(article, icon_class: str) -> str | None:
    icon = article.select_one(f"i.{icon_class}")
    if icon is None or icon.parent is None:
        return None
    return icon.parent.get_text(" ", strip=True)


def _h6_wert(container, label_praefix: str) -> str | None:
    for h6 in container.select("h6"):
        if h6.get_text(strip=True).startswith(label_praefix):
            p = h6.find_next_sibling("p")
            if p is not None:
                text = p.get_text(" ", strip=True)
                return text or None
    return None
