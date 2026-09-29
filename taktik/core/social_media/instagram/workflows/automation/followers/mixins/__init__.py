"""Follower workflow mixins: reusable logic blocks."""

from taktik.core.social_media.instagram.workflows.automation.followers.mixins.checkpoints import FollowerCheckpointsMixin
from taktik.core.social_media.instagram.workflows.automation.followers.mixins.extraction import FollowerExtractionMixin
from taktik.core.social_media.instagram.workflows.automation.followers.mixins.navigation import FollowerNavigationMixin

__all__ = [
    'FollowerCheckpointsMixin',
    'FollowerExtractionMixin',
    'FollowerNavigationMixin',
]
