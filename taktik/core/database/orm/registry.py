"""ORM pilot (Vague D) - entity registry.

Single list of mapped entities + their natural order column, consumed by the
parity validator/tests. Add new pilot entities here as the ORM is extended
family by family.
"""
from __future__ import annotations

from taktik.core.database.orm.app_config_entity import AppConfig
from taktik.core.database.orm.interaction_entity import Interaction

# (entity, order_by_column)
PILOT_ENTITIES = [
    (AppConfig, "key"),
    (Interaction, "id"),
]
