"""Prüft den zentralen Grundsatz aus Abschnitt 9.2/17.2: eine echte Zugriffsschranke wird

eskaliert statt umgangen, und sie blockiert nur den betroffenen Job/das betroffene Portal -
alle übrigen Portale laufen unbeeinflusst weiter (Kapitel 17.2, 9.4).
"""
from app import pipeline, queue
from app.agents.connector import CONNECTORS
from app.agents.connector.base import BaseConnector
from app.exceptions import AccessBlocked
from app.models import Escalation, Job, Portal


class _LoginWallConnector(BaseConnector):
    slug = "test-loginwall"
    name = "Test-Portal mit Login-Schranke"
    base_url = "https://example.invalid/"

    def fetch_list_page(self, page: int):
        raise AccessBlocked(
            "login_erforderlich", "Testfall: echtes Bieterkonto erforderlich.",
            ["Nur Metadaten erfassen", "Bieterkonto bereitstellen"], empfehlung="Nur Metadaten erfassen",
        )

    def fetch_detail(self, candidate):  # pragma: no cover - im Testfall nicht erreicht
        raise NotImplementedError


def test_zugriffsschranke_wird_eskaliert_nicht_umgangen(db):
    portal = Portal(name="Login-Test-Portal", slug="test-loginwall", base_url="https://example.invalid/")
    anderes_portal = Portal(name="Normales Portal", slug="test-normal", base_url="https://example.invalid/2")
    db.add_all([portal, anderes_portal])
    db.commit()
    db.refresh(portal)
    db.refresh(anderes_portal)

    CONNECTORS[_LoginWallConnector.slug] = _LoginWallConnector
    try:
        job = queue.enqueue(db, "discovery", portal_id=portal.id, payload={})
        pipeline.process_job(db, job)

        db.refresh(job)
        assert job.status == "waiting_for_decision"

        eskalationen = db.query(Escalation).filter(Escalation.job_id == job.id).all()
        assert len(eskalationen) == 1
        assert eskalationen[0].kategorie == "login_erforderlich"
        assert eskalationen[0].status == "offen"

        # anderes Portal ist von der Eskalation komplett unberührt (Kapitel 17.2 Kernprinzip).
        andere_jobs = db.query(Job).filter(Job.portal_id == anderes_portal.id).all()
        assert andere_jobs == []
    finally:
        del CONNECTORS[_LoginWallConnector.slug]


def test_technischer_fehler_wird_automatisch_wiederholt(db, portal):
    class _FlakyConnector(BaseConnector):
        slug = portal.slug
        name = "Flaky"
        base_url = "https://example.invalid/"
        aufrufe = 0

        def fetch_list_page(self, page: int):
            from app.exceptions import TechnicalFailure

            _FlakyConnector.aufrufe += 1
            raise TechnicalFailure("Simulierter Timeout")

        def fetch_detail(self, candidate):  # pragma: no cover
            raise NotImplementedError

    CONNECTORS[portal.slug] = _FlakyConnector
    try:
        queue.enqueue(db, "discovery", portal_id=portal.id, payload={}, max_versuche=3)
        job = None
        for _ in range(3):
            job = queue.claim_next(db, "discovery")
            assert job is not None
            pipeline.process_job(db, job)
            db.refresh(job)
            if job.status == "failed":
                break

        assert job.status == "failed"
        assert job.versuch_nr == 3
        assert _FlakyConnector.aufrufe == 3
    finally:
        del CONNECTORS[portal.slug]
