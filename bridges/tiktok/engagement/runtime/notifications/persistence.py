"""Notifications persistence for TikTok, on the same table Instagram already writes.

Nothing here is new machinery. `notifications` is cross-platform, `NotificationService
.record_notifications(platform=...)` takes the platform as a parameter, and the attribution query
that reads it back is already keyed on `n.platform` -- its own comment says TikTok "naturally
returns an empty summary (0 rows) rather than an error". It returned empty because nobody was
writing. This writes.

What the attribution does with the rows, and therefore the one thing that has to be right: it
LEFT JOINs the notification's actor to our past `interactions` on

    a.uname = lower(n.actor_username) AND a.account_id = n.account_id
    AND datetime(a.t) <= datetime(n.first_seen_at)

-- every like, comment, DM and story view we did to that person BEFORE they followed us. That is
the whole question ("did we earn this follower?"), and it hangs on `actor_username` being a
HANDLE.

Which is why this module refuses display names. TikTok's new-followers page and Activity page both
render display names -- `Allocin(gl)és` for @allocingles -- and a row filed under one joins to
nothing, so the follower shows up as "never engaged". That is a confident wrong answer, and it is
worse than no row: an empty attribution reads as "we have not scanned", a poisoned one reads as
"this campaign does nothing".

Best-effort throughout: persisting must never break a scan. Never logs a notification body.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bridges.tiktok.runtime.ipc import logger
from taktik.core.database.notifications import NotificationService
from taktik.core.database.tiktok_account_identity import (
    looks_like_tiktok_handle,
    resolve_tiktok_account_id,
)

_PLATFORM = "tiktok"

#: Re-exported so callers have the same test the writer applies: a scan that resolves handles one
#: profile at a time should know which rows it still owes a resolution to, rather than discovering
#: later that they were dropped.
#:
#: A LAST LINE, not the mechanism. An all-lowercase display name with no spaces is
#: indistinguishable from a handle by shape. What keeps the data honest is the caller: handles come
#: from opening the profile and reading them.
looks_like_handle = looks_like_tiktok_handle


def resolve_account_id(username: Optional[str]) -> Optional[int]:
    """Map the connected TikTok account to an account id, creating it if needed.

    Through `resolve_tiktok_account_id`, which goes to the TIKTOK repository. The obvious
    `get_db_service().get_or_create_account(...)` is what this used to call, and it resolves
    against Instagram -- see that module for what that cost.
    """
    return resolve_tiktok_account_id(username, logger=logger)


def record_scan_notifications(
    account_username: Optional[str],
    items: List[Dict[str, Any]],
) -> List[bool]:
    """Persist scanned notifications; return `is_new` per item, in the same order.

    Items whose `username` is not a handle are recorded as NOT NEW and are not written at all --
    see the module docstring. The count of those is logged, because a scan that silently drops
    half its rows looks exactly like an account with half the activity.
    """
    if not items:
        return []

    account_id = resolve_account_id(account_username)
    if account_id is None:
        logger.warning(f"[NOTIF] No TikTok account for {account_username!r} — nothing persisted")
        return [False] * len(items)

    writable: List[Dict[str, Any]] = []
    positions: List[int] = []
    for index, item in enumerate(items):
        if looks_like_handle(item.get("username")):
            writable.append(item)
            positions.append(index)

    dropped = len(items) - len(writable)
    if dropped:
        logger.warning(
            f"[NOTIF] {dropped}/{len(items)} notification(s) sans pseudo résolu — non écrites "
            "(elles se joindraient à rien et compteraient comme « jamais engagé »)"
        )
    if not writable:
        return [False] * len(items)

    flags = [False] * len(items)
    try:
        written = NotificationService.record_notifications(
            platform=_PLATFORM, account_id=account_id, items=writable,
        )
    except Exception as exc:
        logger.warning(f"[NOTIF] Failed to persist TikTok notifications: {exc}")
        return flags

    for position, is_new in zip(positions, written):
        flags[position] = bool(is_new)
    logger.info(
        f"[NOTIF] {sum(flags)} nouvelle(s) notification(s) sur {len(writable)} écrite(s)"
    )
    return flags


__all__ = ["looks_like_handle", "record_scan_notifications", "resolve_account_id"]
