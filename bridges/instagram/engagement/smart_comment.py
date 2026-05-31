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
import time
from dataclasses import asdict
from typing import List, Dict, Any

# Bootstrap: UTF-8 + loguru + sys.path in one call. This implementation is
# one level below the public entrypoint, so resolve back to bot/ explicitly.
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.instagram.base import logger, InstagramBridgeBase, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_comments import SmartCommentCommentsMixin
from bridges.instagram.engagement.runtime.smart_comment_media import SmartCommentMediaMixin
from bridges.instagram.engagement.runtime.smart_comment_models import (
    PostContext,
    ScrapedComment,
)
from bridges.instagram.engagement.runtime.smart_comment_navigation import SmartCommentNavigationMixin
from bridges.instagram.engagement.runtime.smart_comment_post_context import SmartCommentPostContextMixin
from bridges.instagram.engagement.runtime.smart_comment_reply import SmartCommentReplyMixin
from bridges.instagram.engagement.runtime.smart_comment_target import SmartCommentTargetMixin


class SmartCommentBridge(
    SmartCommentMediaMixin,
    SmartCommentTargetMixin,
    SmartCommentCommentsMixin,
    SmartCommentReplyMixin,
    SmartCommentPostContextMixin,
    SmartCommentNavigationMixin,
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

    # =========================================================================
    # PHASE 1: POST CONTEXT EXTRACTION
    # =========================================================================

    # =========================================================================
    # PHASE 2: COMMENT SCRAPING
    # =========================================================================

    # =========================================================================
    # PHASE 3: AI QUALIFICATION & REPLY GENERATION
    # (Called from Electron side via fal.ai - bridge just sends data)
    # =========================================================================

    def get_scrape_results(self) -> Dict[str, Any]:
        """Return all scraped data for AI processing on the Electron/Node side."""
        return {
            "post_context": asdict(self.post_context),
            "comments": [asdict(c) for c in self.comments],
            "total_comments": len(self.comments),
            "unique_users": len(set(c.username for c in self.comments)),
            "author_comments": len([c for c in self.comments if c.is_author]),
            "reply_comments": len([c for c in self.comments if c.is_reply]),
        }

    # =========================================================================
    # PHASE 4: REPLY TO COMMENT
    # =========================================================================

    # =========================================================================
    # ORCHESTRATION
    # =========================================================================

    def run_scrape(self) -> Dict[str, Any]:
        """Run the scraping phase: extract post context + scrape all comments.

        If targetUsername is provided in config, navigates to the target profile first,
        scrapes profile info, then opens the first post before scraping comments.
        Otherwise, scrapes from whatever post is currently visible on screen.
        """
        target_username = self.config.get('targetUsername', '').strip().lstrip('@')
        target_profile_data = None

        # ===== PHASE 0: Navigate to target (if provided) =====
        if target_username:
            send_event("scrape_status", status="restarting", message="Restarting Instagram...")
            logger.info(f"Dynamic target mode: navigating to @{target_username}")

            # Step 0a: Restart Instagram for clean state (ensures home page)
            self.restart_instagram()

            # Step 0b: Navigate to target profile (deep link or search)
            send_event("scrape_status", status="navigating", message=f"Navigating to @{target_username}...")
            if not self.navigate_to_target_profile(target_username):
                return {"success": False, "error": f"Could not navigate to @{target_username}'s profile"}

            # Step 0c: Scrape target profile info
            send_event("scrape_status", status="scraping_profile", message=f"Scraping @{target_username} profile...")
            target_profile = self.scrape_target_profile()
            target_profile_data = asdict(target_profile)

            # Send profile info to frontend
            send_event("target_profile", profile=target_profile_data)

            # Check if profile is private
            if target_profile.is_private:
                return {"success": False, "error": f"@{target_username} is a private account"}

            # Step 0d: Open first post
            send_event("scrape_status", status="opening_post", message="Opening first post...")
            if not self.open_first_post():
                return {"success": False, "error": f"Could not open first post on @{target_username}'s profile"}

            logger.info(f"Successfully navigated to @{target_username}'s first post")

        # ===== PHASE 1: Extract post context =====
        self.extract_post_context()

        # Enrich post context with target profile data if available
        if target_profile_data:
            self.post_context.target_bio = target_profile_data.get('bio', '')
            self.post_context.target_profile = target_profile_data
            # If author_username wasn't detected from the post, use the target username
            if not self.post_context.author_username and target_username:
                self.post_context.author_username = target_username

        # ===== PHASE 1b: Extract post URL (disabled for now — buggy Share→Copy Link flow) =====
        # TODO: Re-enable when clipboard reading is reliable
        # send_event("scrape_status", status="extracting_url", message="Extracting post URL...")
        # post_url = self.extract_post_url()
        # if post_url:
        #     logger.info(f"Post URL captured: {post_url}")
        # else:
        #     logger.warning("Could not capture post URL — reply phase will use fallback navigation")

        # ===== PHASE 2: Screenshot =====
        screenshot_path = self.take_post_screenshot()

        # ===== PHASE 3: Open comments =====
        if not self.open_comments():
            return {"success": False, "error": "Could not open comments"}

        # Keep default comment sort ("For you") — no filter change needed

        # Dismiss keyboard if visible
        try:
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                logger.info("Tapped comments title to dismiss keyboard")
                time.sleep(1)
            else:
                self.device.click(self.screen_width // 2, 150)
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Keyboard dismiss attempt: {e}")

        # Wait for comments to fully load
        time.sleep(2)

        # ===== PHASE 4: Scrape comments =====
        max_comments = self.config.get('maxComments', 500)
        self.scrape_all_comments(max_comments)

        # ===== PHASE 5: Return results =====
        results = self.get_scrape_results()
        results["success"] = True
        results["screenshot_path"] = screenshot_path
        return results


def main():
    from bridges.instagram.engagement.runtime.smart_comment_commands import run_smart_comment_cli

    run_smart_comment_cli(sys.argv[1:])


if __name__ == '__main__':
    main()
