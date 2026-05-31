"""Message composer helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import random
import time

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.runtime.ipc import logger


class ColdDMSenderMixin:
    """DM composer and invite-state detection for Cold DM outreach."""

    def _init_cold_dm_sender(self, device_id: str) -> None:
        self._keyboard = KeyboardService(device_id)

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation."""
        logger.info("Sending message...")

        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            msg_input = self.device(textContains="Message")

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

        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
        if not send_btn.exists:
            send_btn = self.device(description="Send")
        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")

        if send_btn.exists:
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found")
        return False

    def check_invite_already_sent(self) -> bool:
        """Check if we're on the 'Invite sent' screen."""
        invite_sent = self.device(textContains="Invite sent")
        if invite_sent.exists:
            logger.info("Invite already sent to this user")
            return True

        invite_msg = self.device(textContains="invite is accepted")
        if invite_msg.exists:
            logger.info("Invite already sent (waiting for acceptance)")
            return True

        return False
