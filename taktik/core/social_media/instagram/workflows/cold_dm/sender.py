"""Sending in the conversation the Instagram Cold DM opened."""

from __future__ import annotations

import time
from typing import Any, Callable

from loguru import logger

from taktik.core.shared.behavior.typing import calculate_dm_typing_delay


class ColdDMSenderMixin:
    """The cold DM's send: its pace, then the production sending in an open conversation."""

    # What the host gives this mixin (`ColdDMNavigationMixin`), like a field of a TypeScript interface.
    _cold_dm_messaging: Callable[[], Any]

    def send_message(self, message: str):
        """Send `message` in the open conversation: what the conversation then shows
        (`ReplyOutcome`: sent, waiting to be sent, not sent), or `INVITE_ALREADY_SENT` when a
        message request to this account is already waiting.

        The time a human takes to type the message is waited first, then the message is typed
        without typos (`MessagingBusiness.send_in_open_conversation`, the welcome DM's too).
        """
        logger.info("Sending message...")
        time.sleep(calculate_dm_typing_delay(message))
        return self._cold_dm_messaging().send_in_open_conversation(message, typos=False)
