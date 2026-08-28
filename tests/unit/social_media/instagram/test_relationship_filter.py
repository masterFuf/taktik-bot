"""Skipping a profile on the relationship its list row already shows.

The decision lived twice — in the likers path and the followers path — as the same twelve
lines, down to an identical French log message. Two spellings of one rule drift: teach one a
new state and the other keeps answering the old way, silently. These lock the rule now that a
single module owns it.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.relationship_filter import (
    REASON_ALREADY_FOLLOWING,
    REASON_FOLLOWS_US,
    relationship_skip_reason,
    wants_relationship_skip,
)

FOLLOWS_US = {"skip_follows_us": True}
WE_FOLLOW = {"skip_already_following": True}
BOTH = {"skip_follows_us": True, "skip_already_following": True}


@pytest.mark.parametrize("criteria,expected", [
    (None, False),
    ({}, False),
    ({"skip_follows_us": False, "skip_already_following": False}, False),
    (FOLLOWS_US, True),
    (WE_FOLLOW, True),
    (BOTH, True),
])
def test_the_row_is_only_read_when_a_switch_asks_for_it(criteria, expected):
    # Reading the row costs a device round trip: with both switches off there is nothing to
    # decide and no reason to pay for the answer.
    assert wants_relationship_skip(criteria) is expected


def test_they_follow_us_is_skipped_only_when_asked():
    assert relationship_skip_reason(FOLLOWS_US, "follow_back") == REASON_FOLLOWS_US
    assert relationship_skip_reason(WE_FOLLOW, "follow_back") is None


@pytest.mark.parametrize("state", ["following", "requested"])
def test_we_already_follow_them_covers_a_pending_request(state):
    # A request sent to a private account is a relationship too: re-targeting gains nothing.
    assert relationship_skip_reason(WE_FOLLOW, state) == REASON_ALREADY_FOLLOWING
    assert relationship_skip_reason(FOLLOWS_US, state) is None


def test_a_row_offering_to_follow_is_a_target():
    assert relationship_skip_reason(BOTH, "follow") is None


@pytest.mark.parametrize("state", [None, "", "unknown", "message"])
def test_an_unreadable_row_falls_through_rather_than_being_dropped(state):
    # FAIL-OPEN, and it is the point: a last row half past the fold reads as nothing, and the
    # profile-level guard stays the source of truth. Opening one profile too many costs
    # seconds; dropping a valid target costs it for good.
    assert relationship_skip_reason(BOTH, state) is None


def test_the_two_reasons_never_collide():
    # They are recorded as the filter reason and feed the analytics funnel built on it, so a
    # row can only ever carry one of them.
    assert relationship_skip_reason(BOTH, "follow_back") == REASON_FOLLOWS_US
    assert relationship_skip_reason(BOTH, "following") == REASON_ALREADY_FOLLOWING
    assert REASON_FOLLOWS_US != REASON_ALREADY_FOLLOWING
