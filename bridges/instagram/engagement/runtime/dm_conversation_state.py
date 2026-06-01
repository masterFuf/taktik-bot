"""DM conversation state helpers for the Instagram DM bridge."""

from __future__ import annotations

import re
import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMConversationStateMixin:
    """Resolve conversation metadata and keep navigation state recoverable."""

    def _resolve_thread_username(self, thread_info: dict, fallback: str) -> str:
        username = fallback
        try:
            username_elem = self.device(resourceId=DM_SELECTORS.thread_username_resource_id)
            if username_elem.exists:
                for idx in range(username_elem.count):
                    elem = username_elem[idx]
                    bounds = elem.info.get("bounds", {})
                    thread_bounds = thread_info.get("bounds", {})
                    if bounds and thread_bounds:
                        if (
                            bounds.get("top", 0) >= thread_bounds.get("top", 0)
                            and bounds.get("bottom", 0) <= thread_bounds.get("bottom", 0)
                        ):
                            username = elem.get_text() or username
                            break
        except Exception:
            pass
        return username

    def _detect_conversation_reply_state(self, real_username: str) -> tuple[bool, bool]:
        is_group = False
        can_reply = True
        header_subtitle = self.device(resourceId=DM_SELECTORS.conversation_header_subtitle_resource_id)
        if header_subtitle.exists:
            try:
                subtitle_text = header_subtitle.get_text() or ""
                subtitle_info = header_subtitle.info
                subtitle_desc = subtitle_info.get("contentDescription", "") or ""
                combined = (subtitle_text + " " + subtitle_desc).lower()
                is_group_pattern = bool(re.search(DM_SELECTORS.conversation_group_member_pattern, combined))

                if is_group_pattern or any(keyword in combined for keyword in DM_SELECTORS.conversation_group_member_keywords):
                    is_group = True
                    logger.info(f"Groupe détecté via subtitle: {combined[:50]}")
            except Exception as e:
                logger.debug(f"Erreur détection groupe via subtitle: {e}")

        composer = self.device(resourceId=DM_SELECTORS.composer_edittext_resource_id)
        if not composer.exists:
            can_reply = False
            if not is_group:
                is_group = True
                logger.info(f"Broadcast channel détecté (pas de composer): {real_username}")

        return is_group, can_reply

    def _return_to_inbox_if_needed(self) -> None:
        inbox_list = self.device(resourceId=DM_SELECTORS.inbox_thread_list_resource_id)
        if not inbox_list.exists:
            self._go_back_from_conversation(delay=1)

    def _go_back_from_conversation(self, delay: float = 1) -> None:
        back_btn = self.device(resourceId=DM_SELECTORS.conversation_back_button_resource_id)
        if back_btn.exists:
            back_btn.click()
        else:
            self.device.press("back")
        time.sleep(delay)
