"""DM persistence wiring for the TikTok DM bridges.

Best-effort: persisting conversations must NEVER break the read/send flow.
Source of truth = Bot (records into dm_threads / dm_messages via DmConversationService).
Security (AGENTS): never log DM content -- only usernames / counts.

TikTok read nothing into those tables. The schema was written cross-platform from the start
(`platform` column, an `unread_count` comment that names TikTok), and the service is fully
parameterised, so what was missing was the wiring -- with one real obstacle in the way.

**The reader cannot see who wrote a bubble.** `DMActions.get_messages` marks every message
`is_sent: False` and says so in a comment. Filing that as-is would produce a table stating that
we never answered anybody, and "have we already replied" is precisely the question these tables
exist to answer -- a wrong answer there is worse than no table at all.

So direction is not read off the screen, it is remembered. What WE send is certain at send time
and is recorded then; a later read matches a text against that record. The rule is:

    a text already on record as ours, in this thread, is ours -- everything else is received.

Its one blind spot is stated rather than hidden: a correspondent echoing one of our messages
back, byte for byte, is filed as ours. That is the same class of limitation the schema already
accepts for its content hash, and it does not affect the answered/unanswered signal.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bridges.tiktok.runtime.ipc import logger
from taktik.core.database import configure_db_service, get_db_service
from taktik.core.database.messaging import DmConversationService

_PLATFORM = "tiktok"

# A real TikTok @handle: letters/digits/dot/underscore. A conversation header can also show a
# display name (spaces, emoji) -- those are kept as the thread partner but never linked to
# social_profiles, which would pollute the table with names that are not handles.
_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def _looks_like_handle(value: str) -> bool:
    return bool(value) and bool(_HANDLE_RE.match(value))


def resolve_account_id(bot_username: Optional[str]) -> Optional[int]:
    """Map the logged-in TikTok handle to an account id, creating it if needed.

    `tiktok_startup` already reads our own profile at launch and returns that handle; the DM
    runners simply discarded it. No extra navigation, no second profile visit.
    """
    username = (bot_username or "").strip().lower().lstrip("@")
    if not _looks_like_handle(username):
        logger.warning("[DM] Logged-in TikTok account unreadable; DM persistence skipped")
        return None
    try:
        configure_db_service()
        account_id, _ = get_db_service().get_or_create_account(username, is_bot=True)
        logger.info(f"[DM] Resolved logged-in account @{username} (id={account_id})")
        return account_id
    except Exception as exc:
        logger.warning(f"[DM] Account identity resolution failed: {exc}")
        return None


def _partner_profile_id(handle: str) -> Optional[int]:
    try:
        profile_id, _ = get_db_service().get_or_create_profile({"username": handle})
        return profile_id
    except Exception as exc:
        logger.warning(f"[DM] get_or_create_profile failed for @{handle}: {exc}")
        return None


def _messages_payload(conversation: Dict[str, Any], known_sent: List[str]) -> List[Dict[str, Any]]:
    """Turn read messages into rows, resolving direction from what we know we sent."""
    ours = {text.strip() for text in known_sent if text and text.strip()}
    payload: List[Dict[str, Any]] = []
    for message in conversation.get("messages", []) or []:
        text = message.get("text")
        payload.append(
            {
                "direction": "sent" if (text or "").strip() in ours else "received",
                "text": text,
                "msg_type": message.get("type", "text"),
                # TikTok shows a date separator ("Aujourd'hui 13:12") rather than a per-bubble
                # label, so most messages carry none. Absent stays absent: sent_at keeps its
                # sortable insertion default and nothing is invented for display.
                "displayed_at": message.get("timestamp"),
            }
        )
    return payload


def record_conversations(
    account_id: Optional[int], conversations: List[Dict[str, Any]]
) -> None:
    """Persist the read conversations + their messages. Best-effort."""
    if not account_id or not conversations:
        return
    try:
        configure_db_service()
    except Exception:
        pass

    saved = 0
    for conversation in conversations:
        partner = (conversation.get("name") or conversation.get("username") or "").strip()
        if not partner:
            continue

        known_sent = DmConversationService.known_sent_texts(_PLATFORM, account_id, partner)
        messages = _messages_payload(conversation, known_sent)
        if not messages:
            # A conversation opened but unread (or a group we skipped) carries no message. The
            # thread row would then claim a zero-message conversation over whatever a previous
            # pass had recorded, so it is left alone.
            continue

        try:
            link_handle = partner.lower() if _looks_like_handle(partner) else None
            DmConversationService.record_conversation(
                platform=_PLATFORM,
                account_id=account_id,
                partner_username=partner,
                messages=messages,
                partner_profile_id=_partner_profile_id(link_handle) if link_handle else None,
                is_group=bool(conversation.get("is_group")),
                can_reply=bool(conversation.get("can_reply", True)),
                last_message_is_ours=messages[-1]["direction"] == "sent",
                unread_count=int(conversation.get("unread_count") or 0),
            )
            saved += 1
        except Exception as exc:
            logger.warning(f"[DM] Failed to persist conversation with {partner}: {exc}")
    if saved:
        logger.info(f"[DM] Persisted {saved} conversation(s)")


def record_sent(account_id: Optional[int], partner_username: str, message: str) -> None:
    """Persist a message we sent. Best-effort.

    This is the certain half of the direction question, and the reason the reader can resolve
    the other half at all.
    """
    if not account_id or not partner_username or not message:
        return
    try:
        try:
            configure_db_service()
        except Exception:
            pass
        link_handle = partner_username.lower() if _looks_like_handle(partner_username) else None
        DmConversationService.record_sent_message(
            platform=_PLATFORM,
            account_id=account_id,
            partner_username=partner_username,
            text=message,
            partner_profile_id=_partner_profile_id(link_handle) if link_handle else None,
        )
    except Exception as exc:
        logger.warning(f"[DM] Failed to persist sent message to {partner_username}: {exc}")


def record_sent_results(
    account_id: Optional[int], messages: List[Dict[str, Any]], results: List[Dict[str, Any]]
) -> None:
    """Persist the messages a bulk send actually delivered.

    Only the successful ones: a row for a message that never left would answer "have we already
    replied" with a yes that no screen can back up.
    """
    if not account_id:
        return
    by_conversation = {
        str(item.get("conversation", "")).strip(): str(item.get("message", ""))
        for item in messages
        if isinstance(item, dict)
    }
    for result in results or []:
        if not result.get("success"):
            continue
        conversation = str(result.get("conversation", "")).strip()
        text = by_conversation.get(conversation)
        if conversation and text:
            record_sent(account_id, conversation, text)


__all__ = [
    "record_conversations",
    "record_sent",
    "record_sent_results",
    "resolve_account_id",
]
