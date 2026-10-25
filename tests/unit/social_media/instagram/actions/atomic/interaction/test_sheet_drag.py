"""A sheet is dragged closed one way: from its grab bar, accompanied, at a hand's speed.

`drag_sheet_off_screen` (`bottom_sheet.py`) is that one way. Before it, the sheets' closers each
had their own gesture:

- `dismiss_bottom_sheet` dragged for a fixed 0.6 s whatever the distance: from the grab bar of a
  sheet expanded on a 2160 px screen, 3260 px/s, faster than a hand carries a sheet on the glass;
- the likers popup (`_close_popup_by_swipe_down`) and the comments sheet (`_close_comment_popup`)
  sent a coarse 0.3 s `swipe` from the grab bar, which Android reads as a fling (the sheet drops one
  state and stays open); on a sheet expanded to the top of the screen, the first pressed Back
  instead, the second skipped the grab bar and flung the sheet from the middle of the screen;
- `_close_comment_popup` said True when every strategy had failed and the sheet was still up.

The screens are real dumps, anonymized: the comments of a post expanded to the top of the screen
(Instagram 410, English) and the likers sheet of a post on a C57 S (410, English, 576x1280).
"""

import pytest
from loguru import logger

from taktik.core.shared.behavior import gesture_primitives
from taktik.core.social_media.instagram.actions.atomic.interaction import bottom_sheet
from taktik.core.social_media.instagram.actions.base.base_business import popup_handling
from taktik.core.social_media.instagram.actions.base.base_business.popup_handling import PopupHandlingMixin
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.services.comment import action as comment_action
from taktik.core.social_media.instagram.services.comment.action import CommentAction
from taktik.core.social_media.instagram.ui.selectors.shell.popups import POPUP_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (
    SheetPhone, assert_accompanied_drag, assert_starts_at_the_grab_bar, capture, centre_of, drags_journaled,
    node_with_id)

COMMENT_SHEET_EXPANDED = capture("ig410_en_comment_sheet.xml")
LIKERS_SHEET_C57S = capture("ig410_en_likers_sheet_two_likers_c57s.xml")
FEED_BEHIND = capture("ig410_en_feed_post_hours_ago.xml")
HAND = gesture_primitives._CONTROLLED_VEL_RANGE


def _grab_bar(xml):
    return centre_of(node_with_id(xml, "bottom_sheet_drag_handle_prism"))


class _Sheets(PopupHandlingMixin):
    """What the likers and comments closers are given by their host: the facade, the catalogues."""

    _close_comment_popup = CommentAction._close_comment_popup

    def __init__(self, phone):
        self.device = DeviceFacade(phone)
        self.logger = logger
        self.popup_selectors = POPUP_SELECTORS
        self.post_selectors = POST_COMMENTS_SELECTORS
        self._human_like_delay = lambda *_a, **_k: None


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    for module in (bottom_sheet, popup_handling, comment_action):
        monkeypatch.setattr(module.time, "sleep", lambda *_a, **_k: None)


@pytest.fixture
def journal():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="DEBUG")
    yield lines
    logger.remove(sink)


def test_the_shared_dismiss_drags_at_a_hands_speed_whatever_the_screen(journal):
    phone = SheetPhone(COMMENT_SHEET_EXPANDED, after=FEED_BEHIND, closes_on=("drag",))

    closed = bottom_sheet.dismiss_bottom_sheet(phone, lambda: phone.screen is COMMENT_SHEET_EXPANDED)

    assert closed is True
    assert [g[0] for g in phone.gestures] == ["press", "press", "press", "drag"], phone.gestures
    (_kind, points), ((start, _end, ms),) = phone.gestures[-1], drags_journaled(journal)
    assert points[0] == start
    assert_starts_at_the_grab_bar(start, _grab_bar(COMMENT_SHEET_EXPANDED), phone.height)
    assert_accompanied_drag(points, ms, phone.height, HAND)


def test_the_duration_of_the_sheet_drag_is_drawn_never_fixed(journal):
    """A fixed duration is a different speed on every screen height and the same gesture every
    time: the drag draws its own, for the distance."""
    for _ in range(8):
        phone = SheetPhone(COMMENT_SHEET_EXPANDED, after=FEED_BEHIND)
        assert bottom_sheet.drag_sheet_off_screen(phone, lambda: phone.screen is COMMENT_SHEET_EXPANDED)

    durations = [ms for _start, _end, ms in drags_journaled(journal)]
    assert len(durations) == 8 and len(set(durations)) > 1, durations


def test_the_likers_popup_is_dragged_from_its_grab_bar_not_flung(journal):
    phone = SheetPhone(LIKERS_SHEET_C57S, after=FEED_BEHIND)
    sheets = _Sheets(phone)
    assert sheets._is_likers_popup_open()

    assert sheets._close_popup_by_swipe_down() is True

    assert [g[0] for g in phone.gestures] == ["drag"], phone.gestures
    (_kind, points), ((start, _end, ms),) = phone.gestures[0], drags_journaled(journal)
    assert points[0] == start
    assert_starts_at_the_grab_bar(start, _grab_bar(LIKERS_SHEET_C57S), phone.height)
    assert_accompanied_drag(points, ms, phone.height, HAND)


def test_a_likers_popup_the_drag_leaves_up_gets_back_and_is_said_still_open():
    phone = SheetPhone(LIKERS_SHEET_C57S, after=LIKERS_SHEET_C57S)

    assert _Sheets(phone)._close_popup_by_swipe_down() is False
    assert [g[0] for g in phone.gestures] == ["drag", "press"], phone.gestures


def test_an_expanded_comments_sheet_is_dragged_from_its_grab_bar(journal):
    # Back does not close it (a focused composer eats it): only a drag does.
    phone = SheetPhone(COMMENT_SHEET_EXPANDED, after=FEED_BEHIND, closes_on=("drag",))

    assert _Sheets(phone)._close_comment_popup() is True

    drags = [g for g in phone.gestures if g[0] == "drag"]
    assert len(drags) == 1 and phone.gestures[-1] is drags[0], phone.gestures
    assert "swipe" not in [g[0] for g in phone.gestures]
    ((_kind, points),), ((start, _end, ms),) = drags, drags_journaled(journal)
    assert points[0] == start
    assert_starts_at_the_grab_bar(start, _grab_bar(COMMENT_SHEET_EXPANDED), phone.height)
    assert_accompanied_drag(points, ms, phone.height, HAND)


def test_a_comments_sheet_still_up_after_every_strategy_is_said_open():
    phone = SheetPhone(COMMENT_SHEET_EXPANDED, after=COMMENT_SHEET_EXPANDED)

    assert _Sheets(phone)._close_comment_popup() is False
