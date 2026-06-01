"""Comment list navigation support for Instagram Smart Comment."""

from __future__ import annotations

import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentCommentNavigationMixin:
    """Scroll the comments list and expand reply threads."""

    def _scroll_comments_down(self):
        """Scroll the comments list down quickly."""
        try:
            if not self._comment_list_bounds:
                comment_list = self.device(resourceId=POST_COMMENTS_SELECTORS.comments_list_resource_id)
                if comment_list.exists:
                    self._comment_list_bounds = comment_list.info.get("bounds", {})
                    logger.debug(f"Cached comment list bounds: {self._comment_list_bounds}")

            if self._comment_list_bounds:
                top = self._comment_list_bounds.get("top", 234)
                bottom = self._comment_list_bounds.get("bottom", 1090)
                center_x = self.screen_width // 2
                start_y = top + int((bottom - top) * 0.75)
                end_y = top + int((bottom - top) * 0.25)
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
            else:
                center_x = self.screen_width // 2
                start_y = int(self.screen_height * 0.65)
                end_y = int(self.screen_height * 0.25)
                logger.debug(f"Fallback scroll: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.15)
        except Exception as e:
            logger.warning(f"Scroll error: {e}")

    def _expand_reply_threads(self) -> bool:
        """Click 'View X more replies' buttons to expand reply threads."""
        expanded = False
        try:
            for pattern in POST_COMMENTS_SELECTORS.expand_replies_text_contains:
                view_replies = self.device(textContains=pattern, clickable=True)
                if not view_replies.exists:
                    continue
                for i in range(view_replies.count):
                    try:
                        elem = view_replies[i]
                        elem_text = (elem.info.get("text", "") or "").lower()
                        elem_desc = (elem.info.get("contentDescription", "") or "").lower()
                        combined = elem_text + " " + elem_desc

                        if any(token in combined for token in POST_COMMENTS_SELECTORS.expand_replies_positive_tokens):
                            if any(token in combined for token in POST_COMMENTS_SELECTORS.expand_replies_hidden_tokens):
                                continue
                            logger.info(f"Expanding thread: {elem.info.get('text', '')}")
                            elem.click()
                            expanded = True
                            time.sleep(0.5)
                    except Exception:
                        continue

            if not expanded:
                for desc_kw in POST_COMMENTS_SELECTORS.expand_replies_description_contains:
                    elems = self.device(descriptionContains=desc_kw, clickable=True)
                    if elems.exists:
                        for i in range(elems.count):
                            try:
                                elem_desc = (elems[i].info.get("contentDescription", "") or "").lower()
                                if any(token in elem_desc for token in POST_COMMENTS_SELECTORS.expand_replies_hidden_tokens):
                                    continue
                                logger.info(f"Expanding thread (desc): {elems[i].info.get('contentDescription', '')}")
                                elems[i].click()
                                expanded = True
                                time.sleep(0.5)
                            except Exception:
                                continue

        except Exception as e:
            logger.debug(f"Expand reply threads error: {e}")

        return expanded
