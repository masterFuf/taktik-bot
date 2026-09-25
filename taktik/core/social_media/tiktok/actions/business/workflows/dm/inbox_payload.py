"""One reading of a TikTok inbox payload, for the bridges and the Agent handler alike.

Four flows share the DM workflow: new followers (list, follow back), unreplied conversations,
message requests (list, accept/decline) and activity. The wire form is the pages' camelCase
(`TikTokNewFollowers.tsx`, `TikTokUnreplied.tsx`, `TikTokRequests.tsx`, `TikTokActivity.tsx`); the
snake_case names an Agent plan or a CLI call writes stay accepted. Every key is read by name, so
the app's config contract test can see which ones the bot reads. The welcome pass reads its own
block, `ai.newFollowers`, through `services/welcome/decision.parse_welcome_policy`.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_payload import (
    as_bool,
    as_float,
    as_int,
    first_given,
)

from .models import DMConfig

NEW_FOLLOWERS = "new_followers"
UNREPLIED = "dm_unreplied"
REQUESTS = "dm_requests"
ACTIVITY = "dm_activity"
INBOX_FLOWS = (NEW_FOLLOWERS, UNREPLIED, REQUESTS, ACTIVITY)

#: How many rows each list reads when the payload does not say.
DEFAULT_MAX_ITEMS = {NEW_FOLLOWERS: 50, UNREPLIED: 30, REQUESTS: 30, ACTIVITY: 20}

FOLLOW_BACK = "follow_back"
EXECUTE = "execute"


def device_id_from_payload(payload: Mapping[str, Any]) -> Optional[str]:
    return first_given(payload.get("deviceId"), payload.get("device_id"))


def inbox_mode_from_payload(payload: Mapping[str, Any]) -> str:
    """`scrape` unless the payload names another mode (`follow_back`, `execute`)."""
    return str(payload.get("mode") or "scrape").strip() or "scrape"


def inbox_config_from_payload(flow: str, payload: Mapping[str, Any]) -> DMConfig:
    """Only the two acting flows carry a delay; the read-only ones run on plain defaults."""
    if flow in (NEW_FOLLOWERS, REQUESTS):
        return DMConfig(
            delay_between_conversations=as_float(
                first_given(payload.get("delayBetweenActions"), payload.get("delay_between_actions")), 1.0
            )
        )
    return DMConfig()


def max_items_from_payload(flow: str, payload: Mapping[str, Any]) -> int:
    return as_int(first_given(payload.get("maxItems"), payload.get("max_items")), DEFAULT_MAX_ITEMS[flow])


def only_unreplied_from_payload(payload: Mapping[str, Any]) -> bool:
    return as_bool(first_given(payload.get("onlyUnreplied"), payload.get("only_unreplied")), True)


def follow_back_usernames_from_payload(payload: Mapping[str, Any]) -> list[str]:
    """The names to follow back, without "@".

    The row is matched by CONTAINMENT on the displayed name, which carries no "@". The page takes
    its names off that same screen, but a plan or a CLI operator writes "@name", and the
    containment would then never match.
    """
    raw = first_given(payload.get("usernames"), payload.get("targetUsernames"), payload.get("target_usernames"))
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, (list, tuple)):
        return []
    names = [str(name).strip().lstrip("@") for name in raw]
    return [name for name in names if name]


def request_decisions_from_payload(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    """The well-formed `{username, action, message?}` decisions: accept or decline, a name without
    "@", a reply only when it has text."""
    raw = payload.get("decisions")
    if not isinstance(raw, (list, tuple)):
        return []

    decisions: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        username = str(item.get("username") or "").strip().lstrip("@")
        action = str(item.get("action") or "").strip().lower()
        if not username or action not in {"accept", "decline"}:
            continue
        decision = {"username": username, "action": action}
        message = str(item.get("message") or "").strip()
        if message:
            decision["message"] = message
        decisions.append(decision)
    return decisions


__all__ = [
    "ACTIVITY",
    "DEFAULT_MAX_ITEMS",
    "EXECUTE",
    "FOLLOW_BACK",
    "INBOX_FLOWS",
    "NEW_FOLLOWERS",
    "REQUESTS",
    "UNREPLIED",
    "device_id_from_payload",
    "follow_back_usernames_from_payload",
    "inbox_config_from_payload",
    "inbox_mode_from_payload",
    "max_items_from_payload",
    "only_unreplied_from_payload",
    "request_decisions_from_payload",
]
