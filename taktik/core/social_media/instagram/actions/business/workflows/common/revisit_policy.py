"""When may the bot come back to a profile it has already seen?

Two independent operator settings, deliberately separate because they answer different
questions:

- ``reinteraction_days``  — "after how long do I engage someone again?" A profile this
  account already interacted with is left alone until the delay has passed.
- ``refilter_days``       — "after how long do I give a rejected profile another look?"
  A profile this account filtered out (too few posts, private, …) is re-evaluated once
  the delay has passed. Filter reasons expire: an account with no posts in December may
  have thirty today, and a private account may have gone public.

Both are scoped to the ACCOUNT being automated — profiles known through another account
are never skipped here, so each of the operator's accounts builds its own history.

Both delays used to be out of the operator's hands: the interaction one was written by
hand as `hours_limit=24*60` at each of the four decision points, and the filter one never
expired at all — a single rejection banned a profile from that account permanently. This
module is the single owner of the semantic, so the four call sites stay in step.

(Unrelated: the hashtag workflow's `hours_limit=168` is a POST-level dedup — "have I
already engaged this post" — not a profile revisit delay. It is not governed here.)
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_REINTERACTION_DAYS = 60
DEFAULT_REFILTER_DAYS = 90

# "Never come back" is expressed as 0 by the operator. The processed-profile lookup is a
# time window, so "never" becomes a window wide enough to cover any real history.
_A_CENTURY_IN_HOURS = 24 * 365 * 100


def _positive_int(value: Any, fallback: int) -> int:
    """Operator input -> a sane day count. Absent/invalid -> fallback; negative -> 0 ("never")."""
    if value is None:
        return fallback
    try:
        days = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, days)


@dataclass(frozen=True)
class RevisitPolicy:
    """Resolved revisit delays, in days. 0 means "never come back"."""

    reinteraction_days: int = DEFAULT_REINTERACTION_DAYS
    refilter_days: int = DEFAULT_REFILTER_DAYS

    @classmethod
    def from_filters(cls, filters: Optional[Dict[str, Any]]) -> "RevisitPolicy":
        """Build from the workflow's filter block (bot snake_case or desktop camelCase)."""
        data = filters if isinstance(filters, dict) else {}
        return cls(
            reinteraction_days=_positive_int(
                data.get("reinteraction_days", data.get("reinteractionDays")),
                DEFAULT_REINTERACTION_DAYS,
            ),
            refilter_days=_positive_int(
                data.get("refilter_days", data.get("refilterDays")),
                DEFAULT_REFILTER_DAYS,
            ),
        )

    @property
    def reinteraction_hours(self) -> int:
        """Window handed to the processed-profile lookup (0 days = never re-interact)."""
        if self.reinteraction_days <= 0:
            return _A_CENTURY_IN_HOURS
        return self.reinteraction_days * 24

    @property
    def filtered_max_age_days(self) -> Optional[int]:
        """Age beyond which a stored filter is ignored. None = filters never expire."""
        return self.refilter_days if self.refilter_days > 0 else None


__all__ = [
    "RevisitPolicy",
    "DEFAULT_REINTERACTION_DAYS",
    "DEFAULT_REFILTER_DAYS",
]
