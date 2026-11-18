"""The values of a TikTok run's end sentence: what the app puts in the markers of its motive.

The app says why a run ended with the sentence of its motive's code (« Limite de profils atteinte
({count}/{limit}) »). Instagram sends those values with the code (`reason_params` of its
`session_stop` line, filled by the factories of `.../instagram/.../session/stop_reasons.py`). TikTok
sent the code alone, and its sentences showed their markers. A TikTok run now sends them the same
way: `reason_params` on its `status` line, beside `completion_reason`, from this one table.

The names are those of the shared sentences, the code TikTok's motive maps to on the app side
(`src/lib/contract/tiktokStopReasons.ts`): `max_profiles_reached` is `profiles_cap`, whose sentence
names `count` and `limit`. A motive whose sentence names nothing gets no values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

#: The longest error text a crash's sentence carries, as on Instagram (`stop_reasons.crashed`).
CRASH_TEXT_LIMIT = 200


@dataclass(frozen=True)
class RunTally:
    """What a run counted when it ended, under the names the sentences use. 0 when not counted."""

    profiles: int = 0
    profiles_limit: int = 0
    likes: int = 0
    likes_limit: int = 0
    follows: int = 0
    follows_limit: int = 0
    #: Accounts (or rows) read in the list.
    seen: int = 0
    #: The whole list, when the run walked all of it.
    total: int = 0
    #: Known accounts in a row that stopped the run.
    streak: int = 0
    scrolls: int = 0
    #: The duration cap, in minutes.
    minutes: int = 0
    #: Unfollows in a row the screen did not confirm.
    unconfirmed: int = 0
    #: Gestures given (likes, follows, comments...), or rows written by a sync.
    interactions: int = 0
    #: The exception's text, for a crash.
    error: str = ""


def reason_params(reason: str, tally: RunTally) -> Dict[str, Any]:
    """The values the sentence of `reason` names, taken from `tally`; {} when it names none."""
    if reason == "max_profiles_reached":
        return {"count": tally.profiles, "limit": tally.profiles_limit}
    if reason == "max_likes_reached":
        return {"count": tally.likes, "limit": tally.likes_limit}
    if reason == "max_follows_reached":
        return {"count": tally.follows, "limit": tally.follows_limit}
    if reason == "max_scrolls_reached":
        return {"scrolls": tally.scrolls, "seen": tally.seen}
    if reason == "max_duration_reached":
        return {"minutes": tally.minutes}
    if reason == "unfollow_unconfirmed":
        return {"count": tally.unconfirmed}
    if reason == "no_more_followers":
        return {"seen": tally.seen}
    if reason == "list_exhausted":
        return {"seen": tally.seen, "total": tally.total}
    if reason in ("known_reached", "max_consecutive_known_usernames"):
        return {"streak": tally.streak, "seen": tally.seen}
    if reason == "completed":
        return {"interactions": tally.interactions}
    if reason == "crashed":
        return {"error": (tally.error.strip() or "unknown error")[:CRASH_TEXT_LIMIT]}
    return {}


__all__ = ["CRASH_TEXT_LIMIT", "RunTally", "reason_params"]
