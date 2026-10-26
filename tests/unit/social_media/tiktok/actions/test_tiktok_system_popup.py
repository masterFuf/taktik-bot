"""An Android dialog counts as closed once it has left the screen, not once Back was pressed.

`close_system_popup` pressed Back on any Android dialog and answered True. An « isn't responding »
dialog ignores Back: on TikTok 43.1.4 on the official emulator (2026-10-25), the Lab's
`tt.popups.close_system` found the same dialog before and after its Back, and reported a success.
The For You loop, told the blocking popup was closed, retried its swipe without counting an error.

The screens are captures, anonymized: that dialog, and the For You feed of the same session.
Evaluated by uiautomator2's own `d.xpath()` engine, through the production device facade.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.atomic.interaction.popup_actions import PopupActions
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
NOT_RESPONDING = (FIXTURES / "tt4314_en_app_not_responding.xml").read_text(encoding="utf-8")
FEED = (FIXTURES / "tt4314_en_for_you_video_guest.xml").read_text(encoding="utf-8")


class _Phone:
    """Shows `xml`, and `after_back` once Back is pressed."""

    wait_timeout = 1.0

    def __init__(self, xml, after_back):
        self.xml, self.after_back = xml, after_back
        self.keys = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def press(self, key, *_a, **_k):
        self.keys.append(key)
        if key == "back":
            self.xml = self.after_back

    def window_size(self):
        return 1080, 2400


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)


def test_a_dialog_that_ignores_back_is_not_reported_closed():
    phone = _Phone(NOT_RESPONDING, after_back=NOT_RESPONDING)
    assert PopupActions(phone).close_system_popup() is False
    assert phone.keys == ["back"]


def test_a_dialog_that_back_closes_is_reported_closed():
    phone = _Phone(NOT_RESPONDING, after_back=FEED)
    assert PopupActions(phone).close_system_popup() is True
    assert phone.keys == ["back"]


def test_no_dialog_no_back():
    phone = _Phone(FEED, after_back=FEED)
    assert PopupActions(phone).close_system_popup() is False
    assert phone.keys == []
