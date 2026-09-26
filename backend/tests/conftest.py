import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="ausschreibungscrawler-test-")
os.environ["CRAWLER_DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
# Tests dürfen nie ein echtes, lokal laufendes Ollama ansprechen - Ollama-Tests setzen den
# Anbieter gezielt und nutzen einen httpx.MockTransport (siehe test_assistant_ollama.py).
os.environ["CRAWLER_KEVIN_ANBIETER"] = "anthropic"
os.environ["CRAWLER_OLLAMA_URL"] = "http://127.0.0.1:9"  # nie ein echtes, lokal laufendes Ollama

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Portal  # noqa: E402


@pytest.fixture(autouse=True)
def _kein_hintergrund_nachlauf(monkeypatch):
    # KI-Nachprüfung/Benachrichtigung nach einem Lauf startet sonst einen Thread, der parallel zum
    # Zurücksetzen der Test-DB auf sie zugreift. Getestet wird sie direkt (test_ausbau_*.py).
    from app import nachlauf

    monkeypatch.setattr(nachlauf, "starte_im_hintergrund", lambda: None)
    from app import themen
    from app.api import themen as themen_api

    monkeypatch.setattr(themen, "ordne_im_hintergrund_neu_ein", lambda: None)
    monkeypatch.setattr(themen_api, "ordne_im_hintergrund_neu_ein", lambda: None)


@pytest.fixture(autouse=True)
def _reset_db():
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def portal(db):
    p = Portal(name="Test-Portal", slug="test-portal", base_url="https://example.invalid/")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p
