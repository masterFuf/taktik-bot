"""One reading of a TikTok notifications payload, for the bridge and the Agent handler alike.

The wire form is the desktop page's camelCase (`TikTokNotifications.tsx`); the snake_case names an
Agent plan or a CLI call writes stay accepted. Every key is read by name, so the app's config
contract test can see which ones the bot reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_int,
    first_given,
)


@dataclass(frozen=True)
class NotificationsSettings:
    """What one notifications pass does. The four steps cost very different device time."""

    #: Record new followers, so the attribution can say whether we engaged them first.
    scan_new_followers: bool = True
    #: How many display names to resolve into handles, one profile open each.
    max_follower_resolutions: int = 10
    read_activity: bool = True
    max_activity_rows: int = 30
    #: The one-tap wave on threads we never opened. 0 = off.
    max_hellos: int = 0
    #: Follows from the suggestions block of the Activity summary. 0 = off.
    max_suggested_follows: int = 0


def notifications_settings_from_payload(payload: Mapping[str, Any]) -> NotificationsSettings:
    """The pass a payload asks for; an absent key keeps the page's default."""
    return NotificationsSettings(
        scan_new_followers=as_bool(
            first_given(payload.get("scanNewFollowers"), payload.get("scan_new_followers")), True
        ),
        max_follower_resolutions=as_int(
            first_given(payload.get("maxFollowerResolutions"), payload.get("max_follower_resolutions")), 10
        ),
        read_activity=as_bool(first_given(payload.get("readActivity"), payload.get("read_activity")), True),
        max_activity_rows=as_int(
            first_given(payload.get("maxActivityRows"), payload.get("max_activity_rows")), 30
        ),
        max_hellos=as_int(first_given(payload.get("maxHellos"), payload.get("max_hellos")), 0),
        max_suggested_follows=as_int(
            first_given(payload.get("maxSuggestedFollows"), payload.get("max_suggested_follows")), 0
        ),
    )


__all__ = ["NotificationsSettings", "notifications_settings_from_payload"]
