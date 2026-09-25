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
- Bekannte Einschränkungen dieser CSV-Variante (bewusst nicht kompensiert, um keine falschen
  Daten zu erzeugen):
  1. Kein "Angebotsfrist"-Feld enthalten (nur Bindefrist/`tenderValidityDeadline` und
     `publicOpeningDate` = Termin der öffentlichen Angebotsöffnung, beides KEIN Ersatz für die
     Angebotsfrist selbst) - `angebotsfrist` bleibt bewusst leer, genau wie beim TED-Connector.
  2. Da viele Bekanntmachungen ohnehin EU-weit sind, gibt es wahrscheinlich Überschneidungen mit
     den TED-/DTVP-Datensätzen (dieselbe Ausschreibung über zwei Quellen, mit unterschiedlichen
     IDs) - die Duplikaterkennung (Kapitel 18) arbeitet je Portal, erkennt das also nicht als
     Duplikat. Bewusst in Kauf genommen (Nutzerentscheidung 05.09.2026): breite Abdeckung wichtiger
     als Deduplizierung über Portalgrenzen hinweg.
  3. Keine bestätigte, stabile Detailseiten-URL pro Bekanntmachung auf oeffentlichevergabe.de
     gefunden (probiert: `/notice/<id>`, `/api/notices/<id>` - beides ohne Treffer). `direktlink`
     verweist daher auf das Vergabestellen-Profil (`buyerProfileURL`/`organisationInternetAddress`),
     ersatzweise auf die offizielle Suchoberfläche - beides echte, funktionierende Seiten, auch
     wenn nicht exakt auf die einzelne Bekanntmachung gesprungen wird.
"""
from __future__ import annotations

import csv
import io
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta

import httpx

from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.exceptions import TechnicalFailure

API_URL = "https://www.oeffentlichevergabe.de/api/notice-exports"
SUCH_UI = "https://www.oeffentlichevergabe.de/ui/"


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
        url = f"{API_URL}?pubDay={tag.isoformat()}&format=csv.zip"

        self._respect_rate_limit()
        try:
            response = self.client.get(url)
        except httpx.HTTPError as exc:
            raise TechnicalFailure(f"Bekanntmachungsservice: HTTP-Fehler bei {tag}: {exc}") from exc
        if response.status_code >= 400:
            raise TechnicalFailure(f"Bekanntmachungsservice: HTTP {response.status_code} bei {tag}")

        notizen = _zip_zu_notizen(response.content)
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
                "verfahrensart": meta.get("noticeType"),
                "cpv_codes": meta.get("cpv_codes") or [],
            },
        )


def _zip_zu_notizen(zip_bytes: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        notice_rows = _lese_csv(zf, "notice.csv")
        organisation_rows = _lese_csv(zf, "organisation.csv")
        purpose_rows = _lese_csv(zf, "purpose.csv")
        classification_rows = _lese_csv(zf, "classification.csv")
        place_rows = _lese_csv(zf, "placeOfPerformance.csv")

    def schluessel(row: dict) -> tuple[str, str]:
        return (row["noticeIdentifier"], row["noticeVersion"])

    kaeufer: dict[tuple[str, str], dict] = {}
    for row in organisation_rows:
        if row.get("organisationRole") == "buyer" and schluessel(row) not in kaeufer:
            kaeufer[schluessel(row)] = row

    titel_je_notiz: dict[tuple[str, str], list[str]] = defaultdict(list)
    beschreibung_je_notiz: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in purpose_rows:
        k = schluessel(row)
        if row.get("title"):
            titel_je_notiz[k].append(row["title"])
        if row.get("description"):
            beschreibung_je_notiz[k].append(row["description"])

    cpv_je_notiz: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in classification_rows:
        code = row.get("mainClassificationCode")
        if code and code not in cpv_je_notiz[schluessel(row)]:
            cpv_je_notiz[schluessel(row)].append(code)

    ort_je_notiz: dict[tuple[str, str], str] = {}
    for row in place_rows:
        k = schluessel(row)
        if k not in ort_je_notiz:
            teile = [row.get("placePerformancePostCode"), row.get("placePerformanceCity")]
            ort_je_notiz[k] = " ".join(t for t in teile if t).strip()

    notizen = []
    for row in notice_rows:
        k = schluessel(row)
        kaeufer_row = kaeufer.get(k, {})
        titel = " | ".join(dict.fromkeys(titel_je_notiz.get(k, []))) or None
        beschreibung = "\n\n".join(dict.fromkeys(beschreibung_je_notiz.get(k, []))) or None
        vergabestelle = kaeufer_row.get("organisationName")
        direktlink = (
            kaeufer_row.get("buyerProfileURL")
            or kaeufer_row.get("organisationInternetAddress")
            or SUCH_UI
        )
        notizen.append(
            {
                "noticeIdentifier": row["noticeIdentifier"],
                "noticeVersion": row["noticeVersion"],
                "titel": titel or f"Bekanntmachung {row['noticeIdentifier'][:8]}",
                "beschreibung": beschreibung,
                "vergabestelle": vergabestelle,
                "ort_region": ort_je_notiz.get(k) or None,
                "veroeffentlichungsdatum": row.get("publicationDate"),
                "noticeType": row.get("noticeType"),
                "cpv_codes": cpv_je_notiz.get(k, []),
                "direktlink": direktlink,
            }
        )
    return notizen


def _lese_csv(zf: zipfile.ZipFile, dateiname: str) -> list[dict]:
    try:
        with zf.open(dateiname) as f:
            text = io.TextIOWrapper(f, encoding="utf-8")
            return list(csv.DictReader(text))
    except KeyError:
        return []
