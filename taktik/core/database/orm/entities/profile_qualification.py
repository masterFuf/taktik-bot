"""ORM (Vague D) - SQLAlchemy mapping for the unified ``profile_qualification`` table.

Counterpart of front ``electron/database/orm/entities/ProfileQualificationEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, Integer, Text

from taktik.core.database.orm.base import Base


class ProfileQualification(Base):
    __tablename__ = "profile_qualification"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    profile_id = Column(Integer)
    username = Column(Text, nullable=False)
    has_ai = Column(Integer)
    has_taxonomy = Column(Integer)
    provider = Column(Text)
    model = Column(Text)
    criteria_hash = Column(Text)
    ai_niche = Column(Text)
    ai_specific_niche = Column(Text)
    ai_score = Column(Integer)
    ai_classification = Column(Text)
    ai_profession = Column(Text)
    ai_profession_tags = Column(Text)
    ai_gender = Column(Text)
    ai_age_group = Column(Text)
    ai_account_based_in = Column(Text)
    location_city = Column(Text)
    location_region = Column(Text)
    analysis_json = Column(Text)
    enrichment_source = Column(Text)
    enrichment_created_at = Column(Text)
    enrichment_updated_at = Column(Text)
    niche_slug = Column(Text)
    sub_niche_slug = Column(Text)
    account_type = Column(Text)
    market_scope = Column(Text)
    target_segments = Column(Text)
    confidence = Column(Float)
    raw_snapshot = Column(Text)
    taxonomy_source = Column(Text)
    taxonomy_created_at = Column(Text)
    taxonomy_updated_at = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)
    sync_id = Column(Text)
