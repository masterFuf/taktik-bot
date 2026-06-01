"""Comment scraping helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_comment_extraction import (
    SmartCommentCommentExtractionMixin,
)
from bridges.instagram.engagement.runtime.smart_comment_comment_navigation import (
    SmartCommentCommentNavigationMixin,
)
from bridges.instagram.engagement.runtime.smart_comment_models import ScrapedComment
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentCommentsMixin(SmartCommentCommentExtractionMixin, SmartCommentCommentNavigationMixin):
    """Open, sort and scrape Instagram comments for Smart Comment."""

    def open_comments(self) -> bool:
        """Open the comments section of the current post."""
        logger.info("Opening comments...")

        comment_btn = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_button_resource_id)
        if comment_btn.exists:
            parent = comment_btn.up(className=POST_COMMENTS_SELECTORS.parent_view_group_class_name, clickable=True)
            if parent and parent.exists:
                parent.click()
            else:
                comment_btn.click()
            time.sleep(2)

            title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
            if title.exists and title.get_text() in POST_COMMENTS_SELECTORS.comment_title_texts:
                logger.info("Comments page opened successfully")
                return True

        buttons = self.device(className=POST_COMMENTS_SELECTORS.button_class_name)
        for i in range(buttons.count):
            try:
                btn = buttons[i]
                text = btn.get_text() or ""
                if text and text.isdigit() and int(text) > 0:
                    info = btn.info
                    bounds = info.get("bounds", {})
                    left = bounds.get("left", 0)
                    if 300 < left < 500:
                        btn.click()
                        time.sleep(2)
                        title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
                        if title.exists and title.get_text() in POST_COMMENTS_SELECTORS.comment_title_texts:
                            logger.info("Comments page opened via count button")
                            return True
            except Exception:
                continue

        logger.error("Could not open comments")
        return False

    def change_comment_sort(self, sort_type: str = "most_recent") -> bool:
        """Change comment sorting. Options: 'for_you', 'most_recent', 'meta_verified'."""
        logger.info(f"Changing comment sort to: {sort_type}")

        sort_btn = self.device(text=POST_COMMENTS_SELECTORS.default_sort_label, className=POST_COMMENTS_SELECTORS.button_class_name)
        if not sort_btn.exists:
            sort_btn = self.device(description=POST_COMMENTS_SELECTORS.default_sort_label)
        if not sort_btn.exists:
            for label in POST_COMMENTS_SELECTORS.sort_button_labels:
                sort_btn = self.device(text=label, className=POST_COMMENTS_SELECTORS.button_class_name)
                if sort_btn.exists:
                    break

        if not sort_btn.exists:
            logger.warning("Sort button not found")
            return False

        sort_btn.click()
        time.sleep(1)

        targets = POST_COMMENTS_SELECTORS.sort_options.get(
            sort_type,
            POST_COMMENTS_SELECTORS.sort_options["most_recent"],
        )
        for target in targets:
            option = self.device(text=target)
            if not option.exists:
                option = self.device(description=target)
            if option.exists:
                option.click()
                time.sleep(1)
                logger.info(f"Sorted by: {target}")
                return True

        self.device.press("back")
        logger.warning(f"Sort option '{sort_type}' not found")
        return False

    def scrape_all_comments(self, max_comments: int = 500) -> list[ScrapedComment]:
        """Scrape all comments from the currently open comments page."""
        logger.info(f"Scraping comments (max {max_comments})...")

        seen_keys = set()
        scroll_attempts = 0
        no_new_count = 0
        max_no_new = 5

        self._comment_list_bounds = None

        while len(self.comments) < max_comments and no_new_count < max_no_new:
            new_found = self._extract_visible_comments_fast(seen_keys, max_comments)

            if new_found == 0:
                no_new_count += 1
            else:
                no_new_count = 0

            send_event(
                "scrape_progress",
                current=len(self.comments),
                total=max_comments,
                scroll=scroll_attempts,
            )

            if len(self.comments) >= max_comments:
                break

            expanded = self._expand_reply_threads()
            if expanded:
                time.sleep(0.8)
                new_from_expand = self._extract_visible_comments_fast(seen_keys, max_comments)
                if new_from_expand > 0:
                    no_new_count = 0
                    send_event(
                        "scrape_progress",
                        current=len(self.comments),
                        total=max_comments,
                        scroll=scroll_attempts,
                    )

            if len(self.comments) >= max_comments:
                break

            scroll_attempts += 1
            self._scroll_comments_down()
            time.sleep(0.3)

        logger.info(f"Scraped {len(self.comments)} comments total")
        send_event("scrape_complete", total=len(self.comments))
        return self.comments
