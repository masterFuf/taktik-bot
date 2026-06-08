"""ORM (Vague D) - SQLAlchemy mapping for the unified ``accounts`` table.

Counterpart of front ``electron/database/orm/entities/AccountEntity.ts``. Mapping
only - the schema stays owned by the migrations (the engine never runs DDL).
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    legacy_account_id = Column(Integer)
    username = Column(Text, nullable=False)
    is_bot = Column(Integer)
    user_id = Column(Integer)
    license_id = Column(Integer)
    display_name = Column(Text)
    qualification_prompt = Column(Text)
    bio = Column(Text)
    niche = Column(Text)
    product_service = Column(Text)
    objective = Column(Text)
    target_audience = Column(Text)
    tone_personality = Column(Text)
    preferred_language = Column(Text)
    website = Column(Text)
    unique_selling_point = Column(Text)
    custom_context = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)
    sync_id = Column(Text)
