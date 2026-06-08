"""ORM (Vague D) - SQLAlchemy mapping for the unified ``social_graph_sync`` table.

Counterpart of front ``electron/database/orm/entities/SocialGraphSyncEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class SocialGraphSync(Base):
    __tablename__ = "social_graph_sync"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    account_id = Column(Integer)
    username = Column(Text)
    direction = Column(Text)
    display_name = Column(Text)
    is_reciprocal = Column(Integer)
    followed_by_bot = Column(Integer)
    unfollowed_at = Column(Text)
    first_seen_at = Column(Text)
    last_seen_at = Column(Text)
    source = Column(Text)
