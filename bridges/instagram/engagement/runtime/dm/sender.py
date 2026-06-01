"""DM composer and send-button handling for the Instagram DM bridge."""

from __future__ import annotations

import random
import time

from bridges.instagram.engagement.runtime.dm.timing import calculate_dm_typing_delay
from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS


class DMSenderMixin:
    """Send messages in the currently opened Instagram DM conversation."""

    def _simulate_typing_delay(self, text: str):
        """
        Simulate human typing time without actually typing char by char.
        This avoids issues with emojis and special characters while still
        appearing natural (not instant).
        """
        total_time = calculate_dm_typing_delay(text)
        logger.info(f"Simulating typing for {total_time:.1f}s ({len(text)} chars)...")
        time.sleep(total_time)

    def _find_message_input(self):
        message_input_ids = DM_SELECTORS.message_input_resource_ids
        msg_input = self.device(resourceId=message_input_ids[0])
        if not msg_input.exists and len(message_input_ids) > 1:
            logger.info("Trying alternative input selector...")
            msg_input = self.device(resourceId=message_input_ids[1])
        if not msg_input.exists:
            logger.info("Trying EditText class...")
            msg_input = self.device(className=DM_SELECTORS.edit_text_class_name)
        if not msg_input.exists:
            logger.info("Trying hint text...")
            for text in DM_SELECTORS.message_input_text_contains:
                msg_input = self.device(textContains=text)
                if msg_input.exists:
                    break
        return msg_input

    def _type_dm_message(self, msg_input, message: str) -> bool:
        self._simulate_typing_delay(message)

        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
            return True

        logger.warning("Taktik Keyboard failed, trying fallback methods...")
        try:
            msg_input.set_text(message)
            logger.info("Text set via set_text")
            return True
        except Exception as e:
            logger.warning(f"set_text failed: {e}, trying send_keys...")

        try:
            msg_input.send_keys(message)
            logger.info("Text set via send_keys")
            return True
        except Exception as e:
            logger.error(f"send_keys also failed: {e}")
            return False

    def _find_send_button(self):
        send_btn = None
        labels = ["container", "direct"]
        for resource_id, label in zip(DM_SELECTORS.send_button_resource_ids[:2], labels):
            send_btn = self.device(resourceId=resource_id)
            logger.info(f"Send button ({label}): exists={send_btn.exists}")
            if send_btn.exists:
                return send_btn

        for description in DM_SELECTORS.send_button_descriptions:
            send_btn = self.device(description=description)
            logger.info(f"Send button ({description}): exists={send_btn.exists}")
            if send_btn.exists:
                return send_btn

        for resource_id in DM_SELECTORS.send_button_resource_ids[2:]:
            send_btn = self.device(resourceId=resource_id)
            logger.info(f"Send button (send_button): exists={send_btn.exists}")
            if send_btn.exists:
                return send_btn

        return send_btn

    def _log_clickable_elements_for_send_debug(self) -> None:
        try:
            clickables = self.device(clickable=True)
            for i in range(min(clickables.count, 20)):
                elem = clickables[i]
                info = elem.info
                logger.info(
                    f"Clickable {i}: {info.get('resourceId', '')} - "
                    f"{info.get('contentDescription', '')} - {info.get('className', '')}"
                )
        except Exception:
            pass

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation with human-like timing."""
        logger.info("Sending message...")

        msg_input = self._find_message_input()
        if not msg_input.exists:
            logger.error("Message input not found")
            return False

        logger.info(f"Found message input: {msg_input.info}")

        msg_input.click()
        time.sleep(random.uniform(0.5, 0.8))

        if not self._type_dm_message(msg_input, message):
            return False

        time.sleep(random.uniform(0.3, 0.5))

        send_btn = self._find_send_button()
        if send_btn and send_btn.exists:
            logger.info(f"Clicking send button: {send_btn.info}")
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found - dumping UI elements for debugging")
        self._log_clickable_elements_for_send_debug()
        return False
