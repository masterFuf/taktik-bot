"""The interaction loop of the runs walks the likers of a post until their list ends, not 50 drags on.

`LikersWorkflowBase._interact_with_likers_list` is the loop of the Feed, Hashtag and Post URL runs
and of the Lab's `engagement.engage_likers`: it opens each new row of the likers sheet, then reads
the sheet again. It stopped on its target, on an empty sheet, or after 50 drags without a new row
(`max_scroll_attempts`): on a post liked twice, both likers walked, it dragged a sheet that could
no longer move 50 times. It now stops on the end that `ScrollEndDetector` tells, with the threshold
of the reading of the likers (`likers_list_end_detector`): two drags in a row that change nothing.

The detector hears only the readings that follow a drag (and the first one). After walking the rows
of a screen the loop reads the SAME screen again without dragging: that reading is not "a drag that
changed nothing" (journal IG-FEED-031), and counting it would end the list one drag early.

The screens are the real likers sheets of `likers_sheet_phone` (C57 S, Instagram 410 in English).
The host is the loop's own class, built by its constructor on that phone; what happens on a
profile (`_process_profile_on_screen`) and the base's decisions are the only stand-ins.
"""

import time

import pytest

from unit.social_media.instagram.services.likers_sheet_phone import LONG_LIST, TWO_LIKERS, LikersSheetPhone
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.base_business.profile_processing import ProfileProcessingResult
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.actions.base.stats import create_workflow_stats
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.common.likers_base import LikersWorkflowBase


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield
    set_active_locale(None)


def _base_knows(monkeypatch, known):
    """The base's answer for each liker: `known` ones were processed before, by this account."""
    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_skippable",
                        staticmethod(lambda username, _account, **_kw: (username in known, "already_processed")))
    monkeypatch.setattr(InstagramWorkflowStateService, "get_skip_detail",
                        staticmethod(lambda *_a, **_kw: None))


def _run_loop(phone):
    """The loop on the phone, each profile opened coming back filtered. Returns the visits."""
    host = LikersWorkflowBase(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    host._human_like_delay = lambda *_a, **_kw: None
    host.detection_actions.wait_for_profile_screen = lambda timeout=0: True
    visits = []

    def visit(username, *_a, **_kw):
        visits.append(username)
        return ProfileProcessingResult(ProfileProcessingResult.FILTERED_CRITERIA, username)

    host._process_profile_on_screen = visit
    host._interact_with_likers_list(create_workflow_stats("feed"), {}, max_interactions=5,
                                    source_type="FEED", source_name="feed")
    return visits


def test_two_likers_walked_then_two_drags_on_a_list_that_no_longer_moves(monkeypatch):
    _base_knows(monkeypatch, known=set())
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)

    visits = _run_loop(phone)

    assert sorted(visits) == phone.likers_shown()
    drags_up = len(phone.likers_after_each_drag_up)
    assert drags_up == 2, f"{drags_up} drag(s) up a list of two likers that no longer moves"


def test_a_list_already_handled_is_dragged_while_it_moves_then_two_drags_more(monkeypatch):
    phone = LikersSheetPhone(capture(LONG_LIST), moves=True)
    first_screen = phone.likers_shown()
    _base_knows(monkeypatch, known=set(first_screen))

    visits = _run_loop(phone)

    assert visits == []
    shown = [first_screen] + phone.likers_after_each_drag_up
    moved = [after != before for before, after in zip(shown, shown[1:])]
    # Every drag moved the list until it was empty, then two drags showed it still: the end.
    assert moved[-2:] == [False, False], f"likers after each drag: {phone.likers_after_each_drag_up}"
    assert all(moved[:-2]) and len(moved) > 2, f"likers after each drag: {phone.likers_after_each_drag_up}"
