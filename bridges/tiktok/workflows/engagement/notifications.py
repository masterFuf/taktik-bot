#!/usr/bin/env python3
"""TikTok notifications workflow: read what came in, and answer what is worth answering.

Instagram has had this for a while; TikTok had no workflow of the kind at all. What the platform
offers is four things, and this runs whichever the config asks for:

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
"""

from typing import Any, Dict, Optional

from bridges.tiktok.runtime.ipc import logger, send_log, send_message, send_status
from bridges.tiktok.runtime.startup import tiktok_startup


def run_notifications_workflow(config: Dict[str, Any]) -> int:
    """Run the notifications pass. Returns a process exit code."""
    device_id = config.get("deviceId") or config.get("device_id") or ""
    manager, bot_username = tiktok_startup(device_id, fetch_profile=True)
    if manager is None:
        send_status("error", "Could not start TikTok")
        return 1

    device = manager.device_manager.device
    stats: Dict[str, Any] = {
        "new_followers_listed": 0,
        "new_followers_recorded": 0,
        "activity_read": 0,
        "activity_by_kind": {},
        "hello_sent": 0,
        "suggested_followed": 0,
    }

    try:
        _scan_followers(device, config, bot_username, stats)
        _read_activity(device, config, stats)
        _say_hello(device, config, stats)
        _follow_suggested(device, config, stats)
    except Exception as exc:
        logger.error(f"Notifications workflow failed: {exc}")
        send_status("error", str(exc))
        send_message("notifications_result", success=False, stats=stats, error=str(exc))
        return 1

    send_status("success", "Notifications pass finished")
    send_message("notifications_result", success=True, stats=stats)
    logger.info(f"🔔 {stats}")
    return 0


# ----------------------------------------------------------------------------------------------


def _scan_followers(device, config: Dict[str, Any], bot_username: Optional[str], stats) -> None:
    if not config.get("scanNewFollowers", True):
        return
    from bridges.tiktok.engagement.runtime.notifications.scan import scan_new_followers

    send_status("running", "Reading new followers")
    outcome = scan_new_followers(
        device,
        account_username=bot_username,
        max_resolutions=int(config.get("maxFollowerResolutions", 10)),
    )
    stats["new_followers_listed"] = outcome["listed"]
    stats["new_followers_recorded"] = outcome["resolved"]
    # Said out loud: a budget that silently drops half the list looks exactly like a quiet week.
    if outcome["skipped_over_budget"]:
        send_log("warning", f"{outcome['skipped_over_budget']} follower(s) left unresolved (budget)")


def _read_activity(device, config: Dict[str, Any], stats) -> None:
    if not config.get("readActivity", True):
        return
    import collections

    from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    send_status("running", "Reading the activity page")
    # Back to the inbox first. The step before this one ends on the new-followers page or on a
    # profile, and the Activity entry only exists in the inbox -- measured: without this the read
    # returned 0 rows on an account that had 24, which reads as a quiet week rather than as being
    # on the wrong screen.
    if not DMActions(device).navigate_to_inbox():
        send_log("warning", "The inbox could not be opened")
        return

    activity = ActivityActions(device)
    # Expanded: the summary shows a handful of rows and stops, which reads exactly like an
    # account nobody has interacted with.
    if not activity.open_activity(expand=True):
        send_log("warning", "The activity page could not be opened")
        return

    rows = activity.read_activity(max_rows=int(config.get("maxActivityRows", 30)))
    stats["activity_read"] = len(rows)
    stats["activity_by_kind"] = dict(collections.Counter(row.kind for row in rows))
    for row in rows:
        send_message(
            "activity_row",
            kind=row.kind,
            usernames=row.usernames,
            others_count=row.others_count,
            age=row.age_label,
            post_count=row.post_count,
        )


def _say_hello(device, config: Dict[str, Any], stats) -> None:
    budget = int(config.get("maxHellos", 0))
    if budget <= 0:
        return
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    send_status("running", "Saying hello")
    dm = DMActions(device)
    if not dm.navigate_to_inbox():
        send_log("warning", "The inbox could not be opened")
        return

    for name in dm.say_hello_candidates()[:budget]:
        if dm.say_hello(name):
            stats["hello_sent"] += 1
            send_message("hello_sent", name=name)


def _follow_suggested(device, config: Dict[str, Any], stats) -> None:
    budget = int(config.get("maxSuggestedFollows", 0))
    if budget <= 0:
        return
    from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    send_status("running", "Following suggested accounts")
    DMActions(device).navigate_to_inbox()
    activity = ActivityActions(device)
    # NOT expanded: the suggestions block does not exist on the "Tout voir" list.
    if not activity.open_activity(expand=False):
        send_log("warning", "The activity page could not be opened")
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
            stats["suggested_followed"] += 1
            send_message("suggested_followed", name=suggestion["name"])


__all__ = ["run_notifications_workflow"]
