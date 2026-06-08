"""ORM (Vague D) - SQLAlchemy mapping for the unified ``sessions_unified`` table.

Counterpart of front ``electron/database/orm/entities/SessionUnifiedEntity.ts``.
Mapping only - the schema stays owned by the migrations.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, Integer, Text

from taktik.core.database.orm.base import Base


class SessionUnified(Base):
    __tablename__ = "sessions_unified"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Text, nullable=False)
    legacy_session_id = Column(Integer)
    account_id = Column(Integer)
    session_name = Column(Text)
    target_type = Column(Text)
    workflow_type = Column(Text)
    target = Column(Text)
    start_time = Column(Text)
    end_time = Column(Text)
    duration_seconds = Column(Integer)
    config_used = Column(Text)
    status = Column(Text)
    error_message = Column(Text)
    synced_to_api = Column(Integer)
    ai_total_cost_usd = Column(Float)
    ai_profiles_analyzed = Column(Integer)
    ai_posts_analyzed = Column(Integer)
    ai_comments_generated = Column(Integer)
    stats_total_interactions = Column(Integer)
    stats_likes = Column(Integer)
    stats_follows = Column(Integer)
    stats_unfollows = Column(Integer)
    stats_comments = Column(Integer)
    stats_story_views = Column(Integer)
    stats_story_likes = Column(Integer)
    stats_profile_visits = Column(Integer)
    profiles_visited = Column(Integer)
    posts_watched = Column(Integer)
    likes = Column(Integer)
    follows = Column(Integer)
    favorites = Column(Integer)
    comments = Column(Integer)
    shares = Column(Integer)
    errors = Column(Integer)
    videos_watched = Column(Integer)
    created_at = Column(Text)
    updated_at = Column(Text)
    sync_id = Column(Text)
