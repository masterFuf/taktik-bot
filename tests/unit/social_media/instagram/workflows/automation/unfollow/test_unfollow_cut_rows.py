"""The unfollow acts on whole rows, and finds its row again after the profile.

Pixel 6a, Instagram 447, our account, 2026-10-24 (Lab `engagement.unfollow_account`): the walk
tapped the row of its candidate when 16 px of it showed at the bottom of the list, its profile
opened, and back from it the list had moved by a few pixels: the row was declared lost
(`row_lost`) without being looked for, and nothing was unfollowed.

- a row cut by the edge of the list is no row the reader returns (`_rows_cut_by_the_list`, the
  rule of `ui_dump.whole_in_band` the feed already used for its carousel): a drag shows it whole;
- back from a profile, the row is looked for where the list is, then one row further, then one row
  back (`_row_found_again`), before `row_lost`.

The screens are real dumps of that phone, anonymized: the top of our following list (its last row,
`name_31`, cut at the bottom of the list; `user_5` offers to follow back) and the list as it was
back from the profile. The screens DERIVED from them say so where they are built.
"""

from types import SimpleNamespace

import pytest

from fake_follow_list import (
    FakeDetection, FakeFacade, FakeScreen, Graph, derived_row_button, profile_xml, walk_list,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.automation.unfollow import workflow as unfollow_workflow
from taktik.core.social_media.instagram.workflows.automation.unfollow.workflow import UnfollowBusiness
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
TOP = (FIXTURES / "ig447_fr_following_list_top_last_row_cut.xml").read_text(encoding="utf-8")
BACK = (FIXTURES / "ig447_fr_following_list_back_from_profile.xml").read_text(encoding="utf-8")
CUT_ROW = "name_31"                 # 99 px of its 189 above the bottom of the list
CANDIDATE = "name_59"               # whole near the bottom of the list, back from the profile


@pytest.fixture(autouse=True)
def _french_and_fast(monkeypatch):
    set_active_locale("fr")
    monkeypatch.setattr(unfollow_workflow.time, "sleep", lambda _s: None)
    for name in ("confirm_dialog_timeout", "row_state_timeout", "profile_open_timeout",
                 "following_tab_timeout", "list_load_timeout"):
        monkeypatch.setattr(UnfollowBusiness, name, 0.0)
    for name in ("emit_unfollow", "emit_stats", "emit_unfollow_plan", "emit_profile_visit"):
        monkeypatch.setattr(unfollow_workflow.IPCEmitter, name, staticmethod(lambda *a, **k: None))
    yield
    set_active_locale(None)


def _business(*screens):
    screen = FakeScreen(*screens)
    business = UnfollowBusiness(FakeFacade(screen))
    business.detection_actions = FakeDetection(screen, business)
    business.nav_actions.problematic_page_detector = SimpleNamespace(is_action_blocked=lambda: False)
    business._scroll_following_list = lambda: screen.advance() or True
    business._nudge_follow_list = lambda forward: screen.advance() or True
    business._record_action = lambda username, action, count=1: None
    return business, screen


# ── a. Whole rows only ────────────────────────────────────────────────────────

def test_a_row_cut_by_the_bottom_of_the_list_is_not_read():
    business, _screen = _business(TOP)

    rows = business._visible_follow_rows()

    assert [row["username"] for row in rows] == ["user_2", "name_18", "user_3", "user_4", "name_25",
                                                 "user_5", "name_29"]
    assert CUT_ROW not in business.unpaired_on_screen


def test_a_whole_row_against_the_top_of_the_list_is_read():
    # Back from the profile the first row starts on the list's top edge, as tall as the others
    business, _screen = _business(BACK)

    names = [row["username"] for row in business._visible_follow_rows()]

    assert names[0] == "user_7" and len(names) == 10


def test_a_following_that_offers_to_follow_back_is_said_not_followed(monkeypatch):
    # « Suivre en retour » on our following list: we do not follow that account, the read leaves
    # it out and says why
    business, _screen = _business(TOP)
    graph = Graph()
    graph.install(monkeypatch)
    business._get_account_id = lambda: 1
    business.nav_actions.navigate_to_profile_tab = lambda: True
    business.nav_actions.open_following_list = lambda: True
    business._set_following_list_sort = lambda order: False

    stats = business.sync_following_list({"mode": "fast", "list_reload_waits": []})

    assert {row["username"]: row["state"] for row in business._visible_follow_rows()}["user_5"] == "follow_back"
    assert "user_5" not in graph.followings and stats["left_out"] == {"follow_back": 1}


def test_the_walk_never_taps_a_cut_row():
    business, screen = _business(TOP)

    stats = walk_list(business, {"unfollow_mode": "all"}, names=[CUT_ROW])

    cut_top = 2238   # the top of the cut row, in the capture
    assert not [tap for tap in business.device.taps if tap[1] >= cut_top], business.device.taps
    # The list counts 1 265 on its tab and shows 7 rows: its end is not proven, the candidate was
    # not reached (never said absent)
    assert stats["unfollows_made"] == 0 and stats["not_reached"] == 1


# ── b. Back from the profile ─────────────────────────────────────────────────

# Derived: the list as it came back, moved by about a row: the candidate is not on screen.
MOVED = BACK.replace(f'text="{CANDIDATE}"', 'text="user_99"')
# Derived: the candidate's row once unfollowed, its button offering to follow again.
UNFOLLOWED = derived_row_button(BACK, CANDIDATE, "Suivre")


def test_the_row_is_looked_for_again_after_the_profile():
    # The list, the candidate's profile, back on a list moved by a row, one short drag, the unfollow
    business, screen = _business(BACK, profile_xml(CANDIDATE), MOVED, BACK, UNFOLLOWED)

    stats = walk_list(business, {"unfollow_mode": "all", "skip_verified": True}, names=[CANDIDATE])

    assert stats["profile_refusals"] == {}, stats
    assert stats["unfollows_made"] == 1
    assert screen.presses == ["back"]


def test_a_row_found_nowhere_around_is_lost_and_the_walk_ends():
    # c. No candidate left after it: the walk ends there, no drag to the end of the list
    business, screen = _business(BACK, profile_xml(CANDIDATE), MOVED)

    stats = walk_list(business, {"unfollow_mode": "all", "skip_verified": True}, names=[CANDIDATE])

    assert stats["profile_refusals"] == {"row_lost": 1}
    assert stats["scrolls"] == 0 and stats["candidates_left"] == 0
