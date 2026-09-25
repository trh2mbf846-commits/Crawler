"""Connector: Vergabeplattform Berlin / Vergabekooperation Berlin (u. a. für die BVG).

Verifiziert am 31.08.2026 gegen die echte Seite (Netzzugriff wurde in dieser Session
freigeschaltet). Befund:

- Keine robots.txt vorhanden (404) -> keine per robots.txt kommunizierten Einschränkungen.
  Die Nutzungsbedingungen (Teilnahmebedingungen) regeln ausschließlich die Teilnahme an
  Vergabeverfahren (Angebotsabgabe) nach Registrierung; das bloße Einsehen veröffentlichter
  Bekanntmachungen ist ausdrücklich ohne Registrierung möglich ("Anmelden" ist ein separater
  Menüpunkt, keine Zugriffsschranke für die öffentliche Suche). Kein Hinweis auf ein Verbot
  automatisierten Abrufs gefunden.
- Der von Vincent vorgegebene Einstiegslink (`LoginControllerServlet?function=CookiesCheckDone`)
  ist tatsächlich nur ein Cookie-Consent-Schritt, KEIN Bieter-Login - danach ist die
  öffentliche Bekanntmachungssuche voll nutzbar (System: Administration Intelligence AG,
  "NetServer"/AI Vergabemanager).
- Die öffentliche Ausschreibungssuche liegt unter `PublicationSearchControllerServlet` mit
  `Category=InvitationToTender` (server-seitig gerendertes HTML, Tabelle mit `data-oid` je
  Zeile), Pagination über `&Start=0/50/100/...` (50 Treffer/Seite, reine GET-Links).
- Die Detailseite wird clientseitig über eine kleine POST-Anfrage an `DataProvider`
  (`param=Redirect&OID=<data-oid>&function=Detail&category=InvitationToTender`) aufgelöst,
  liefert aber deterministisch immer `PublicationControllerServlet?function=Detail&TOID=<oid>
  &Category=InvitationToTender` zurück - dieser Connector baut die URL daher direkt, ohne den
  zusätzlichen POST-Roundtrip.
- Detailseite ist vollständig öffentlich, inkl. Vergabeunterlagen ("Die Auftragsunterlagen
  stehen für einen uneingeschränkten und vollständigen direkten Zugang gebührenfrei zur
  Verfügung") - keine Zugriffsschranke im Sinne von Abschnitt 9.2 gefunden.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure

BASE_URL = "https://vergabekooperation.berlin/NetServer/"
ENTRY_URL = BASE_URL + "LoginControllerServlet?function=CookiesCheckDone"
SEARCH_URL = BASE_URL + "PublicationSearchControllerServlet"
DETAIL_URL = BASE_URL + "PublicationControllerServlet"
PAGE_SIZE = 50

_ROW_SELECTOR = "tr.tableRow.clickable-row.publicationDetail[data-oid]"


class VergabekooperationBerlinConnector(BaseConnector):
    slug = "vergabekooperation-berlin"
    name = "Vergabeplattform Berlin (Vergabekooperation Berlin)"
    base_url = BASE_URL
    vorgegeben = True
    robots_status = "geprueft_ok"
    tos_hinweis = (
        "Keine robots.txt vorhanden (404, geprüft 31.08.2026). Teilnahmebedingungen "
        "verlangen Registrierung nur für die Angebotsabgabe, nicht für das Einsehen "
        "öffentlicher Bekanntmachungen. Kein Hinweis auf Verbot automatisierten Abrufs."
    )

    def _session_ready(self) -> bool:
        return getattr(self, "_cookie_established", False)

    def _ensure_session(self) -> None:
        if self._session_ready():
            return
        self.polite_get(ENTRY_URL)
        self._cookie_established = True

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        self._ensure_session()

        start = (page - 1) * PAGE_SIZE
        url = (
            f"{SEARCH_URL}?function=SearchPublications&Category=InvitationToTender"
            f"&Gesetzesgrundlage=All&Start={start}&thContext=publications"
        )
        response = self.polite_get(url)
        soup = BeautifulSoup(response.text, "lxml")

        rows = soup.select(_ROW_SELECTOR)
        if not rows and page == 1:
            if soup.select_one("table.tableHorizontalHeader") is None:
                raise TechnicalFailure(
                    "Vergabeplattform Berlin: Ergebnistabelle nicht gefunden - "
                    "Seitenstruktur hat sich vermutlich geändert (Cookie-Consent-Schritt prüfen)."
                )
            # echte 0-Treffer-Situation - vom Source-Health-Monitoring überwacht (Kapitel 21.3)

        candidates: list[RawCandidate] = []
        for row in rows:
            oid = row.get("data-oid")
            if not oid:
                continue
            tds = row.find_all("td")
            tender_type_cells = row.select("td.tenderType")
            titel_el = row.select_one("td.tender")
            vergabestelle_el = row.select_one("td.tenderAuthority")
            frist_el = row.select_one("td.tenderDeadline")
            candidates.append(
                RawCandidate(
                    externe_id=oid,
                    detail_url=f"{DETAIL_URL}?function=Detail&TOID={oid}&Category=InvitationToTender",
                    titel_hint=(titel_el or (tds[1] if len(tds) > 1 else None)).get_text(strip=True)
                    if (titel_el or len(tds) > 1) else None,
                    listen_metadaten={
                        "veroeffentlichungsdatum": tds[0].get_text(strip=True) if tds else None,
                        "vergabestelle": vergabestelle_el.get_text(strip=True) if vergabestelle_el else None,
                        "verfahrensart": tender_type_cells[0].get_text(strip=True) if tender_type_cells else None,
                        "angebotsfrist": frist_el.get_text(strip=True) if frist_el else None,
                    },
                )
            )

        has_more = soup.select_one('a[title="Next Page"]') is not None
        return candidates, has_more

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        self._ensure_session()
        response = self.polite_get(candidate.detail_url)
        soup = BeautifulSoup(response.text, "lxml")

        area = soup.select_one("#printarea") or soup
        volltext = re.sub(r"\s+", " ", area.get_text(" ", strip=True)).strip()

        geschaetzter_wert = _extract(r"Geschätzter Wert ohne MwSt\. \(in Euro\):\s*([\d.,]+)", volltext)
        cpv = _extract(r"CPV-Code Hauptteil:\s*([\d-]+)", volltext)
        # Die "Beschreibung:"-Klausel liegt in einer verschachtelten Tabelle mitten im Dokument;
        # ohne gezielte Extraktion würde kurzbeschreibung sonst mit der Navigations-/
        # Kopfzeilen-Boilerplate vom Seitenanfang beginnen (siehe Normalization-Fallback).
        kurzbeschreibung = _extract(
            r"Beschreibung:\s*(.*?)(?:\s*Art des Auftrags:|\s*Umfang der Auftragsvergabe|\s*Hauptklassifizierung|\s*$)",
            volltext,
        )

        dokumente_links = [
            a["href"] if a["href"].startswith("http") else BASE_URL + a["href"].lstrip("/")
            for a in area.select("a[href]")
            if "TenderingProcedureDetails" in a.get("href", "") or "Unterlagen" in a.get_text()
        ]

        meta = candidate.listen_metadaten
        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": candidate.titel_hint,
                "volltext": volltext,
                "kurzbeschreibung": kurzbeschreibung,
                "vergabestelle": meta.get("vergabestelle"),
                "verfahrensart": meta.get("verfahrensart"),
                "veroeffentlichungsdatum": meta.get("veroeffentlichungsdatum"),
                "angebotsfrist": meta.get("angebotsfrist"),
                "geschaetzter_wert": geschaetzter_wert,
                "cpv_codes": [cpv] if cpv else [],
                "dokumente_links": list(dict.fromkeys(dokumente_links)),
            },
        )


def _extract(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None
