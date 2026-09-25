"""Connector: Bekanntmachungsservice / Datenservice Öffentlicher Einkauf (Nutzeranfrage 05.09.2026:

"andere Wege finden, Portale zu implementieren" - offizielle Datenquellen statt Website-Scraping
für die zuvor blockierten Portale).

Verifiziert am 05.09.2026 gegen die echte API. Befund:

- Das Beschaffungsamt des BMI betreibt unter `oeffentlichevergabe.de` den zentralen
  "Bekanntmachungsservice" (Teil des "Datenservice Öffentlicher Einkauf") - eine offizielle,
  dokumentierte OpenData-REST-Schnittstelle (Swagger: `/documentation/swagger-ui/opendata/`),
  KEIN Scraping, kein robots.txt-Thema, kein Login. Endpunkt:
  `GET /api/notice-exports?pubDay=YYYY-MM-DD&format=csv.zip` liefert ein ZIP mit den an diesem
  Tag veröffentlichten Bekanntmachungen aus Bund, Ländern UND Kommunen als normalisierte,
  zusammenhängende CSV-Dateien (notice/organisation/purpose/classification/placeOfPerformance/...).
- WICHTIG (Mehrwert ggü. den bereits implementierten Connectoren): Diese Quelle bildet auch
  Bekanntmachungen von Vergabestellen ab, die intern eine der bewusst NICHT implementierten
  Plattformen nutzen (Kapitel 9.2) - stichprobenartig geprüft: Käufer mit
  `organisationInternetAddress`/`buyerProfileURL` auf `deutsche-evergabe.de` und zahlreiche
  Brandenburg-Vergabestellen tauchen im Datensatz auf. Das deckt einen Teil der dort gehosteten,
  EU-schwellenwertigen Bekanntmachungen ab, ohne die blockierten Portale selbst anzufragen.
- Umstellung 25.09.2026 (Nutzerrückmeldung: "viele falsch oder direkt Dokumente zum Download"):
  statt der vereinfachten CSV-Variante wird jetzt das vollständige eForms-XML-Export
  (`format=eforms.zip`, eine XML-Datei je Bekanntmachung) ausgewertet. Live-Befund an einem
  Tages-Export (1121 Bekanntmachungen): Die CSV-Variante enthielt
  1. ca. 35 % Bekanntmachungen, auf die man sich gar nicht bewerben kann (Zuschlagsmitteilungen
     "can-*", Vertragsänderungen, Vorinformationen) - jetzt nur noch Auftragsbekanntmachungen
     ("cn-*"), deren Angebotsfrist nicht schon abgelaufen ist;
  2. keinen Link auf das einzelne Verfahren (nur Homepage der Vergabestelle, bei der Hälfte gar
     nichts) - eForms enthält dagegen Abgabe-URL (BT-18) und Unterlagen-URL (BT-15), daraus
     wählt verfahrenslink.py die Verfahrensseite auf der Vergabeplattform (97 % der offenen
     Ausschreibungen, 0 PDF-Links; Bekanntmachungen ganz ohne verfahrensspezifischen Link werden
     ausgelassen statt auf eine allgemeine Seite zu zeigen);
  3. keine Angebotsfrist - eForms enthält sie (BT-131, bei ca. 87 %).
- Überschneidungen mit TED/DTVP (dieselbe EU-Ausschreibung über mehrere Quellen) fängt die
  portalübergreifende Duplikaterkennung ab.
"""
from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime, timedelta

import httpx
from lxml import etree

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.agents.connector.verfahrenslink import ist_dateidownload, waehle_verfahrenslink
from app.exceptions import TechnicalFailure

logger = logging.getLogger("ausschreibungscrawler.oeffentlichevergabe")

API_URL = "https://www.oeffentlichevergabe.de/api/notice-exports"


class OeffentlicheVergabeConnector(BaseConnector):
    slug = "oeffentlichevergabe"
    name = "Bekanntmachungsservice (Bund/Länder/Kommunen)"
    base_url = API_URL
    vorgegeben = False
    robots_status = "geprueft_ok"
    # Nutzeranfrage 05.09.2026: möglichst viele Ausschreibungen abbilden - 7 Tage zurück pro
    # Zyklus (ein einzelner Tag liegt bei Bund/Länder/Kommunen bereits bei 500-1000+
    # Bekanntmachungen). Ein Tages-ZIP ist bewusst granular (statt der riesigen Monats-ZIPs).
    # Einmal eingelesene Tage liefern beim nächsten Zyklus dieselben noticeIdentifier zurück,
    # die Duplikaterkennung (Kapitel 18) fängt das ab statt doppelte Tenders anzulegen.
    max_pages = 7
    tos_hinweis = (
        "Offizielle OpenData-REST-API des Beschaffungsamts des BMI (Datenservice Öffentlicher "
        "Einkauf), kein Scraping, kein Login. Dokumentiert unter "
        "/documentation/swagger-ui/opendata/."
    )

    def fetch_list_page(self, page: int) -> tuple[list[RawCandidate], bool]:
        tag = (datetime.utcnow().date() - timedelta(days=page))
        url = f"{API_URL}?pubDay={tag.isoformat()}&format=eforms.zip"

        self._respect_rate_limit()
        try:
            response = self.client.get(url)
        except httpx.HTTPError as exc:
            raise TechnicalFailure(f"Bekanntmachungsservice: HTTP-Fehler bei {tag}: {exc}") from exc
        if response.status_code >= 400:
            raise TechnicalFailure(f"Bekanntmachungsservice: HTTP {response.status_code} bei {tag}")

        notizen = _zip_zu_notizen(response.content, heute=datetime.utcnow())
        candidates = [
            RawCandidate(
                externe_id=f"{n['noticeIdentifier']}-{n['noticeVersion']}",
                detail_url=n["direktlink"],
                titel_hint=n["titel"],
                listen_metadaten=n,
            )
            for n in notizen
        ]
        return candidates, page < self.max_pages

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        # Alle Felder liegen bereits aus dem Tages-Export vor (siehe Modul-Docstring) - kein
        # weiterer HTTP-Request nötig.
        meta = candidate.listen_metadaten
        return RawDetail(
            externe_id=candidate.externe_id,
            detail_url=candidate.detail_url,
            felder={
                "titel": meta.get("titel"),
                "volltext": meta.get("beschreibung"),
                "kurzbeschreibung": meta.get("beschreibung"),
                "vergabestelle": meta.get("vergabestelle"),
                "ort_region": meta.get("ort_region"),
                "veroeffentlichungsdatum": meta.get("veroeffentlichungsdatum"),
                "verfahrensart": meta.get("verfahrensart"),
                "cpv_codes": meta.get("cpv_codes") or [],
                "angebotsfrist": meta.get("angebotsfrist"),
                "geschaetzter_wert": meta.get("geschaetzter_wert"),
                "dokumente_links": meta.get("dokumente_links") or [],
            },
        )


_VERFAHRENSARTEN = {
    "open": "Offenes Verfahren",
    "restricted": "Nicht offenes Verfahren",
    "neg-w-call": "Verhandlungsverfahren mit Teilnahmewettbewerb",
    "neg-wo-call": "Verhandlungsverfahren ohne Teilnahmewettbewerb",
    "comp-dial": "Wettbewerblicher Dialog",
    "innovation": "Innovationspartnerschaft",
    "comp-tend": "Wettbewerbliches Verfahren",
    "oth-single": "Sonstiges einstufiges Verfahren",
    "oth-mult": "Sonstiges mehrstufiges Verfahren",
}


def _zip_zu_notizen(zip_bytes: bytes, heute: datetime | None = None) -> list[dict]:
    """Liest ein eForms-Tages-ZIP und liefert nur bewerbbare Ausschreibungen mit Verfahrenslink."""
    notizen = []
    ausgelassen = {"kein_aufruf_zum_wettbewerb": 0, "frist_abgelaufen": 0, "kein_verfahrenslink": 0}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for dateiname in zf.namelist():
            if not dateiname.endswith(".xml"):
                continue
            try:
                wurzel = etree.fromstring(zf.read(dateiname))
            except etree.XMLSyntaxError:
                logger.warning("Bekanntmachungsservice: ungültiges XML %s übersprungen", dateiname)
                continue
            notiz, grund = _eforms_zu_notiz(wurzel, dateiname, heute)
            if notiz is None:
                ausgelassen[grund] += 1
            else:
                notizen.append(notiz)
    logger.info("Bekanntmachungsservice: %d übernommen, ausgelassen: %s", len(notizen), ausgelassen)
    return notizen


def _texte(knoten, pfad: str) -> list[str]:
    return [t.strip() for t in knoten.xpath(pfad) if isinstance(t, str) and t.strip()]


def _deutsch_oder_erstes(knoten, pfad: str) -> str | None:
    elemente = knoten.xpath(pfad)
    for element in elemente:
        if (element.get("languageID") or "").upper() in ("DEU", "GER") and (element.text or "").strip():
            return element.text.strip()
    for element in elemente:
        if (element.text or "").strip():
            return element.text.strip()
    return None


def _lokal(*namen: str) -> str:
    """XPath über lokale Elementnamen (eForms nutzt mehrere UBL-/eForms-Namensräume)."""
    return "/".join(f'*[local-name()="{n}"]' for n in namen)


def _ohne_zeitzone(datum: str, uhrzeit: str | None) -> str:
    # "2026-10-27+01:00" + "10:00:00+01:00" -> "2026-10-27T10:00:00" (naiv, wie alle anderen Felder)
    tag = datum[:10]
    zeit = (uhrzeit or "")[:8]
    return f"{tag}T{zeit}" if len(zeit) == 8 else tag


def _eforms_zu_notiz(wurzel, dateiname: str, heute: datetime | None) -> tuple[dict | None, str]:
    typ = (_texte(wurzel, "/*/" + _lokal("NoticeTypeCode") + "/text()") or [""])[0]
    if not typ.startswith("cn-"):
        return None, "kein_aufruf_zum_wettbewerb"

    fristen = sorted(
        _ohne_zeitzone(periode.xpath(_lokal("EndDate") + "/text()")[0], (periode.xpath(_lokal("EndTime") + "/text()") or [None])[0])
        for periode in wurzel.xpath("//" + _lokal("TenderSubmissionDeadlinePeriod"))
        if periode.xpath(_lokal("EndDate") + "/text()")
    )
    angebotsfrist = fristen[0] if fristen else None
    if angebotsfrist and heute and angebotsfrist[:10] < heute.date().isoformat():
        return None, "frist_abgelaufen"

    abgabe_urls = _texte(wurzel, "//" + _lokal("TenderRecipientParty", "EndpointID") + "/text()")
    unterlagen_urls = _texte(wurzel, "//" + _lokal("CallForTendersDocumentReference") + "//" + _lokal("URI") + "/text()")
    direktlink = waehle_verfahrenslink(abgabe_urls, unterlagen_urls)
    if not direktlink:
        return None, "kein_verfahrenslink"

    notice_id = (_texte(wurzel, "/*/" + _lokal("ID") + "/text()") or [dateiname.rsplit("-", 1)[0]])[0]
    version = (_texte(wurzel, "/*/" + _lokal("VersionID") + "/text()") or ["01"])[0]

    projekt = "/*/" + _lokal("ProcurementProject") + "/"
    los_projekt = "/*/" + _lokal("ProcurementProjectLot", "ProcurementProject") + "/"
    titel = _deutsch_oder_erstes(wurzel, projekt + _lokal("Name")) or _deutsch_oder_erstes(wurzel, los_projekt + _lokal("Name"))
    beschreibung = _deutsch_oder_erstes(wurzel, projekt + _lokal("Description")) or _deutsch_oder_erstes(
        wurzel, los_projekt + _lokal("Description")
    )

    kaeufer_id = (_texte(wurzel, "/*/" + _lokal("ContractingParty", "Party", "PartyIdentification", "ID") + "/text()") or [None])[0]
    vergabestelle = ort = None
    for firma in wurzel.xpath("//" + _lokal("Organization", "Company")):
        if kaeufer_id and kaeufer_id in _texte(firma, _lokal("PartyIdentification", "ID") + "/text()"):
            vergabestelle = _deutsch_oder_erstes(firma, _lokal("PartyName", "Name"))
            plz = (_texte(firma, _lokal("PostalAddress", "PostalZone") + "/text()") or [""])[0]
            stadt = (_texte(firma, _lokal("PostalAddress", "CityName") + "/text()") or [""])[0]
            ort = f"{plz} {stadt}".strip() or None
            break
    if vergabestelle is None:
        # Vereinfachte nationale Variante (unterschwellig): Name/Adresse direkt am Auftraggeber
        # statt über efac:Organizations referenziert.
        partei = wurzel.xpath("/*/" + _lokal("ContractingParty", "Party"))
        if partei:
            vergabestelle = _deutsch_oder_erstes(partei[0], _lokal("PartyName", "Name"))
            plz = (_texte(partei[0], _lokal("PostalAddress", "PostalZone") + "/text()") or [""])[0]
            stadt = (_texte(partei[0], _lokal("PostalAddress", "CityName") + "/text()") or [""])[0]
            ort = f"{plz} {stadt}".strip() or None
    if vergabestelle:
        vergabestelle = " ".join(vergabestelle.split())

    wert_text = (_texte(wurzel, projekt + _lokal("RequestedTenderTotal", "EstimatedOverallContractAmount") + "/text()") or [None])[0]
    try:
        geschaetzter_wert = float(wert_text) if wert_text else None
    except ValueError:
        geschaetzter_wert = None

    verfahren = (_texte(wurzel, "/*/" + _lokal("TenderingProcess", "ProcedureCode") + "/text()") or [""])[0]

    return {
        "noticeIdentifier": notice_id,
        "noticeVersion": version,
        "titel": titel or f"Bekanntmachung {notice_id[:8]}",
        "beschreibung": beschreibung,
        "vergabestelle": vergabestelle,
        "ort_region": ort,
        "veroeffentlichungsdatum": (
            (_texte(wurzel, "/*/" + _lokal("IssueDate") + "/text()") or _texte(wurzel, "/*/" + _lokal("RequestedPublicationDate") + "/text()") or [""])[0][:10]
            or None
        ),
        "angebotsfrist": angebotsfrist,
        "verfahrensart": _VERFAHRENSARTEN.get(verfahren, verfahren or None),
        "cpv_codes": list(dict.fromkeys(_texte(wurzel, "//" + _lokal("MainCommodityClassification", "ItemClassificationCode") + "/text()"))),
        "geschaetzter_wert": geschaetzter_wert,
        "dokumente_links": list(dict.fromkeys(u for u in unterlagen_urls if ist_dateidownload(u))),
        "direktlink": direktlink,
    }, ""
