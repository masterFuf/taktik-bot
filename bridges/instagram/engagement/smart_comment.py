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
import re
import subprocess
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
from bridges.instagram.engagement.runtime.smart_comment_post_context import SmartCommentPostContextMixin
from bridges.instagram.engagement.runtime.smart_comment_reply import SmartCommentReplyMixin
from bridges.instagram.engagement.runtime.smart_comment_target import SmartCommentTargetMixin


class SmartCommentBridge(
    SmartCommentMediaMixin,
    SmartCommentTargetMixin,
    SmartCommentCommentsMixin,
    SmartCommentReplyMixin,
    SmartCommentPostContextMixin,
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

    def verify_post_fingerprint(self) -> bool:
        """Verify we're on the correct post by checking date and caption prefix.

        Uses post_date and caption prefix from config (saved during scrape) to
        confirm we navigated to the right post. This is a safety check.
        """
        expected_date = self.config.get('postDate', '').strip()
        expected_caption = self.config.get('captionPrefix', '').strip()

        if not expected_date and not expected_caption:
            logger.debug("No post fingerprint in config — skipping verification")
            return True  # Nothing to verify against

        try:
            # Check date from header content-desc
            actual_date = ""
            header = self.device(resourceId="com.instagram.android:id/row_feed_profile_header")
            if header.exists:
                desc = header.info.get('contentDescription', '') or ''
                date_match = re.search(
                    r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})', desc
                )
                if date_match:
                    actual_date = date_match.group(1)

            # Check caption prefix
            actual_caption = ""
            caption_elem = self.device(className="com.instagram.ui.widget.textview.IgTextLayoutView")
            if caption_elem.exists:
                actual_caption = (caption_elem.get_text() or "").strip()
                # The raw caption from IgTextLayoutView starts with "username caption..."
                # but captionPrefix from config was already cleaned of the username during scrape.
                # Strip the username prefix if present.
                author = self.config.get('targetUsername', '').strip().lstrip('@')
                if author and actual_caption.lower().startswith(author.lower()):
                    actual_caption = actual_caption[len(author):].strip()
                # Also strip trailing "more"/"plus"/"less"/"moins"
                actual_caption = re.sub(r'\s+(more|plus|less|moins)\s*$', '', actual_caption)

            # Verify date match
            if expected_date and actual_date:
                if expected_date.lower() != actual_date.lower():
                    logger.warning(f"Post date mismatch! Expected: '{expected_date}', Got: '{actual_date}'")
                    return False
                logger.info(f"Post date verified: {actual_date}")

            # Verify caption prefix match (first 80 chars)
            if expected_caption and actual_caption:
                # Compare first N chars (caption may be truncated on screen)
                prefix_len = min(len(expected_caption), 80)
                expected_prefix = expected_caption[:prefix_len].lower()
                actual_prefix = actual_caption[:prefix_len].lower()
                if expected_prefix != actual_prefix:
                    logger.warning(f"Caption prefix mismatch! Expected: '{expected_prefix[:60]}...', Got: '{actual_prefix[:60]}...'")
                    return False
                logger.info(f"Caption prefix verified ({prefix_len} chars match)")

            return True

        except Exception as e:
            logger.warning(f"Error verifying post fingerprint: {e}")
            return True  # Don't block on verification errors

    def navigate_to_post_url(self, post_url: str) -> bool:
        """Navigate directly to a specific post via its URL using Android deep link.

        This is much more reliable than profile → first post, because it opens
        the exact post regardless of which post was scraped.
        """
        logger.info(f"Navigating to post via URL: {post_url}")
        try:
            # Use am start to open the URL in Instagram
            from taktik.core.clone import get_active_package
            pkg = get_active_package()
            result = subprocess.run(
                ['adb', '-s', self.device_id, 'shell',
                 'am', 'start', '-a', 'android.intent.action.VIEW',
                 '-d', post_url,
                 '-p', pkg],
                capture_output=True, text=True, timeout=10, encoding='utf-8', errors='replace'
            )
            logger.debug(f"am start result: {result.stdout.strip()}")
            time.sleep(4)  # Wait for Instagram to load the post

            # Verify we landed on a post (check for comment button or like button)
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL")
                    return True

            # Sometimes Instagram shows a loading screen, wait more
            time.sleep(3)
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL (after extra wait)")
                    return True

            logger.warning("Post URL navigation: could not verify landing on post")
            return False

        except Exception as e:
            logger.error(f"Error navigating to post URL: {e}")
            return False

    def _navigate_to_comments(self) -> bool:
        """Navigate to the comments of the target post.

        Strategy (in order of preference):
        1. If we have a post_url → deep link directly to the post
        2. If we have a targetUsername → navigate to profile → open first post (legacy fallback)
        3. Fail if neither is available
        """
        # Reset cached UI bounds (stale after restart)
        self._comment_list_bounds = None

        post_url = self.config.get('postUrl', '') or self.post_context.post_url
        target_username = self.config.get('targetUsername', '').strip().lstrip('@')

        if not post_url and not target_username:
            logger.error("No postUrl or targetUsername available for navigation")
            return False

        logger.info("Restarting Instagram for navigation reset...")
        self.restart_instagram()

        if post_url:
            # ===== PREFERRED: Navigate directly to the exact post =====
            logger.info(f"Using post URL for precise navigation: {post_url}")
            if not self.navigate_to_post_url(post_url):
                logger.warning("Post URL navigation failed, trying profile fallback...")
                if target_username:
                    if not self._navigate_via_profile(target_username):
                        return False
                else:
                    logger.error("Post URL navigation failed and no targetUsername for fallback")
                    return False
        elif target_username:
            # ===== FALLBACK: Navigate via profile → first post =====
            logger.warning(f"No post URL available — falling back to @{target_username}'s first post")
            if not self._navigate_via_profile(target_username):
                return False

        if not self.open_comments():
            logger.error("Could not open comments")
            return False

        # Dismiss keyboard if visible
        try:
            title = self.device(resourceId="com.instagram.android:id/title_text_view")
            if title.exists:
                title.click()
                time.sleep(1)
        except Exception:
            pass

        time.sleep(1)
        return True

    def _navigate_via_profile(self, target_username: str) -> bool:
        """Navigate to profile → open first post → scroll through posts to find the right one.

        After opening the first post, Instagram shows a scrollable feed of all
        the profile's posts. We scroll down through them, checking the fingerprint
        (date + caption prefix) on each one until we find a match.
        """
        expected_date = self.config.get('postDate', '').strip()
        expected_caption = self.config.get('captionPrefix', '').strip()
        has_fingerprint = bool(expected_date or expected_caption)

        logger.info(f"Navigating via profile: @{target_username} (fingerprint: {'yes' if has_fingerprint else 'no'})")

        if not self.navigate_to_target_profile(target_username):
            logger.error(f"Could not navigate to @{target_username}")
            return False

        if not self.open_first_post():
            logger.error("Could not open first post")
            return False

        # If no fingerprint data, just use the first post (old behavior)
        if not has_fingerprint:
            logger.info("No fingerprint data — using first post")
            return True

        # Check if the first post already matches
        if self.verify_post_fingerprint():
            logger.info("First post matches fingerprint!")
            return True

        # Scroll through posts to find the matching one
        max_posts_to_check = 12  # Don't scroll forever — check up to ~12 posts
        for i in range(max_posts_to_check):
            logger.info(f"Post {i+2}/{max_posts_to_check+1}: scrolling to next post...")

            # Scroll down to the next post in the feed
            # Instagram's post feed scrolls vertically when viewing from a profile grid
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.8),
                self.screen_width // 2,
                int(self.screen_height * 0.2),
                duration=0.3
            )
            time.sleep(2)

            # Verify we're still on a post (not scrolled past all posts)
            on_post = False
            for indicator in [
                "com.instagram.android:id/row_feed_button_comment",
                "com.instagram.android:id/row_feed_button_like",
                "com.instagram.android:id/like_button",
            ]:
                if self.device(resourceId=indicator).exists:
                    on_post = True
                    break

            if not on_post:
                logger.warning("Scrolled past all visible posts — target post not found")
                break

            # Check fingerprint on this post
            if self.verify_post_fingerprint():
                logger.info(f"Found matching post after scrolling through {i+2} posts!")
                return True

            logger.debug(f"Post {i+2} does not match fingerprint, continuing...")

        logger.error(f"Could not find matching post after checking {max_posts_to_check+1} posts on @{target_username}'s profile")
        return False


def main():
    from bridges.instagram.engagement.runtime.smart_comment_commands import run_smart_comment_cli

    run_smart_comment_cli(sys.argv[1:])


if __name__ == '__main__':
    main()
