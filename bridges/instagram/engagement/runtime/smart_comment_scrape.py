"""Scrape orchestration for the Instagram Smart Comment bridge."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from bridges.instagram.base import logger, send_message as send_event


class SmartCommentScrapeMixin:
    """High-level scrape orchestration and result serialization."""

    def get_scrape_results(self) -> dict[str, Any]:
        """Return all scraped data for AI processing on the Electron/Node side."""
        return {
            "post_context": asdict(self.post_context),
            "comments": [asdict(c) for c in self.comments],
            "total_comments": len(self.comments),
            "unique_users": len(set(c.username for c in self.comments)),
            "author_comments": len([c for c in self.comments if c.is_author]),
            "reply_comments": len([c for c in self.comments if c.is_reply]),
        }

    def run_scrape(self) -> dict[str, Any]:
        """Run the scraping phase: extract post context and scrape comments."""
        target_username = self.config.get("targetUsername", "").strip().lstrip("@")
        target_profile_data = None

        if target_username:
            send_event("scrape_status", status="restarting", message="Restarting Instagram...")
            logger.info(f"Dynamic target mode: navigating to @{target_username}")

            self.restart_instagram()

            send_event("scrape_status", status="navigating", message=f"Navigating to @{target_username}...")
            if not self.navigate_to_target_profile(target_username):
                return {"success": False, "error": f"Could not navigate to @{target_username}'s profile"}

            send_event("scrape_status", status="scraping_profile", message=f"Scraping @{target_username} profile...")
            target_profile = self.scrape_target_profile()
            target_profile_data = asdict(target_profile)

            send_event("target_profile", profile=target_profile_data)

            if target_profile.is_private:
                return {"success": False, "error": f"@{target_username} is a private account"}

            send_event("scrape_status", status="opening_post", message="Opening first post...")
            if not self.open_first_post():
                return {"success": False, "error": f"Could not open first post on @{target_username}'s profile"}

            logger.info(f"Successfully navigated to @{target_username}'s first post")

        self.extract_post_context()

        if target_profile_data:
            self.post_context.target_bio = target_profile_data.get("bio", "")
            self.post_context.target_profile = target_profile_data
            if not self.post_context.author_username and target_username:
                self.post_context.author_username = target_username

        screenshot_path = self.take_post_screenshot()

        if not self.open_comments():
            return {"success": False, "error": "Could not open comments"}

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

        time.sleep(2)

        max_comments = self.config.get("maxComments", 500)
        self.scrape_all_comments(max_comments)

        results = self.get_scrape_results()
        results["success"] = True
        results["screenshot_path"] = screenshot_path
        return results
