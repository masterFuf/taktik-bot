"""ORM pilot (Vague D) - SQLAlchemy engine factory.

INVARIANTS (shared dual-runtime SQLite + Turso sync):
  - The ORM MAPS existing tables only. NEVER call ``Base.metadata.create_all`` -
    the schema is owned by the physical migrations. (Equivalent of TypeORM's
    ``synchronize: false`` on the front side.)
  - Not wired into the bot runtime yet. Exercised only by the standalone parity
    validator (``bot/scripts/orm_pilot/validate_app_config.py``) against a COPY
    of the real DB.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_orm_engine(db_path: str) -> Engine:
    """Create a read-mapping SQLAlchemy engine over an existing SQLite file.

    The caller must never run DDL through this engine on the shared base.
    """
    return create_engine(f"sqlite:///{db_path}", future=False)
