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

The screens are real dumps, anonymized: the options sheet of another profile (Instagram 410,
English) over that profile, and the contacts request (447, French), an Instagram alert.
"""

import re

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
OPTIONS_SHEET = (FIXTURES / "ig410_en_profile_options_sheet.xml").read_text(encoding="utf-8")
PROFILE_BEHIND = (FIXTURES / "ig410_en_profile_following.xml").read_text(encoding="utf-8")
CONTACTS_PROMPT = (FIXTURES / "ig447_fr_discover_people_contacts_prompt.xml").read_text(encoding="utf-8")

_NODE = re.compile(r"<node\b[^>]*>")
_BOUNDS = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _attribute(tag, name):
    found = re.search(rf'\b{name}="([^"]*)"', tag)
    return found.group(1) if found else ""


def _bounds(tag):
    return tuple(int(v) for v in _BOUNDS.search(_attribute(tag, "bounds")).groups())


def _matches(tag, selector):
    """A uiautomator2 selector (`d(resourceId=..., text=...)`), the keys the detector writes."""
    for key, wanted in selector.items():
        value = {"resourceId": "resource-id", "resourceIdMatches": "resource-id", "text": "text",
                 "textContains": "text", "description": "content-desc",
                 "className": "class"}.get(key)
        if value is None:
            return False
        actual = _attribute(tag, value)
        if key == "resourceIdMatches":
            if not re.fullmatch(wanted, actual):
                return False
        elif key == "textContains":
            if wanted not in actual:
                return False
        elif actual != wanted:
            return False
    return True


def _sheet_top(xml):
    """The top of the sheet on the capture: its grab bar's frame."""
    for tag in _NODE.findall(xml):
        if _attribute(tag, "resource-id").endswith("bottom_sheet_drag_handle_frame"):
            return _bounds(tag)[1]
    raise AssertionError("no sheet on this capture")


class _Phone:
    """uiautomator2 as the detector drives it. A selector's `click()` taps the centre of the
    element's bounds, as uiautomator2's does; any gesture shows the screen behind."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, behind):
        self.screen, self.behind = screen, behind
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "com.instagram.mainactivity.MainActivity"}

    def window_size(self):
        return 1080, 2160

    def _gesture(self, gesture):
        self.gestures.append(gesture)
        self.screen = self.behind

    def click(self, x, y):
        self._gesture(("click", int(x), int(y)))

    def press(self, key):
        self._gesture(("press", key))

    def swipe(self, *args, **_k):
        self._gesture(("swipe",) + tuple(int(v) for v in args[:4]))

    def __call__(self, **selector):
        phone = self
        tags = [tag for tag in _NODE.findall(self.screen) if _matches(tag, selector)]

        class _Element:
            def exists(self):
                return bool(tags)

            @property
            def info(self):
                left, top, right, bottom = _bounds(tags[0])
                return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

            def click(self):
                left, top, right, bottom = _bounds(tags[0])
                phone.click((left + right) // 2, (top + bottom) // 2)

        return _Element()


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    run_halt.reinitialiser()
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


def test_the_options_sheet_is_closed_by_a_tap_above_it_never_on_its_rows():
    phone = _Phone(OPTIONS_SHEET, behind=PROFILE_BEHIND)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": True, "soft_ban": False,
                      "page_type": "follow_options_bottom_sheet"}
    kind, _x, y = phone.gestures[0]
    assert kind == "click" and y < _sheet_top(OPTIONS_SHEET), phone.gestures
    assert len(phone.gestures) == 1


def test_a_close_that_crashes_after_the_detection_names_the_page_left_open(monkeypatch):
    phone = _Phone(OPTIONS_SHEET, behind=PROFILE_BEHIND)
    detector = ProblematicPageDetector(phone)

    def crash():
        raise RuntimeError("closing table unavailable")

    monkeypatch.setattr(detector, "_closers", crash)

    assert detector.detect_and_handle_problematic_pages() == {
        "detected": True, "closed": False, "soft_ban": False,
        "page_type": "follow_options_bottom_sheet"}


def test_an_alert_whose_dismissal_crashes_is_named_left_open(monkeypatch):
    locales.set_active_locale("fr")
    phone = _Phone(CONTACTS_PROMPT, behind=PROFILE_BEHIND)
    detector = ProblematicPageDetector(phone)

    def crash(*_a, **_k):
        raise RuntimeError("uiautomator2 server gone")

    monkeypatch.setattr(detector, "_click_button_from_selectors", crash)

    assert detector.detect_and_handle_problematic_pages() == {
        "detected": True, "closed": False, "soft_ban": False, "page_type": "instagram_alert"}
    assert phone.gestures == []


def test_a_detection_that_crashes_is_never_nothing_detected(monkeypatch):
    detector = ProblematicPageDetector(_Phone(OPTIONS_SHEET, behind=PROFILE_BEHIND))

    def crash(*_a, **_k):
        raise RuntimeError("pattern table broken")

    monkeypatch.setattr(detector, "_matches", crash)

    with pytest.raises(RuntimeError, match="pattern table broken"):
        detector.detect_and_handle_problematic_pages()
