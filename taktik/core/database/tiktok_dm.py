"""TikTok DM persistence: the conversations a read brings back, the messages we send, and the
anti-duplicate probes of the welcome DM.

Best-effort: persisting conversations must NEVER break the read or the send. Source of truth = Bot
(`dm_threads` / `dm_messages` through `DmConversationService`, `sent_dms` through `SentDMService`).
Security (AGENTS): never logs DM content, only usernames and counts.

Written by the DM read and send (`tiktok/.../workflows/dm/agent_handler.py`) and by the welcome
pass of the new-followers flow (`dm/welcome_pass.py`), from the desktop bridge and the CLI alike.

TikTok read nothing into those tables. The schema was written cross-platform from the start
(`platform` column, an `unread_count` comment that names TikTok), and the service is fully
parameterised, so what was missing was the wiring -- with one real obstacle in the way.

**Direction, once unreadable, is now measured.** `DMActions.get_messages` used to mark every
message `is_sent: False` -- the mobile UI names no sender -- which would have produced a table
stating we never answered anybody, precisely the question these tables exist to answer. The
reader now reads the bubble's ALIGNMENT, verified on both phones of a two-way conversation and
on both versions: the same two messages landed on opposite sides depending on which phone read
them.

What we record at send time is kept as a safety net underneath. A bubble whose bounds cannot be
read comes back `is_sent: False`, and a message we know we sent must not then be filed as
theirs. The net's one blind spot is stated rather than hidden: a correspondent echoing one of
our messages back byte for byte is filed as ours -- the same class of limitation the schema
already accepts for its content hash, and without effect on the answered/unanswered signal.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

from loguru import logger

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

    The session start already reads our own profile and hands that handle over: no extra
    navigation, no second profile visit.
    """
    username = (bot_username or "").strip().lower().lstrip("@")
    if not _looks_like_handle(username):
        logger.warning("[DM] Logged-in TikTok account unreadable; DM persistence skipped")
        return None
    # Through the TIKTOK repository. `get_db_service().get_or_create_account(...)` was what this
    # called, and it resolves against Instagram: TikTok DMs ended up filed under the INSTAGRAM id
    # of the same handle, while that account's TikTok interactions sat under another id. Nothing
    # errored; the rows simply belonged to nobody.
    from taktik.core.database.tiktok_account_identity import resolve_tiktok_account_id

    account_id = resolve_tiktok_account_id(username, logger=logger)
    if account_id is None:
        logger.warning("[DM] Account identity resolution failed")
        return None
    logger.info(f"[DM] Resolved logged-in account @{username} (id={account_id})")
    return account_id


def _configure_database() -> None:
    # Imported at call time, like the service itself: the database package owns the singleton.
    from taktik.core.database import configure_db_service

    try:
        configure_db_service()
    except Exception:
        pass


def _partner_profile_id(handle: str) -> Optional[int]:
    from taktik.core.database import get_db_service

    try:
        profile_id, _ = get_db_service().get_or_create_profile({"username": handle})
        return profile_id
    except Exception as exc:
        logger.warning(f"[DM] get_or_create_profile failed for @{handle}: {exc}")
        return None


def _messages_payload(conversation: Dict[str, Any], known_sent: List[str]) -> List[Dict[str, Any]]:
    """Turn read messages into rows.

    The reader reports direction itself, from the bubble's alignment -- measured on both phones of
    a two-way conversation, on 43.1.4 and 46.6.3, where the same two messages landed on opposite
    sides. What we recorded at send time stays as a SAFETY NET underneath: a bubble whose bounds
    could not be read comes back `is_sent: False`, and a message we know we sent must not then be
    filed as theirs.
    """
    ours = {text.strip() for text in known_sent if text and text.strip()}
    payload: List[Dict[str, Any]] = []
    for message in conversation.get("messages", []) or []:
        text = message.get("text")
        is_ours = bool(message.get("is_sent")) or (text or "").strip() in ours
        payload.append(
            {
                "direction": "sent" if is_ours else "received",
                "text": text,
                "msg_type": message.get("type", "text"),
                # TikTok shows a date separator rather than a per-bubble label, so most messages
                # carry none. Absent stays absent: sent_at keeps its sortable insertion default and
                # nothing is invented for display.
                "displayed_at": message.get("timestamp"),
            }
        )
    return payload


def record_conversations(account_id: Optional[int], conversations: List[Dict[str, Any]]) -> None:
    """Persist the read conversations and their messages. Best-effort."""
    if not account_id or not conversations:
        return
    _configure_database()

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
        _configure_database()
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


# ---------------------------------------------------------------------------
# Anti-duplicate probes of the welcome DM
# ---------------------------------------------------------------------------
# These go to the repositories rather than to `SentDMService` / `DmConversationService`, and
# they RAISE instead of returning False. Both services catch Exception and answer False, which
# reads as "never contacted" whether nobody was written to or the query blew up -- that swallow
# is how Instagram's cold DM ran for months with no duplicate protection at all. `WelcomeDmGuard`
# turns a raise into UNKNOWN and refuses the send; a False here would be a blind outreach.


def _open_database() -> sqlite3.Connection:
    """Open the local database, or raise. A missing file is a refusal, not an empty answer."""
    from taktik.core.database.local.paths import get_default_database_path

    db_path = get_default_database_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"local database not found at {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def sent_dm_already_recorded(account_id: int, handle: str) -> bool:
    """Has this account already written to @handle on TikTok? Raises when it cannot answer.

    `sent_dms` is SHARED with the cold DM workflow on purpose: someone we already wrote to is
    not a stranger to greet, whichever flow wrote first.
    """
    from taktik.core.database.repositories.messaging import SentDMRepository

    connection = _open_database()
    try:
        return SentDMRepository(connection).check_already_sent(account_id, handle, _PLATFORM)
    finally:
        connection.close()


def thread_carries_our_message(account_id: int, handle: str) -> bool:
    """Does a thread with @handle already hold a message WE sent? Raises when it cannot answer.

    `sent_dms` alone misses a conversation started from the inbox -- a manual answer, an
    auto-reply, the DM read workflow -- and none of those write that marker.
    """
    from taktik.core.database.repositories.messaging import (
        DmMessageRepository,
        DmThreadRepository,
    )

    connection = _open_database()
    try:
        threads = DmThreadRepository(connection)
        # `find_sync_id_for_inbox` does not create the tables itself; on a standalone database
        # the desktop has never opened, the lookup would raise and refuse every recipient.
        threads.ensure_table()
        sync_id = threads.find_sync_id_for_inbox(_PLATFORM, account_id, handle)
        if not sync_id:
            return False
        return DmMessageRepository(connection).has_sent_message(_PLATFORM, sync_id)
    finally:
        connection.close()


def record_welcome_dm(
    account_id: int,
    recipient: str,
    message: str,
    success: bool,
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
    platform: str = _PLATFORM,
) -> None:
    """Record a SENT welcome DM: the shared duplicate marker and the conversation itself.

    Only successes. `check_already_sent` matches a row whatever its `success` value, so writing
    a failed attempt would lock that recipient out of every later one -- the opposite of what a
    failure means. The cost is stated rather than hidden: a privacy-blocked account is visited
    again on the next run, which spends a profile visit and sends nothing.
    """
    if not success:
        logger.info(f"✉️ Welcome DM non abouti pour @{recipient} ({error_message or 'send failed'})")
        return

    from taktik.core.database.messaging import SentDMService

    try:
        SentDMService.record(account_id, recipient, message, True, None, session_id, platform=platform)
    except Exception as exc:
        logger.warning(f"[WELCOME] Marqueur sent_dms non écrit pour @{recipient}: {exc}")
    # The certain half of the direction question: the TikTok reader cannot see who wrote a
    # bubble, so a later inbox read recognises our own message only from this row.
    record_sent(account_id, recipient, message)


__all__ = [
    "record_conversations",
    "record_sent",
    "record_sent_results",
    "record_welcome_dm",
    "resolve_account_id",
    "sent_dm_already_recorded",
    "thread_carries_our_message",
]
