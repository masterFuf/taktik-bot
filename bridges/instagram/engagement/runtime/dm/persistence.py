"""DM persistence wiring for the Instagram DM bridge.

Best-effort: persisting conversations/replies must NEVER break the read/send flow.
Source of truth = Bot (records into dm_threads / dm_messages via DmConversationService).
Security (AGENTS): never log DM content — only usernames / counts.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from bridges.instagram.runtime.ipc import logger
from taktik.core.database import configure_db_service, get_db_service
from taktik.core.database.messaging import DmConversationService

_PLATFORM = "instagram"


def resolve_account_id(bridge) -> Optional[int]:
    """Identify the logged-in account by visiting our own profile (cached on the bridge).

    Returns None on failure — persistence is then skipped, the DM flow continues.
    """
    cached = getattr(bridge, "_dm_account_id", None)
    if cached is not None:
        return cached
    try:
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
        from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

        configure_db_service()
        nav = NavigationActions(bridge.device_manager)
        profile_biz = ProfileBusiness(bridge.device_manager)

        nav.navigate_to_profile_tab()
        time.sleep(1.5)
        info = profile_biz.get_complete_profile_info(navigate_if_needed=False, enrich=False)
        username = (info.get("username") or "").strip().lower() if info else ""
        if not username:
            logger.warning("[DM] Could not detect the logged-in account; DM persistence skipped")
            return None

        account_id, _ = get_db_service().get_or_create_account(username, is_bot=True)
        bridge._dm_account_id = account_id
        logger.info(f"[DM] Resolved logged-in account @{username} (id={account_id})")
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


def _get_or_create_partner_profile_id(username: str) -> Optional[int]:
    """Register the interlocutor as a social_profiles row (username is enough to link)."""
    try:
        profile_id, _ = get_db_service().get_or_create_profile(
            {"username": username, "platform": _PLATFORM}
        )
        return profile_id
    except Exception as exc:
        logger.warning(f"[DM] get_or_create_profile failed for @{username}: {exc}")
        return None


def _messages_payload(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for message in conv.get("messages", []) or []:
        payload.append(
            {
                "direction": "sent" if message.get("is_sent") else "received",
                "text": message.get("text"),
                "msg_type": message.get("type", "text"),
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
        username = (conv.get("username") or conv.get("inbox_username") or "").strip()
        if not username:
            continue
        try:
            partner_profile_id = _get_or_create_partner_profile_id(username.lower())
            DmConversationService.record_conversation(
                platform=_PLATFORM,
                account_id=account_id,
                partner_username=username,
                messages=_messages_payload(conv),
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


def record_reply(account_id: Optional[int], partner_username: str, message: str) -> None:
    """Persist a reply we sent. Best-effort."""
    if not account_id or not partner_username:
        return
    try:
        partner_profile_id = _get_or_create_partner_profile_id(partner_username.lower())
        DmConversationService.record_sent_message(
            platform=_PLATFORM,
            account_id=account_id,
            partner_username=partner_username,
            text=message,
            partner_profile_id=partner_profile_id,
        )
    except Exception as exc:
        logger.warning(f"[DM] Failed to persist sent reply to @{partner_username}: {exc}")


__all__ = ["resolve_account_id", "account_id_for_send", "record_conversations", "record_reply"]
