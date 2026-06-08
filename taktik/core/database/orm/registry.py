"""ORM pilot (Vague D) - entity registry.

Single list of mapped entities + their natural order column, consumed by the
parity validator/tests. Mirrors the front ORM_ENTITIES. Add new pilot entities
here as the ORM is extended.
"""
from __future__ import annotations

from taktik.core.database.orm.entities import (
    Account,
    AppConfig,
    DailyStatsUnified,
    FilteredProfile,
    Interaction,
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
