"""One reading of a TikTok DM payload (read, send, cold DM), for the bridge and the Agent handler
alike.

The wire form is the desktop page's camelCase (`TikTokDM.tsx`, `TikTokUnreplied.tsx` for the
replies, `TikTokColdDM.tsx` for the cold DM, and the scheduler's DM nodes); the snake_case names an
Agent plan or a CLI call writes stay accepted. Every key is read by name, so the app's config
contract test can see which ones the bot reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
    keyword_list,
    text_list,
)

from .models import DMConfig


def dm_read_config_from_payload(payload: Mapping[str, Any]) -> DMConfig:
    """The config of one inbox read; an absent key keeps the page's default."""
    return DMConfig(
        max_conversations=as_int(
            first_given(payload.get("maxConversations"), payload.get("max_conversations")), 20
        ),
        skip_notifications=as_bool(
            first_given(payload.get("skipNotifications"), payload.get("skip_notifications")), True
        ),
        skip_groups=as_bool(first_given(payload.get("skipGroups"), payload.get("skip_groups")), False),
        only_unread=as_bool(first_given(payload.get("onlyUnread"), payload.get("only_unread")), False),
        delay_between_conversations=as_float(
            first_given(payload.get("delayBetweenConversations"), payload.get("delay_between_conversations")),
            1.0,
        ),
        mark_as_read=as_bool(first_given(payload.get("markAsRead"), payload.get("mark_as_read")), True),
        close_sticker_suggestions=as_bool(
            first_given(payload.get("closeStickerSuggestions"), payload.get("close_sticker_suggestions")), True
        ),
    )


def dm_send_config_from_payload(payload: Mapping[str, Any]) -> DMConfig:
    """The config of one bulk send; an absent key keeps the page's default."""
    return DMConfig(
        delay_between_conversations=as_float(
            first_given(
                payload.get("delayBetweenMessages"),
                payload.get("delay_between_messages"),
                payload.get("delay_between_conversations"),
            ),
            1.0,
        ),
        delay_after_send=as_float(first_given(payload.get("delayAfterSend"), payload.get("delay_after_send")), 0.5),
        close_sticker_suggestions=as_bool(
            first_given(payload.get("closeStickerSuggestions"), payload.get("close_sticker_suggestions")), True
        ),
    )


def dm_messages_from_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The messages to send, as `{conversation, message}`, in order.

    `messages` is the page's list, kept as written: the conversation is the name the inbox shows,
    and an AI reply is typed exactly as the model wrote it. Without a list, one message as a CLI
    call writes it: `conversation` (or `username`) and `message`.
    """
    raw_messages = payload.get("messages")
    if raw_messages:
        if not isinstance(raw_messages, (list, tuple)):
            raise ValueError("TikTok DM send requires messages to be a list")
        return [
            {"conversation": item.get("conversation", ""), "message": item.get("message", "")}
            for item in raw_messages
            if isinstance(item, Mapping)
        ]

    conversation = str(first_given(payload.get("conversation"), payload.get("username")) or "").strip()
    message = str(payload.get("message") or "").strip()
    return [{"conversation": conversation, "message": message}] if conversation or message else []


@dataclass(frozen=True)
class DMOutreachRequest:
    """One cold-DM run: who to write to, what, at which pace, and as which account."""

    recipients: list
    #: The static messages, kept as written; in AI mode, only the fallback.
    messages: list
    delay_min: Any
    delay_max: Any
    max_dms: int
    account_id: int
    session_id: str
    #: "manual" (the static list) or "ai" (one message written per recipient).
    message_mode: str
    ai_prompt: str
    openrouter_api_key: str

    @property
    def wants_ai(self) -> bool:
        return self.message_mode == "ai"


def _pause(value: Any, default: Any) -> Any:
    """A pause in seconds, kept as sent (30 stays 30); a text is read as a number."""
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def dm_outreach_request_from_payload(payload: Mapping[str, Any], *, default_session_id: str) -> DMOutreachRequest:
    """The cold DM as the page and the scheduler send it, or as an Agent plan or a CLI call writes it.

    Recipients as a list are kept as given; as text, split on commas. The messages are kept as
    written: a message may hold a comma.
    """
    session_id = first_given(payload.get("sessionId"), payload.get("session_id"))
    return DMOutreachRequest(
        recipients=keyword_list(
            first_given(payload.get("recipients"), payload.get("targetUsernames"), payload.get("target_usernames"))
        ),
        messages=text_list(first_given(payload.get("messages"), payload.get("messageTemplates"))),
        delay_min=_pause(first_given(payload.get("delayMin"), payload.get("delay_min")), 30),
        delay_max=_pause(first_given(payload.get("delayMax"), payload.get("delay_max")), 60),
        max_dms=as_int(first_given(payload.get("maxDms"), payload.get("max_dms")), 50),
        account_id=as_int(first_given(payload.get("accountId"), payload.get("account_id")), 1),
        session_id=str(session_id) if session_id is not None else default_session_id,
        message_mode=str(first_given(payload.get("messageMode"), payload.get("message_mode")) or "manual"),
        ai_prompt=str(first_given(payload.get("aiPrompt"), payload.get("ai_prompt")) or ""),
        openrouter_api_key=str(
            first_given(payload.get("openrouterApiKey"), payload.get("openrouter_api_key")) or ""
        ),
    )


__all__ = [
    "DMOutreachRequest",
    "dm_messages_from_payload",
    "dm_outreach_request_from_payload",
    "dm_read_config_from_payload",
    "dm_send_config_from_payload",
]
