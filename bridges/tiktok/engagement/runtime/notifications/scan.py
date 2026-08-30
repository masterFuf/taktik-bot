"""Scan TikTok's new followers so the attribution can answer "did we earn them?".

The question the front already knows how to ask -- `NotificationAttributionService` -- is: of the
people who followed us this week, how many had we engaged first, and with what? It answers it by
joining each notification's actor to our own past `interactions` rows dated BEFORE the follow.

So the scan's job is small and exact: put one row per new follower into `notifications`, under a
HANDLE. Everything else was already built for Instagram and is platform-generic.

The cost is the handle. TikTok's new-followers page renders display names and nothing else --
`Allocin(gl)és` where the handle is `allocingles` -- so each one has to be opened and read, about
thirteen seconds apiece. That is why there is a budget, and why what the budget leaves out is
reported rather than dropped quietly: a scan that resolved four of twenty and said "4 followers"
would look exactly like an account that gained four.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bridges.tiktok.engagement.runtime.notifications.persistence import (
    looks_like_handle,
    record_scan_notifications,
)
from bridges.tiktok.runtime.ipc import logger

#: The notification type the `follows` attribution category looks for. Same vocabulary Instagram
#: writes, because the read model is shared and it filters on `n.type IN (...)`.
NEW_FOLLOWER_TYPE = "new_follower"


def scan_new_followers(
    device: Any,
    *,
    account_username: Optional[str],
    max_resolutions: int = 10,
) -> Dict[str, Any]:
    """Read the new-followers page, resolve handles, and persist one notification each.

    Returns what happened, in enough detail to tell the three different kinds of nothing apart:
    the page would not open, the page was empty, or the page was full and the budget ran out.
    """
    from taktik.core.social_media.tiktok.actions.atomic.dm_actions import DMActions

    dm = DMActions(device)
    result: Dict[str, Any] = {
        "opened": False,
        "listed": 0,
        "resolved": 0,
        "unresolved": 0,
        "skipped_over_budget": 0,
        "new": 0,
        "items": [],
    }

    if not dm.open_new_followers_page():
        logger.warning("[NOTIF] La page « Nouveaux followers » n'a pas pu être ouverte")
        return result
    result["opened"] = True

    rows = dm.get_new_followers(max_items=50)
    result["listed"] = len(rows)
    if not rows:
        logger.info("[NOTIF] Aucun nouveau follower listé")
        return result

    items: List[Dict[str, Any]] = []
    for row in rows:
        shown = (row.get("username") or "").strip()
        if not shown:
            continue
        if len(items) >= max_resolutions:
            result["skipped_over_budget"] += 1
            continue

        # Already a handle on some rows; opening the profile is only worth its thirteen seconds
        # when it is not.
        handle = shown if looks_like_handle(shown) else (dm.open_new_follower_profile(shown) or "")
        if not looks_like_handle(handle):
            result["unresolved"] += 1
            logger.warning(f"[NOTIF] Pseudo non résolu pour {shown!r} — non écrit")
            continue

        result["resolved"] += 1
        items.append({
            "type": NEW_FOLLOWER_TYPE,
            "username": handle,
            # The row's own wording, kept as the screen wrote it. The read model dates a
            # notification by (scan time - this label), so it is not decoration.
            "time": row.get("activity") or "",
            "label": shown,
            "has_action": bool(row.get("can_follow_back")),
        })

        # Opening a profile leaves the phone on it. Without coming back, the next row is looked
        # for on a screen that has no list.
        if not looks_like_handle(shown):
            dm.open_new_followers_page()

    if result["skipped_over_budget"]:
        logger.warning(
            f"[NOTIF] {result['skipped_over_budget']} follower(s) au-delà du budget de "
            f"{max_resolutions} résolutions — ni résolus ni écrits"
        )

    flags = record_scan_notifications(account_username, items)
    result["new"] = sum(1 for flag in flags if flag)
    result["items"] = items
    logger.info(
        f"[NOTIF] {result['listed']} listé(s), {result['resolved']} résolu(s), "
        f"{result['new']} nouveau(x)"
    )
    return result


__all__ = ["NEW_FOLLOWER_TYPE", "scan_new_followers"]
