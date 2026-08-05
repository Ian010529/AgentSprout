from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def migrations_are_current(engine: Engine) -> bool:
    return current_revision(engine) == head_revision()
