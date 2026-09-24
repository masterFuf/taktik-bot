"""One reading of a TikTok unfollow payload, for the bridge and the Agent handler alike.

Two readers used to exist, and they disagreed. The desktop page and the scheduler node send the
pause between two unfollows as `delay_min` / `delay_max` (the snake_case of the rest of that
payload: `max_unfollows`, `skip_friends`); the bridge read `minDelay` / `maxDelay`, a name nobody
sends, and every run paused 1 to 3 s whatever the operator had set. The Agent handler read a third
spelling, `min_delay`.

The wire form is `delay_min` / `delay_max`. The other two stay accepted at the door: `min_delay`
is what an Agent plan writes, `minDelay` what a standalone caller or an older plan may still carry.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from .models import UnfollowConfig


def _first_present(*values: Any) -> Optional[Any]:
    """The first value that was actually given: None and an empty string are "not set"."""
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_delay(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def unfollow_config_from_payload(payload: Mapping[str, Any]) -> UnfollowConfig:
    """Build the workflow config from a bridge or Agent payload."""
    max_unfollows = _first_present(payload.get("max_unfollows"), payload.get("maxUnfollows"))

    # `skip_friends` is the operator's switch; `include_friends` the Agent's older name for its
    # opposite. The switch wins when both are present.
    skip_friends = _first_present(payload.get("skip_friends"), payload.get("skipFriends"))
    if skip_friends is not None:
        include_friends = not _as_bool(skip_friends)
    else:
        include_friends = _as_bool(
            _first_present(payload.get("include_friends"), payload.get("includeFriends"), False)
        )

    min_delay = _first_present(
        payload.get("delay_min"), payload.get("min_delay"), payload.get("minDelay")
    )
    max_delay = _first_present(
        payload.get("delay_max"), payload.get("max_delay"), payload.get("maxDelay")
    )
    max_scroll_attempts = _first_present(
        payload.get("max_scroll_attempts"), payload.get("maxScrollAttempts")
    )

    return UnfollowConfig(
        max_unfollows=int(max_unfollows) if max_unfollows is not None else 20,
        include_friends=include_friends,
        min_delay=_as_delay(min_delay, 1.0),
        max_delay=_as_delay(max_delay, 3.0),
        max_scroll_attempts=int(max_scroll_attempts) if max_scroll_attempts is not None else 10,
    )


__all__ = ["unfollow_config_from_payload"]
