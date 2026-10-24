"""What a DM sent in an open conversation came to: sent, waiting to be sent, or not sent.

The one check of every Instagram DM send (the reply of the inbox, the welcome DM, the cold DM), read on
the conversation after Send was tapped. A bubble Instagram shows waiting to be sent (its « Envoi… » /
« Sending… » icon, no network) leaves by itself when the network is back: it is neither a send proven
(nothing counted as sent) nor a failure to try again (a second one would go). Measured on a Pixel 6 Pro
(Instagram 410, French and English, 2026-10-24).
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Callable, List

from loguru import logger

from taktik.core.shared.device.screen import screen_size_of
from taktik.core.social_media.instagram.workflows.dm.conversation_payload import pending_send_texts
from taktik.core.social_media.instagram.workflows.dm.message_extraction import DMMessageExtractionMixin


class ReplyOutcome(Enum):
    """What a DM sent in an open conversation came to."""

    #: Our text is the newest outgoing bubble of the conversation: a send proven.
    SENT = "sent"
    #: Our bubble is in the conversation and Instagram shows it waiting to be sent (no network): it
    #: leaves by itself when the network is back. Neither a send proven nor a failure to try again.
    PENDING = "pending"
    #: Nothing of ours went into the conversation (no composer, no send button, no bubble).
    NOT_SENT = "not_sent"


def normalize_message(text: str) -> str:
    """Whitespace-collapsed, lowercased form for resilient bubble matching."""
    return " ".join((text or "").split()).lower()


def same_message(shown: str, message: str) -> bool:
    """Is the bubble text `shown` our `message`? IG may elide a very long bubble: a prefix either way
    is accepted, from 12 characters (a short message must match exactly)."""
    actual, target = normalize_message(shown), normalize_message(message)
    if not actual or not target:
        return False
    if actual == target:
        return True
    shorter = min(len(actual), len(target))
    return shorter >= 12 and (actual.startswith(target[:shorter]) or target.startswith(actual[:shorter]))


def send_state(device: Any, message: str, bubbles: List[dict]) -> ReplyOutcome:
    """Where `message` stands in the open conversation, read on its newest bubble (`bubbles`, the
    reader's `{text, is_sent, top}`).

    SENT when it is the newest OUTGOING bubble: the bottom-most bubble, not "any bubble with this
    text", so an identical message sent earlier is no proof. PENDING when that newest bubble is ours
    with the sending icon at its side (the icon also shifts the bubble to the left, where it read as a
    received one). NOT_SENT otherwise.
    """
    if not normalize_message(message) or not bubbles:
        return ReplyOutcome.NOT_SENT
    last = max(bubbles, key=lambda bubble: bubble["top"])
    if not same_message(last["text"], message):
        return ReplyOutcome.NOT_SENT
    if any(same_message(text, message) for text in pending_send_texts(device.dump_hierarchy())):
        return ReplyOutcome.PENDING
    return ReplyOutcome.SENT if last["is_sent"] else ReplyOutcome.NOT_SENT


def reply_outcome(device: Any, message: str, read_bubbles: Callable[[], List[dict]],
                  attempts: int = 4, delay: float = 0.8) -> ReplyOutcome:
    """Poll the conversation until `message` shows up as its newest outgoing bubble, sent.

    The bubble appears a beat after the send round-trips, so it is looked for a few times; a bubble
    waiting to be sent is watched as long (the network may come back). Anything but SENT means the
    caller does not count the message as sent; PENDING also means it must not send it again.
    """
    state = ReplyOutcome.NOT_SENT
    for attempt in range(attempts):
        state = send_state(device, message, read_bubbles())
        if state is ReplyOutcome.SENT:
            return state
        if attempt < attempts - 1:
            time.sleep(delay)
    if state is ReplyOutcome.PENDING:
        logger.warning("Message waiting to be sent: Instagram shows it in the conversation with its "
                       "sending icon (no network?); it leaves by itself, not counted, not sent again")
    else:
        logger.error("Send not confirmed: message did not appear in the conversation")
    return state


class ConversationBubbles(DMMessageExtractionMixin):
    """The bubble reader of the open conversation (`DMMessageExtractionMixin`) on any device a caller
    holds: a profile's sending (`MessagingBusiness`) has no DM runtime of its own."""

    def __init__(self, device: Any):
        self.device = device

    @property
    def screen_width(self) -> int:
        return screen_size_of(self.device)[0]


__all__ = ["ConversationBubbles", "ReplyOutcome", "normalize_message", "reply_outcome", "same_message",
           "send_state"]
