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
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.database.repositories.notifications import NotificationRepository

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


def record_suggestion_follows(account_username: Optional[str],
                             labels: List[str]) -> int:
    """Persist the follows made from the suggestions block; returns the rows written.

    Same table and same action type as every other follow (`interactions`, 'FOLLOW'),
    so a run made from this surface shows up in the session history and the daily
    counters like any other — that was the whole point of doing it here.

    Known limit of the surface: it exposes the DISPLAYED label, never the @handle, so
    that label is what gets stored, with its provenance in `content`. The following_sync
    reconciles the real handles later.
    """
    if not labels:
        return 0
    account_id = _account_id_for(account_username or "")
    if account_id is None:
        logger.warning("[NOTIF] No account resolved: suggestion follows NOT recorded")
        return 0
    written = 0
    for label in labels:
        try:
            InstagramWorkflowStateService.record_individual_actions(
                username=label,
                action_type="FOLLOW",
                count=1,
                account_id=account_id,
                content="Suggestion Instagram (notifications)",
            )
            written += 1
        except Exception as exc:
            logger.warning(f"[NOTIF] Failed to record a suggestion follow: {exc}")
    return written


def build_known_checker(account_username: Optional[str]):
    """Predicate ``item -> bool`` = "already recorded for this account", for the scan's early-stop.

    Preloads the account's known content hashes ONCE so the scan can recognise already-seen
    notifications in memory and stop scrolling into old, already-scraped territory. Returns None
    when the account is unknown or nothing is recorded yet (=> the scan reads fully, as before).
    Best-effort: never raises into the scan.
    """
    account_id = _account_id_for(account_username or "")
    if account_id is None:
        return None
    try:
        known = NotificationService.known_content_hashes(_PLATFORM, account_id)
    except Exception as exc:
        logger.warning(f"[NOTIF] Could not preload known hashes: {exc}")
        return None
    if not known:
        return None  # first scan for this account -> read the whole feed

    def _is_known(item: Dict[str, Any]) -> bool:
        actor = (item.get("username") or "").strip().lower() or None
        chash = NotificationRepository.content_hash(
            _PLATFORM, account_id, item.get("type"), actor, item.get("text"), item.get("time"),
        )
        return chash in known

    return _is_known


__all__ = ["record_scan_notifications", "build_known_checker"]
