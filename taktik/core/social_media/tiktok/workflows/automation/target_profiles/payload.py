"""What a TikTok Target Profiles payload says beyond the Followers settings: the list, the budget.

The interaction settings are the Followers ones (`followers/payload.py`), read the same way.
"""

from __future__ import annotations

from typing import Any, Mapping


def target_profiles_from_payload(payload: Mapping[str, Any]) -> list[str]:
    """The profiles to visit: `profiles`, `targetProfiles` or `usernames`, "@" removed.

    Never `targets` nor `searchQuery`: on this family they name whose followers to walk, and
    reading them here would turn a run launched without a list into a run against one account.
    """
    for key in ("profiles", "targetProfiles", "usernames"):
        raw = payload.get(key)
        if raw:
            if isinstance(raw, str):
                raw = [raw]
            # Filtered after the "@" is gone: a bare "@" is no profile.
            cleaned = (str(item or "").strip().lstrip("@").strip() for item in raw)
            return [name for name in cleaned if name]
    return []


def profile_visit_budget(payload: Mapping[str, Any], profiles: list[str]) -> int:
    """`maxProfiles`, else `maxFollowers`, else one visit per listed profile."""
    return int(payload.get("maxProfiles") or payload.get("maxFollowers") or len(profiles))


__all__ = ["profile_visit_budget", "target_profiles_from_payload"]
