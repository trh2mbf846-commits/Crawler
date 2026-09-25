from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import Boolean, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger("ausschreibungscrawler.db")

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


def _sqlite_synchronisiere_fehlende_spalten() -> None:
    """Ergänzt fehlende Spalten in bereits existierenden SQLite-Tabellen.

    `Base.metadata.create_all()` legt nur komplett fehlende Tabellen an, nie fehlende Spalten in
    bereits existierenden Tabellen. Live entdeckt 25.09.2026: eine persistente Dev-DB, die älter
    ist als spätere Modell-Erweiterungen dieser Session (z. B. `Tender.gemerkt`,
    `TenderDocument.volltext`), crasht dadurch mit `no such column`. Best-effort per ALTER TABLE -
    absichtlich nur additiv (nie ein DROP/RENAME), deshalb ohne Datenverlustrisiko.
    """
    inspector = inspect(engine)
    vorhandene_tabellen = set(inspector.get_table_names())
    with engine.begin() as connection:
        for tabelle in Base.metadata.sorted_tables:
            if tabelle.name not in vorhandene_tabellen:
                continue  # komplett neue Tabelle - übernimmt create_all()
            vorhandene_spalten = {spalte["name"] for spalte in inspector.get_columns(tabelle.name)}
            for spalte in tabelle.columns:
                if spalte.name in vorhandene_spalten:
                    continue
                spalten_typ = spalte.type.compile(dialect=engine.dialect)
                anweisung = f'ALTER TABLE "{tabelle.name}" ADD COLUMN "{spalte.name}" {spalten_typ}'
                if not spalte.nullable:
                    default = "0" if isinstance(spalte.type, Boolean) else "''"
                    anweisung += f" NOT NULL DEFAULT {default}"
                logger.info("Ergänze fehlende Spalte: %s", anweisung)
                connection.execute(text(anweisung))


def init_db() -> None:
    from app import models  # noqa: F401  (Modelle registrieren)

    Base.metadata.create_all(bind=engine)
    if _IST_SQLITE:
        _sqlite_synchronisiere_fehlende_spalten()
