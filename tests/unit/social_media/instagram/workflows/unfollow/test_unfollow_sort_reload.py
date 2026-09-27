"""After the sort, the following list reloads: a read before its rows come back finds none.

Measured on a Pixel 3 (Instagram 410, in French): right after the "plus récent" option is tapped,
the list's header already names the new order while the list shows only its loading placeholder
(`listview_shimmer`), no row. The unfollow confirmed its sort on that header, read the list 1.6 s
later, found no row and took the empty screen for the end of the list: "Following sync complete:
0 new, 0 updated, 0 seen" out of 1 929 followings. The rows were there a few seconds later.

The screens are real dumps of that phone, anonymized: the list in its default order, the sort
sheet, the list reloading after the tap (`ig410_fr_following_list_reloading_after_sort.xml`) and
the list once its rows are back. The rows come back `RELOAD_S` seconds of the test's clock after
the tap: longer than the pause the sync takes after its sort, as on that run.
"""

from pathlib import Path

import pytest

from fake_follow_list import FakeClock, FakeFacade, FakeScreen, Graph
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.list_proof import PROOF_BY_KNOWN_ACCOUNT
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import (
    actions as actions_module,
    sync_following as following_module,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parents[2] / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


LIST_DEFAULT = _capture("ig410_fr_following_list_sorted_default.xml")
SHEET = _capture("ig410_fr_following_list_sort_sheet.xml")
RELOADING = _capture("ig410_fr_following_list_reloading_after_sort.xml")
LIST_LATEST = _capture("ig410_fr_following_list_sorted_latest.xml")
RELOAD_S = 3.0
USERNAME = '//*[@resource-id="com.instagram.android:id/follow_list_username"]'
FIRST_ROW = FakeScreen(LIST_LATEST).xpath(USERNAME).all()[0].text


class ReloadingList(FakeScreen):
    """The screens in the order Instagram shows them; the reloading list gives way to its rows
    once `reload_s` seconds have passed on the clock since it showed."""

    def __init__(self, clock, reload_s, *screens):
        super().__init__(*screens)
        self.clock = clock
        self.reload_s = reload_s
        self.reloading_since = None

    def advance(self):
        super().advance()
        if self.screens[self.index] is RELOADING:
            self.reloading_since = self.clock.now

    def _settle(self):
        if self.reloading_since is not None and self.clock.now - self.reloading_since >= self.reload_s:
            self.reloading_since = None
            FakeScreen.advance(self)

    def tree(self):
        self._settle()
        return super().tree()

    def dump_hierarchy(self, *a, **k):
        self._settle()
        return super().dump_hierarchy(*a, **k)


@pytest.fixture(autouse=True)
def _french(monkeypatch):
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _business(monkeypatch, graph, reload_s=RELOAD_S):
    clock = FakeClock()
    monkeypatch.setattr(actions_module, "time", clock)
    monkeypatch.setattr(following_module, "time", clock)
    screen = ReloadingList(clock, reload_s, LIST_DEFAULT, SHEET, RELOADING, LIST_LATEST)
    business = UnfollowBusiness(FakeFacade(screen))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_following_list = lambda: True
    business._scroll_following_list = lambda: screen.advance() or True
    graph.install(monkeypatch)
    return business, screen


def test_the_reloading_capture_names_the_new_order_and_shows_no_row():
    screen = FakeScreen(RELOADING)
    names = screen.xpath('//*[@resource-id="com.instagram.android:id/follow_list_username"]').all()
    header = screen.xpath('//*[@resource-id="com.instagram.android:id/sorting_entry_row_option"]').get_text()
    assert names == []
    assert "plus récent" in header
    assert screen.xpath('//*[@resource-id="com.instagram.android:id/listview_shimmer"]').exists


def test_the_sort_hands_the_list_back_once_its_rows_are_there(monkeypatch):
    business, screen = _business(monkeypatch, Graph())

    assert business._set_following_list_sort("latest") is True
    assert screen.screens[screen.index] is LIST_LATEST
    assert business._visible_follow_rows()


def test_the_sync_reads_the_rows_of_the_reloaded_list(monkeypatch):
    graph = Graph()
    business, _screen = _business(monkeypatch, graph)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["expected"] == 1923  # the count the list showed when it opened
    assert stats["total_seen"] > 0
    assert graph.followings[0] == FIRST_ROW


def test_a_sorted_read_that_stops_at_a_known_account_is_proven_up_to_date(monkeypatch):
    # The base knows more than half of the tab's count, the first row among them.
    graph = Graph(known_followings={FIRST_ROW} | {f"compte_exemple_{i}" for i in range(1000)})
    business, _screen = _business(monkeypatch, graph)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["stopped_early"] is True
    assert stats["proof"] == PROOF_BY_KNOWN_ACCOUNT and stats["success"] is True
    # Up to date, not complete: no account missing from the read is taken for unfollowed.
    assert stats["complete"] is False and graph.unfollowed == []


def test_a_list_that_never_reloads_proves_nothing(monkeypatch):
    business, _screen = _business(monkeypatch, Graph(), reload_s=float("inf"))

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["total_seen"] == 0 and stats["expected"] == 1923
    assert stats["proof"] is None and stats["success"] is False


def test_the_unfollow_decides_nothing_on_a_following_read_that_proves_nothing(monkeypatch):
    business, screen = _business(monkeypatch, Graph(), reload_s=float("inf"))
    followers_synced = []
    business.sync_followers_list = lambda cfg: followers_synced.append(cfg) or {}
    business._open_list_and_walk = lambda *a: pytest.fail("no walk on an unchecked base")

    stats = business.run_unfollow_workflow({"unfollow_mode": "non-followers", "max_unfollows": 5})

    assert stats["stop_reason"].code == "following_list_unproven"
    assert stats["stop_reason"].params == {"seen": 0, "expected": 1923}
    assert followers_synced == []
    assert len(screen.taps) == 2  # the sort icon and its option: nothing after
