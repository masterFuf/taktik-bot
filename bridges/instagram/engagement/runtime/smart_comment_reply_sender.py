"""Reply typing/sending support for Instagram Smart Comment."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentReplySenderMixin:
    """Type reply text and send it through the comments composer."""

    def _scroll_comments_to_top(self):
        """Scroll the comments list to the top with fast flick gestures."""
        try:
            comment_list = self.device(resourceId=POST_COMMENTS_SELECTORS.comments_list_resource_id)
            if not comment_list.exists:
                return
            bounds = comment_list.info.get("bounds", {})
            top = bounds.get("top", 234)
            bottom = bounds.get("bottom", 738)
            center_x = self.screen_width // 2
            start_y = top + int((bottom - top) * 0.2)
            end_y = top + int((bottom - top) * 0.9)
        except Exception:
            center_x = self.screen_width // 2
            start_y = 200
            end_y = 600

        for _ in range(15):
            try:
                self.device.swipe(center_x, start_y, center_x, end_y, duration=0.1)
                time.sleep(0.15)
            except Exception:
                break

    def _type_with_taktik_keyboard(self, text: str) -> bool:
        """Type text using Taktik Keyboard via shared KeyboardService."""
        return self._keyboard.type_text(text)

    def _type_reply_text(self, input_field, current_text: str, reply_text: str) -> bool:
        typed = False

        if self._type_with_taktik_keyboard(reply_text):
            time.sleep(0.5)
            after_text = input_field.get_text() or ""
            if len(after_text) > len(current_text):
                logger.info(f"Taktik Keyboard success: '{after_text[:40]}...'")
                typed = True
            else:
                logger.warning(f"Taktik Keyboard broadcast OK but text not inserted (field: '{after_text[:40]}')")
        else:
            logger.warning("Taktik Keyboard broadcast failed")

        if not typed:
            logger.info("Trying set_text fallback...")
            try:
                input_field.set_text(current_text + reply_text)
                time.sleep(0.5)
                after_text = input_field.get_text() or ""
                if len(after_text) > len(current_text):
                    logger.info(f"set_text success: '{after_text[:40]}...'")
                    typed = True
                else:
                    logger.warning("set_text did not insert text")
            except Exception as e:
                logger.warning(f"set_text failed: {e}")

        if not typed:
            logger.info("Trying send_keys fallback...")
            try:
                input_field.click()
                time.sleep(0.3)
                input_field.send_keys(reply_text)
                time.sleep(0.5)
                after_text = input_field.get_text() or ""
                if len(after_text) > len(current_text):
                    logger.info(f"send_keys success: '{after_text[:40]}...'")
                    typed = True
                else:
                    logger.warning("send_keys did not insert text")
            except Exception as e:
                logger.warning(f"send_keys failed: {e}")

        return typed

    def _find_reply_send_button(self):
        send_btn = None
        for resource_id in POST_COMMENTS_SELECTORS.post_comment_button_resource_ids:
            send_btn = self.device(resourceId=resource_id)
            if send_btn.exists:
                return send_btn

        for description in POST_COMMENTS_SELECTORS.post_comment_button_descriptions:
            send_btn = self.device(description=description)
            if send_btn.exists:
                return send_btn

        return send_btn

    def _log_potential_send_buttons(self) -> None:
        try:
            xml = self.device.dump_hierarchy()
            root = ET.fromstring(xml)
            for elem in root.iter():
                rid = elem.get("resource-id", "") or ""
                desc = elem.get("content-desc", "") or ""
                text = elem.get("text", "") or ""
                desc_lower = desc.lower()
                if any(token in rid or token in desc_lower for token in POST_COMMENTS_SELECTORS.post_comment_debug_tokens):
                    logger.debug(f"Potential send button: rid={rid} desc={desc} text={text} bounds={elem.get('bounds', '')}")
        except Exception as e:
            logger.debug(f"UI dump failed: {e}")

    def _dismiss_keyboard_and_scroll_top(self):
        """After sending a reply, dismiss the keyboard and scroll comments back to top."""
        try:
            title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
            if title.exists:
                title.click()
                time.sleep(0.5)
            else:
                self.device.press("back")
                time.sleep(0.5)

                title = self.device(resourceId=POST_COMMENTS_SELECTORS.comment_title_resource_id)
                if not title.exists:
                    logger.warning("Comments page lost after back press, reopening...")
                    if not self.open_comments():
                        return False
                    time.sleep(1)

            self._comment_list_bounds = None

            logger.debug("Scrolling comments back to top...")
            self._scroll_comments_to_top()
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.warning(f"Error dismissing keyboard / scrolling to top: {e}")
            return True
