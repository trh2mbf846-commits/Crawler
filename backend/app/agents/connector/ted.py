"""Connector: TED – Tenders Electronic Daily (EU-weite Ausschreibungen, Kapitel 3).

Verifiziert am 04.09.2026 (Recherche-Agent + eigene Nachprüfung). Befund:

- `ted.europa.eu` selbst läuft hinter einer AWS-WAF-Bot-Challenge (robots.txt liefert HTTP 202
  mit `x-amzn-waf-action: challenge`) - dort wird NICHT gescraped.
- Es gibt aber eine offizielle, öffentlich dokumentierte REST Search API unter
  `api.ted.europa.eu`, die OHNE API-Key/Login funktioniert (Doku: docs.ted.europa.eu/api).
  Das ist der einzige für diesen Connector verwendete Zugriffsweg - kein HTML-Scraping.
- Deutschland-weite Treffer (CY = DEU) liegen bei >16.000/Monat ohne Themenfilter - für den
  Scope dieses Projekts wird die Serverseitige Volltextsuche (FT-Operator) der API selbst
  genutzt, um auf die relevanten Themenfelder (Kapitel 4.1 + Nutzeranfrage 01.09.2026:
  Planung/Bauüberwachung/Beratung) vorzufiltern - das ist die von der API vorgesehene, robuste
  Art der Vorfilterung (Kapitel 8.1), kein Umgehen irgendeiner Schranke.
- Detailfelder (Titel, Beschreibung, Vergabestelle, CPV-Code, Frist) werden direkt im
  Such-Response mitgeliefert (siehe FIELDS unten, alle live gegen die echte API verifiziert) -
  kein zusätzlicher Request pro Ausschreibung nötig.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.agents.connector.verfahrenslink import waehle_verfahrenslink
from app.exceptions import TechnicalFailure

API_URL = "https://api.ted.europa.eu/v3/notices/search"

FIELDS = [
    "ND", "TI", "PD", "CY", "classification-cpv",
    "deadline-receipt-tender-date-lot", "description-lot", "buyer-name", "notice-type", "links",
    # BT-18 Abgabe-URL / BT-15 Unterlagen-URL: Verfahrensseite auf der Vergabeplattform (25.09.2026)
    "submission-url-lot", "document-url-lot",
]

PAGE_SIZE = 50
# Zeitfenster: TED-Suche deckt laufend neue Bekanntmachungen ab - ein rollierendes Fenster
# reicht, ältere Ausschreibungen sind ohnehin meist schon abgelaufen (Kapitel 6: status).
_FENSTER_TAGE = 120


def _ft_query() -> str:
    # Repräsentative Teilmenge der Keyword-Listen (Kapitel 4.1 + Nutzeranfrage) als OR-Klauseln.
    # TED "FT ~" ist eine Fuzzy-/Teilstring-Volltextsuche - anders als die eigene
    # Wortgrenzen-Absicherung in keywords.py (siehe dortige Doku) kann hier auf die
    # Wortgrenzen-Polsterung verzichtet werden, da es sich um eine Portal-eigene Suchfunktion
    # handelt, keinen eigenen naiven Teilstring-Abgleich.
    begriffe = [
        "kuenstliche intelligenz", "artificial intelligence", "machine learning",
        "maschinelles lernen", "deep learning", "chatbot", "large language model",
        "ki-strategie", "generative ki",
        "bauueberwachung", "bauleitung", "projektsteuerung",
        "technische planung", "ingenieurleistungen",
        "strategieberatung", "unternehmensberatung",
    ]
    # Zusätzlich die Stichworte KI-bezogener Themen aus der Oberfläche (app/themen.py), z. B.
    # "ki-avatar", "ki-schulung" - sonst lieferte TED solche Ausschreibungen gar nicht erst.
    for b in _themen_begriffe():
        if b not in begriffe:
            begriffe.append(b)
    ft_clauses = " OR ".join(f'FT ~ "{b}"' for b in begriffe)
    cutoff = (datetime.utcnow() - timedelta(days=_FENSTER_TAGE)).strftime("%Y%m%d")
    # form-type = competition (25.09.2026): nur Auftragsbekanntmachungen, auf die man sich bewerben
    # kann - ohne den Filter kamen auch Zuschlagsmitteilungen (Auftrag schon vergeben) mit.
    return f'CY = DEU AND PD >= {cutoff} AND form-type = competition AND ({ft_clauses})'


def _themen_begriffe() -> list[str]:
    try:
        from app.db import SessionLocal
        from app.themen import ted_suchbegriffe

        db = SessionLocal()
        try:
            return ted_suchbegriffe(db)
        finally:
            db.close()
    except Exception:  # Themen sind eine Ergänzung - TED läuft notfalls mit den festen Begriffen
        return []


class TedConnector(BaseConnector):
    slug = "ted"
    name = "TED – Tenders Electronic Daily"
    base_url = API_URL
    vorgegeben = False
    robots_status = "geprueft_ok"
    # Nutzeranfrage 05.09.2026: möglichst viele Ausschreibungen abbilden, lokal filtern statt
    # serverseitig vorab stark einzuschränken - 20 Seiten x 50 = bis zu 1000 Kandidaten (das
    # Zeitfenster _FENSTER_TAGE und der thematische FT-Filter grenzen weiterhin sinnvoll ein).
    max_pages = 20
    tos_hinweis = (
        "Offizielle REST Search API (api.ted.europa.eu), kein Key/Login nötig. "
        "ted.europa.eu selbst (WAF-geschützt) wird nicht angefragt."
    )

    def _search(self, page: int) -> dict:
        self._respect_rate_limit()
        payload = {"query": _ft_query(), "fields": FIELDS, "page": page, "limit": PAGE_SIZE, "scope": "ALL"}
        try:
            response = self.client.post(API_URL, json=payload, headers={"Content-Type": "application/json"})
        except httpx.HTTPError as exc:
            raise TechnicalFailure(f"TED-API: HTTP-Fehler: {exc}") from exc
        if response.status_code >= 400:
            raise TechnicalFailure(f"TED-API: HTTP {response.status_code}: {response.text[:500]}")
        data = response.json()
        if "message" in data and "notices" not in data:
            raise TechnicalFailure(f"TED-API: Fehlermeldung: {data['message'][:500]}")
        return data

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        data = self._search(page)
        notices = data.get("notices") or []
        total = data.get("totalNoticeCount", 0)

        candidates: list[RawCandidate] = []
        for notice in notices:
            nd = notice.get("ND")
            if not nd:
                continue
            title = _de_or_first(notice.get("TI"))
            candidates.append(
                RawCandidate(
                    externe_id=nd,
                    detail_url=_direktlink(notice, nd),
                    titel_hint=title,
                    listen_metadaten={"notice": notice},
                )
            )

        has_more = page * PAGE_SIZE < total
        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        # Alle Felder liegen bereits aus der Listenseite vor (siehe Modul-Docstring) - kein
        # weiterer API-Call nötig.
        notice = candidate.listen_metadaten.get("notice", {})
        beschreibung = _de_or_first(notice.get("description-lot"))
        vergabestelle = _de_or_first(notice.get("buyer-name"))
        # Bekannte Einschränkung (verifiziert 04.09.2026): das Feld liefert der Such-Index für
        # einen Teil der Bekanntmachungen leer, auch wenn die zugehörige eForms-XML eine Frist
        # enthält (BT-131 EndDate). Kein Bug im Connector - angebotsfrist bleibt dann None, was
        # von Ranking/Sortierung bereits neutral behandelt wird; die Originalseite zeigt die Frist.
        fristen = notice.get("deadline-receipt-tender-date-lot") or []
        cpv = list(dict.fromkeys(notice.get("classification-cpv") or []))

        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": candidate.titel_hint,
                "volltext": beschreibung,
                "kurzbeschreibung": beschreibung,
                "vergabestelle": vergabestelle,
                "veroeffentlichungsdatum": notice.get("PD"),
                "angebotsfrist": fristen[0] if fristen else None,
                "cpv_codes": cpv,
                "verfahrensart": notice.get("notice-type"),
            },
        )


def _de_or_first(value) -> str | None:
    """TED liefert mehrsprachige Objekte ({"deu": [...], "eng": [...], ...}) - Deutsch

    bevorzugen, sonst erste verfügbare Sprache, sonst None. Werte sind Listen (meist mit
    genau einem Eintrag) oder bereits ein String."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for lang in ("deu", "eng"):
            if lang in value:
                v = value[lang]
                return v[0] if isinstance(v, list) else v
        for v in value.values():
            return v[0] if isinstance(v, list) else v
    return None


def _direktlink(notice: dict, nd: str) -> str:
    # Bevorzugt die Verfahrensseite auf der Vergabeplattform, auf der man sich informieren und
    # bewerben kann (Nutzerwunsch 25.09.2026); sonst die TED-Bekanntmachung selbst (vollständige
    # Bekanntmachung mit allen Angaben, nie ein bloßer Download).
    verfahrenslink = waehle_verfahrenslink(
        _als_liste(notice.get("submission-url-lot")), _als_liste(notice.get("document-url-lot"))
    )
    if verfahrenslink:
        return verfahrenslink
    links = notice.get("links") or {}
    html_direct = (links.get("htmlDirect") or {}).get("DEU") or (links.get("htmlDirect") or {}).get("ENG")
    if html_direct:
        return html_direct
    return f"https://ted.europa.eu/de/notice/-/detail/{nd}"


def _als_liste(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [u for v in value.values() for u in _als_liste(v)]
    return [u for u in value if isinstance(u, str)]
