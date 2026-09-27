"""U6: reciprocity, for real.

The "don't follow back" category of the followers tab lists FANS (they follow us, we do not
follow them). It used to be read as the accounts WE follow that do not follow back: every fan got
a following row, and every following absent from the category was marked as a mutual. Now the
category only records fans, and the last word before an unfollow is the "Follows you" badge read
on the right profile.

The screens are real dumps, anonymized: the followers list of Instagram 410 in English (Pixel 3a,
2026-09-23), the profile of an account we follow in French (Pixel 3), and, in English (Pixel 3a,
2026-09-27), the profile of a MUTUAL: it is in our followers list and we follow it. No profile of
the corpus (about 2 800 dumps of 410 and 447, French and English) shows a "Follows you" or
"Vous suit" badge, the mutual's included: the badge that proves it is never read.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


FIXTURES = Path(__file__).parents[2] / "fixtures"
FOLLOWERS_LIST = (FIXTURES / "ig410_en_own_followers_list_categories.xml").read_text(encoding="utf-8")
FOLLOWED_PROFILE = (FIXTURES / "ig410_fr_profile_following.xml").read_text(encoding="utf-8")
MUTUAL_PROFILE_EN = (FIXTURES / "ig410_en_profile_following.xml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(sync_following.time, "sleep", lambda _s: None)
    yield
    set_active_locale(None)


class _GraphSpy:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return set() if name.startswith("get_") else "new"
        return record


def test_the_fans_category_records_fans_and_never_a_following(monkeypatch):
    graph = _GraphSpy()
    monkeypatch.setattr(sync_following, "InstagramFollowGraphService", graph)
    business = UnfollowBusiness(FakeFacade(FakeScreen(FOLLOWERS_LIST)))
    business._get_account_id = lambda: 1
    business.nav_actions = SimpleNamespace(navigate_to_profile_tab=lambda: True, open_followers_list=lambda: True)
    business._click_non_followers_category = lambda: True
    business._has_follow_back_row = lambda: True
    business._extract_all_non_followers = lambda: ["fan_one", "fan_two"]

    stats = business.scrape_non_followers_category()

    assert stats["fans_count"] == 2 and stats["non_followers_count"] == 2
    assert stats["mutuals_count"] == 0
    names = [name for name, _args, _kwargs in graph.calls]
    assert names == ["upsert_follower", "upsert_follower"]
    for _name, _args, kwargs in graph.calls:
        assert kwargs["is_following_back"] is False and kwargs["source"] == "fans_category"


def _business(screen_xml, on_profile=True, shown="alice"):
    screen = FakeScreen(screen_xml)
    facade = FakeFacade(screen)
    facade.xpath = screen.xpath
    business = UnfollowBusiness(facade)
    business.detection_actions = SimpleNamespace(
        is_on_profile_screen=lambda: on_profile,
        get_username_from_profile=lambda: shown,
    )
    return business


def test_a_loaded_profile_without_the_badge_reads_as_not_following_us():
    assert _business(FOLLOWED_PROFILE)._profile_follows_you("alice") is False
    assert _business(FOLLOWED_PROFILE)._profile_follows_you("@Alice") is False


@pytest.mark.xfail(strict=True, reason=(
    "no Instagram 410 or 447 profile shows a 'Follows you' / 'Vous suit' badge, a mutual's "
    "included (unfollow.follows_back_indicators, mixins/decision.py _profile_follows_you): the "
    "last check before an unfollow never says yes"))
def test_the_profile_of_a_mutual_says_it_follows_us():
    set_active_locale("en")
    assert _business(MUTUAL_PROFILE_EN)._profile_follows_you("alice") is True


def test_no_badge_proves_nothing_off_the_right_profile():
    """Absent on another profile, or off any profile, is a doubt, not a 'no'."""
    assert _business(FOLLOWED_PROFILE, shown="bob")._profile_follows_you("alice") is None
    assert _business(FOLLOWED_PROFILE, on_profile=False)._profile_follows_you("alice") is None
