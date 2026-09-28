"""TikTok 47.0.3 renamed the inbox row that opens the Activity page: « Activité et nouveaux
abonnés », the new followers having moved into Activity (the inbox says so in a banner: « Les
nouveaux followers déménagent. Retrouve-le dans Activité »). The row is the inbox's Activity
section, one definition (`INBOX_SELECTORS.activity_section`, locale key `inbox.activity_section`),
read by the production that opens the page and by the one that lists the inbox sections.

The screen is a real capture, anonymized: the inbox of the Pixel 6a (TikTok 47.0.3 in French,
2026-09-29), taken before `tt.activity.open` in the Lab auto-test. Evaluated by uiautomator2's
`d.xpath()` engine, as on the phone.
"""

import time
from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.actions.core.device_facade import DeviceFacade
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale

FIXTURES = Path(__file__).parent / "fixtures"
INBOX_4703 = (FIXTURES / "tt4703_fr_inbox_activity_and_new_followers.xml").read_text(encoding="utf-8")
#: The clickable row « Activité et nouveaux abonnés » of that capture (left, top, right, bottom).
ACTIVITY_ROW = (0, 878, 1080, 1067)


class _Phone:
    """uiautomator2 as the production touches it: `xpath()`, one dump, and the taps it injects."""

    wait_timeout = 0.2

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2400)

    def click(self, x, y):
        self.taps.append((x, y))


@pytest.fixture
def french_4703(monkeypatch):
    """A French phone on TikTok 47.0.3, as its connection and language detection leave the catalogues."""
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    apply_version_overrides("tiktok", "47.0.3")
    set_active_locale("fr")
    yield
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


def test_the_activity_row_of_the_inbox_is_the_one_tapped(french_4703):
    phone = _Phone(INBOX_4703)
    # A still photo: the page never comes up. What is proven is the row found and tapped.
    ActivityActions(DeviceFacade(phone)).open_activity(expand=False)
    assert len(phone.taps) == 1
    x, y = phone.taps[0]
    left, top, right, bottom = ACTIVITY_ROW
    assert left <= x <= right and top <= y <= bottom


def test_the_inbox_lists_its_activity_section(french_4703):
    """The new followers have no section of their own any more; Activity and the system notifications do."""
    sections = DMActions(DeviceFacade(_Phone(INBOX_4703)))._get_notification_sections()
    assert [section["notification_type"] for section in sections] == ["activity", "system"]
