"""
🎯 Workflows d'acquisition utilisateurs.

This package holds the main workflows that target and interact with
users through the different sources.
"""

from taktik.core.social_media.instagram.actions.business.workflows.post_url import PostUrlBusiness
from taktik.core.social_media.instagram.actions.business.workflows.hashtag import HashtagBusiness
from taktik.core.social_media.instagram.actions.business.workflows.followers import FollowerBusiness
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import UnfollowBusiness
from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness

# NOTE: no NotificationsBusiness here. The activity feed is owned by the notifications
# ENGAGEMENT workflow (`workflows/management/notifications`), driven by notifications_bridge —
# a single implementation that also persists, dedups and closes Instagram. The legacy business
# action that treated notifications as just another profile source has been removed.

__all__ = [
    'PostUrlBusiness',
    'HashtagBusiness',
    'FollowerBusiness',
    'UnfollowBusiness',
    'FeedBusiness'
]
