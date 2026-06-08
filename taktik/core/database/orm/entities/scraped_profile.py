"""ORM (Vague D) - SQLAlchemy mapping for the unified ``scraped_profiles`` table.

Counterpart of front ``electron/database/orm/entities/ScrapedProfileEntity.ts``.
Mapping only - the schema stays owned by the migrations. (This is the N:M junction
scraping_session<->social_profile; the profile data lives in ``social_profiles``.)
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class ScrapedProfile(Base):
    __tablename__ = "scraped_profiles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    scraping_id = Column(Integer)
    profile_id = Column(Integer)
    scraped_at = Column(Text)
    is_enriched = Column(Integer)
    ai_score = Column(Integer)
    ai_qualified = Column(Integer)
    ai_analysis = Column(Text)
    qualification_criteria = Column(Text)
    scored_at = Column(Text)
    source_post_url = Column(Text)
