"""ORM (Vague D) - SQLAlchemy mapping for the unified ``filtered_profiles`` table.

Counterpart of front ``electron/database/orm/entities/FilteredProfileEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class FilteredProfile(Base):
    __tablename__ = "filtered_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    profile_id = Column(Integer)
    account_id = Column(Integer)
    username = Column(Text)
    filtered_at = Column(Text)
    reason = Column(Text)
    source_type = Column(Text)
    source_name = Column(Text)
    session_id = Column(Integer)
    sync_id = Column(Text)
