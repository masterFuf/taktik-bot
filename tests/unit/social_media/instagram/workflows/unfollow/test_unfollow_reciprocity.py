"""U6: reciprocity, for real.

The "don't follow back" category of the followers tab lists FANS (they follow us, we do not
follow them). It used to be read as the accounts WE follow that do not follow back: every fan got
a following row, and every following absent from the category was marked as a mutual. Now the
category only records fans, and the last word before an unfollow is the "Follows you" badge read
on the right profile.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


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
    business = UnfollowBusiness(FakeFacade(FakeScreen(follow_list_xml([]))))
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


def _profile_screen(badge: bool) -> str:
    # A loaded profile: the header's action button says we follow the account ("Suivi(e)").
    extra = ('<node index="5" text="Vous suit" resource-id="" class="android.widget.TextView" '
             'content-desc="" bounds="[40,500][300,540]" />') if badge else ""
    extra += ('<node index="6" text="Suivi(e)" resource-id="com.instagram.android:id/profile_header_follow_button" '
              'class="android.widget.Button" content-desc="" bounds="[40,600][500,680]" />')
    return follow_list_xml([], extra=extra)


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


def test_the_badge_is_read_on_the_right_profile():
    assert _business(_profile_screen(badge=True))._profile_follows_you("alice") is True
    assert _business(_profile_screen(badge=False))._profile_follows_you("@Alice") is False


def test_no_badge_proves_nothing_off_the_right_profile():
    """Absent on another profile, or off any profile, is a doubt, not a 'no'."""
    assert _business(_profile_screen(badge=False), shown="bob")._profile_follows_you("alice") is None
    assert _business(_profile_screen(badge=False), on_profile=False)._profile_follows_you("alice") is None
