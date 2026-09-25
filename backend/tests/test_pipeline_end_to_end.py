"""End-to-End-Test der vollständigen Agentenkette (Kapitel 19.3) mit einem Fake-Connector,

der zwei feste Kandidaten liefert - ohne echten Netzzugriff nachvollziehbar, dass
Discovery -> Analysis -> Normalization -> Duplicate -> Classification -> Ranking/Search
korrekt ineinandergreifen.
"""
from app import pipeline
from app.agents.connector import CONNECTORS
from app.agents.connector.base import BaseConnector, RawCandidate, RawDetail
from app.models import RankingScore, Tender


class _FakeConnector(BaseConnector):
    slug = "test-fake"
    name = "Fake-Portal"
    base_url = "https://example.invalid/"

    _DETAILS = {
        "1": {
            "titel": "KI-gestützte Dokumentenanalyse für die Verwaltung",
            "volltext": "Gesucht wird ein Anbieter für Machine Learning und Natural Language Processing.",
            "vergabestelle": "Testbehörde",
            "veroeffentlichungsdatum": "01.08.2026",
            "angebotsfrist": "30.09.2026",
        },
        "2": {
            "titel": "Lieferung von Büromöbeln",
            "volltext": "Beschaffung von Schreibtischen und Stühlen für ein Verwaltungsgebäude.",
            "vergabestelle": "Testbehörde",
            "veroeffentlichungsdatum": "01.08.2026",
            "angebotsfrist": "15.09.2026",
        },
    }

    def fetch_list_page(self, page: int):
        if page > 1:
            return [], False
        return [
            RawCandidate(externe_id="1", detail_url="https://example.invalid/1", titel_hint="A"),
            RawCandidate(externe_id="2", detail_url="https://example.invalid/2", titel_hint="B"),
        ], False

    def fetch_detail(self, candidate: RawCandidate) -> RawDetail:
        return RawDetail(externe_id=candidate.externe_id, detail_url=candidate.detail_url, felder=dict(self._DETAILS[candidate.externe_id]))


def test_vollstaendiger_durchlauf_erzeugt_klassifizierte_ausschreibungen(db):
    from app.models import Portal

    p = Portal(name="Fake-Portal", slug="test-fake", base_url="https://example.invalid/")
    db.add(p)
    db.commit()
    db.refresh(p)

    CONNECTORS[_FakeConnector.slug] = _FakeConnector
    try:
        ergebnis = pipeline.run_portal_cycle(db, p)
        assert ergebnis["job_status"] == "succeeded"

        tenders = db.query(Tender).filter(Tender.portal_id == p.id).all()
        assert len(tenders) == 2

        ki_tender = next(t for t in tenders if "Dokumentenanalyse" in t.titel)
        moebel_tender = next(t for t in tenders if "Büromöbeln" in t.titel)

        assert ki_tender.ki_relevanz_score == "stark"
        assert moebel_tender.ki_relevanz_score == "nicht"

        assert db.get(RankingScore, ki_tender.id) is not None
        assert ki_tender.angebotsfrist.month == 9 and ki_tender.angebotsfrist.day == 30

        # Zweiter Lauf mit identischen Daten darf keine Duplikate erzeugen (Kapitel 17.3 Idempotenz).
        ergebnis2 = pipeline.run_portal_cycle(db, p)
        assert ergebnis2["job_status"] == "succeeded"
        tenders_nach_zweitem_lauf = db.query(Tender).filter(Tender.portal_id == p.id).all()
        assert len(tenders_nach_zweitem_lauf) == 2
    finally:
        del CONNECTORS[_FakeConnector.slug]
