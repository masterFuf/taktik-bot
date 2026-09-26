"""TikTok notifications pass: read what came in, and answer what is worth answering.

Instagram has had this for a while; TikTok had no workflow of the kind at all. What the platform
offers is four things, and this runs whichever the settings ask for:

    new followers      -> recorded so the attribution can say whether we engaged them first
    activity           -> who liked, saved, reposted, commented, or looked
    say hello          -> the one-tap wave TikTok offers on threads we never opened
    suggested accounts -> follow, straight from the Activity summary

Two things it deliberately does NOT do.

It does not resolve a handle for every Activity row. The rows name people by display name, and
opening each one costs about twenty seconds and often lands on a video rather than a profile. So
Activity is READ -- counted, typed, reported -- and only the new-followers pass, where opening the
row is the only way in anyway, produces attribution rows.

And it does not re-open profiles the welcome pass has already opened. When that pass runs it
resolves every handle itself and records the notifications from what it already holds; this
workflow's own scan exists for runs where it does not.

Events go through an injected notifier shaped like the bridge IPC (`status`, `log`, `send`);
a notifier without `send` (the CLI's) drops the per-row events and keeps the rest.
"""

from __future__ import annotations

import collections
from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block

from .payload import NotificationsSettings


def _emit(notifier: Any, method: str, *args: Any, **kwargs: Any) -> None:
    target = getattr(notifier, method, None)
    if callable(target):
        target(*args, **kwargs)


def new_pass_stats() -> Dict[str, Any]:
    return {
        "new_followers_listed": 0,
        "new_followers_recorded": 0,
        "activity_read": 0,
        "activity_by_kind": {},
        "hello_sent": 0,
        "suggested_followed": 0,
    }


def _refused(device, action: str, target: str) -> bool:
    """After a gesture that writes: is TikTok refusing it? The one look (production detector)."""
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import (
        DetectionActions,
    )

    return look_for_action_block(DetectionActions(device), after=action, target=target)


def run_notifications_pass(
    device: Any,
    settings: NotificationsSettings,
    *,
    bot_username: Optional[str],
    notifier: Any,
) -> Dict[str, Any]:
    """Run the four steps in order. A step that raises ends the pass, reported as failed."""
    stats = new_pass_stats()
    try:
        # Each step that writes stops at the first refusal; the next steps do not start.
        steps = (
            lambda: _scan_followers(device, settings, bot_username, stats, notifier),
            lambda: _read_activity(device, settings, stats, notifier),
            lambda: _say_hello(device, settings, stats, notifier),
            lambda: _follow_suggested(device, settings, stats, notifier),
        )
        for step in steps:
            if run_halt.arret_demande():
                break
            step()
    except Exception as exc:
        logger.error(f"Notifications workflow failed: {exc}")
        _emit(notifier, "status", "error", str(exc))
        _emit(notifier, "send", "notifications_result", success=False, stats=stats, error=str(exc))
        return {"success": False, "stats": stats, "error": str(exc)}

    halt = run_halt.arret_demande()
    if halt:
        reason = halt.get("code")
        _emit(notifier, "status", "error", f"Notifications pass stopped: {reason}")
        _emit(notifier, "send", "notifications_result", success=False, stats=stats,
              stop_reason=reason)
        return {"success": False, "stats": stats, "stop_reason": reason}
    _emit(notifier, "status", "success", "Notifications pass finished")
    _emit(notifier, "send", "notifications_result", success=True, stats=stats)
    logger.info(f"🔔 {stats}")
    return {"success": True, "stats": stats}


def _scan_followers(device, settings: NotificationsSettings, bot_username, stats, notifier) -> None:
    if not settings.scan_new_followers:
        return
    from .scan import scan_new_followers

    _emit(notifier, "status", "running", "Reading new followers")
    outcome = scan_new_followers(
        device,
        account_username=bot_username,
        max_resolutions=settings.max_follower_resolutions,
    )
    stats["new_followers_listed"] = outcome["listed"]
    stats["new_followers_recorded"] = outcome["resolved"]
    # Said out loud: a budget that silently drops half the list looks exactly like a quiet week.
    if outcome["skipped_over_budget"]:
        _emit(notifier, "log", "warning", f"{outcome['skipped_over_budget']} follower(s) left unresolved (budget)")


def _read_activity(device, settings: NotificationsSettings, stats, notifier) -> None:
    if not settings.read_activity:
        return
    from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    _emit(notifier, "status", "running", "Reading the activity page")
    # Back to the inbox first. The step before this one ends on the new-followers page or on a
    # profile, and the Activity entry only exists in the inbox -- measured: without this the read
    # returned 0 rows on an account that had 24, which reads as a quiet week rather than as being
    # on the wrong screen.
    if not DMActions(device).navigate_to_inbox():
        _emit(notifier, "log", "warning", "The inbox could not be opened")
        return

    activity = ActivityActions(device)
    # Expanded: the summary shows a handful of rows and stops, which reads exactly like an
    # account nobody has interacted with.
    if not activity.open_activity(expand=True):
        _emit(notifier, "log", "warning", "The activity page could not be opened")
        return

    rows = activity.read_activity(max_rows=settings.max_activity_rows)
    stats["activity_read"] = len(rows)
    stats["activity_by_kind"] = dict(collections.Counter(row.kind for row in rows))
    for row in rows:
        _emit(
            notifier,
            "send",
            "activity_row",
            kind=row.kind,
            usernames=row.usernames,
            others_count=row.others_count,
            age=row.age_label,
            post_count=row.post_count,
        )


def _say_hello(device, settings: NotificationsSettings, stats, notifier) -> None:
    budget = settings.max_hellos
    if budget <= 0:
        return
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    _emit(notifier, "status", "running", "Saying hello")
    dm = DMActions(device)
    if not dm.navigate_to_inbox():
        _emit(notifier, "log", "warning", "The inbox could not be opened")
        return

    for name in dm.say_hello_candidates()[:budget]:
        if dm.say_hello(name):
            if _refused(device, "hello", name):
                return
            stats["hello_sent"] += 1
            _emit(notifier, "send", "hello_sent", name=name)


def _follow_suggested(device, settings: NotificationsSettings, stats, notifier) -> None:
    budget = settings.max_suggested_follows
    if budget <= 0:
        return
    from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    _emit(notifier, "status", "running", "Following suggested accounts")
    DMActions(device).navigate_to_inbox()
    activity = ActivityActions(device)
    # NOT expanded: the suggestions block does not exist on the "Tout voir" list.
    if not activity.open_activity(expand=False):
        _emit(notifier, "log", "warning", "The activity page could not be opened")
        return

    # The block sits at the bottom of the summary.
    suggestions = []
    for _ in range(8):
        suggestions = activity.read_suggested_accounts()
        if suggestions:
            break
        activity._scroll_down(scale=0.6)

    for suggestion in suggestions[:budget]:
        if activity.follow_suggested_account(suggestion["name"]):
            if _refused(device, "follow", suggestion["name"]):
                return
            stats["suggested_followed"] += 1
            _emit(notifier, "send", "suggested_followed", name=suggestion["name"])


__all__ = ["new_pass_stats", "run_notifications_pass"]
