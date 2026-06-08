"""ORM (Vague D) - SQLAlchemy mapping for the unified ``app_config`` table.

Counterpart of front ``electron/database/orm/entities/AppConfigEntity.ts``.
``app_config`` is Electron-owned, local-only (NOT Turso-synced), key/value.
Explicit mapping only; the schema is owned by the migrations, never by the ORM.
"""
from __future__ import annotations

from sqlalchemy import Column, Text

from taktik.core.database.orm.base import Base


class AppConfig(Base):
    __tablename__ = "app_config"

    key = Column(Text, primary_key=True)
    value_json = Column(Text)
    updated_at = Column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AppConfig key={self.key!r}>"
