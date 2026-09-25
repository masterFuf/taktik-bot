"""Data models for the TikTok Unfollow workflow."""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


#: Why a row was left alone, as the events and the stats name it. The page shows each one.
SKIP_FRIENDS = "friends"
#: The list hides the handle on this row: it could be neither dated, nor checked, nor recorded.
SKIP_HANDLE_UNKNOWN = "handle_unknown"
SKIP_FOLLOWED_TOO_RECENTLY = "followed_too_recently"
SKIP_FOLLOW_DATE_UNKNOWN = "follow_date_unknown"

#: A tap the row did not confirm, and the run stop it leads to when it repeats.
NOT_CONFIRMED = "not_confirmed"
STOP_UNFOLLOW_UNCONFIRMED = "unfollow_unconfirmed"


@dataclass
class UnfollowConfig:
    """Configuration for the Unfollow workflow."""
    max_unfollows: int = 20
    include_friends: bool = False
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_scroll_attempts: int = 10
    #: Keep an account followed less than this many days ago; 0 = no age rule. The age is the
    #: bot's own last FOLLOW, else the first sighting by a following sync
    #: (`TikTokFollowGraphService.get_follow_age_days`). An account that NOTHING dates (no acting
    #: account, no FOLLOW and no sync) is KEPT, motive `follow_date_unknown`: in doubt, protect,
    #: as the Instagram unfollow does. A row without a handle is kept whatever this is
    #: (`handle_unknown`).
    min_follow_age_days: int = 0
    #: The acting account: dates its follows and files its unfollows. Without it neither can be done.
    bot_username: Optional[str] = None
    #: How long a tapped row may take to offer "Follow" again, a confirmation sheet included,
    #: before the tap counts as NOT confirmed. A bounded wait on the row, not a fixed delay.
    confirm_timeout: float = 3.0
    #: Unconfirmed taps in a row that stop the run: the screen is no longer doing what the run
    #: thinks (a block, another screen). Tapping on would be tapping blind.
    max_unconfirmed_in_a_row: int = 3


@dataclass
class UnfollowStats:
    """Stats for the Unfollow workflow."""
    unfollowed: int = 0
    skipped_friends: int = 0
    skipped_handle_unknown: int = 0
    skipped_recent_follows: int = 0
    skipped_follow_date_unknown: int = 0
    #: Taps after which the row still did not offer to follow: NOT counted as unfollows.
    unconfirmed: int = 0
    #: Confirmed unfollows written to the base (interaction + closed following row).
    recorded: int = 0
    errors: int = 0
    #: Why the run stopped early, when it did ('' otherwise).
    stop_reason: str = ""
    #: Motive -> count, for the page ("why so few?") and the run log.
    refusals: Dict[str, int] = field(default_factory=dict)

    @property
    def skipped(self) -> int:
        return sum(self.refusals.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unfollowed": self.unfollowed,
            "skipped": self.skipped,
            "skipped_friends": self.skipped_friends,
            "skipped_handle_unknown": self.skipped_handle_unknown,
            "skipped_recent_follows": self.skipped_recent_follows,
            "skipped_follow_date_unknown": self.skipped_follow_date_unknown,
            "unconfirmed": self.unconfirmed,
            "recorded": self.recorded,
            "errors": self.errors,
            "stop_reason": self.stop_reason,
            "refusals": dict(self.refusals),
        }
