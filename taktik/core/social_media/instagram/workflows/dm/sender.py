"""DM composer and send-button handling for the Instagram DM inbox."""

from __future__ import annotations

import random
import time
from typing import Any, Callable

from loguru import logger
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.behavior.typing import calculate_dm_typing_delay
from taktik.core.shared.input.taktik_keyboard import ensure_taktik_keyboard
from taktik.core.social_media.instagram.actions.atomic.text.dm_composer import (
    click_send_button,
    find_message_input,
    resolve_device_id,
    type_message,
)
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome, reply_outcome


class DMSenderMixin:
    """Send messages in the currently opened Instagram DM conversation."""

    # What the runtime gives (`InstagramDMRuntime`), declared here as an interface would be.
    device: Any
    _collect_text_messages: Callable[[], list]

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
        """Delegates to the shared composer atomic — see `dm_composer.find_message_input`."""
        return find_message_input(self.device, logger=logger)

    def _type_dm_message(self, msg_input, message: str) -> bool:
        """Delegates to the shared composer atomic.

        The simulated typing delay stays here: this runtime paced itself before typing, and the
        shared function only types. Once humanised typing is on, its own think-pauses make this
        wait redundant — that is a rhythm change, not a refactor, so it is left alone.
        """
        self._simulate_typing_delay(message)
        return type_message(
            self.device,
            getattr(self, "device_id", None),
            message,
            element=msg_input,
            logger=logger,
        )

    def _verify_message_sent(self, message: str, attempts: int = 4, delay: float = 0.8) -> ReplyOutcome:
        """What the reply came to, read on the open conversation by the one check of every DM send
        (`reply_check.reply_outcome`), with this runtime's bubble reader."""
        return reply_outcome(self.device, message, self._collect_text_messages, attempts=attempts, delay=delay)

    def send_message(self, message: str) -> ReplyOutcome:
        """Send a message in the current conversation with human-like timing.

        SENT ONLY once the message is confirmed as the newest outgoing bubble in the thread. A
        click that does not actually submit (empty composer, mis-targeted button, IG hiccup) is
        NOT_SENT, so the caller never persists a phantom reply that was never delivered. A bubble
        Instagram shows waiting to be sent is PENDING: not recorded, not sent again.
        """
        logger.info("Sending message...")

        msg_input = self._find_message_input()
        if msg_input is None:
            logger.error("Message input not found")
            return ReplyOutcome.NOT_SENT

        logger.info(f"Found message input: {msg_input.info}")

        # Before the tap: a keyboard switched after it can cost the field its focus.
        ensure_taktik_keyboard(resolve_device_id(self.device, getattr(self, "device_id", None)))
        if not tap_element_human(self.device, msg_input, logger=logger):
            msg_input.click()
        time.sleep(random.uniform(0.5, 0.8))

        if not self._type_dm_message(msg_input, message):
            return ReplyOutcome.NOT_SENT

        time.sleep(random.uniform(0.3, 0.5))

        # The one Send button of every DM send (`dm_composer.find_send_button`).
        if not click_send_button(self.device, logger=logger):
            logger.error("Send button not found or not pressed")
            return ReplyOutcome.NOT_SENT

        state = self._verify_message_sent(message)
        if state is ReplyOutcome.SENT:
            logger.info("Message sent and confirmed in the conversation")
        return state
