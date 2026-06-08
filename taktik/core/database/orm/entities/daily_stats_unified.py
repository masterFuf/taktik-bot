"""ORM (Vague D) - SQLAlchemy mapping for the unified ``daily_stats_unified`` table.

Counterpart of front ``electron/database/orm/entities/DailyStatsUnifiedEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, Text

from taktik.core.database.orm.base import Base


class DailyStatsUnified(Base):
    __tablename__ = "daily_stats_unified"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    account_id = Column(Integer)
    date = Column(Text)
    total_likes = Column(Integer)
    total_follows = Column(Integer)
    total_unfollows = Column(Integer)
    total_comments = Column(Integer)
    total_profile_visits = Column(Integer)
    total_story_views = Column(Integer)
    total_story_likes = Column(Integer)
    total_favorites = Column(Integer)
    total_shares = Column(Integer)
    total_posts_watched = Column(Integer)
    total_sessions = Column(Integer)
    completed_sessions = Column(Integer)
    failed_sessions = Column(Integer)
    total_duration_seconds = Column(Integer)
    synced_to_api = Column(Integer)
    synced_at = Column(Text)
    created_at = Column(Text)
    updated_at = Column(Text)
