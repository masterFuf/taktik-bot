"""Post context extraction for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict

from bridges.instagram.runtime.ipc import logger, send_message as send_event
from bridges.instagram.engagement.runtime.smart_comment_models import PostContext
from bridges.instagram.engagement.runtime.smart_comment_post_stats import SmartCommentPostStatsMixin
from bridges.instagram.engagement.runtime.smart_comment_post_url import SmartCommentPostUrlMixin
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS


class SmartCommentPostContextMixin(SmartCommentPostStatsMixin, SmartCommentPostUrlMixin):
    """Caption, date, stats and post URL extraction for Smart Comment."""

    def _expand_caption(self):
        """Click the 'more' button to expand the full caption text."""
        try:
            caption_view = self.device(className=POST_DETAIL_SELECTORS.caption_layout_class_name)
            if not caption_view.exists:
                return

            caption_text = caption_view.get_text() or ""
            if not any(caption_text.rstrip().endswith(label) for label in POST_DETAIL_SELECTORS.caption_expand_labels):
                logger.debug("Caption does not appear truncated — no 'more' button to click")
                return

            more_btn = None
            for label in POST_DETAIL_SELECTORS.caption_expand_labels:
                more_btn = self.device(description=label)
                if more_btn.exists:
                    break
                more_btn = self.device(text=label, className=POST_DETAIL_SELECTORS.button_class_name)
                if more_btn.exists:
                    break

            if more_btn and more_btn.exists:
                more_btn.click()
                time.sleep(1)
                logger.info("Clicked 'more' to expand caption")
            else:
                logger.debug("'more' button not found — caption may already be fully visible")
        except Exception as e:
            logger.debug(f"Error expanding caption: {e}")

    def extract_post_context(self) -> PostContext:
        """Extract context from the currently visible post."""
        logger.info("Extracting post context...")

        author_elem = self.device(resourceId=POST_DETAIL_SELECTORS.post_author_name_resource_id)
        if author_elem.exists:
            self.post_context.author_username = author_elem.get_text() or ""
            logger.info(f"Post author (from profile name): {self.post_context.author_username}")

        self._expand_caption()

        caption_elem = self.device(className=POST_DETAIL_SELECTORS.caption_layout_class_name)
        if caption_elem.exists:
            try:
                full_text = caption_elem.get_text() or ""
                if not self.post_context.author_username and full_text:
                    first_space = full_text.find(" ")
                    if first_space > 0:
                        candidate = full_text[:first_space].strip()
                        if re.match(r"^[\w][\w.]{0,29}$", candidate):
                            self.post_context.author_username = candidate
                            logger.info(f"Post author (from caption prefix): {self.post_context.author_username}")

                if self.post_context.author_username and full_text.startswith(self.post_context.author_username):
                    self.post_context.caption = full_text[len(self.post_context.author_username):].strip()
                else:
                    self.post_context.caption = full_text
                self.post_context.caption = re.sub(POST_DETAIL_SELECTORS.caption_tail_pattern, "", self.post_context.caption)
                logger.info(f"Caption ({len(self.post_context.caption)} chars): {self.post_context.caption[:150]}...")
            except Exception as e:
                logger.warning(f"Error extracting caption: {e}")

        try:
            xml = self.device.dump_hierarchy()
            if xml:
                root = ET.fromstring(xml)
                for elem in root.iter():
                    text = (elem.get("text", "") or "").strip()
                    content_desc = (elem.get("content-desc", "") or "").strip()
                    cls = elem.get("class", "") or ""
                    if (
                        cls == POST_DETAIL_SELECTORS.text_view_class_name
                        and text
                        and re.match(POST_DETAIL_SELECTORS.post_date_pattern, text)
                    ):
                        self.post_context.post_date = text
                        logger.info(f"Post date: {text}")
                        break
                    if (
                        not self.post_context.post_date
                        and content_desc
                        and re.match(POST_DETAIL_SELECTORS.post_date_pattern, content_desc)
                    ):
                        self.post_context.post_date = content_desc
                        logger.info(f"Post date (from content-desc): {content_desc}")
                        break
        except Exception as e:
            logger.debug(f"Error extracting post date: {e}")

        if not self.post_context.post_date:
            try:
                header = self.device(resourceId=POST_DETAIL_SELECTORS.post_profile_header_resource_id)
                if header.exists:
                    desc = header.info.get("contentDescription", "") or ""
                    date_match = re.search(POST_DETAIL_SELECTORS.post_date_search_pattern, desc)
                    if date_match:
                        self.post_context.post_date = date_match.group(1)
                        logger.info(f"Post date (from header): {self.post_context.post_date}")
            except Exception as e:
                logger.debug(f"Error extracting date from header: {e}")

        if not self.post_context.author_username:
            try:
                for rid in POST_DETAIL_SELECTORS.post_media_description_resource_ids:
                    elem = self.device(resourceId=rid)
                    if elem.exists:
                        desc = elem.info.get("contentDescription", "") or ""
                        by_match = re.search(POST_DETAIL_SELECTORS.author_from_media_description_pattern, desc)
                        if by_match:
                            self.post_context.author_username = by_match.group(1)
                            logger.info(f"Post author (from content-desc): {self.post_context.author_username}")
                            break
            except Exception as e:
                logger.debug(f"Fallback author extraction: {e}")

        if not self.post_context.author_username:
            logger.warning("Could not detect post author username — author detection will be unreliable")

        self._extract_post_stats()

        self.post_context.target_bio = self.config.get("targetBio", "")

        send_event("post_context", context=asdict(self.post_context))
        return self.post_context
