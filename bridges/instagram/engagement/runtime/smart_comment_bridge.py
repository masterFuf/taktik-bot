"""Instagram Smart Comment bridge runtime class."""

from __future__ import annotations

from typing import Any, Dict, List

from bridges.instagram.engagement.runtime.smart_comment_comments import SmartCommentCommentsMixin
from bridges.instagram.engagement.runtime.smart_comment_media import SmartCommentMediaMixin
from bridges.instagram.engagement.runtime.smart_comment_models import PostContext, ScrapedComment
from bridges.instagram.engagement.runtime.smart_comment_navigation import SmartCommentNavigationMixin
from bridges.instagram.engagement.runtime.smart_comment_post_context import SmartCommentPostContextMixin
from bridges.instagram.engagement.runtime.smart_comment_reply import SmartCommentReplyMixin
from bridges.instagram.engagement.runtime.smart_comment_scrape import SmartCommentScrapeMixin
from bridges.instagram.engagement.runtime.smart_comment_target import SmartCommentTargetMixin
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import logger


class SmartCommentBridge(
    SmartCommentMediaMixin,
    SmartCommentTargetMixin,
    SmartCommentCommentsMixin,
    SmartCommentReplyMixin,
    SmartCommentPostContextMixin,
    SmartCommentNavigationMixin,
    SmartCommentScrapeMixin,
    InstagramBridgeBase,
):
    """Bridge for AI-powered comment reply marketing."""

    def __init__(self, device_id: str, config: Dict[str, Any], package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self.config = config
        self._init_smart_comment_reply(device_id)
        self.post_context = PostContext()
        self.comments: List[ScrapedComment] = []
        self.qualified_comments: List[ScrapedComment] = []
        self._comment_list_bounds = None

    def restart_instagram(self):
        """Restart Instagram for clean state via AppService."""
        super().restart_instagram()
        logger.info("Instagram restarted successfully")


__all__ = ["SmartCommentBridge"]
