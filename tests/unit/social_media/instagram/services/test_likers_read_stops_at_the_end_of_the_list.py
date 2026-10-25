"""The likers of a post are read until their list ends: once it no longer moves, the reading stops.

Measured on a C57 S (Instagram 410 in English, 576x1280, 2026-10-25), Lab action `post.read_likers`
on a post of the home feed liked twice: both likers were read on the first screen, then the reading
dragged the sheet 20 more times, the same two rows each time, before it gave up (134 s for two
handles). It stopped only on its target or on 20 drags without a new handle: it could not tell a
finished list from a list still going. The reading (`LikerExtractionMixin._extract_likers_after_click`,
the one of the runs and of the Lab) now stops when its drags show the same likers twice in a row,
the end that `ScrollEndDetector` tells; the second drag is the margin for rows still loading.

A list whose first likers were all handled before is not finished for that: it moves, and the
reading goes on while it does.

The screens are real dumps, anonymized: the likers sheet of that two-likes post
(`ig410_en_likers_sheet_two_likers_c57s.xml`) and the sheet of a post with thousands of likes, six
rows on screen (`ig410_en_likers_sheet_long_list_c57s.xml`), both on that phone. The host is the
Lab's `a.popup`, `BaseBusinessAction`, built by its own constructor on a phone that replays the
capture: the two-likers list does not move under a drag, the long one moves by the drag's travel.
"""

import time
from types import SimpleNamespace

import pytest

from likers_sheet_phone import LONG_LIST, TWO_LIKERS, LikersSheetPhone
from profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from taktik.core.social_media.instagram.actions.base.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    # Every wait of the reading: the pauses between its drags, the closing of the sheet.
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    set_active_locale("en")
    yield
    set_active_locale(None)


def _lab_popup_host(phone, automation=None):
    host = BaseBusinessAction(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)), automation=automation)
    host._human_like_delay = lambda *_args, **_kwargs: None
    return host


def test_the_captured_sheet_holds_two_likers():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)

    assert _lab_popup_host(phone)._is_likers_popup_open() is True
    assert len(phone.likers_shown()) == 2


def test_a_finished_list_stops_the_reading_after_two_drags_that_show_nothing_new():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)

    likers = _lab_popup_host(phone)._extract_likers_after_click(max_interactions=10, multiply_by=1)

    assert len(likers) == 2
    drags = len(phone.likers_after_each_drag_up)
    assert drags == 2, f"{drags} drag(s) up a list of two likers that no longer moves"


def test_a_list_whose_first_likers_were_handled_goes_on_while_it_moves(monkeypatch):
    phone = LikersSheetPhone(capture(LONG_LIST), moves=True)
    first_screen = phone.likers_shown()
    assert len(first_screen) == 6
    handled = []

    def already_processed(username, _account_id):
        handled.append(username)
        return True

    monkeypatch.setattr(InstagramWorkflowStateService, "is_profile_already_processed",
                        staticmethod(already_processed))

    likers = _lab_popup_host(phone, SimpleNamespace(active_account_id=1))._extract_likers_after_click(
        max_interactions=10, multiply_by=1)

    assert likers == []
    assert sorted(set(handled)) == first_screen
    shown = [first_screen] + phone.likers_after_each_drag_up
    moved = [after != before for before, after in zip(shown, shown[1:])]
    # Every drag moved the list until it was empty, then two drags showed it still: the end.
    assert moved[-2:] == [False, False], f"likers after each drag: {phone.likers_after_each_drag_up}"
    assert all(moved[:-2]) and len(moved) > 2, f"likers after each drag: {phone.likers_after_each_drag_up}"
