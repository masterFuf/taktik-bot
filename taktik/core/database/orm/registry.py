"""ORM pilot (Vague D) - entity registry.

Single list of mapped entities + their natural order column, consumed by the
parity validator/tests. Mirrors the front ORM_ENTITIES. Add new pilot entities
here as the ORM is extended.
"""
from __future__ import annotations

from taktik.core.database.orm.app_config_entity import AppConfig
from taktik.core.database.orm.interaction_entity import Interaction
from taktik.core.database.orm.unified_models import (
    Account,
    DailyStatsUnified,
    FilteredProfile,
    ProfileQualification,
    ScrapedProfile,
    SessionUnified,
    SocialGraphSync,
    SocialProfile,
)

# (entity, order_by_column)
PILOT_ENTITIES = [
    (AppConfig, "key"),
    (Interaction, "id"),
    (Account, "id"),
    (SocialProfile, "id"),
    (SessionUnified, "id"),
    (ProfileQualification, "id"),
    (DailyStatsUnified, "id"),
    (SocialGraphSync, "id"),
    (FilteredProfile, "id"),
    (ScrapedProfile, "id"),
]
