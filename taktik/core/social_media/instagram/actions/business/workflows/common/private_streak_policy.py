"""Getting out of a poisoned head-of-list, when Instagram serves a flagged account
its private followers first.

Measured, not assumed. Two accounts were run on the SAME source, on the same people, at
the same minute: the order of the two lists correlated at rho = +0.12 (a stable list
served to everyone would be ~+0.9), and the mismatch targeted private profiles
specifically — mean normalised rank shift -0.63 for private profiles against +0.08 for
public ones, permutation p = 0.0015. One account met its five private profiles at ranks
29/34/37/38/39 of 39; the other met the same people straight away.

The decisive detail is that the RATE is unchanged (12.8% vs 8.8% of the followers seen).
It is not the quantity of private profiles that differs, it is their POSITION. A flagged
account therefore burns its whole session budget in a head of list it was handed, and
never reaches the public zone — which is how a source ends up at 70% "Private profile"
rejections while the same source is fine for another account.

So this is a RESCUE mechanism, not a filter: when a streak of consecutive private
profiles says we are inside the poisoned zone, the workflow transports itself further
down the list and resumes there.

What this module owns is the DECISION (are we in the zone, how far should we jump). The
gesture itself belongs to the workflow, which alone knows how to scroll its own list —
followers, likers, commenters. Keeping the decision here is what stops target, hashtag
and post-likers from drifting apart on one notion, the way they already share
`max_consecutive_known_usernames`.
"""

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_THRESHOLD = 5
DEFAULT_BASE_FLINGS = 6
DEFAULT_MAX_JUMPS = 3

# A fling with coast carries the content ~2.5-4x past the finger, so one gesture moves
# roughly eight to fifteen rows depending on device and row height. Ten is the working
# estimate used ONLY to avoid flinging past the end of a short list — it is not a
# position count, and nothing downstream may treat it as one: a fling skips rows by
# construction, which is exactly why no index can be tracked through a transport.
_ESTIMATED_ROWS_PER_FLING = 10


def _positive_int(value: Any, fallback: Optional[int]) -> Optional[int]:
    """Operator input -> a sane count. Absent/invalid -> fallback; 0 or less -> None ("never")."""
    if value is None:
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else None


@dataclass(frozen=True)
class PrivateStreakPolicy:
    """Resolved settings for the private-zone escape.

    ``threshold`` at None disables the mechanism entirely — the operator's "Never", and
    also what an account with no restriction gets in practice, since the streak simply
    never reaches the threshold.
    """

    threshold: Optional[int] = DEFAULT_THRESHOLD
    base_flings: int = DEFAULT_BASE_FLINGS
    max_jumps: int = DEFAULT_MAX_JUMPS

    @property
    def enabled(self) -> bool:
        return self.threshold is not None and self.threshold > 0

    @classmethod
    def from_filters(cls, filters: Optional[Dict[str, Any]]) -> "PrivateStreakPolicy":
        """Build from the workflow's filter block (bot snake_case or desktop camelCase).

        Disabled outright when the operator ALLOWS private profiles: they are then not
        rejected, there is no poisoned zone to escape, and jumping would only skip
        perfectly valid targets.
        """
        data = filters if isinstance(filters, dict) else {}

        allow_private = data.get("allow_private", data.get("allowPrivate", False))
        if allow_private:
            return cls(threshold=None)

        raw = data.get("max_consecutive_private_profiles",
                       data.get("maxConsecutivePrivateProfiles", DEFAULT_THRESHOLD))
        return cls(threshold=_positive_int(raw, DEFAULT_THRESHOLD))

    def should_escape(self, private_streak: int, jumps_done: int) -> bool:
        """Are we deep enough in a private run to justify a jump, and allowed one more?"""
        if not self.enabled:
            return False
        if jumps_done >= self.max_jumps:
            return False
        return private_streak >= int(self.threshold)

    def flings_for_jump(self, jumps_done: int, source_followers: Optional[int] = None) -> int:
        """How many fling gestures the next transport is worth.

        Doubling each time: a first jump that lands in more private profiles means the
        zone is deeper than assumed, and creeping forward would pay the visit cost of
        several more private profiles to learn it again.

        Jittered by ±25% on purpose. A fling through a follower list is an ordinary human
        gesture — it is how anyone looks for someone in their followers. What would NOT
        be ordinary is the same amplitude fired at the same trigger every time: that turns
        a rescue into a signature, which is the thing we are trying not to hand over.

        Capped by the source's follower count when it is known, because flinging 24 times
        through an 84-follower list only lands at the bottom.
        """
        planned = self.base_flings * (2 ** max(0, jumps_done))
        jittered = max(1, int(round(planned * random.uniform(0.75, 1.25))))

        if source_followers and source_followers > 0:
            reachable = max(1, math.ceil(source_followers / _ESTIMATED_ROWS_PER_FLING))
            return min(jittered, reachable)
        return jittered
