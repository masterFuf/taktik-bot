"""The ``follow_actor`` verb: follow whoever just engaged with one of our comments.

Someone who likes or answers a comment WE posted is the warmest signal the activity feed
carries — we produced the trigger, they read it, and they reacted. If the run that left that
comment did not follow them, this is the moment where a follow costs the least and converts
the most.

Unlike ``follow_back``, there is no inline button to tap: a "liked your comment" row offers
nothing. The actor's profile has to be opened, which is also what makes the guard free — the
follow button on the header IS the relationship, and reading it is the same production call
every workflow already makes before deciding anything about a profile.

Refusing is the default. The states that mean "we are already in a relationship" are skipped,
and so is an UNREADABLE state: ``follow_user`` is not guarded internally, so tapping blind on
a profile we already follow would UNFOLLOW it. Fail-closed here, unlike the read-only skip
paths elsewhere, because the cost of being wrong is not symmetrical.

SECURITY (AGENTS): usernames and states only, never profile content.
"""

from __future__ import annotations

from typing import Any, Dict

from bridges.instagram.runtime.ipc import logger

FOLLOW_ACTOR_ACTION = "follow_actor"

# Notification families whose actor engaged with something WE wrote. Kept here rather than
# inferred: a like on one of our POSTS is a different population (people who already follow
# us), and a follow aimed at them would spend the budget on a relationship that exists.
ENGAGEMENT_TYPES = ("comment_like", "comment_reply")

# Relationship states that mean "nothing to do" — we already follow them, a request is
# pending, or the header only offers Message (which itself means we follow them).
ALREADY_RELATED_STATES = ("following", "requested", "message")


def follow_actor(device, username: str) -> Dict[str, Any]:
    """Open ``username``'s profile, read the relationship, follow only if there is none.

    Returns the usual batch result dict, plus the ``state`` that was read so the trail says
    WHY a follow did not happen rather than just that it did not.
    """
    handle = (username or "").strip()
    if not handle:
        return {"success": False, "error": "Missing username"}

    from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions

    nav = NavigationActions(device)
    clicks = ClickActions(device)

    try:
        if not nav.navigate_to_profile(handle):
            return {"success": False, "error": f"Could not open @{handle}"}

        state = clicks.get_follow_button_state()
        logger.info(f"[NOTIF] @{handle} relationship: {state}")

        if state in ALREADY_RELATED_STATES:
            return {"success": True, "skipped": True, "reason": state,
                    "state": state, "message": f"@{handle} — already in a relationship"}
        if state == "unknown":
            # See the module docstring: an unreadable button is the one case where acting
            # could undo a follow instead of making one.
            return {"success": True, "skipped": True, "reason": "unknown_state",
                    "state": state, "message": f"@{handle} — relationship unreadable, left alone"}

        followed = bool(clicks.follow_user(handle))
        return ({"success": True, "state": state, "message": f"followed @{handle}"} if followed
                else {"success": False, "state": state, "error": f"Could not follow @{handle}"})
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[NOTIF] follow_actor @{handle} failed: {exc}")
        return {"success": False, "error": str(exc)}
    finally:
        _return_home(device, nav)


def _return_home(device, nav) -> None:
    """Back to the feed. Best-effort: a failed return must not fail the follow."""
    try:
        nav.navigate_to_home()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[NOTIF] Could not return home after a follow: {exc}")


__all__ = ["ENGAGEMENT_TYPES", "FOLLOW_ACTOR_ACTION", "follow_actor"]
