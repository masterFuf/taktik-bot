#!/usr/bin/env python3
"""
Smart Comment Bridge for TAKTIK Desktop
AI-powered comment reply marketing system.

Workflow:
1. Open a target post (competitor)
2. Screenshot the post → fal.ai Vision → understand visual context
3. Extract caption + post metadata
4. Open comments → scrape ALL comments (scroll through entire list)
5. AI Qualifier: filter comments that are relevant prospects
6. AI Reply Generator: generate contextual replies for each qualified comment
7. Reply to comments one by one with human-like delays

Usage:
    python smart_comment_bridge.py <config_file.json>

Config JSON:
{
    "deviceId": "HBEDU19325000489",
    "falApiKey": "...",
    "postUrl": "https://www.instagram.com/p/...",  // optional, if not already on post
    "targetBio": "...",  // bio of the target account (optional, scraped if missing)
    "mode": "scrape" | "qualify" | "reply_all",
    "maxComments": 500,
    "qualificationPrompt": "...",  // custom prompt for qualifying prospects
    "replyPrompt": "...",  // custom prompt/strategy for generating replies
    "replyTone": "casual" | "professional" | "friendly",
    "replyLanguage": "fr",
    "delayBetweenReplies": [30, 90],  // min/max seconds between replies
    "dryRun": false  // if true, generate replies but don't post them
}
"""

import sys
import os
from typing import List, Dict, Any

# Bootstrap: UTF-8 + loguru + sys.path in one call. This implementation is
# one level below the public entrypoint, so resolve back to bot/ explicitly.
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.instagram.runtime.bridge import InstagramBridgeBase
from bridges.instagram.runtime.ipc import logger
from bridges.instagram.engagement.runtime.smart_comment_comments import SmartCommentCommentsMixin
from bridges.instagram.engagement.runtime.smart_comment_media import SmartCommentMediaMixin
from bridges.instagram.engagement.runtime.smart_comment_models import (
    PostContext,
    ScrapedComment,
)
from bridges.instagram.engagement.runtime.smart_comment_navigation import SmartCommentNavigationMixin
from bridges.instagram.engagement.runtime.smart_comment_post_context import SmartCommentPostContextMixin
from bridges.instagram.engagement.runtime.smart_comment_reply import SmartCommentReplyMixin
from bridges.instagram.engagement.runtime.smart_comment_scrape import SmartCommentScrapeMixin
from bridges.instagram.engagement.runtime.smart_comment_target import SmartCommentTargetMixin


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

        # Results
        self.post_context = PostContext()
        self.comments: List[ScrapedComment] = []
        self.qualified_comments: List[ScrapedComment] = []

        # UI state cache
        self._comment_list_bounds = None

    # =========================================================================
    # PHASE 0: TARGET NAVIGATION (uses existing framework classes)
    # =========================================================================

    def restart_instagram(self):
        """Restart Instagram for clean state via AppService."""
        super().restart_instagram()
        logger.info("Instagram restarted successfully")


def main():
    from bridges.instagram.engagement.runtime.smart_comment_commands import run_smart_comment_cli

    run_smart_comment_cli(sys.argv[1:])


if __name__ == '__main__':
    main()
