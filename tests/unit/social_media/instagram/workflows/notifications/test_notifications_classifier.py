"""Unit tests for the notifications activity-feed classifier (pure logic).

Synthetic fragment dicts keep the test independent of the live locale catalog —
we assert the classification/username/time/action logic, not the IG strings.
"""

from taktik.core.social_media.instagram.workflows.notifications.classifier import (
    classify_row,
    extract_time,
    row_has_action,
)

FRAGMENTS = {
    # Insertion order == classification priority.
    "comment_mention": ["vous a mentionné", "mentioned you"],
    "comment_like": ["a aimé votre commentaire", "liked your comment"],
    "post_like": ["a aimé votre photo", "liked your photo"],
    "new_follower": ["a commencé à vous suivre", "started following you"],
    "follow_request": ["a demandé à vous suivre", "requested to follow you"],
    "message": ["nouveau message de", "new message from"],
}


def test_actor_leads_the_type_phrase():
    ntype, user = classify_row("alice a commencé à vous suivre 2 j", FRAGMENTS)
    assert ntype == "new_follower"
    assert user == "alice"


def test_phrase_leads_username_taken_after():
    ntype, user = classify_row("new message from bob.", FRAGMENTS)
    assert ntype == "message"
    assert user == "bob"


def test_priority_specific_before_generic():
    # Contains both "liked your comment" and "liked your photo"; the more specific
    # comment_like must win because it precedes post_like in insertion order.
    ntype, _ = classify_row("carol liked your comment and liked your photo", FRAGMENTS)
    assert ntype == "comment_like"


def test_unmatched_row_is_other():
    ntype, user = classify_row("some unrelated system row", FRAGMENTS)
    assert ntype == "other"
    assert user == ""


def test_time_token_stripped_from_username():
    _, user = classify_row("dave 3 h requested to follow you", FRAGMENTS)
    assert "h" not in user.split()  # the "3 h" token is removed
    assert user == "dave"


def test_extract_time_returns_last_token():
    assert extract_time("alice liked your photo 2 j") == "2 j"
    assert extract_time("no time here") == ""


def test_row_has_action_detects_affordances():
    assert row_has_action("alice a demandé à vous suivre · Confirmer") is True
    assert row_has_action("bob mentioned you · Reply") is True
    assert row_has_action("carol liked your photo") is False


def test_the_age_of_a_row_is_a_range_read_from_the_time_token():
    """« 2 j » is at least 48 h old and less than 72 h; French and English units, one table."""
    from taktik.core.social_media.instagram.workflows.notifications.classifier import age_range

    hour, day = 3600, 24 * 3600
    assert age_range("2 j") == (2 * day, 3 * day)
    assert age_range("3d") == (3 * day, 4 * day)
    assert age_range("5 h") == (5 * hour, 6 * hour)
    assert age_range("54m") == (54 * 60, 55 * 60)
    assert age_range("12 min") == (12 * 60, 13 * 60)
    assert age_range("1 sem") == (7 * day, 14 * day)
    assert age_range("1w") == (7 * day, 14 * day)
    assert age_range("") is None
    assert age_range("Publicités") is None
    # What extract_time finds is what age_range reads.
    assert age_range(extract_time("user_3 a commencé à vous suivre. 8 h")) == (8 * hour, 9 * hour)
