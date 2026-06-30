"""DM persistence wiring for the Instagram DM bridge.

Best-effort: persisting conversations/replies must NEVER break the read/send flow.
Source of truth = Bot (records into dm_threads / dm_messages via DmConversationService).
Security (AGENTS): never log DM content — only usernames / counts.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from bridges.instagram.runtime.ipc import logger
from taktik.core.database import configure_db_service, get_db_service
from taktik.core.database.messaging import DmConversationService

_PLATFORM = "instagram"

# A real Instagram @handle: letters/digits/dot/underscore only. The DM inbox sometimes
# shows a display name (spaces, emoji) instead — we won't link those to social_profiles
# (a profile visit, deferred, is needed to resolve the real handle).
_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def _looks_like_handle(value: str) -> bool:
    return bool(value) and bool(_HANDLE_RE.match(value))


def _account_id_for(bridge, username: str) -> Optional[int]:
    """Map a detected logged-in username to an account id (created if needed) + cache it."""
    username = (username or "").strip().lower()
    if not _looks_like_handle(username):
        return None
    configure_db_service()
    account_id, _ = get_db_service().get_or_create_account(username, is_bot=True)
    bridge._dm_account_id = account_id
    # Cache the handle too so the read result can tell the front which account this inbox
    # belongs to (front loads that account's AI persona for reply generation).
    bridge._dm_account_username = username
    return account_id


def account_id_from_inbox_header(bridge) -> Optional[int]:
    """Identify the logged-in account by reading the inbox header (no navigation).

    The DM inbox shows the account's @handle in the "username v" switcher at the top
    (resource-id ``igds_action_bar_title``). Must be called while on the inbox. Returns
    None if the header is unreadable, so the caller can fall back to a profile visit.
    """
    cached = getattr(bridge, "_dm_account_id", None)
    if cached is not None:
        return cached
    try:
        from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS

        element = bridge.device(resourceId=DM_SELECTORS.inbox_title_resource_id)
        if not element.exists(timeout=2):
            return None
        username = (element.get_text() or "").strip()
        account_id = _account_id_for(bridge, username)
        if account_id is not None:
            logger.info(f"[DM] Account from inbox header @{username.lower()} (id={account_id})")
        return account_id
    except Exception as exc:
        logger.warning(f"[DM] Could not read account from inbox header: {exc}")
        return None


def resolve_account_id(bridge) -> Optional[int]:
    """Identify the logged-in account by visiting our own profile (cached on the bridge).

    Fallback used only when the inbox header could not be read.
    Returns None on failure — persistence is then skipped, the DM flow continues.
    """
    cached = getattr(bridge, "_dm_account_id", None)
    if cached is not None:
        return cached
    try:
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
        from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

        nav = NavigationActions(bridge.device_manager)
        profile_biz = ProfileBusiness(bridge.device_manager)

        nav.navigate_to_profile_tab()
        time.sleep(1.5)
        info = profile_biz.get_complete_profile_info(navigate_if_needed=False, enrich=False)
        username = (info.get("username") or "").strip() if info else ""
        account_id = _account_id_for(bridge, username)
        if account_id is None:
            logger.warning("[DM] Could not detect the logged-in account; DM persistence skipped")
            return None
        logger.info(f"[DM] Resolved logged-in account @{username.lower()} (id={account_id})")
        return account_id
    except Exception as exc:
        logger.warning(f"[DM] Account identity resolution failed: {exc}")
        return None


def account_id_for_send(bridge, partner_username: str) -> Optional[int]:
    """Account to attribute a reply to. Reuse the thread read earlier (no profile visit);
    fall back to resolving our identity only when the thread is unknown."""
    existing = DmConversationService.lookup_account_id(_PLATFORM, partner_username)
    if existing is not None:
        return existing
    return resolve_account_id(bridge)


def _get_or_create_partner_profile_id(handle: str) -> Optional[int]:
    """Register the interlocutor as a social_profiles row and return its id.

    Only call with a real @handle (the repo is Instagram-scoped, platform implied).
    """
    try:
        profile_id, _ = get_db_service().get_or_create_profile({"username": handle})
        return profile_id
    except Exception as exc:
        logger.warning(f"[DM] get_or_create_profile failed for @{handle}: {exc}")
        return None


def _messages_payload(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for message in conv.get("messages", []) or []:
        payload.append(
            {
                "direction": "sent" if message.get("is_sent") else "received",
                "text": message.get("text"),
                "msg_type": message.get("type", "text"),
                # Raw IG date/time label (e.g. "Jun 12, 10:29 AM") -> displayed_at for display
                # only; the message's sent_at keeps its sortable insertion-time default.
                "displayed_at": message.get("timestamp"),
            }
        )
    return payload


def record_conversations(account_id: Optional[int], conversations: List[Dict[str, Any]]) -> None:
    """Persist the read conversations + their messages. Best-effort."""
    if not account_id or not conversations:
        return
    try:
        configure_db_service()
    except Exception:
        pass

    saved = 0
    for conv in conversations:
        # Same identifier the front uses to reply (open_conversation) -> thread key matches send.
        username = (conv.get("username") or conv.get("inbox_username") or "").strip()
        messages = _messages_payload(conv)
        # Skip non-conversations (e.g. the "your note" row at the top of the IG inbox has no messages).
        if not username or not messages:
            continue
        try:
            # Only link to social_profiles when we have a real @handle; a display name
            # (spaces/emoji) would pollute the table. Real-handle resolution via a profile
            # visit is deferred.
            link_handle = username.lower() if _looks_like_handle(username) else None
            partner_profile_id = _get_or_create_partner_profile_id(link_handle) if link_handle else None
            DmConversationService.record_conversation(
                platform=_PLATFORM,
                account_id=account_id,
                partner_username=username,
                messages=messages,
                partner_profile_id=partner_profile_id,
                external_thread_id=conv.get("inbox_username"),
                is_group=bool(conv.get("is_group")),
                can_reply=bool(conv.get("can_reply", True)),
                last_message_is_ours=bool(conv.get("last_message_is_ours")),
            )
            saved += 1
        except Exception as exc:
            logger.warning(f"[DM] Failed to persist conversation @{username}: {exc}")
    if saved:
        logger.info(f"[DM] Persisted {saved} conversation(s)")


def last_known_message(account_id: Optional[int], inbox_username: str) -> Optional[Dict[str, Any]]:
    """Stored last message ``{text, is_ours}`` for a known thread, or None. Best-effort.

    Used by the reader to short-circuit a conversation whose last message is already on
    record (no new activity) — looked up from the inbox row BEFORE opening the thread.
    """
    if not account_id or not inbox_username:
        return None
    # DmConversationService.last_known_message opens its own lightweight sqlite connection — no
    # configure_db_service() needed. This runs before EVERY thread open, so keep it cheap (the
    # heavy LocalDatabaseClient re-init per conversation is unnecessary here).
    try:
        return DmConversationService.last_known_message(_PLATFORM, account_id, inbox_username)
    except Exception as exc:
        logger.warning(f"[DM] last_known_message lookup failed: {exc}")
        return None


def thread_answer_state(account_id: Optional[int], inbox_username: str) -> Dict[str, Any]:
    """Whether WE already answered a thread + its known incoming texts (``{has_sent, received_texts}``).
    Best-effort; empty state on any failure. Used by the reader's vanish-mode safety net."""
    empty: Dict[str, Any] = {"has_sent": False, "received_texts": []}
    if not account_id or not inbox_username:
        return empty
    try:
        return DmConversationService.thread_answer_state(_PLATFORM, account_id, inbox_username)
    except Exception as exc:
        logger.warning(f"[DM] thread_answer_state lookup failed: {exc}")
        return empty


def mark_thread_answered(account_id: Optional[int], inbox_username: str) -> None:
    """Re-assert in the DB that WE answered a thread (vanish-mode safety net). Best-effort."""
    if not account_id or not inbox_username:
        return
    try:
        DmConversationService.mark_thread_answered(_PLATFORM, account_id, inbox_username)
    except Exception as exc:
        logger.warning(f"[DM] mark_thread_answered failed: {exc}")


def record_reply(account_id: Optional[int], partner_username: str, message: str) -> None:
    """Persist a reply we sent. Best-effort."""
    if not account_id or not partner_username:
        return
    try:
        # The send path runs in its own DB context; configure the service before resolving the
        # partner profile id (otherwise get_db_service() raises "not configured"). Best-effort.
        try:
            configure_db_service()
        except Exception:
            pass
        link_handle = partner_username.lower() if _looks_like_handle(partner_username) else None
        partner_profile_id = _get_or_create_partner_profile_id(link_handle) if link_handle else None
        DmConversationService.record_sent_message(
            platform=_PLATFORM,
            account_id=account_id,
            partner_username=partner_username,
            text=message,
            partner_profile_id=partner_profile_id,
        )
    except Exception as exc:
        logger.warning(f"[DM] Failed to persist sent reply to @{partner_username}: {exc}")


__all__ = [
    "account_id_from_inbox_header",
    "resolve_account_id",
    "account_id_for_send",
    "last_known_message",
    "mark_thread_answered",
    "record_conversations",
    "record_reply",
    "thread_answer_state",
]
