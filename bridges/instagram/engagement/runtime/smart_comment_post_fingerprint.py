"""Post fingerprint verification support for Instagram Smart Comment."""

from __future__ import annotations

import re

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS


class SmartCommentPostFingerprintMixin:
    """Verify that the currently visible post matches the expected date/caption."""

    def verify_post_fingerprint(self) -> bool:
        """Verify we're on the correct post by checking date and caption prefix."""
        expected_date = self.config.get("postDate", "").strip()
        expected_caption = self.config.get("captionPrefix", "").strip()

        if not expected_date and not expected_caption:
            logger.debug("No post fingerprint in config - skipping verification")
            return True

        try:
            actual_date = ""
            header = self.device(resourceId=POST_DETAIL_SELECTORS.post_profile_header_resource_id)
            if header.exists:
                desc = header.info.get("contentDescription", "") or ""
                date_match = re.search(POST_DETAIL_SELECTORS.post_date_search_pattern, desc)
                if date_match:
                    actual_date = date_match.group(1)

            actual_caption = ""
            caption_elem = self.device(className=POST_DETAIL_SELECTORS.caption_layout_class_name)
            if caption_elem.exists:
                actual_caption = (caption_elem.get_text() or "").strip()
                author = self.config.get("targetUsername", "").strip().lstrip("@")
                if author and actual_caption.lower().startswith(author.lower()):
                    actual_caption = actual_caption[len(author):].strip()
                actual_caption = re.sub(POST_DETAIL_SELECTORS.caption_tail_pattern, "", actual_caption)

            if expected_date and actual_date:
                if expected_date.lower() != actual_date.lower():
                    logger.warning(f"Post date mismatch! Expected: '{expected_date}', Got: '{actual_date}'")
                    return False
                logger.info(f"Post date verified: {actual_date}")

            if expected_caption and actual_caption:
                prefix_len = min(len(expected_caption), 80)
                expected_prefix = expected_caption[:prefix_len].lower()
                actual_prefix = actual_caption[:prefix_len].lower()
                if expected_prefix != actual_prefix:
                    logger.warning(
                        f"Caption prefix mismatch! Expected: '{expected_prefix[:60]}...', "
                        f"Got: '{actual_prefix[:60]}...'"
                    )
                    return False
                logger.info(f"Caption prefix verified ({prefix_len} chars match)")

            return True

        except Exception as e:
            logger.warning(f"Error verifying post fingerprint: {e}")
            return True
