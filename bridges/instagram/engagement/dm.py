#!/usr/bin/env python3
"""
DM Bridge for TAKTIK Desktop
Unified bridge for reading and sending Instagram DM messages.

Usage:
    python dm_bridge.py read <device_id> <limit>
    python dm_bridge.py send <device_id> <username> <message>
"""

import sys
import os
import time
import random

# Bootstrap: UTF-8 + loguru + sys.path in one call
bot_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, bot_dir)
from bridges.common.runtime.bootstrap import setup_environment
setup_environment()

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.base import logger, InstagramBridgeBase
from bridges.instagram.engagement.runtime.dm_navigation import DMInboxNavigationMixin
from bridges.instagram.engagement.runtime.dm_reader import DMConversationReaderMixin



class DMBridge(DMConversationReaderMixin, DMInboxNavigationMixin, InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)

    def _simulate_typing_delay(self, text: str):
        """
        Simulate human typing time without actually typing char by char.
        This avoids issues with emojis and special characters while still
        appearing natural (not instant).
        """
        # Calculate realistic typing time: ~40-80ms per character for a fast typer
        # But cap it to avoid very long waits
        char_count = len(text)

        # Base time: 30-50ms per character
        base_time = char_count * random.uniform(0.03, 0.05)

        # Add some "thinking" time at the start (0.5-1.5s)
        thinking_time = random.uniform(0.5, 1.5)

        # Cap total time at 5 seconds max
        total_time = min(base_time + thinking_time, 5.0)

        logger.info(f"Simulating typing for {total_time:.1f}s ({char_count} chars)...")
        time.sleep(total_time)

    def send_message(self, message: str) -> bool:
        """Send a message in the current conversation with human-like timing."""
        logger.info("Sending message...")

        # Find message input - try multiple selectors
        msg_input = self.device(resourceId="com.instagram.android:id/row_thread_composer_edittext")
        if not msg_input.exists:
            logger.info("Trying alternative input selector...")
            msg_input = self.device(resourceId="com.instagram.android:id/message_content")
        if not msg_input.exists:
            logger.info("Trying EditText class...")
            msg_input = self.device(className="android.widget.EditText")
        if not msg_input.exists:
            logger.info("Trying hint text...")
            msg_input = self.device(textContains="Message")

        if not msg_input.exists:
            logger.error("Message input not found")
            return False

        logger.info(f"Found message input: {msg_input.info}")

        # Click on input field
        msg_input.click()
        time.sleep(random.uniform(0.5, 0.8))

        # Simulate typing delay (looks like we're typing)
        self._simulate_typing_delay(message)

        # Use Taktik Keyboard for reliable input (supports emojis, special chars, etc.)
        if self._keyboard.type_text(message):
            logger.info("Text set via Taktik Keyboard")
        else:
            # Fallback to set_text or send_keys
            logger.warning("Taktik Keyboard failed, trying fallback methods...")
            try:
                msg_input.set_text(message)
                logger.info("Text set via set_text")
            except Exception as e:
                logger.warning(f"set_text failed: {e}, trying send_keys...")
                try:
                    msg_input.send_keys(message)
                    logger.info("Text set via send_keys")
                except Exception as e2:
                    logger.error(f"send_keys also failed: {e2}")
                    return False

        time.sleep(random.uniform(0.3, 0.5))  # Brief pause before sending

        # Find send button - try multiple selectors
        send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button_container")
        logger.info(f"Send button (container): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(resourceId="com.instagram.android:id/row_thread_composer_send_button")
            logger.info(f"Send button (direct): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Envoyer")
            logger.info(f"Send button (Envoyer): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Send")
            logger.info(f"Send button (Send): exists={send_btn.exists}")

        if not send_btn.exists:
            send_btn = self.device(description="Send message")
            logger.info(f"Send button (Send message): exists={send_btn.exists}")

        if not send_btn.exists:
            # Try to find any clickable element near the input that could be send
            send_btn = self.device(resourceId="com.instagram.android:id/send_button")
            logger.info(f"Send button (send_button): exists={send_btn.exists}")

        if send_btn.exists:
            logger.info(f"Clicking send button: {send_btn.info}")
            send_btn.click()
            time.sleep(1)
            logger.info("Message sent!")
            return True

        logger.error("Send button not found - dumping UI elements for debugging")
        # Log all clickable elements for debugging
        try:
            clickables = self.device(clickable=True)
            for i in range(min(clickables.count, 20)):
                elem = clickables[i]
                info = elem.info
                logger.info(f"Clickable {i}: {info.get('resourceId', '')} - {info.get('contentDescription', '')} - {info.get('className', '')}")
        except Exception:
            pass

        return False


def main():
    from bridges.instagram.engagement.runtime.dm_commands import run_dm_cli

    run_dm_cli(sys.argv[1:])


if __name__ == "__main__":
    main()
