"""When a source has nothing left to give.

Two ways to answer "stop working this source", and they do not measure the same thing:

- ``max_consecutive_known_usernames`` counts PROFILES already in the database. It speaks the
  product's language — the operator thinks in accounts encountered, not in gestures.
- ``max_no_new_usernames_scrolls`` counts SCROLLS that surfaced nothing new. A technical
  detail of the transport, kept for configs written before the first existed.

The fallback is the part worth being careful with: the legacy scroll limit defaults to 20
ONLY when the username limit is absent. Setting the modern one must not silently arm the old
one as well, or a run would stop on whichever trips first — which is not what either
setting promises.

Target, hashtag and post-likers share this notion; resolving it in one place is what stops
them drifting apart on it, as they already did on their stop policy.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


LEGACY_SCROLL_FALLBACK = 20


def _at_least_one(value: Any) -> int:
    """Operator input -> a usable count. Never below 1: zero would stop before starting."""
    return max(1, int(value or 1))


@dataclass(frozen=True)
class StopLimits:
    """Resolved end-of-source limits. ``None`` on either side means "do not stop on it"."""

    max_consecutive_known_usernames: Optional[int] = None
    legacy_max_no_new_usernames_scrolls: Optional[int] = None


def resolve_stop_limits(config: Optional[Dict[str, Any]]) -> StopLimits:
    """Read both end-of-source limits, preserving the legacy fallback rule."""
    config = config or {}

    known = config.get('max_consecutive_known_usernames')
    if known is not None:
        known = _at_least_one(known)

    legacy = config.get('max_no_new_usernames_scrolls')
    if legacy is not None:
        legacy = _at_least_one(legacy)
    elif known is None:
        legacy = LEGACY_SCROLL_FALLBACK

    return StopLimits(max_consecutive_known_usernames=known,
                      legacy_max_no_new_usernames_scrolls=legacy)


__all__ = ["StopLimits", "resolve_stop_limits", "LEGACY_SCROLL_FALLBACK"]
