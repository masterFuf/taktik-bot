"""Our followers, read from the top of the list: the read stops at the followers the base knows.

The unfollow read our whole followers list at every run, to learn who follows us: 1 222 followers
read in 9 minutes on a Pixel 3 for 2 new ones, the first two rows of the list. On Instagram 410 the
list shows the newest follower first, so once the base knows our followers, a read from the top
learns the new ones and stops at a run of known ones, when the base plus the new ones match the
tab's count (`list_proof.base_matches_count`); otherwise it reads the whole list, whose end proves
who left us.

The screens are real dumps of Instagram 410 in English (Pixel 3a, 2026-09-28): the top of our own
followers list ("295 followers"), then the three screens the production drag of the follow lists
brings up after it, anonymized with ONE replacement table, so a name keeps its value from a screen
to the next. Instagram 447 is played on our own followers list of a Pixel 6a ("678 followers",
2026-09-23), whose tab shows a sort control. Two tests play screens DERIVED from these dumps, and
say so: the count of the tab rewritten, and one row's button taken out.
"""

import pytest

from fake_follow_list import FakeFacade, FakeScreen, Graph, derived_row_button
from taktik.core.social_media.instagram.actions.business.workflows.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.candidates import (
    FollowersSnapshot,
    FollowingRecord,
    select_candidates,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.list_proof import (
    PROOF_BY_BASE_COUNT,
    PROOF_BY_COUNT,
)
from taktik.core.social_media.instagram.actions.business.workflows.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREENS = [(FIXTURES / f"ig410_en_own_followers_newest_first_{n}.xml").read_text(encoding="utf-8")
           for n in (1, 2, 3, 4)]
IG447_FOLLOWERS = (FIXTURES / "ig447_fr_own_followers_list.xml").read_text(encoding="utf-8")

# The rows of the four screens, top to bottom (the newest follower first).
ROWS = ["user_2", "user_3", "user_4", "name_7", "name_10", "user_5", "user_6", "user_7", "user_8",
        "user_9", "user_10", "user_11", "user_12", "user_13", "user_14", "user_15", "name_56",
        "user_16", "user_17", "user_18", "name_68", "user_19", "user_20"]
# The followers of the account further down the list, as the base knows them.
OLDER = [f"older_{i}" for i in range(272)]
COUNT = 295


@pytest.fixture(autouse=True)
def _english_and_fast(monkeypatch):
    set_active_locale("en")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    monkeypatch.setattr(UnfollowBusiness, "following_tab_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "list_load_timeout", 0.0)
    yield
    set_active_locale(None)


def _read(screens, graph, monkeypatch):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_followers_list = lambda: True
    business._scroll_followers_list = lambda: screen.advance() or True
    graph.install(monkeypatch)
    return business, business.sync_followers_list({"mode": "fast"})


def test_the_read_stops_after_ten_known_followers_when_the_base_matches_the_count(monkeypatch):
    # Two new followers since the last read: the first two rows.
    graph = Graph(known_followers=ROWS[2:] + OLDER)

    _business, stats = _read(SCREENS, graph, monkeypatch)

    assert stats["proof"] == PROOF_BY_BASE_COUNT and stats["incremental"] is True
    assert graph.followers == ROWS[:12]            # the 2 new ones, then 10 known in a row
    assert stats["scrolls"] == 1
    # every follower, the ones the read did not reach included: the base holds them
    assert stats["complete"] is True and len(stats["usernames"]) == COUNT
    assert {"user_2", "user_3", "older_0", "user_20"} <= stats["usernames"]
    assert stats["known_before"] == 293 and stats["known_after"] == COUNT
    assert graph.followers_gone == []              # a read that stopped early shows no departure
    assert graph.reciprocity == [stats["usernames"]]
    assert stats["success"] is True


def test_a_follower_back_among_the_new_ones_does_not_stop_the_read(monkeypatch):
    # user_3 followed us, left, and came back: the base knows it, and it shows among the new ones.
    graph = Graph(known_followers=["user_3"] + ROWS[3:] + OLDER[:271])

    _business, stats = _read(SCREENS, graph, monkeypatch)

    assert stats["proof"] == PROOF_BY_BASE_COUNT
    assert "user_4" in graph.followers and "user_4" in stats["usernames"]


def test_a_base_short_of_the_count_reads_the_whole_list(monkeypatch):
    # The base was never read whole: 121 followers known, the tab says 295.
    graph = Graph(known_followers=ROWS[2:] + OLDER[:100])

    _business, stats = _read(SCREENS, graph, monkeypatch)

    assert stats["incremental"] is False and stats["proof"] is None and stats["complete"] is False
    assert graph.followers == ROWS                 # every row of the four screens
    assert graph.reciprocity == []


def test_a_base_over_the_count_reads_the_whole_list(monkeypatch):
    # Ten followers left since the last complete read: the base holds 10 more than the tab.
    graph = Graph(known_followers=ROWS[2:] + OLDER + [f"left_{i}" for i in range(10)])

    _business, stats = _read(SCREENS, graph, monkeypatch)

    assert stats["incremental"] is False and stats["proof"] is None
    assert graph.followers == ROWS


def _with_count(xml: str, count: int) -> str:
    """The dump with its followers tab showing `count` (derived: the only change)."""
    assert xml.count(f'text="{COUNT} followers"') == 1
    return xml.replace(f'text="{COUNT} followers"', f'text="{count} followers"')


def test_a_complete_read_marks_the_followers_gone(monkeypatch):
    # Derived: the tab counts the 23 rows the four screens hold, so the read ends the list. The
    # base holds three followers that left: more than the count, the list is read whole.
    screens = [_with_count(xml, len(ROWS)) for xml in SCREENS]
    graph = Graph(known_followers=ROWS + ["left_1", "left_2", "left_3"])

    _business, stats = _read(screens, graph, monkeypatch)

    assert stats["proof"] == PROOF_BY_COUNT and stats["incremental"] is False
    assert graph.followers_gone == ["left_1", "left_2", "left_3"] and stats["departures"] == 3
    assert stats["usernames"] == set(ROWS)


def test_a_follower_shown_without_its_button_is_not_marked_gone(monkeypatch):
    # Derived: on the last screen, the button of user_20 is not in the dump (the read cannot pair
    # it to its name, so it does not count the row). The name is on screen: user_20 did not leave.
    screens = [_with_count(xml, len(ROWS)) for xml in SCREENS]
    screens[3] = derived_row_button(screens[3], "user_20", None)
    graph = Graph(known_followers=ROWS + ["left_1", "left_2", "left_3"])

    _business, stats = _read(screens, graph, monkeypatch)

    assert stats["proof"] == PROOF_BY_COUNT and "user_20" not in graph.followers
    assert graph.followers_gone == ["left_1", "left_2", "left_3"]


def test_a_followers_tab_with_a_sort_control_is_read_whole(monkeypatch):
    # Instagram 447: the tab sorts "Par défaut", and that order is not the follow date (between two
    # reads of a Pixel 6a account, the new followers were spread down the list). The run of known
    # followers is shortened to 2 here, so the one screen could stop the read if the tab allowed it.
    set_active_locale("fr")
    rows = ["user_5", "user_6", "name_17", "user_7", "user_8"]
    graph = Graph(known_followers=rows + [f"older_{i}" for i in range(673)])
    screen = FakeScreen(IG447_FOLLOWERS)
    business = UnfollowBusiness(FakeFacade(screen))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_followers_list = lambda: True
    business._scroll_followers_list = lambda: screen.advance() or True
    business.known_in_a_row_to_stop = 2
    graph.install(monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert stats["expected"] == 678 and stats["incremental"] is False and stats["proof"] is None
    assert graph.followers == rows


def test_the_unfollow_keeps_a_follower_the_read_did_not_reach(monkeypatch):
    """The decision on an incremental read: a following the base knows as a follower, far below the
    stop point, follows back; one the base does not know as a follower does not."""
    graph = Graph(known_followers=ROWS[2:] + OLDER)
    _business, stats = _read(SCREENS, graph, monkeypatch)
    followers = FollowersSnapshot(usernames=frozenset(stats["usernames"]), complete=stats["complete"])
    old = unfollow_workflow.datetime(2026, 9, 1)
    records = [FollowingRecord("older_200", followed_by_bot=True, followed_at=old),
               FollowingRecord("never_followed_us", followed_by_bot=True, followed_at=old)]

    selection = select_candidates(records, {"unfollow_mode": "non-followers"}, followers,
                                  unfollow_workflow.datetime(2026, 9, 28))

    assert selection.candidates == ["never_followed_us"]
    assert selection.refusals == {"follows_back": 1}
