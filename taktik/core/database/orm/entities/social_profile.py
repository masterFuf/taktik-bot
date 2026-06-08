"""ORM (Vague D) - SQLAlchemy mapping for the unified ``social_profiles`` table.

Counterpart of front ``electron/database/orm/entities/SocialProfileEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class SocialProfile(Base):
    __tablename__ = "social_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    legacy_profile_id = Column(Integer)
    username = Column(Text, nullable=False)
    display_name = Column(Text)
    biography = Column(Text)
    followers_count = Column(Integer)
    following_count = Column(Integer)
    posts_count = Column(Integer)
    likes_count = Column(Integer)
    is_private = Column(Integer)
    is_verified = Column(Integer)
    is_business = Column(Integer)
    business_category = Column(Text)
    website = Column(Text)
    profile_pic_path = Column(Text)
    notes = Column(Text)
    account_based_in = Column(Text)
    date_joined = Column(Text)
    location_city = Column(Text)
    location_region = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)
    sync_id = Column(Text)
    ai_screenshot_path = Column(Text)
