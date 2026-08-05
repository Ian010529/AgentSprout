from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_sqlite_engine(settings: Settings) -> Engine:
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    def configure_sqlite(dbapi_connection: DBAPIConnection, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    event.listen(engine, "connect", configure_sqlite)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
