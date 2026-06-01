"""Message composer helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import random
import time

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class ColdDMSenderMixin:
    """DM composer and invite-state detection for Cold DM outreach."""

    def _init_cold_dm_sender(self, device_id: str) -> None:
        self._keyboard = KeyboardService(device_id)

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation."""
        logger.info("Sending message...")

        msg_input = self.device(resourceId=DM_SELECTORS.composer_edittext_resource_id)
        if not msg_input.exists:
            msg_input = self.device(className=DM_SELECTORS.edit_text_class_name)
        for text in DM_SELECTORS.message_input_text_contains:
            if msg_input.exists:
                break
            msg_input = self.device(textContains=text)

        if not msg_input.exists:
            if self.check_invite_already_sent():
                return "invite_sent"
            logger.error("Message input not found")
            return False

        msg_input.click()
        time.sleep(0.5)

        typing_time = min(len(message) * random.uniform(0.03, 0.05) + random.uniform(0.5, 1.5), 5.0)
        time.sleep(typing_time)

        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False

        time.sleep(0.5)

        send_btn = None
        for resource_id in DM_SELECTORS.send_button_resource_ids[:2]:
            send_btn = self.device(resourceId=resource_id)
            if send_btn.exists:
                break
        for description in DM_SELECTORS.send_button_content_descriptions:
            if send_btn and send_btn.exists:
                break
            send_btn = self.device(description=description)

        if send_btn and send_btn.exists:
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found")
        return False

    def check_invite_already_sent(self) -> bool:
        """Check if we're on the 'Invite sent' screen."""
        for text in DM_SELECTORS.invite_sent_text_contains:
            invite_sent = self.device(textContains=text)
            if invite_sent.exists:
                logger.info("Invite already sent to this user")
                return True

        return False
