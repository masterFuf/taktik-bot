"""U9: the unified follow list is read on OUR FOLLOWING tab, never on the followers one."""

import pytest

from fake_follow_list import FakeFacade, FakeScreen, follow_list_xml, unified_tabs
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

ROWS = [("ghost", "Suivi(e)"), ("friend", "Suivi(e)")]


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "following_tab_timeout", 0.0)
    yield
    set_active_locale(None)


def _business(*screens):
    screen = FakeScreen(*screens)
    return UnfollowBusiness(FakeFacade(screen)), screen


def test_a_list_without_tabs_is_taken_as_is():
    business, screen = _business(follow_list_xml(ROWS))
    assert business._ensure_following_tab() is True
    assert business.device.taps == []


def test_the_following_tab_already_shown_is_not_tapped():
    business, screen = _business(follow_list_xml(ROWS, extra=unified_tabs(selected=1)))
    assert business._ensure_following_tab() is True
    assert business.device.taps == []


def test_the_list_opened_on_the_followers_tab_is_switched_to_following():
    business, screen = _business(
        follow_list_xml(ROWS, extra=unified_tabs(selected=0)),
        follow_list_xml(ROWS, extra=unified_tabs(selected=1)),
    )
    assert business._ensure_following_tab() is True
    assert len(business.device.taps) == 1
    # the tap landed on the "suivi(e)s" title, the second tab
    x = (business.device.taps[0][0] + business.device.taps[0][2]) / 2 if len(business.device.taps[0]) == 4 \
        else business.device.taps[0][0]
    assert 270 <= x <= 530


def test_a_tab_tapped_but_not_shown_refuses_the_list():
    business, screen = _business(follow_list_xml(ROWS, extra=unified_tabs(selected=0)))
    assert business._ensure_following_tab() is False


def test_tabs_without_a_readable_following_title_refuse_the_list():
    # the paid subscriptions tab ("abonnements") must never pass for our following
    tabs = unified_tabs(selected=0, titles=("673 followers", "0 abonnements", "À vérifier"))
    business, screen = _business(follow_list_xml(ROWS, extra=tabs))
    assert business._ensure_following_tab() is False
    assert business.device.taps == []


def test_english_tabs():
    set_active_locale("en")
    titles = ("295 followers", "48 following", "0 subscriptions", "Flagged")
    business, screen = _business(
        follow_list_xml([("ghost", "Following")], extra=unified_tabs(selected=0, titles=titles)),
        follow_list_xml([("ghost", "Following")], extra=unified_tabs(selected=1, titles=titles)),
    )
    assert business._ensure_following_tab() is True
    assert len(business.device.taps) == 1


def test_the_engine_touches_no_row_when_the_following_tab_cannot_be_shown(monkeypatch):
    monkeypatch.setattr(UnfollowBusiness, "confirm_dialog_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "row_state_timeout", 0.0)
    business, screen = _business(follow_list_xml(ROWS, extra=unified_tabs(selected=0)))
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_following_list = lambda: True
    recorded = []
    business._record_action = lambda username, action, count=1: recorded.append(username)

    stats = business.unfollow_listed_accounts(["ghost"], {"unfollow_mode": "all"})

    assert stats["errors"] == 1 and stats["unfollows_made"] == 0
    assert recorded == [] and len(business.device.taps) == 1  # the tab tap, no row tap


def test_the_following_sync_records_nothing_from_the_followers_tab(monkeypatch):
    business, screen = _business(follow_list_xml(ROWS, extra=unified_tabs(selected=0)))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_following_list = lambda: True
    departures = []
    business._record_following_departures = lambda *a, **k: departures.append(a) or 0

    stats = business.sync_following_list({"mode": "fast"})

    assert not stats.get("complete") and not stats.get("success")
    assert departures == []
