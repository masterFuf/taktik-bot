"""Notifications persistence wiring for the Instagram notifications bridge.

Best-effort: persisting must NEVER break the scan flow.
Source of truth = Bot (records into the ``notifications`` table via NotificationService).
Security (AGENTS): never log the notification body — only usernames / counts / types.

The activity feed has no account header (unlike the DM inbox's igds_action_bar_title),
so the owning account is passed in by the front (resolved via getLatestDeviceAccounts) —
see notifications-persistence-spec.md. Linking the actor to social_profiles + computing
attribution is deferred to a later step (this module only dedups + flags is_new).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bridges.instagram.runtime.ipc import logger
from taktik.core.database import configure_db_service, get_db_service
from taktik.core.database.notifications import NotificationService

_PLATFORM = "instagram"

# A real Instagram @handle (the connected account passed by the front).
_HANDLE_RE = re.compile(r"^[a-zA-Z0-9._]{1,30}$")


def _looks_like_handle(value: str) -> bool:
    return bool(value) and bool(_HANDLE_RE.match(value))


def _account_id_for(username: str) -> Optional[int]:
    """Map the connected-account username to an account id (created if needed)."""
    username = (username or "").strip().lower()
    if not _looks_like_handle(username):
        return None
    try:
        configure_db_service()
        account_id, _ = get_db_service().get_or_create_account(username, is_bot=True)
        return account_id
    except Exception as exc:
        logger.warning(f"[NOTIF] Could not resolve account @{username}: {exc}")
        return None


def record_scan_notifications(
    account_username: Optional[str],
    items: List[Dict[str, Any]],
) -> List[bool]:
    """Persist scanned notifications for the logged-in account; return ``is_new`` per item.

    Best-effort: a missing account / DB returns all-False and never raises into the scan.
    NEVER logs the notification body.
    """
    if not items:
        return []
    account_id = _account_id_for(account_username or "")
    if account_id is None:
        return [False] * len(items)
    try:
        return NotificationService.record_notifications(
            platform=_PLATFORM, account_id=account_id, items=items,
        )
    except Exception as exc:
        logger.warning(f"[NOTIF] Failed to persist notifications: {exc}")
        return [False] * len(items)


__all__ = ["record_scan_notifications"]
