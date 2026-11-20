"""What the notifications scan counts as not read yet, row by row.

The activity feed has no server id and no read mark. A row is judged by its age (« 2 j ») against
the account's last scan, the way a Symfony voter answers one question per subject:

- surely newer than the last scan: unread, even when its identity is already recorded (a new like
  from someone already seen has the identity of the old one, `NotificationRepository.content_hash`);
- surely older than the horizon (the last scan, or `FIRST_SCAN_HORIZON_DAYS` on a first scan):
  beyond, not read, even when its identity is unknown;
- in between (its age range straddles the horizon), or with no readable age: the recorded
  identity decides, unknown means unread.

Pure: no device, no database. `persistence.build_unread_rule` builds it from the record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from taktik.core.contract.instagram_notifications import FIRST_SCAN_HORIZON_DAYS
from taktik.core.social_media.instagram.workflows.notifications.classifier import age_range

#: What `UnreadRule.verdict` answers.
UNREAD = "unread"
READ = "read"
BEYOND = "beyond"

KnownChecker = Callable[[Dict[str, Any]], bool]


@dataclass(frozen=True)
class UnreadRule:
    """The horizon of one scan and how a row is judged against it."""

    #: How far back the scan reads, in seconds: since the last scan, or the first-scan days.
    horizon_s: float
    #: Nothing recorded for the account: the horizon is the first-scan days.
    first_scan: bool
    #: "Already recorded for this account", by the row's identity; None: nothing recorded.
    is_known: Optional[KnownChecker] = None

    @classmethod
    def for_first_scan(cls) -> "UnreadRule":
        return cls(horizon_s=FIRST_SCAN_HORIZON_DAYS * 24 * 3600, first_scan=True)

    @classmethod
    def since_last_scan(cls, last_scan_at: datetime, now: datetime,
                        is_known: Optional[KnownChecker]) -> "UnreadRule":
        return cls(horizon_s=max(0.0, (now - last_scan_at).total_seconds()), first_scan=False,
                   is_known=is_known)

    @property
    def reached_reason(self) -> str:
        """The scan's stop reason once it reads only what is not for it."""
        return "first_scan_horizon" if self.first_scan else "already_read"

    def verdict(self, row: Dict[str, Any]) -> str:
        age = age_range(row.get("time") or "")
        if age is not None and age.less_than_s <= self.horizon_s:
            return UNREAD
        if age is not None and age.at_least_s > self.horizon_s:
            return BEYOND
        if self.is_known is not None and self.is_known(row):
            return READ
        return UNREAD


__all__ = ["BEYOND", "READ", "UNREAD", "KnownChecker", "UnreadRule"]
