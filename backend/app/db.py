from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_IST_SQLITE = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _IST_SQLITE else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

if _IST_SQLITE:
    # WAL-Modus + grosszuegiger busy_timeout (Nutzeranfrage 05.09.2026: Portale beim
    # Aktualisieren-Button parallel statt sequenziell abarbeiten) - ohne WAL blockiert ein
    # SQLite-Schreibvorgang alle anderen Verbindungen sofort mit "database is locked"; mit WAL
    # koennen mehrere Threads gleichzeitig lesen waehrend einer schreibt, und busy_timeout laesst
    # konkurrierende Schreibzugriffe kurz warten statt sofort fehlzuschlagen.
    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (Modelle registrieren)

    Base.metadata.create_all(bind=engine)
