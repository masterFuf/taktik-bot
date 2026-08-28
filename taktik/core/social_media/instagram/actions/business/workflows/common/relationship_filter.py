"""Should this profile be skipped because of the relationship we already have with it?

Two operator switches, answered from a LIST ROW without opening the profile — the cheapest
skip there is, since it costs no navigation, no extraction and no AI call:

- ``skip_follows_us``        — they already follow us, so re-targeting them gains no follower.
- ``skip_already_following`` — we already follow them, or asked to on a private account.

The states this reads (``follow_back``, ``following``, ``requested``) are produced by
`classify_follow_state`, the single source of truth that turns an action button's text into a
relationship. This module owns the DECISION and nothing else: what a caller does with a reason
— log it, count it, record it as filtered, `continue` or `return` — differs from one call site
to the next and stays with them.

It exists because that decision was written TWICE, down to the same French log line, in the
likers path and the followers path. Two spellings of one rule drift: the day someone teaches
one of them a new state, the other keeps the old answer, and nothing says so.
"""

from typing import Any, Mapping, Optional

# The relationship a row can show, in the vocabulary `classify_follow_state` emits.
FOLLOWS_US_STATE = "follow_back"
WE_FOLLOW_STATES = ("following", "requested")

# Operator-facing reasons. They travel to the database as the filter reason and to the
# analytics funnel built on it, so they are values, not log decoration.
REASON_FOLLOWS_US = "Already follows us"
REASON_ALREADY_FOLLOWING = "Already followed by us"


def wants_relationship_skip(filter_criteria: Optional[Mapping[str, Any]]) -> bool:
    """Whether either switch is on.

    Asked BEFORE reading the row, because reading it costs a device round trip: with both
    switches off there is nothing to decide and no reason to pay for the answer.
    """
    if not filter_criteria:
        return False
    return bool(
        filter_criteria.get("skip_follows_us")
        or filter_criteria.get("skip_already_following")
    )


def relationship_skip_reason(
    filter_criteria: Optional[Mapping[str, Any]],
    row_state: Optional[str],
) -> Optional[str]:
    """Why this row should be skipped, or None to go on and open the profile.

    FAIL-OPEN by construction: an unreadable row — `None`, `unknown`, a last row half past the
    fold — matches no state and falls through to the profile-level guard, which stays the
    source of truth. Opening one profile too many costs a few seconds; dropping a valid target
    costs it for good.
    """
    if not filter_criteria:
        return None
    if filter_criteria.get("skip_follows_us") and row_state == FOLLOWS_US_STATE:
        return REASON_FOLLOWS_US
    if filter_criteria.get("skip_already_following") and row_state in WE_FOLLOW_STATES:
        return REASON_ALREADY_FOLLOWING
    return None


__all__ = [
    "FOLLOWS_US_STATE",
    "WE_FOLLOW_STATES",
    "REASON_FOLLOWS_US",
    "REASON_ALREADY_FOLLOWING",
    "wants_relationship_skip",
    "relationship_skip_reason",
]
