"""Post navigation helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import subprocess
import time

from bridges.instagram.engagement.runtime.smart_comment_post_fingerprint import SmartCommentPostFingerprintMixin
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_COMMENTS_SELECTORS,
    POST_DETAIL_SELECTORS,
)


class SmartCommentNavigationMixin(SmartCommentPostFingerprintMixin):
    """Navigate to the exact post used by Smart Comment reply mode."""

    def navigate_to_post_url(self, post_url: str) -> bool:
        """Navigate directly to a specific post via its URL using Android deep link."""
        logger.info(f"Navigating to post via URL: {post_url}")
        try:
            from taktik.core.clone import get_active_package

            pkg = get_active_package()
            result = subprocess.run(
                [
                    "adb",
                    "-s",
                    self.device_id,
                    "shell",
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.VIEW",
                    "-d",
                    post_url,
                    "-p",
                    pkg,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace",
            )
            logger.debug(f"am start result: {result.stdout.strip()}")
            time.sleep(4)

            for indicator in POST_DETAIL_SELECTORS.post_landing_indicator_resource_ids:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL")
                    return True

            time.sleep(3)
            for indicator in POST_DETAIL_SELECTORS.post_landing_indicator_resource_ids:
                if self.device(resourceId=indicator).exists:
                    logger.info("Successfully navigated to post via URL (after extra wait)")
                    return True

            logger.warning("Post URL navigation: could not verify landing on post")
            return False

        except Exception as e:
            logger.error(f"Error navigating to post URL: {e}")
            return False

    def _navigate_to_comments(self) -> bool:
        """Navigate to the comments of the target post."""
        self._comment_list_bounds = None

        post_url = self.config.get("postUrl", "") or self.post_context.post_url
        target_username = self.config.get("targetUsername", "").strip().lstrip("@")

        if not post_url and not target_username:
            logger.error("No postUrl or targetUsername available for navigation")
            return False

        logger.info("Restarting Instagram for navigation reset...")
        self.restart_instagram()

        if post_url:
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
            logger.warning(f"No post URL available — falling back to @{target_username}'s first post")
            if not self._navigate_via_profile(target_username):
                return False

        if not self.open_comments():
            logger.error("Could not open comments")
            return False

        try:
            title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
            if title.exists:
                title.click()
                time.sleep(1)
        except Exception:
            pass

        time.sleep(1)
        return True

    def _navigate_via_profile(self, target_username: str) -> bool:
        """Navigate to profile, open first post, then find the fingerprinted post."""
        expected_date = self.config.get("postDate", "").strip()
        expected_caption = self.config.get("captionPrefix", "").strip()
        has_fingerprint = bool(expected_date or expected_caption)

        logger.info(f"Navigating via profile: @{target_username} (fingerprint: {'yes' if has_fingerprint else 'no'})")

        if not self.navigate_to_target_profile(target_username):
            logger.error(f"Could not navigate to @{target_username}")
            return False

        if not self.open_first_post():
            logger.error("Could not open first post")
            return False

        if not has_fingerprint:
            logger.info("No fingerprint data — using first post")
            return True

        if self.verify_post_fingerprint():
            logger.info("First post matches fingerprint!")
            return True

        max_posts_to_check = 12
        for i in range(max_posts_to_check):
            logger.info(f"Post {i+2}/{max_posts_to_check+1}: scrolling to next post...")

            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.8),
                self.screen_width // 2,
                int(self.screen_height * 0.2),
                duration=0.3,
            )
            time.sleep(2)

            on_post = False
            for indicator in POST_DETAIL_SELECTORS.post_landing_indicator_resource_ids:
                if self.device(resourceId=indicator).exists:
                    on_post = True
                    break

            if not on_post:
                logger.warning("Scrolled past all visible posts — target post not found")
                break

            if self.verify_post_fingerprint():
                logger.info(f"Found matching post after scrolling through {i+2} posts!")
                return True

            logger.debug(f"Post {i+2} does not match fingerprint, continuing...")

        logger.error(f"Could not find matching post after checking {max_posts_to_check+1} posts on @{target_username}'s profile")
        return False
