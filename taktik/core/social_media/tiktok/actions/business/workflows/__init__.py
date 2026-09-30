"""Workflow actions for TikTok automation.

"""

from taktik.core.social_media.tiktok.actions.business.workflows.for_you import ForYouWorkflow, ForYouConfig, ForYouStats
from taktik.core.social_media.tiktok.actions.business.workflows.dm import (
    DMWorkflow,
    DMConfig,
    DMStats,
    ConversationData,
)
from taktik.core.social_media.tiktok.actions.business.workflows.search import SearchWorkflow, SearchConfig, SearchStats
from taktik.core.social_media.tiktok.actions.business.workflows.followers import (
    FollowersWorkflow,
    FollowersConfig,
    FollowersStats,
)
from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles import (
    TargetProfilesWorkflow,
    TargetProfilesConfig,
)

__all__ = [
    'ForYouWorkflow',
    'ForYouConfig',
    'ForYouStats',
    'DMWorkflow',
    'DMConfig',
    'DMStats',
    'ConversationData',
    'SearchWorkflow',
    'SearchConfig',
    'SearchStats',
    'FollowersWorkflow',
    'FollowersConfig',
    'FollowersStats',
    'TargetProfilesWorkflow',
    'TargetProfilesConfig',
]
