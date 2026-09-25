"""One reading of a TikTok DM payload (read, send), for the bridge and the Agent handler alike.

The wire form is the desktop page's camelCase (`TikTokDM.tsx`, `TikTokUnreplied.tsx` for the
replies, and the scheduler's DM node); the snake_case names an Agent plan or a CLI call writes stay
accepted. Every key is read by name, so the app's config contract test can see which ones the bot
reads.
"""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
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


__all__ = ["dm_messages_from_payload", "dm_read_config_from_payload", "dm_send_config_from_payload"]
