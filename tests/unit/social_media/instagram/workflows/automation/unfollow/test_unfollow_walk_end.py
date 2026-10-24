"""The unfollow's walk of our following list ends like a list read: on proof, after the reload waits.

The walk (`UnfollowBusiness._unfollow_in_open_list`) ended on three drags in a row without a new
name, with its own counter. On a Pixel 6a (Instagram 447, 2026-10-24) that sign was what a page
Instagram is slow to serve looked like: the following read stopped at 175 of 1 265 nine seconds
after its last new name. The reads got the end of `list_proof.ListReadEnd` (the waits of the reload
net, 5, 12 and 25 s, while the tab's count says names are missing); the walk kept its own, and a
late page marked every candidate left « not in the list » for the session.

The walk now ends through the same `ListReadEnd`, on the tab's count. A walk proven to the end of
the list says its candidates left are not in it (`not_in_list`); one that ends unproven says they
were not reached (`not_reached`), never that they are absent. Either way they are handled for the
session, so the next batch takes the next candidates.

The pages are written by `fake_follow_list.follow_list_xml` with the tab strip of the real 447
dumps: no capture holds a list that pauses.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import FakeDetection, FakeFacade, FakeScreen, follow_list_xml, unified_tabs, walk_list
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.automation.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins import actions as actions_mixin
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.workflows.common.list_reload_policy import DEFAULT_WAITS_SECONDS


@pytest.fixture
def kept(monkeypatch):
    """The screens kept for diagnosis, by label."""
    kept = []
    monkeypatch.setattr(actions_mixin, "capture_screen_snapshot", lambda _device, label, **_k: kept.append(label))
    return kept


@pytest.fixture
def slept(monkeypatch, kept):
    """French, every sleep of the code recorded instead of slept, no IPC, no screen kept."""
    set_active_locale("fr")
    slept = []
    monkeypatch.setattr(unfollow_workflow.time, "sleep", slept.append)
    for name in ("confirm_dialog_timeout", "row_state_timeout", "profile_open_timeout",
                 "following_tab_timeout", "list_load_timeout"):
        monkeypatch.setattr(UnfollowBusiness, name, 0.0)
    for name in ("emit_unfollow", "emit_stats", "emit_unfollow_plan"):
        monkeypatch.setattr(unfollow_workflow.IPCEmitter, name, staticmethod(lambda *a, **k: None))
    yield slept
    set_active_locale(None)


def _following_page(rows, count):
    titles = ("9 followers", f"{count} suivi(e)s", "0 abonnements", "À vérifier")
    return follow_list_xml(rows, extra=unified_tabs(selected=1, titles=titles))


def _business(*screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business.detection_actions = FakeDetection(screen, business)
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    business._scroll_following_list = lambda: screen.advance() or True
    recorded = []
    business._record_action = lambda username, action, count=1: recorded.append(username)
    return business, recorded


def _waits(slept):
    return [seconds for seconds in slept if seconds in DEFAULT_WAITS_SECONDS]


FIRST = [(f"a{i}", "Suivi(e)") for i in range(1, 7)]
REST = [(f"a{i}", "Suivi(e)") for i in range(7, 13)]
NO_PAUSE = {"unfollow_delay_range": (1, 1)}


def test_the_walk_waits_for_a_page_that_comes_late(slept):
    # The first page, three drags that bring nothing (the list loads its next page), then the page
    # of the candidate. The walk ended on the third quiet drag and called it « not in the list ».
    unfollowed = [row if row[0] != "a10" else ("a10", "Suivre") for row in REST]
    business, recorded = _business(*[_following_page(FIRST, 12)] * 4, _following_page(REST, 12),
                                   _following_page(unfollowed, 12))

    stats = walk_list(business, NO_PAUSE, names=["a10"])

    assert stats["unfollows_made"] == 1 and recorded == ["a10"]
    assert stats["not_in_list"] == 0 and stats["not_reached"] == 0
    assert _waits(slept) == [DEFAULT_WAITS_SECONDS[0]]


def test_a_walk_that_never_comes_back_does_not_call_its_candidates_absent(slept, kept):
    # The run's shape: names stop coming far short of the count. Every wait is given; the walk
    # proved no end of the list, so its candidate was not reached, not found absent. The screen it
    # stopped on is kept.
    business, recorded = _business(_following_page(FIRST, 1265))

    stats = walk_list(business, NO_PAUSE, names=["a900"])

    assert _waits(slept) == list(DEFAULT_WAITS_SECONDS)
    assert (stats["not_in_list"], stats["not_reached"]) == (0, 1)
    assert "a900" in business._handled and recorded == []
    assert kept == ["unfollow_walk_unproven"]


def test_a_walk_proven_to_the_end_of_the_list_says_its_candidates_are_not_in_it(slept, kept):
    # The six rows of a list of six: the count proves the end, no wait is given.
    business, recorded = _business(_following_page(FIRST, 6))

    stats = walk_list(business, NO_PAUSE, names=["ghost_of_the_base"])

    assert _waits(slept) == []
    assert (stats["not_in_list"], stats["not_reached"]) == (1, 0)
    assert "ghost_of_the_base" in business._handled and recorded == [] and kept == []


def test_the_walk_ends_on_the_suggestions_under_the_list(slept):
    # The suggestions under the list end it at once, without the waits or a drag; the gap to the
    # count (6 of 100) is beyond the 5 % the suggestions may prove, so its candidate was not reached.
    titles = ("9 followers", "100 suivi(e)s", "0 abonnements", "À vérifier")
    business, _recorded = _business(follow_list_xml(FIRST + [("someone_else", "Suivre")],
                                                    extra=unified_tabs(selected=1, titles=titles),
                                                    suggestions_before=6))

    stats = walk_list(business, NO_PAUSE, names=["a900"])

    assert _waits(slept) == [] and stats["scrolls"] == 0
    assert (stats["not_in_list"], stats["not_reached"]) == (0, 1)
