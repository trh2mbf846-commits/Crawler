"""Nur bewerbbare Ausschreibungen mit Link auf die konkrete Verfahrensseite (Nutzerrückmeldung
25.09.2026: "viele falsch oder direkt Dokumente zum Download")."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timedelta

from app.agents.connector.oeffentlichevergabe import _zip_zu_notizen
from app.agents.connector.ted import _direktlink
from app.agents.connector.verfahrenslink import ist_verfahrensspezifisch, waehle_verfahrenslink
from app.bereinigung import bereinige_unbrauchbare_ausschreibungen
from app.models import Portal, Tender
from app.tender_queries import search_tenders

# --- Linkauswahl ----------------------------------------------------------------------------


def test_verfahrensseiten_werden_erkannt():
    for url in [
        "https://www.dtvp.de/Satellite/notice/CXVHYDPYTWTKMJPL",
        "https://www.evergabe-online.de/tenderdetails.html?id=890720",
        "https://www.subreport.de/E59965491",
        "https://vergabekooperation.berlin/NetServer/TenderingProcedureDetails?function=_Details&TenderOID=54321-Tender-19b01b86d8b",
    ]:
        assert ist_verfahrensspezifisch(url), url


def test_startseiten_und_downloads_werden_abgelehnt():
    for url in [
        "https://www.meinauftrag.rib.de",
        "https://vergabekooperation.berlin/NetServer/",
        "https://vergabeplattform.stadt-koeln.de/NetServer/ParticipationControllerServlet",
        "https://www.subreport-elvis.de/download/bund/E73523792/1790079442572/bekanntmachung.pdf",
        "https://example.org/unterlagen/leistungsbeschreibung.pdf",
        "121002165",
        "www.sachsenenergie.de/AVA",
    ]:
        assert not ist_verfahrensspezifisch(url), url


def test_abgabelink_vor_unterlagenlink_und_startseite_wird_uebersprungen():
    assert waehle_verfahrenslink(
        ["https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX"], ["https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX/documents"]
    ) == "https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX"
    assert waehle_verfahrenslink(
        ["https://www.had.de"], ["https://www.had.de/NetServer/TenderingProcedureDetails?function=_Details&TenderOID=54321-Tender-1"]
    ).startswith("https://www.had.de/NetServer/TenderingProcedureDetails")


def test_subreport_pdf_wird_auf_verfahrensseite_umgeschrieben():
    pdf = "https://www.subreport-elvis.de/download/bund/E73523792/1790079442572/bekanntmachung.pdf"
    assert waehle_verfahrenslink([], [pdf]) == "https://www.subreport.de/E73523792"


def test_ohne_verfahrenslink_none():
    assert waehle_verfahrenslink(["https://www.swm.de"], ["121002165"]) is None


def test_ted_nutzt_plattformlink_sonst_ted_seite():
    notice = {
        "submission-url-lot": ["https://www.dtvp.de/Satellite/notice/CXP4YHYMG3X"],
        "document-url-lot": ["https://www.dtvp.de/Satellite/notice/CXP4YHYMG3X/documents"],
    }
    assert _direktlink(notice, "533573-2026") == "https://www.dtvp.de/Satellite/notice/CXP4YHYMG3X"
    assert _direktlink({"submission-url-lot": ["https://www.meinauftrag.rib.de"]}, "1-2026") == (
        "https://ted.europa.eu/de/notice/-/detail/1-2026"
    )


# --- Bekanntmachungsservice (eForms) --------------------------------------------------------

_KOPF = (
    '<ContractNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2" '
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
)


def _eforms(typ="cn-standard", frist="2026-10-27+01:00", abgabe="", unterlagen="", kaeufer_direkt=True):
    return (
        f"{_KOPF}<cbc:ID schemeName=\"notice-id\">abc-123</cbc:ID><cbc:VersionID>01</cbc:VersionID>"
        f"<cbc:IssueDate>2026-09-21+02:00</cbc:IssueDate><cbc:NoticeTypeCode>{typ}</cbc:NoticeTypeCode>"
        + (
            "<cac:ContractingParty><cac:Party><cac:PartyName><cbc:Name>Landkreis\n Neunkirchen</cbc:Name></cac:PartyName>"
            "<cac:PostalAddress><cbc:CityName>Ottweiler</cbc:CityName><cbc:PostalZone>66564</cbc:PostalZone></cac:PostalAddress>"
            "</cac:Party></cac:ContractingParty>"
            if kaeufer_direkt else ""
        )
        + "<cac:TenderingProcess><cbc:ProcedureCode>open</cbc:ProcedureCode></cac:TenderingProcess>"
        "<cac:ProcurementProject><cbc:Name languageID=\"ENG\">KI platform</cbc:Name>"
        "<cbc:Name languageID=\"DEU\">KI-Plattform</cbc:Name><cbc:Description languageID=\"DEU\">Beschreibung</cbc:Description>"
        "<cac:MainCommodityClassification><cbc:ItemClassificationCode>72000000</cbc:ItemClassificationCode></cac:MainCommodityClassification>"
        "</cac:ProcurementProject><cac:ProcurementProjectLot><cac:TenderingTerms>"
        + (f"<cac:CallForTendersDocumentReference><cac:Attachment><cac:ExternalReference><cbc:URI>{unterlagen}</cbc:URI>"
           "</cac:ExternalReference></cac:Attachment></cac:CallForTendersDocumentReference>" if unterlagen else "")
        + (f"<cac:TenderRecipientParty><cbc:EndpointID>{abgabe}</cbc:EndpointID></cac:TenderRecipientParty>" if abgabe else "")
        + "</cac:TenderingTerms><cac:TenderingProcess>"
        + (f"<cac:TenderSubmissionDeadlinePeriod><cbc:EndDate>{frist}</cbc:EndDate><cbc:EndTime>10:00:00+01:00</cbc:EndTime>"
           "</cac:TenderSubmissionDeadlinePeriod>" if frist else "")
        + "</cac:TenderingProcess></cac:ProcurementProjectLot></ContractNotice>"
    )


def _zip(**dateien: str) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as zf:
        for name, inhalt in dateien.items():
            zf.writestr(f"{name}.xml", inhalt)
    return puffer.getvalue()


def test_eforms_nur_offene_ausschreibungen_mit_verfahrenslink():
    link = "https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX"
    notizen = _zip_zu_notizen(
        _zip(
            gut=_eforms(abgabe=link, unterlagen=link + "/documents"),
            zuschlag=_eforms(typ="can-standard", abgabe=link),
            abgelaufen=_eforms(frist="2026-08-01+02:00", abgabe=link),
            ohne_link=_eforms(abgabe="https://www.meinauftrag.rib.de"),
        ),
        heute=datetime(2026, 9, 25),
    )

    assert len(notizen) == 1
    n = notizen[0]
    assert n["direktlink"] == link
    assert n["titel"] == "KI-Plattform"  # deutsche Fassung bevorzugt
    assert n["vergabestelle"] == "Landkreis Neunkirchen"  # Whitespace normalisiert
    assert n["ort_region"] == "66564 Ottweiler"
    assert n["angebotsfrist"] == "2026-10-27T10:00:00"
    assert n["verfahrensart"] == "Offenes Verfahren"
    assert n["veroeffentlichungsdatum"] == "2026-09-21"
    assert n["cpv_codes"] == ["72000000"]


def test_eforms_pdf_landet_in_dokumenten_nicht_im_direktlink():
    pdf = "https://www.subreport-elvis.de/download/bund/E73523792/1790079442572/bekanntmachung.pdf"
    (n,) = _zip_zu_notizen(_zip(a=_eforms(unterlagen=pdf)), heute=datetime(2026, 9, 25))
    assert n["direktlink"] == "https://www.subreport.de/E73523792"
    assert n["dokumente_links"] == [pdf]


# --- Übersicht zeigt standardmäßig nur offene -----------------------------------------------


def _tender(db, portal, titel, **felder):
    t = Tender(portal_id=portal.id, titel=titel, direktlink="https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX",
               dedupe_hash=titel, **felder)
    db.add(t)
    db.commit()
    return t


def test_standardsuche_nur_offene_alle_zeigt_alles(db, portal):
    _tender(db, portal, "offen", angebotsfrist=datetime.now() + timedelta(days=5))
    _tender(db, portal, "ohne frist")
    _tender(db, portal, "frist vorbei", angebotsfrist=datetime.now() - timedelta(days=1))
    _tender(db, portal, "abgelaufen", status="abgelaufen")
    _tender(db, portal, "vergeben", status="vergeben")

    offen, _ = search_tenders(db)
    alle, _ = search_tenders(db, status="alle")
    assert {t.titel for t in offen} == {"offen", "ohne frist"}
    assert len(alle) == 5


# --- Bereinigung alter Datensätze -----------------------------------------------------------


def test_bereinigung_entfernt_zuschlaege_und_homepage_links_behaelt_gemerkte(db):
    ov = Portal(name="Bekanntmachungsservice", slug="oeffentlichevergabe", base_url="https://x.invalid/")
    ted = Portal(name="TED", slug="ted", base_url="https://y.invalid/")
    andere = Portal(name="DTVP", slug="dtvp", base_url="https://z.invalid/")
    db.add_all([ov, ted, andere])
    db.commit()
    verfahren = "https://www.dtvp.de/Satellite/notice/CXP4YLPMVFX"
    _tender(db, ted, "ted zuschlag", verfahrensart="can-standard")
    _tender(db, ted, "ted offen", verfahrensart="cn-standard")
    _tender(db, ov, "ov offen neu", verfahrensart="Offenes Verfahren")
    t = _tender(db, ov, "ov homepage", verfahrensart="cn-standard")
    t.direktlink = "https://www.bghw.de"
    g = _tender(db, ov, "ov gemerkt", verfahrensart="can-standard", gemerkt=True)
    _tender(db, andere, "dtvp", verfahrensart="can-standard")
    db.commit()

    assert bereinige_unbrauchbare_ausschreibungen(db) == 2
    uebrig = {t.titel for t in db.query(Tender).all()}
    assert uebrig == {"ted offen", "ov offen neu", "ov gemerkt", "dtvp"}
    assert g.direktlink == verfahren
    assert bereinige_unbrauchbare_ausschreibungen(db) == 0  # idempotent
