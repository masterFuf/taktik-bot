"""ORM pilot (Vague D) - SQLAlchemy engine factory.

INVARIANTS (shared dual-runtime SQLite + Turso sync):
  - The ORM MAPS existing tables only. NEVER call ``Base.metadata.create_all`` -
    the schema is owned by the physical migrations. (Equivalent of TypeORM's
    ``synchronize: false`` on the front side.)
  - ``LocalDatabaseService`` opens it at start and hands it to the repositories, which read
    through its pooled connection (``query_orm_first``); the parity validator
    (``taktik-bot/core/scripts/dev/orm_pilot/validate_entities.py``) runs it against a COPY
    of the real DB.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_orm_engine(db_path: str) -> Engine:
    """Create a read-mapping SQLAlchemy engine over an existing SQLite file.

    The caller must never run DDL through this engine on the shared base. SQLAlchemy 2.0 (the
    first with wheels for Python 3.13 and 3.14) refuses ``future=False``, the 1.4 default this
    call used to spell out.
    """
    return create_engine(f"sqlite:///{db_path}")
