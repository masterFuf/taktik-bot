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

The two gestures are FILED, under a handle, like every other follow and DM the bot makes: a
suggested follow is a `FOLLOW` interaction (the day's follow count, the unfollow), a wave is a
`sent_dms` marker (the "already written to" guard). Their rows show display names only, so the
handle is read where it is printed -- the suggestion's profile, the thread's profile card. A
suggestion whose handle cannot be read is not followed; a wave whose handle cannot be read is sent
and said to be unrecorded. With no readable account, neither gesture is made.

Events go through an injected notifier shaped like the bridge IPC (`status`, `log`, `send`). The
only `send` is the closing `notifications_result`, which the page reads; a notifier without `send`
(the CLI's) drops it and the caller gets the same result as a return value.
"""

from __future__ import annotations

import collections
from typing import Any, Dict, Optional

from loguru import logger

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


class _ActingAccount:
    """The account the gestures are filed under: resolved once, and only when a gesture asks."""

    def __init__(self, username: Optional[str]) -> None:
        self._username = username
        self._resolved = False
        self._id: Optional[int] = None

    def id(self) -> Optional[int]:
        if not self._resolved:
            from taktik.core.database.tiktok_account_identity import resolve_tiktok_account_id

            self._id = resolve_tiktok_account_id(self._username, logger=logger)
            self._resolved = True
        return self._id


def run_notifications_pass(
    device: Any,
    settings: NotificationsSettings,
    *,
    bot_username: Optional[str],
    notifier: Any,
) -> Dict[str, Any]:
    """Run the four steps in order. A step that raises ends the pass, reported as failed."""
    stats = new_pass_stats()
    account = _ActingAccount(bot_username)
    try:
        _scan_followers(device, settings, bot_username, stats, notifier)
        _read_activity(device, settings, stats, notifier)
        _say_hello(device, settings, account, stats, notifier)
        _follow_suggested(device, settings, account, stats, notifier)
    except Exception as exc:
        logger.error(f"Notifications workflow failed: {exc}")
        _emit(notifier, "status", "error", str(exc))
        _emit(notifier, "send", "notifications_result", success=False, stats=stats, error=str(exc))
        return {"success": False, "stats": stats, "error": str(exc)}

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


def _say_hello(device, settings: NotificationsSettings, account: _ActingAccount, stats, notifier) -> None:
    budget = settings.max_hellos
    if budget <= 0:
        return
    account_id = account.id()
    if account_id is None:
        _emit(notifier, "log", "warning", "Hellos skipped: the account could not be read, so none could be recorded")
        return
    from taktik.core.database.tiktok_dm import record_say_hello
    from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions

    _emit(notifier, "status", "running", "Saying hello")
    dm = DMActions(device)
    if not dm.navigate_to_inbox():
        _emit(notifier, "log", "warning", "The inbox could not be opened")
        return

    unrecorded = 0
    for name in dm.say_hello_candidates()[:budget]:
        if not dm.say_hello(name):
            continue
        stats["hello_sent"] += 1
        # After the wave, not before: opening the thread first could take the offer off the row.
        handle = dm.resolve_conversation_handle(name)
        if handle:
            record_say_hello(account_id, handle)
        else:
            unrecorded += 1
        if not dm.is_on_inbox_page() and not dm.navigate_to_inbox():
            _emit(notifier, "log", "warning", "The inbox could not be reopened")
            break

    if unrecorded:
        _emit(notifier, "log", "warning", f"{unrecorded} hello(s) sent but not recorded (handle unreadable)")


def _follow_suggested(device, settings: NotificationsSettings, account: _ActingAccount, stats, notifier) -> None:
    budget = settings.max_suggested_follows
    if budget <= 0:
        return
    account_id = account.id()
    if account_id is None:
        _emit(notifier, "log", "warning",
              "Suggested follows skipped: the account could not be read, so no follow could be counted")
        return
    from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService
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

    unresolved = 0
    for suggestion in suggestions:
        if stats["suggested_followed"] >= budget:
            break
        name = suggestion["name"]
        # Before the follow: a follow nobody can file escapes the day's count and the unfollow.
        handle = activity.resolve_suggested_account_handle(name)
        if not handle:
            unresolved += 1
            if not activity.is_on_activity_page():
                _emit(notifier, "log", "warning", "Lost the activity page while reading a suggested account")
                break
            continue
        if activity.follow_suggested_account(name):
            stats["suggested_followed"] += 1
            if not TikTokFollowGraphService.record_follow(handle, account_id):
                _emit(notifier, "log", "warning", f"The follow of @{handle} could not be recorded")

    if unresolved:
        _emit(notifier, "log", "warning", f"{unresolved} suggested account(s) not followed (handle unreadable)")


__all__ = ["new_pass_stats", "run_notifications_pass"]
