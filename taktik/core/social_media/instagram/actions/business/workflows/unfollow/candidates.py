"""Who may be unfollowed: the decision, taken on data, before any tap.

U2 of the unfollow rebuild (2026-09-24). The screen used to decide: the list path tapped every
"Following" button from the top of the list, mutuals, manual follows and the whitelist included,
whatever mode the page said. The decision is now a pure function of what the base knows (the
active followings, who followed them, when) and of what a followers sync of this run saw; the
screen only acts and checks.

Rules, in order (the first that applies wins):
1. whitelist: never unfollowed;
2. blacklist: unfollowed whatever the mode and the other rules ("priorité sur les règles", as the
   page says);
3. bot follows only (on by default): a follow the bot has no record of is protected;
4. minimum delay since the follow: a follow younger than the delay, or of unknown date, waits;
5. the mode:
   - "non-followers" (default): only accounts KNOWN not to follow back, which takes a COMPLETE
     followers sync of this run: an incomplete sync proves nothing about the accounts it did not
     reach, so nobody qualifies;
   - "mutual": only accounts seen in the followers list;
   - "oldest": every account, oldest follow first;
   - "all": every account.
In doubt, no unfollow: an unknown date, an unknown reciprocity, an unknown mode.
The order is the oldest follow first (blacklist first of all). A profile check on screen comes
afterwards (the "Follows you" badge, verified and business accounts): see the workflow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Set, Tuple

MODES = ("non-followers", "mutual", "oldest", "all")


@dataclass(frozen=True)
class FollowingRecord:
    """One account the active account follows, as the base knows it."""

    username: str
    followed_by_bot: bool = False
    followed_at: Optional[datetime] = None      # the bot's last successful FOLLOW, if any
    first_seen_at: Optional[datetime] = None    # when a following sync first saw it


@dataclass(frozen=True)
class FollowersSnapshot:
    """What a followers sync of THIS run saw. `complete`: the end of the list was reached."""

    usernames: frozenset
    complete: bool


@dataclass
class CandidateSelection:
    candidates: List[str] = field(default_factory=list)
    # reason -> count, for the page ("why so few?") and the run log
    refusals: Dict[str, int] = field(default_factory=dict)

    def refuse(self, reason: str) -> None:
        self.refusals[reason] = self.refusals.get(reason, 0) + 1


def _parse_time(value) -> Optional[datetime]:
    """A stored time (ISO from `interactions`, `YYYY-MM-DD HH:MM:SS` from SQLite), or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def records_from_rows(rows: Iterable[Dict]) -> List[FollowingRecord]:
    """Rows of `InstagramFollowGraphService.list_active_followings` as records.

    A follow is the bot's when `interactions` holds a successful FOLLOW of that profile by that
    account; its date is the last such FOLLOW. Otherwise only the first sighting by a following
    sync dates it. (The two clocks differ by the machine's UTC offset, at most a few hours: noise
    against a delay counted in days.)
    """
    records = []
    for row in rows:
        followed_at = _parse_time(row.get('last_bot_follow_at'))
        records.append(FollowingRecord(
            username=str(row.get('username') or ''),
            followed_by_bot=followed_at is not None,
            followed_at=followed_at,
            first_seen_at=_parse_time(row.get('first_seen_at')),
        ))
    return records


def _clean(values: Optional[Iterable[str]]) -> Set[str]:
    return {str(v).strip().lstrip('@').lower() for v in (values or []) if str(v).strip().lstrip('@')}


def _follow_date(record: FollowingRecord) -> Optional[datetime]:
    """The follow date the delay is measured from: the bot's own follow, else the first sighting."""
    return record.followed_at or record.first_seen_at


def select_candidates(
    records: Iterable[FollowingRecord],
    config: Dict,
    followers: Optional[FollowersSnapshot],
    now: datetime,
) -> CandidateSelection:
    """Apply the rules to the active followings; returns the ordered candidates and the refusals."""
    selection = CandidateSelection()
    mode = config.get('unfollow_mode', 'non-followers')
    if mode not in MODES:
        selection.refuse('unknown_mode')
        return selection
    whitelist = _clean(config.get('whitelist'))
    blacklist = _clean(config.get('blacklist'))
    bot_only = bool(config.get('bot_follows_only', True))
    min_days = float(config.get('min_days_since_follow', 0) or 0)
    follower_names = {u.lower() for u in followers.usernames} if followers else set()

    forced: List[Tuple[datetime, str]] = []
    chosen: List[Tuple[datetime, str]] = []
    oldest_first = datetime.min

    for record in records:
        name = record.username.strip().lstrip('@')
        key = name.lower()
        if not name:
            continue
        when = _follow_date(record)
        order = when or oldest_first

        if key in whitelist:
            selection.refuse('whitelisted')
            continue
        if key in blacklist:
            forced.append((order, name))
            continue
        if bot_only and not record.followed_by_bot:
            selection.refuse('not_followed_by_bot')
            continue
        if min_days > 0:
            if when is None:
                selection.refuse('follow_date_unknown')
                continue
            if (now - when).total_seconds() < min_days * 86400:
                selection.refuse('followed_too_recently')
                continue
        if mode == 'non-followers':
            if followers is None or not followers.complete:
                selection.refuse('reciprocity_unknown')
                continue
            if key in follower_names:
                selection.refuse('follows_back')
                continue
        elif mode == 'mutual':
            if key not in follower_names:
                # Absent from a partial list proves nothing; absent from a complete one means no.
                selection.refuse('not_mutual' if followers and followers.complete else 'reciprocity_unknown')
                continue
        chosen.append((order, name))

    forced.sort(key=lambda item: item[0])
    chosen.sort(key=lambda item: item[0])
    selection.candidates = [name for _, name in forced] + [name for _, name in chosen]
    return selection
