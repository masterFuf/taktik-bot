"""What the check of pages says it did, and where its gestures land.

Two faults of `ProblematicPageDetector.detect_and_handle_problematic_pages`, on real captures:

- a close that crashed after a detection was turned, by a catch-all `try`, into "nothing
  detected": the page was still on screen, and the navigation went on as if the screen were clear.
  The result now names the page, `closed: False`; a crash of the detection itself is no longer
  turned into a "no" either, it reaches the caller;
- on a profile's options sheet, the first close (`tap_background_dimmer`) tapped the centre of the
  dimmer. The dimmer spans the screen BEHIND the sheet ([0,77][1080,2088] on the capture), so its
  centre lies on the sheet's rows: the tap meant to close the sheet landed on "Report". The sheet
  is now closed by the tap above it (`tap_outside`, the one way to tap outside a sheet), on the
  part of the dimmer the sheet leaves visible.

And the drag of a sheet (`swipe_down_handle`) was a coarse 0.3 s `swipe` Android reads as a fling:
the sheet dropped one state and stayed open. A sheet expanded to the top of the screen got a Back
instead, and a sheet without a named grab bar a fling from the middle of the screen. It is now the
one sheet drag of the project (`drag_sheet_off_screen`): from the grab bar, accompanied, at a
hand's speed, and the sheet is said closed only when the next screen no longer shows it.

The screens are real dumps, anonymized: the options sheet of another profile (Instagram 410,
English) over that profile, the contacts request (447, French), an Instagram alert, and two sheets
expanded to the top of the screen (410, English): the comments of a post, its grab bar named, and
the share sheet of a sponsored post, its grab bar anonymous.

Then measured on a C57 S (Instagram 410, English, 576x1280, 2026-10-25), with its two captures: the
comments sheet expanded against the status bar (grab bar at y=53, status bar down to y=43, keyboard
up), and the screen the first drag left. Started on the grab bar, the drag pulled Android's
notification shade down instead of the sheet; the check read the shade, found no sheet on it and
said the page closed, while the sheet was still open under the shade.
"""

import pytest
from loguru import logger

from taktik.core.shared.behavior import gesture_primitives
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.atomic.interaction import bottom_sheet
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import (
    SheetPhone as _Phone, assert_accompanied_drag, assert_starts_at_the_grab_bar, bounds_of, capture,
    centre_of, drags_journaled, node_with_id)

OPTIONS_SHEET = capture("ig410_en_profile_options_sheet.xml")
PROFILE_BEHIND = capture("ig410_en_profile_following.xml")
CONTACTS_PROMPT = capture("ig447_fr_discover_people_contacts_prompt.xml")
COMMENT_SHEET_EXPANDED = capture("ig410_en_comment_sheet.xml")
SHARE_SHEET_EXPANDED = capture("ig410_en_share_sheet_over_sponsored_post.xml")
FEED_BEHIND = capture("ig410_en_feed_post_hours_ago.xml")
COMMENT_SHEET_C57S = capture("ig410_en_comment_sheet_expanded_keyboard_c57s.xml")
NOTIFICATION_SHADE_C57S = capture("ig410_en_notification_shade_over_comment_sheet_c57s.xml")


def _sheet_top(xml):
    """The top of the sheet on the capture: its grab bar's frame."""
    return bounds_of(node_with_id(xml, "bottom_sheet_drag_handle_frame"))[1]


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(bottom_sheet.time, "sleep", lambda *_a, **_k: None)
    run_halt.reinitialiser()
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


def test_the_options_sheet_is_closed_by_a_tap_above_it_never_on_its_rows():
    phone = _Phone(OPTIONS_SHEET, after=PROFILE_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False,
                      "page_type": "follow_options_bottom_sheet"}
    kind, _x, y = phone.gestures[0]
    assert kind == "click" and y < _sheet_top(OPTIONS_SHEET), phone.gestures
    assert len(phone.gestures) == 1


def test_a_close_that_crashes_after_the_detection_names_the_page_left_open(monkeypatch):
    phone = _Phone(OPTIONS_SHEET, after=PROFILE_BEHIND)
    detector = ProblematicPageDetector(phone)

    def crash(*_a, **_k):
        raise RuntimeError("closing table unavailable")

    monkeypatch.setattr(detector, "_closers", crash)

    assert detector.detect_and_handle_problematic_pages() == {
        "detected": True, "closed": False, "soft_ban": False,
        "page_type": "follow_options_bottom_sheet"}


def test_an_alert_whose_dismissal_crashes_is_named_left_open(monkeypatch):
    locales.set_active_locale("fr")
    phone = _Phone(CONTACTS_PROMPT, after=PROFILE_BEHIND)
    detector = ProblematicPageDetector(phone)

    def crash(*_a, **_k):
        raise RuntimeError("uiautomator2 server gone")

    monkeypatch.setattr(detector, "_click_button_from_selectors", crash)

    assert detector.detect_and_handle_problematic_pages() == {
        "detected": True, "closed": False, "soft_ban": False, "page_type": "instagram_alert"}
    assert phone.gestures == []


def test_a_detection_that_crashes_is_never_nothing_detected(monkeypatch):
    detector = ProblematicPageDetector(_Phone(OPTIONS_SHEET, after=PROFILE_BEHIND))

    def crash(*_a, **_k):
        raise RuntimeError("pattern table broken")

    monkeypatch.setattr(detector, "_matches", crash)

    with pytest.raises(RuntimeError, match="pattern table broken"):
        detector.detect_and_handle_problematic_pages()


@pytest.fixture
def journal():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="DEBUG")
    yield lines
    logger.remove(sink)


def test_an_expanded_sheet_is_dragged_off_from_its_grab_bar_never_flung(journal):
    phone = _Phone(COMMENT_SHEET_EXPANDED, after=FEED_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False,
                      "page_type": "follow_options_bottom_sheet"}
    # Nothing above the sheet to tap: the first gesture is the drag, and the only one.
    assert [g[0] for g in phone.gestures] == ["drag"], phone.gestures
    (_kind, points), ((start, end, ms),) = phone.gestures[0], drags_journaled(journal)
    grab_bar = centre_of(node_with_id(COMMENT_SHEET_EXPANDED, "bottom_sheet_drag_handle_prism"))
    assert points[0] == start
    assert_starts_at_the_grab_bar(start, grab_bar, phone.height)
    assert end == points[-1]
    assert_accompanied_drag(points, ms, phone.height, gesture_primitives._CONTROLLED_VEL_RANGE)


def test_a_sheet_with_an_anonymous_grab_bar_is_dragged_not_flung(journal):
    phone = _Phone(SHARE_SHEET_EXPANDED, after=FEED_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False,
                      "page_type": "message_contacts_page"}
    assert [g[0] for g in phone.gestures] == ["drag"], phone.gestures
    (_kind, points), ((_start, _end, ms),) = phone.gestures[0], drags_journaled(journal)
    assert_accompanied_drag(points, ms, phone.height, gesture_primitives._CONTROLLED_VEL_RANGE)


def test_a_sheet_still_on_the_next_screen_is_never_said_closed():
    phone = _Phone(COMMENT_SHEET_EXPANDED, after=COMMENT_SHEET_EXPANDED)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": False, "soft_ban": False,
                      "page_type": "follow_options_bottom_sheet"}
    # One drag: the grab bar did not move, a second one would change nothing. Then the next
    # close of the pattern, Back, which does not close it either.
    assert [g[0] for g in phone.gestures] == ["drag", "press"], phone.gestures


def test_a_sheet_against_the_status_bar_is_dragged_from_below_the_shade_zone(journal):
    phone = _Phone(COMMENT_SHEET_C57S, after=FEED_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result["closed"] is True
    assert [g[0] for g in phone.gestures] == ["drag"], phone.gestures
    (_kind, points), ((start, _end, ms),) = phone.gestures[0], drags_journaled(journal)
    bar_x, bar_y = centre_of(node_with_id(COMMENT_SHEET_C57S, "bottom_sheet_drag_handle_prism"))
    # The finger goes down straight under the grab bar, past the strip where it pulled the shade.
    assert start == points[0] and start[0] == bar_x
    assert start[1] > bar_y and start[1] >= 0.10 * phone.height, start
    assert_accompanied_drag(points, ms, phone.height, gesture_primitives._CONTROLLED_VEL_RANGE)


def test_a_sheet_is_never_said_closed_on_a_screen_that_is_not_instagrams():
    phone = _Phone(COMMENT_SHEET_C57S, after=NOTIFICATION_SHADE_C57S)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": False, "soft_ban": False,
                      "page_type": "follow_options_bottom_sheet"}
    # Its grab bar gone from a screen that still does not prove the sheet closed, the drag does
    # not drag again on whatever is there; the next close of the pattern, Back, is tried.
    assert [g[0] for g in phone.gestures] == ["drag", "press"], phone.gestures

