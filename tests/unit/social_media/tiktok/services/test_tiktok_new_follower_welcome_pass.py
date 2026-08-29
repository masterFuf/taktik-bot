from taktik.core.social_media.tiktok.services.welcome.decision import (
    REASON_AI_OFF,
    REASON_NO_VERDICT,
    REASON_PROFILE_UNREACHABLE,
    REASON_RELEVANT,
    REASON_UNREADABLE_HANDLE,
    WelcomePolicy,
)
from taktik.core.social_media.tiktok.services.welcome.runner import NewFollowerWelcomePass


def _policy(**overrides) -> WelcomePolicy:
    base = {
        "enabled": True,
        "follow_back": True,
        "welcome_dm": True,
        "min_score": 0.5,
        "dm_requires_follow_back": True,
        "messages": ("Bienvenue !",),
    }
    base.update(overrides)
    return WelcomePolicy(**base)


def _relevant(_username):
    return {"relevant": True, "score": 0.9, "follow": True}


def test_a_profile_the_navigation_never_reached_gets_no_verdict_and_no_action():
    """`navigate_to_user_profile` answers ARRIVAL, not the click: False means we are not there.

    Would have caught the pass screenshotting whatever screen it was left on and filing that
    verdict under the follower's name — the black-screenshot qualification, again.
    """
    qualified = []

    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(),
        visit_profile=lambda username: False,
        qualify=lambda username: qualified.append(username) or _relevant(username),
    )
    decisions = welcome_pass.decide([{"username": "creator"}])

    assert qualified == []
    assert decisions[0].reason == REASON_PROFILE_UNREACHABLE
    assert (decisions[0].follow_back, decisions[0].welcome_dm) == (False, False)


def test_a_navigation_that_raises_costs_one_follower_not_the_whole_pass():
    def visit(username):
        if username == "boom":
            raise RuntimeError("device disconnected mid-scroll")
        return True

    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(), visit_profile=visit, qualify=_relevant
    )
    decisions = welcome_pass.decide(["boom", "creator"])

    assert [decision.reason for decision in decisions] == [REASON_PROFILE_UNREACHABLE, REASON_RELEVANT]


def test_a_qualifier_that_raises_costs_the_verdict_not_the_pass():
    """Would have caught one provider timeout ending a run that had 40 followers left to read."""

    def qualify(username):
        if username == "boom":
            raise RuntimeError("provider 502")
        return _relevant(username)

    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(), visit_profile=lambda username: True, qualify=qualify
    )
    decisions = welcome_pass.decide(["boom", "creator"])

    assert decisions[0].reason == REASON_NO_VERDICT
    assert decisions[1].reason == REASON_RELEVANT


def test_every_follower_produces_a_row_even_when_nothing_happens_to_it():
    """A pass that dropped its skipped rows reports "0 welcomed" identically whether the AI
    rejected everyone or the navigation never arrived once."""
    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(),
        visit_profile=lambda username: True,
        qualify=lambda username: {"relevant": username == "yes", "score": 0.9, "follow": True},
    )
    decisions = welcome_pass.decide(["yes", "no", "no"])

    assert len(decisions) == 3
    assert [decision.username for decision in decisions] == ["yes", "no", "no"]


def test_rows_without_a_readable_username_are_reported_not_dropped():
    """The scraper returns a row per list item; an item whose handle could not be read is a
    measurement failure worth seeing, not a gap to close silently."""
    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(), visit_profile=lambda username: True, qualify=_relevant
    )
    decisions = welcome_pass.decide([{"username": ""}, {"activity": "vous suit"}, 42])

    assert [decision.reason for decision in decisions] == [REASON_UNREADABLE_HANDLE] * 3


def test_a_pass_with_ai_off_decides_nothing_and_touches_no_profile():
    """Would have caught the welcome pass walking every profile on a run that never asked for it."""
    visited = []

    welcome_pass = NewFollowerWelcomePass(
        policy=WelcomePolicy(),
        visit_profile=lambda username: visited.append(username) or True,
        qualify=_relevant,
    )
    decisions = welcome_pass.decide([{"username": "creator"}])

    assert visited == []
    assert decisions[0].reason == REASON_AI_OFF


def test_a_scraped_row_and_a_plain_handle_are_read_the_same_way():
    welcome_pass = NewFollowerWelcomePass(
        policy=_policy(), visit_profile=lambda username: True, qualify=_relevant
    )
    decisions = welcome_pass.decide([{"username": "@creator", "can_follow_back": True}, "@creator"])

    assert [decision.username for decision in decisions] == ["creator", "creator"]
    assert all(decision.follow_back and decision.welcome_dm for decision in decisions)
