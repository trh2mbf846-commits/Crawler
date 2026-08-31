from app.agents.connector.base import BaseConnector
from app.agents.connector.db_bieterportal import DbBieterportalConnector
from app.agents.connector.itdz_berlin import ItdzBerlinConnector
from app.agents.connector.vergabekooperation_berlin import VergabekooperationBerlinConnector

CONNECTORS: dict[str, type[BaseConnector]] = {
    ItdzBerlinConnector.slug: ItdzBerlinConnector,
    DbBieterportalConnector.slug: DbBieterportalConnector,
    VergabekooperationBerlinConnector.slug: VergabekooperationBerlinConnector,
}

__all__ = ["BaseConnector", "CONNECTORS"]
