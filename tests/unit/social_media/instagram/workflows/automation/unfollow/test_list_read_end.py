"""A read of a follow list ends on proof, after giving a list short of its count time to load.

Pixel 6a, Instagram 447, our account, 2026-10-24:

- the following read stopped at 175 of 1 265: 31 drags gave 4 to 6 new names each, then three drags
  gave none, nine seconds in all, and the read ended (« NOT proven complete », honestly refused). On
  Instagram 410 a whole read of 1 882 never went more than two drags without a new name. A list
  short of its count by a thousand names is not ended by nine seconds of silence: it is now given
  the waits of the reload net (`ListReloadPolicy`, 5, 12 and 25 s), one drag and one read after
  each, before it ends unproven (`list_proof.ListReadEnd`, shared by the following, followers and
  fans reads);
- the fans category, announced as « user_2 et 536 autres personnes », was read for a fixed
  30 drags: 171 fans, and « Fans category read: 171 » as a success. Its size is now read on the
  category's line before the tap, bounds the drags, and proves the read like a tab's count; a read
  short of it records the fans it read and gives no count.

The followers list with its categories is the real capture of that run (anonymized,
`ig447_fr_own_followers_list_fans_537.xml`); the screens a test derives from it say so where they
are built. The pages of a long list are written by `fake_follow_list.follow_list_xml`: no capture
holds 200 fans or a list that pauses, and their widgets are the ones of the real dumps.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import (
    FakeFacade, FakeScreen, Graph, derived_fans_category_size, follow_list_xml, unified_tabs,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.automation import workflow_runner as runner_module
from taktik.core.social_media.instagram.workflows.automation.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.workflows.automation.unfollow.list_proof import (
    PROOF_BY_COUNT, ListReadEnd, parse_category_size,
)
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins import actions as actions_mixin
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from taktik.core.social_media.instagram.workflows.automation.workflow_runner import WorkflowRunner
from taktik.core.social_media.instagram.workflows.common.list_reload_policy import DEFAULT_WAITS_SECONDS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FANS_537 = (FIXTURES / "ig447_fr_own_followers_list_fans_537.xml").read_text(encoding="utf-8")
FRENCH_OTHERS = ["autres personnes", "autre personne"]


# ── The size a category announces ─────────────────────────────────────────────

@pytest.mark.parametrize("line, labels, size", [
    ("user_2 et 536 autres personnes", FRENCH_OTHERS, 537),     # 447 fr, the run's fans category
    ("user_4 et 1 autre personne", FRENCH_OTHERS, 2),           # 447 fr, « Comptes désactivés »
    ("user_2 and 276 others", ["others"], 277),                 # 410 en
    ("user_2 et 1 234 autres personnes", FRENCH_OTHERS, 1235),  # a count with its thousands space
    ("user_2", FRENCH_OTHERS, 1),
    ("user_2 et name_6", FRENCH_OTHERS, None),                  # two names, no count: no size
    ("user_2 et 536 autres", FRENCH_OTHERS, None),              # a count no label follows
    ("user_2 and 1,2 k others", ["others"], None),              # abbreviated
    ("", FRENCH_OTHERS, None),
    (None, FRENCH_OTHERS, None),
])
def test_the_size_a_category_line_announces(line, labels, size):
    assert parse_category_size(line, labels) == size


# ── When a read ends (the run's numbers) ──────────────────────────────────────

def _quiet_reads(end, count, seen=175):
    """`count` reads without a new name; True when the read ended on the last."""
    ended = False
    for _ in range(count):
        ended = end.after_read(False, seen, suggestions_reached=False, scroll_failed=False, left_out={})
    return ended


def test_a_read_short_of_its_count_is_given_the_reload_waits_before_it_ends():
    end = ListReadEnd(1265, waits=DEFAULT_WAITS_SECONDS)
    assert end.after_read(True, 175, suggestions_reached=False, scroll_failed=False, left_out={}) is False

    given = []
    for _ in DEFAULT_WAITS_SECONDS:
        assert _quiet_reads(end, 3 if not given else 1) is False
        given.append(end.wait)
    assert given == list(DEFAULT_WAITS_SECONDS)

    assert _quiet_reads(end, 1) is True
    assert end.proof is None and end.waited == sum(DEFAULT_WAITS_SECONDS)


def test_a_new_name_gives_the_waits_back():
    end = ListReadEnd(1265, waits=(5.0, 12.0))
    _quiet_reads(end, 3)
    assert end.wait == 5.0
    end.after_read(True, 180, suggestions_reached=False, scroll_failed=False, left_out={})
    _quiet_reads(end, 3, seen=180)
    assert end.wait == 5.0


@pytest.mark.parametrize("expected, suggestions, scroll_failed", [
    (1265, True, False),    # the suggestions under the list: it ended there
    (1265, False, True),    # a drag that failed: waiting proves nothing
    (None, False, False),   # no count: nothing says names are missing
])
def test_a_read_that_cannot_be_short_of_a_count_ends_without_waiting(expected, suggestions, scroll_failed):
    end = ListReadEnd(expected, waits=DEFAULT_WAITS_SECONDS)
    ended = False
    for _ in range(3):
        ended = end.after_read(False, 175, suggestions_reached=suggestions, scroll_failed=scroll_failed,
                               left_out={})
        if ended:
            break
    assert ended is True and end.waited == 0


def test_a_read_that_reaches_its_count_ends_proven_without_waiting():
    end = ListReadEnd(12, waits=DEFAULT_WAITS_SECONDS)
    end.after_read(True, 12, suggestions_reached=False, scroll_failed=False, left_out={})
    assert _quiet_reads(end, 3, seen=12) is True
    assert end.proof == PROOF_BY_COUNT and end.waited == 0


# ── The reads, on a list that pauses ──────────────────────────────────────────

@pytest.fixture(autouse=True)
def _french_and_timed(monkeypatch):
    """French, and every sleep of the code recorded instead of slept."""
    set_active_locale("fr")
    slept = []
    monkeypatch.setattr(unfollow_workflow.time, "sleep", slept.append)
    monkeypatch.setattr(UnfollowBusiness, "following_tab_timeout", 0.0)
    monkeypatch.setattr(UnfollowBusiness, "list_load_timeout", 0.0)
    kept = []
    monkeypatch.setattr(actions_mixin, "capture_screen_snapshot",
                        lambda _device, label, **_k: kept.append(label))
    yield slept, kept
    set_active_locale(None)


def _business(screens, graph, monkeypatch):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_followers_list = lambda: True
    business.nav_actions.open_following_list = lambda: True
    business._set_following_list_sort = lambda order: False
    business._scroll_followers_list = lambda: screen.advance() or True
    business._scroll_following_list = lambda: screen.advance() or True
    graph.install(monkeypatch)
    return business, screen


def _following_page(names, count):
    titles = ("9 followers", f"{count} suivi(e)s", "0 abonnements", "À vérifier")
    return follow_list_xml([(name, "Suivi(e)") for name in names], extra=unified_tabs(selected=1, titles=titles))


def _followers_page(names, count):
    titles = (f"{count} followers", "4 suivi(e)s", "0 abonnements", "À vérifier")
    return follow_list_xml([(name, "Suivi(e)") for name in names], extra=unified_tabs(selected=0, titles=titles))


def _waits(slept):
    return [seconds for seconds in slept if seconds in DEFAULT_WAITS_SECONDS]


FIRST = [f"a{i}" for i in range(1, 7)]
REST = [f"a{i}" for i in range(7, 13)]


def test_a_following_read_waits_for_a_page_that_comes_late(monkeypatch, _french_and_timed):
    # The first page, then three drags that bring nothing (the list loads its next page), then the
    # rest: the read used to end on the third quiet drag, 6 of 12, unproven.
    slept, kept = _french_and_timed
    pages = [_following_page(FIRST, 12)] * 4 + [_following_page(REST, 12)]
    business, _screen = _business(pages, Graph(), monkeypatch)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["total_seen"] == 12 and stats["proof"] == PROOF_BY_COUNT and stats["success"] is True
    assert _waits(slept) == [DEFAULT_WAITS_SECONDS[0]]
    assert kept == []


def test_a_following_read_that_never_comes_back_ends_unproven_after_the_waits(monkeypatch, _french_and_timed):
    # The run's shape: names stop coming far short of the count. Every wait is given, then the read
    # ends unproven, and keeps the screen it stopped on.
    slept, kept = _french_and_timed
    business, _screen = _business([_following_page(FIRST, 1265)], Graph(), monkeypatch)

    stats = business.sync_following_list({"mode": "fast"})

    assert stats["total_seen"] == 6 and stats["proof"] is None and stats["success"] is False
    assert _waits(slept) == list(DEFAULT_WAITS_SECONDS)
    assert kept == ["following_list_unproven"]


def test_the_followers_read_waits_for_a_page_that_comes_late_too(monkeypatch, _french_and_timed):
    slept, _kept = _french_and_timed
    pages = [_followers_page(FIRST, 12)] * 4 + [_followers_page(REST, 12)]
    business, _screen = _business(pages, Graph(), monkeypatch)

    stats = business.sync_followers_list({"mode": "fast"})

    assert stats["total_seen"] == 12 and stats["proof"] == PROOF_BY_COUNT
    assert _waits(slept) == [DEFAULT_WAITS_SECONDS[0]]


def test_a_followers_read_that_never_comes_back_ends_the_full_sync_on_its_own_motive(monkeypatch, _french_and_timed):
    # The full sync (following, then followers): the followers list opened and its read stopped at 6
    # of 1 265 after every wait. It said « liste indisponible » (`list_unavailable`), as if the list
    # had never opened; it is a list read in part, with its numbers.
    _slept, kept = _french_and_timed
    business, _screen = _business([_followers_page(FIRST, 1265)], Graph(), monkeypatch)
    business.sync_following_list = lambda config=None: {
        "new_count": 0, "updated_count": 0, "stopped_early": False, "total_seen": 12, "expected": 12,
        "proof": PROOF_BY_COUNT, "success": True}
    monkeypatch.setattr(runner_module.time, "sleep", lambda _s: None)
    ends = []
    automation = SimpleNamespace(session_finalized=False, unfollow_business=business, stats={})
    automation.helpers = SimpleNamespace(finalize_session=lambda status, reason: ends.append((status, reason)))

    WorkflowRunner(automation)._run_sync_followers_following_workflow({"type": "sync_followers_following"})

    ((status, reason),) = ends
    assert (status, reason.code) == ("INTERRUPTED", "followers_list_unproven")
    assert reason.params == {"seen": 6, "expected": 1265}
    assert kept == ["followers_list_unproven"]


# ── The fans category, read to the size it announces ──────────────────────────

def _fans_pages(count, per_page=5):
    names = [f"fan_{i}" for i in range(1, count + 1)]
    return names, [follow_list_xml([(name, "Suivre en retour") for name in names[start:start + per_page]])
                   for start in range(0, count, per_page)]


def test_the_fans_category_is_read_past_30_drags_to_its_size(monkeypatch):
    # 200 fans, 5 a screen: 40 screens. The read stopped at a fixed 30 drags and announced 155 fans.
    names, pages = _fans_pages(200)
    graph = Graph()
    # The list as found (the tap on the followers tab), then as shown, then the category's pages
    business, _screen = _business([derived_fans_category_size(FANS_537, 200)] * 2 + pages, graph, monkeypatch)

    stats = business.scrape_non_followers_category()

    assert stats["expected"] == 200
    assert stats["fans_count"] == 200 and stats["success"] is True and stats["proof"] == PROOF_BY_COUNT
    assert graph.followers == names


def test_a_fans_category_read_short_of_its_size_gives_no_count(monkeypatch):
    # The run: the category announces 537, its screen shows 4 whole rows of fans (the fifth is cut by
    # the bottom of the list) and nothing more comes.
    graph = Graph()
    business, _screen = _business([FANS_537], graph, monkeypatch)

    stats = business.scrape_non_followers_category()

    assert stats["expected"] == 537 and stats["total_seen"] == 4
    assert stats["success"] is False and stats["read_unproven"] is True
    assert stats["fans_count"] is None and stats["non_followers_count"] is None, "a part read passed for a count"
    # The fans read are recorded: each is a fact the screen showed
    assert graph.followers == ["user_2", "user_5", "user_6", "name_15"]
