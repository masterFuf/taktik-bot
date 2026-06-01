"""Post stats extraction support for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re

from bridges.common.parsing.counts import parse_count
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS


class SmartCommentPostStatsMixin:
    """Extract like/comment counters from the currently visible post."""

    def _extract_post_stats(self):
        """Extract likes/comments count from post."""
        try:
            carousel = self.device(resourceId=POST_DETAIL_SELECTORS.post_media_description_resource_ids[0])
            if carousel.exists:
                desc = carousel.info.get("contentDescription", "")
                likes_match = re.search(r"([\d,]+)\s*likes?", desc)
                comments_match = re.search(r"([\d,]+)\s*comments?", desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(",", ""))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(",", ""))
                logger.info(
                    f"Stats from carousel: {self.post_context.likes_count} likes, "
                    f"{self.post_context.comments_count} comments"
                )
                return

            photo = self.device(resourceId=POST_DETAIL_SELECTORS.post_media_description_resource_ids[1])
            if photo.exists:
                desc = photo.info.get("contentDescription", "")
                likes_match = re.search(r"([\d,]+)\s*likes?", desc)
                comments_match = re.search(r"([\d,]+)\s*comments?", desc)
                if likes_match:
                    self.post_context.likes_count = int(likes_match.group(1).replace(",", ""))
                if comments_match:
                    self.post_context.comments_count = int(comments_match.group(1).replace(",", ""))

            buttons = self.device(className=POST_DETAIL_SELECTORS.button_class_name)
            for i in range(buttons.count):
                try:
                    btn = buttons[i]
                    text = btn.get_text() or ""
                    if text and re.match(r"^[\d,.]+[KMkm]?$", text):
                        count = parse_count(text)
                        info = btn.info
                        bounds = info.get("bounds", {})
                        left = bounds.get("left", 0)
                        if left < 250 and self.post_context.likes_count == 0:
                            self.post_context.likes_count = count
                        elif left < 500 and self.post_context.comments_count == 0:
                            self.post_context.comments_count = count
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"Error extracting post stats: {e}")
