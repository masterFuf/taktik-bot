"""DM composer and send-button handling for the Instagram DM inbox."""

from __future__ import annotations

import random
import time
from enum import Enum
from typing import Any, Callable

from loguru import logger
from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.behavior.typing import calculate_dm_typing_delay
from taktik.core.shared.input.taktik_keyboard import ensure_taktik_keyboard
from taktik.core.social_media.instagram.actions.atomic.text.dm_composer import (
    find_message_input,
    resolve_device_id,
    type_message,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from taktik.core.social_media.instagram.workflows.dm.conversation_payload import pending_send_texts


class ReplyOutcome(Enum):
    """What a reply came to (`DMSenderMixin.send_message`)."""

    #: Our text is the newest outgoing bubble of the conversation: a send proven.
    SENT = "sent"
    #: Our bubble is in the conversation and Instagram shows it waiting to be sent (« Envoi… », no
    #: network): it leaves by itself when the network is back. Neither a send proven (nothing is
    #: recorded) nor a failure to try again (that would send it twice).
    PENDING = "pending"
    #: Nothing of ours went into the conversation (no composer, no send button, no bubble).
    NOT_SENT = "not_sent"


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

    @staticmethod
    def _normalize_message(text: str) -> str:
        """Whitespace-collapsed, lowercased form for resilient bubble matching."""
        return " ".join((text or "").split()).lower()

    @classmethod
    def _same_message(cls, shown: str, message: str) -> bool:
        """Is the bubble text `shown` our `message`? IG may elide a very long bubble: a prefix
        either way is accepted, from 12 characters (a short message must match exactly)."""
        actual, target = cls._normalize_message(shown), cls._normalize_message(message)
        if not actual or not target:
            return False
        if actual == target:
            return True
        shorter = min(len(actual), len(target))
        return shorter >= 12 and (
            actual.startswith(target[:shorter]) or target.startswith(actual[:shorter])
        )

    def _message_send_state(self, message: str) -> ReplyOutcome:
        """Where ``message`` stands in the open conversation, read on its newest bubble.

        SENT when it is the newest OUTGOING bubble: matching the bottom-most bubble rather than
        "any bubble with this text" avoids a false positive when an identical message was sent
        earlier. PENDING when the newest bubble is ours with the « Envoi… » icon at its side (no
        network; the icon also shifts the bubble to the left, where it read as received, and the
        reply was declared « did not appear », Pixel 6 Pro, 410, 2026-10-24). NOT_SENT otherwise.
        """
        if not self._normalize_message(message):
            return ReplyOutcome.NOT_SENT
        bubbles = self._collect_text_messages()
        if not bubbles:
            return ReplyOutcome.NOT_SENT
        last = max(bubbles, key=lambda bubble: bubble["top"])
        if not self._same_message(last["text"], message):
            return ReplyOutcome.NOT_SENT
        if any(self._same_message(text, message) for text in pending_send_texts(self.device.dump_hierarchy())):
            return ReplyOutcome.PENDING
        return ReplyOutcome.SENT if last["is_sent"] else ReplyOutcome.NOT_SENT

    def _message_appears_as_last_sent(self, message: str) -> bool:
        """True if ``message`` is the newest OUTGOING bubble of the open conversation, sent."""
        return self._message_send_state(message) is ReplyOutcome.SENT

    def _verify_message_sent(self, message: str, attempts: int = 4, delay: float = 0.8) -> ReplyOutcome:
        """Poll the thread until our message shows up as the last outgoing bubble, sent.

        The bubble appears a beat after the send round-trips, so we retry a few times before
        giving up; a bubble waiting to be sent is watched as long (the network may come back).
        Anything but SENT means the caller must NOT persist the reply; PENDING also means it must
        not send it again.
        """
        state = ReplyOutcome.NOT_SENT
        for attempt in range(attempts):
            state = self._message_send_state(message)
            if state is ReplyOutcome.SENT:
                return state
            if attempt < attempts - 1:
                time.sleep(delay)
        return state

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

        send_btn = self._find_send_button()
        if not (send_btn and send_btn.exists):
            logger.error("Send button not found - dumping UI elements for debugging")
            self._log_clickable_elements_for_send_debug()
            return ReplyOutcome.NOT_SENT

        logger.info(f"Clicking send button: {send_btn.info}")
        if not tap_element_human(self.device, send_btn, logger=logger):
            send_btn.click()
        time.sleep(1)

        state = self._verify_message_sent(message)
        if state is ReplyOutcome.PENDING:
            logger.warning("Message waiting to be sent: Instagram shows it in the conversation with its "
                           "sending icon (no network?); it leaves by itself, not recorded, not sent again")
            return state
        if state is not ReplyOutcome.SENT:
            logger.error("Send not confirmed: message did not appear in the conversation")
            return state

        logger.info("Message sent and confirmed in the conversation")
        return state
