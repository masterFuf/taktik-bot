"""ORM entity layer (Vague D) - one mapped table per module.

Mirror of the front ``electron/database/orm/entities/*.ts`` layout: one file per
entity instead of a flat ``unified_models.py``. Mapping only - the schema is owned
by the physical migrations (the engine never runs DDL). This barrel re-exports every
entity so the registry / consumers import from a single stable surface.
"""
from __future__ import annotations

from taktik.core.database.orm.entities.account import Account
from taktik.core.database.orm.entities.app_config import AppConfig
from taktik.core.database.orm.entities.daily_stats_unified import DailyStatsUnified
from taktik.core.database.orm.entities.filtered_profile import FilteredProfile
from taktik.core.database.orm.entities.interaction import Interaction
from taktik.core.database.orm.entities.profile_qualification import ProfileQualification
from taktik.core.database.orm.entities.scraped_profile import ScrapedProfile
from taktik.core.database.orm.entities.session_unified import SessionUnified
from taktik.core.database.orm.entities.social_graph_sync import SocialGraphSync
from taktik.core.database.orm.entities.social_profile import SocialProfile

__all__ = [
    "Account",
    "AppConfig",
    "DailyStatsUnified",
    "FilteredProfile",
    "Interaction",
    "ProfileQualification",
    "ScrapedProfile",
    "SessionUnified",
    "SocialGraphSync",
    "SocialProfile",
]
