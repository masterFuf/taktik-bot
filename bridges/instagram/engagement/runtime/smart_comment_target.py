"""Target profile helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger
from bridges.instagram.engagement.runtime.smart_comment_models import TargetProfile
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class SmartCommentTargetMixin:
    """Profile navigation and first-post opening for Smart Comment scraping."""

    def navigate_to_target_profile(self, username: str) -> bool:
        """Navigate to a target user's profile using framework navigation actions."""
        logger.info(f"Navigating to @{username} profile...")
        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation_actions import NavigationActions

            nav = NavigationActions(self.device_manager)
            return nav.navigate_to_profile(username)
        except Exception as e:
            logger.error(f"Error navigating to profile: {e}")
            return False

    def scrape_target_profile(self) -> TargetProfile:
        """Scrape profile information using the framework profile business owner."""
        logger.info("Scraping target profile info via ProfileBusiness...")
        profile = TargetProfile()

        try:
            from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

            profile_biz = ProfileBusiness(self.device_manager)
            profile_info = profile_biz.get_complete_profile_info(navigate_if_needed=False)

            if profile_info:
                profile.username = profile_info.get("username", "") or ""
                profile.full_name = profile_info.get("full_name", "") or ""
                profile.bio = profile_info.get("biography", "") or ""
                profile.followers = profile_info.get("followers_count", 0) or 0
                profile.following = profile_info.get("following_count", 0) or 0
                profile.posts_count = profile_info.get("posts_count", 0) or 0
                profile.is_private = profile_info.get("is_private", False)
                profile.is_verified = profile_info.get("is_verified", False)
                profile.account_type = profile_info.get("business_category", "") or ""
                if not profile.account_type:
                    profile.account_type = "Business" if profile_info.get("is_business", False) else ""

                logger.info(
                    f"Profile scraped: @{profile.username} | {profile.full_name} | "
                    f"{profile.followers} followers | {profile.following} following | "
                    f"{profile.posts_count} posts | type: {profile.account_type}"
                )
            else:
                logger.warning("ProfileBusiness returned None, falling back to basic extraction")
                title_elem = self.device(resourceId=PROFILE_SELECTORS.action_bar_title_resource_id)
                if title_elem.exists:
                    profile.username = (title_elem.get_text() or "").strip()

        except Exception as e:
            logger.error(f"Error scraping profile: {e}")

        return profile

    def open_first_post(self) -> bool:
        """Open the first post in the profile grid using framework click actions."""
        logger.info("Opening first post via ClickActions...")

        try:
            from taktik.core.social_media.instagram.actions.atomic.click_actions import ClickActions

            click = ClickActions(self.device_manager)

            if click.click_first_post_in_grid():
                time.sleep(2)
                if any(self.device(resourceId=indicator).exists for indicator in POST_DETAIL_SELECTORS.post_landing_indicator_resource_ids[:2]):
                    logger.info("Successfully opened first post")
                    return True
                for indicator in POST_DETAIL_SELECTORS.post_reel_landing_indicator_resource_ids:
                    if self.device(resourceId=indicator).exists:
                        logger.info("Successfully opened first post (reel)")
                        return True
                logger.warning("Clicked grid but didn't land on a post, going back to retry")
                self.device.press("back")
                time.sleep(1)

            logger.info("First attempt failed, scrolling to reveal grid and retrying...")
            self.device.swipe(
                self.screen_width // 2,
                int(self.screen_height * 0.7),
                self.screen_width // 2,
                int(self.screen_height * 0.4),
                duration=0.3,
            )
            time.sleep(1)

            if click.click_first_post_in_grid():
                time.sleep(2)
                logger.info("Successfully opened first post after scroll")
                return True

        except Exception as e:
            logger.error(f"Error opening first post: {e}")

        logger.error("Could not find first post to open")
        return False
