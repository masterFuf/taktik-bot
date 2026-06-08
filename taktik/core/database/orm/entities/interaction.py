"""ORM (Vague D) - SQLAlchemy mapping for the unified ``interactions`` table.

Counterpart of front ``electron/database/orm/entities/InteractionEntity.ts``.
A Turso-synced, platform-keyed table. Mapping only; the schema stays owned by the
migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    legacy_id = Column(Integer, nullable=True)
    session_id = Column(Integer, nullable=True)
    account_id = Column(Integer, nullable=True)
    profile_id = Column(Integer, nullable=True)
    interaction_type = Column(Text, nullable=False)
    success = Column(Integer, nullable=True)
    content = Column(Text, nullable=True)
    video_id = Column(Text, nullable=True)
    interaction_time = Column(Text, nullable=True)
    created_at = Column(Text, nullable=True)
    sync_id = Column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Interaction id={self.id} type={self.interaction_type!r}>"
