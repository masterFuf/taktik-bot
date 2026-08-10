"""
🎯 Workflows d'acquisition utilisateurs.

This package holds the main workflows that target and interact with
users through the different sources.
"""

from .post_url import PostUrlBusiness
from .hashtag import HashtagBusiness
from .followers import FollowerBusiness
from .unfollow import UnfollowBusiness
from .feed import FeedBusiness

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
