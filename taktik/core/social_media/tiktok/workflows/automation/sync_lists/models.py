"""Data models for the TikTok follow-graph sync workflow."""

from dataclasses import dataclass, field
from typing import Any, Dict
import time


@dataclass
class SyncListsConfig:
    """Configuration of a follow-graph sync run."""

    #: 'following' (who we follow), 'followers' (who follows us), or 'both'.
    list_type: str = "following"

    #: Stop as soon as a handle we already have is met. The lists are ordered newest-first, so
    #: on a second run everything past that point is already known -- reading it again costs
    #: scrolls and changes nothing.
    incremental: bool = True

    #: Safety bound on scrolling, not a target: the run also stops when a screen brings nothing
    #: new. 60 screens is far past any list we can read in one session.
    max_scrolls: int = 60

    #: Open the profile of rows the list did not name, to read their handle there.
    #:
    #: OFF by default, and the reason is measured: on the operated account's FOLLOWING list
    #: TikTok renders the handle for only about half the rows (19 of 39 on the test account),
    #: while the FOLLOWERS list names every one. Resolving the rest is exact but costs one
    #: profile visit each, so it is the operator's call, not a default.
    resolve_missing_handles: bool = False

    #: Cap on those extra visits when the option is on.
    max_resolutions: int = 50

    #: Delay between actions, in seconds.
    min_delay: float = 0.6
    max_delay: float = 1.4


@dataclass
class SyncListsStats:
    """What a sync run saw and wrote."""

    rows_seen: int = 0
    new_count: int = 0
    updated_count: int = 0

    #: Rows the list showed but did not name, and that were NOT resolved. This is the number
    #: that keeps the run honest: a sync reporting only what it wrote would look complete while
    #: half the list went unrecorded.
    unidentified: int = 0
    resolved: int = 0

    following_seen: int = 0
    followers_seen: int = 0
    reciprocal_seen: int = 0

    stopped_early: bool = False
    errors: int = 0
    completion_reason: str = ""

    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            "rows_seen": self.rows_seen,
            "new_count": self.new_count,
            "updated_count": self.updated_count,
            "unidentified": self.unidentified,
            "resolved": self.resolved,
            "following_seen": self.following_seen,
            "followers_seen": self.followers_seen,
            "reciprocal_seen": self.reciprocal_seen,
            "stopped_early": self.stopped_early,
            "errors": self.errors,
            "completion_reason": self.completion_reason,
            "elapsed_seconds": elapsed,
            "elapsed_formatted": f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }
