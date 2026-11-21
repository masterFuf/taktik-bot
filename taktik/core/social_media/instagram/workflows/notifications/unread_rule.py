"""What the notifications scan counts as not read yet, row by row.

The activity feed has no server id and no read mark. A row is judged by its age (« 2 j ») against
the moment the account's last scan began reading, the way a Symfony voter answers one question per
subject:

- surely newer than the last scan: unread, even when its identity is already recorded (a new like
  from someone already seen has the identity of the old one, `NotificationRepository.content_hash`);
- at least as old as the horizon (the last scan, or `FIRST_SCAN_HORIZON_DAYS` on a first scan, so
  « 1 sem » is beyond a first scan): beyond, not read, even when its identity is unknown;
- in between (its age range straddles the horizon), or with no readable age: the recorded
  identity decides, unknown means unread.

The horizon is measured when the row is judged, right after the screen that shows its age was
read (``clock``, like Symfony's ClockInterface): a horizon measured before the scan reached the
feed would be short by the time it took to get there, and would leave out what came in just after
the last scan began.

Pure: no device, no database. `persistence.build_unread_rule` builds it from the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from taktik.core.contract.instagram_notifications import FIRST_SCAN_HORIZON_DAYS
from taktik.core.social_media.instagram.workflows.notifications.classifier import age_range

#: What `UnreadRule.verdict` answers.
UNREAD = "unread"
READ = "read"
BEYOND = "beyond"

KnownChecker = Callable[[Dict[str, Any]], bool]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The time now, in UTC: the clock of a real scan."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UnreadRule:
    """The horizon of one scan and how a row is judged against it."""

    #: When the account's last scan began reading its feed (UTC); None: a first scan.
    last_read_at: Optional[datetime] = None
    #: "Already recorded for this account", by the row's identity; None: nothing recorded.
    is_known: Optional[KnownChecker] = None
    #: The time a row is judged at.
    clock: Clock = utc_now

    @classmethod
    def for_first_scan(cls) -> "UnreadRule":
        return cls()

    @classmethod
    def since_last_scan(cls, last_read_at: datetime, is_known: Optional[KnownChecker],
                        clock: Clock = utc_now) -> "UnreadRule":
        return cls(last_read_at=last_read_at, is_known=is_known, clock=clock)

    @property
    def first_scan(self) -> bool:
        """Nothing recorded for the account: the horizon is the first-scan days."""
        return self.last_read_at is None

    @property
    def horizon_s(self) -> float:
        """How far back the scan reads now, in seconds: since the last scan began reading, or the
        first-scan days."""
        if self.last_read_at is None:
            return FIRST_SCAN_HORIZON_DAYS * 24 * 3600
        return max(0.0, (self.clock() - self.last_read_at).total_seconds())

    @property
    def reached_reason(self) -> str:
        """The scan's stop reason once it reads only what is not for it."""
        return "first_scan_horizon" if self.first_scan else "already_read"

    def verdict(self, row: Dict[str, Any]) -> str:
        age = age_range(row.get("time") or "")
        horizon_s = self.horizon_s
        if age is not None and age.less_than_s <= horizon_s:
            return UNREAD
        if age is not None and age.at_least_s >= horizon_s:
            return BEYOND
        if self.is_known is not None and self.is_known(row):
            return READ
        return UNREAD


__all__ = ["BEYOND", "READ", "UNREAD", "Clock", "KnownChecker", "UnreadRule", "utc_now"]
