"""Actions module for TikTok automation.

"""

from taktik.core.social_media.tiktok.actions.atomic import (
    ClickActions,
    NavigationActions,
    ScrollActions,
    DetectionActions,
)
from taktik.core.social_media.tiktok.actions.business import ForYouWorkflow, ForYouConfig, ForYouStats

__all__ = [
    # Atomic actions
    'ClickActions',
    'NavigationActions',
    'ScrollActions',
    'DetectionActions',
    # Workflows
    'ForYouWorkflow',
    'ForYouConfig',
    'ForYouStats',
]
